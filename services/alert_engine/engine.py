"""services.alert_engine — turns a risk_engine.RiskAssessment into a tracked alert with a full
lifecycle, and manages caregiver responses to it.

Lifecycle (STEP 7 of the spec):
    DETECTED -> ALERTED -> ACKNOWLEDGED -> ESCALATED -> RESPONDED -> RESOLVED
    (DISMISSED is a terminal branch from ALERTED/ACKNOWLEDGED)

Design notes:
- Framework-independent: no FastAPI/SQLAlchemy import here, so it is fully unit-testable in this
  sandbox (no network -> those packages are not installed). apps/api will wrap this with HTTP routes
  and persistence later.
- In-memory store (AlertStore) with a pluggable clock for deterministic tests. apps/api's SQLAlchemy
  layer will provide a swap-in store with the same interface (see database/models.py Alert table).
- Deduplication: a new detection for the same (patient_id, alert_type) that is already open
  (not RESOLVED/DISMISSED) updates the existing alert's severity/evidence/updated_at instead of
  creating a duplicate row, and records a `duplicate_suppressed` audit event.
- Auto-escalation: if an ALERTED (or ACKNOWLEDGED-but-not-responded) alert is not acknowledged
  within its severity's ack_timeout, `sweep_timeouts()` escalates it and emits an audit event.
  This function is meant to be called periodically (e.g. by a scheduler / websocket loop tick).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
import itertools


class Severity(str, Enum):
    INFORMATIONAL = "informational"
    WARNING = "warning"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"


class Status(str, Enum):
    DETECTED = "DETECTED"
    ALERTED = "ALERTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ESCALATED = "ESCALATED"
    RESPONDED = "RESPONDED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


# How long an alert may sit un-acknowledged before sweep_timeouts() auto-escalates it.
ACK_TIMEOUT = {
    Severity.CRITICAL: timedelta(minutes=5),
    Severity.HIGH_RISK: timedelta(minutes=15),
    Severity.WARNING: timedelta(hours=1),
    Severity.INFORMATIONAL: None,  # never auto-escalates
}

# Escalation level (from risk_engine) -> alert severity.
ESCALATION_TO_SEVERITY = {
    "routine_monitoring": Severity.INFORMATIONAL,
    "caregiver_review": Severity.WARNING,
    "escalate_to_doctor": Severity.HIGH_RISK,
    "emergency": Severity.CRITICAL,
}

_TERMINAL = {Status.RESOLVED, Status.DISMISSED}
_id_counter = itertools.count(1)


def severity_for(recommended_escalation: str, hard_threshold_breaches: list | None = None) -> Severity:
    if hard_threshold_breaches:
        return Severity.CRITICAL
    return ESCALATION_TO_SEVERITY.get(recommended_escalation, Severity.WARNING)


@dataclass
class AuditEvent:
    ts: datetime
    action: str
    actor: str | None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        return d


@dataclass
class Alert:
    id: int
    patient_id: str
    alert_type: str
    severity: Severity
    status: Status
    risk_assessment: dict
    detected_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    escalated_at: datetime | None = None
    responded_at: datetime | None = None
    resolved_at: datetime | None = None
    dismiss_reason: str | None = None
    notes: list = field(default_factory=list)
    audit: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("detected_at", "updated_at", "acknowledged_at", "escalated_at", "responded_at", "resolved_at"):
            if d[k] is not None:
                d[k] = d[k].isoformat() if not isinstance(d[k], str) else d[k]
        d["severity"] = self.severity.value
        d["status"] = self.status.value
        d["notes"] = list(self.notes)
        d["audit"] = [e.to_dict() if isinstance(e, AuditEvent) else e for e in self.audit]
        return d

    def is_open(self) -> bool:
        return self.status not in _TERMINAL

    @classmethod
    def from_dict(cls, d: dict) -> "Alert":
        def dt(v):
            return datetime.fromisoformat(v) if isinstance(v, str) else v
        return cls(
            id=d["id"], patient_id=d["patient_id"], alert_type=d["alert_type"],
            severity=Severity(d["severity"]), status=Status(d["status"]),
            risk_assessment=d["risk_assessment"], detected_at=dt(d["detected_at"]), updated_at=dt(d["updated_at"]),
            acknowledged_at=dt(d.get("acknowledged_at")), acknowledged_by=d.get("acknowledged_by"),
            escalated_at=dt(d.get("escalated_at")), responded_at=dt(d.get("responded_at")),
            resolved_at=dt(d.get("resolved_at")), dismiss_reason=d.get("dismiss_reason"),
            notes=list(d.get("notes", [])),
            audit=[AuditEvent(dt(e["ts"]), e["action"], e.get("actor"), e.get("detail", {})) for e in d.get("audit", [])])


class AlertEngineError(Exception):
    pass


class InvalidTransition(AlertEngineError):
    pass


class AlertStore:
    """In-memory alert store. Deterministic clock injectable for tests."""

    def __init__(self, clock=None):
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._alerts: dict[int, Alert] = {}

    def now(self) -> datetime:
        return self._clock()

    def _on_change(self, alert: "Alert") -> None:
        """Persistence hook, called after every state change. No-op here (in-memory); the SQLite
        subclass in apps/api/sqlite_repo.py overrides it to write through."""

    def _next_id(self) -> int:
        return next(_id_counter)

    # -- creation / dedup --------------------------------------------------
    def detect(self, patient_id: str, alert_type: str, risk_assessment: dict, actor: str | None = None) -> Alert:
        """Ingest a new detection. Deduplicates against any OPEN alert of the same
        (patient_id, alert_type); otherwise creates a new alert (status DETECTED -> ALERTED)."""
        sev = severity_for(risk_assessment.get("recommended_escalation", "routine_monitoring"),
                           risk_assessment.get("hard_threshold_breaches"))
        now = self.now()
        existing = self._find_open(patient_id, alert_type)
        if existing is not None:
            existing.risk_assessment = risk_assessment
            existing.updated_at = now
            upgraded = _severity_rank(sev) > _severity_rank(existing.severity)
            if upgraded:
                existing.severity = sev
            existing.audit.append(AuditEvent(now, "duplicate_suppressed", actor,
                                             {"note": "existing open alert updated instead of duplicating",
                                              "severity_upgraded": upgraded}))
            self._on_change(existing)
            return existing

        alert = Alert(id=self._next_id(), patient_id=patient_id, alert_type=alert_type, severity=sev,
                     status=Status.DETECTED, risk_assessment=risk_assessment, detected_at=now, updated_at=now)
        alert.audit.append(AuditEvent(now, "detected", actor, {"severity": sev.value}))
        alert.status = Status.ALERTED
        alert.audit.append(AuditEvent(now, "alerted", actor, {}))
        self._alerts[alert.id] = alert
        self._on_change(alert)
        return alert

    def _find_open(self, patient_id: str, alert_type: str) -> Alert | None:
        for a in self._alerts.values():
            if a.patient_id == patient_id and a.alert_type == alert_type and a.is_open():
                return a
        return None

    # -- actions --------------------------------------------------------
    def get(self, alert_id: int) -> Alert:
        if alert_id not in self._alerts:
            raise AlertEngineError(f"unknown alert_id {alert_id}")
        return self._alerts[alert_id]

    def list(self, patient_id: str | None = None, status: Status | None = None, open_only: bool = False) -> list[Alert]:
        vals = list(self._alerts.values())
        if patient_id is not None:
            vals = [a for a in vals if a.patient_id == patient_id]
        if status is not None:
            vals = [a for a in vals if a.status == status]
        if open_only:
            vals = [a for a in vals if a.is_open()]
        return sorted(vals, key=lambda a: a.detected_at, reverse=True)

    def acknowledge(self, alert_id: int, actor: str) -> Alert:
        a = self.get(alert_id)
        if a.status not in (Status.ALERTED, Status.ESCALATED):
            raise InvalidTransition(f"cannot acknowledge alert in status {a.status}")
        now = self.now()
        a.status, a.acknowledged_at, a.acknowledged_by, a.updated_at = Status.ACKNOWLEDGED, now, actor, now
        a.audit.append(AuditEvent(now, "acknowledged", actor, {"time_to_ack_seconds": (now - a.detected_at).total_seconds()}))
        self._on_change(a)
        return a

    def dismiss(self, alert_id: int, actor: str, reason: str) -> Alert:
        a = self.get(alert_id)
        if not reason or not reason.strip():
            raise AlertEngineError("dismiss requires a non-empty reason")
        if a.status not in (Status.ALERTED, Status.ACKNOWLEDGED):
            # Once an alert has been escalated or responded to it must be RESOLVED (with what was done),
            # not dismissed as a non-event: dismissing an escalated critical alert with a one-word reason
            # would erase the fact that people were called out for it.
            raise InvalidTransition(f"cannot dismiss alert in status {a.status}; resolve it instead")
        now = self.now()
        a.status, a.dismiss_reason, a.updated_at = Status.DISMISSED, reason, now
        a.audit.append(AuditEvent(now, "dismissed", actor, {"reason": reason}))
        self._on_change(a)
        return a

    def escalate(self, alert_id: int, actor: str | None = None, reason: str = "manual") -> Alert:
        a = self.get(alert_id)
        if not a.is_open():
            raise InvalidTransition(f"cannot escalate alert in status {a.status}")
        now = self.now()
        a.status, a.escalated_at, a.updated_at = Status.ESCALATED, now, now
        a.audit.append(AuditEvent(now, "escalated", actor, {"reason": reason}))
        self._on_change(a)
        return a

    def mark_responded(self, alert_id: int, actor: str, note: str | None = None) -> Alert:
        a = self.get(alert_id)
        if a.status not in (Status.ACKNOWLEDGED, Status.ESCALATED):
            raise InvalidTransition(f"cannot mark responded from status {a.status}")
        now = self.now()
        a.status, a.responded_at, a.updated_at = Status.RESPONDED, now, now
        if note:
            a.notes.append({"ts": now.isoformat(), "author": actor, "note": note})
        a.audit.append(AuditEvent(now, "responded", actor, {"has_note": bool(note)}))
        self._on_change(a)
        return a

    def resolve(self, alert_id: int, actor: str, note: str | None = None) -> Alert:
        a = self.get(alert_id)
        if a.status not in (Status.RESPONDED, Status.ACKNOWLEDGED, Status.ESCALATED):
            raise InvalidTransition(f"cannot resolve alert from status {a.status}")
        now = self.now()
        a.status, a.resolved_at, a.updated_at = Status.RESOLVED, now, now
        if note:
            a.notes.append({"ts": now.isoformat(), "author": actor, "note": note})
        a.audit.append(AuditEvent(now, "resolved", actor, {}))
        self._on_change(a)
        return a

    def add_note(self, alert_id: int, actor: str, note: str) -> Alert:
        a = self.get(alert_id)
        now = self.now()
        a.notes.append({"ts": now.isoformat(), "author": actor, "note": note})
        a.updated_at = now
        a.audit.append(AuditEvent(now, "note_added", actor, {}))
        self._on_change(a)
        return a

    # -- timeout sweep ----------------------------------------------------
    def sweep_timeouts(self) -> list[Alert]:
        """Auto-escalate ALERTED alerts that have sat un-acknowledged past their severity's
        ack_timeout. Returns the list of alerts that were escalated by this call."""
        now = self.now()
        escalated = []
        for a in self._alerts.values():
            if a.status != Status.ALERTED:
                continue
            timeout = ACK_TIMEOUT.get(a.severity)
            if timeout is None:
                continue
            if now - a.detected_at >= timeout:
                a.status, a.escalated_at, a.updated_at = Status.ESCALATED, now, now
                a.audit.append(AuditEvent(now, "auto_escalated", None,
                                          {"reason": "ack_timeout_exceeded", "timeout_seconds": timeout.total_seconds()}))
                escalated.append(a)
                self._on_change(a)
        return escalated


def _severity_rank(sev: Severity) -> int:
    return [Severity.INFORMATIONAL, Severity.WARNING, Severity.HIGH_RISK, Severity.CRITICAL].index(sev)
