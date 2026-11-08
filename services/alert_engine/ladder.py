"""Escalation ladder with timers + time-to-acknowledge metrics.

Each alert climbs L1 (primary caregiver) -> L2 (secondary / supervisor) -> L3 (on-call doctor) -> L4 (emergency
contact) if nobody acknowledges within that severity's per-level timeout. Current level is derived from the alert's
own audit trail ("ladder_level" events), so it survives restarts with no extra table. Timers are demo defaults."""
from __future__ import annotations

from datetime import timedelta
from statistics import median

from .engine import AlertStore, AuditEvent, Severity, Status

LEVELS = ["primary_caregiver", "secondary_caregiver", "on_call_doctor", "emergency_contact"]
LEVEL_TIMEOUT = {  # time an alert may stay unacknowledged at one level before moving up
    Severity.CRITICAL: timedelta(minutes=2), Severity.HIGH_RISK: timedelta(minutes=5),
    Severity.WARNING: timedelta(minutes=15), Severity.INFORMATIONAL: None,
}


def current_level(alert) -> tuple[int, object]:
    """(level index, datetime that level started)."""
    lvl, started = 0, alert.detected_at
    for e in alert.audit:
        if e.action == "ladder_level":
            lvl, started = e.detail["level"], e.ts
    return lvl, started


class EscalationLadder:
    def __init__(self, store: AlertStore, notify=None, timeouts=None):
        """notify(alert, level_name, level_index) is called each time an alert reaches a new level (incl. L1)."""
        self.store, self.notify = store, notify or (lambda *a: None)
        self.timeouts = timeouts or LEVEL_TIMEOUT

    def announce_new(self) -> int:
        """Send L1 notification for alerts that have never been announced."""
        n = 0
        for a in self.store.list(open_only=True):
            if a.status == Status.ALERTED and not any(e.action == "ladder_level" for e in a.audit):
                self._enter(a, 0, "initial")
                n += 1
        return n

    def _enter(self, a, level: int, why: str):
        now = self.store.now()
        a.audit.append(AuditEvent(now, "ladder_level", None, {"level": level, "recipient": LEVELS[level], "why": why}))
        a.updated_at = now
        self.store._on_change(a)
        self.notify(a, LEVELS[level], level)

    def tick(self) -> list:
        """Advance every unacknowledged alert whose level timer expired. Returns [(alert, new_level)]."""
        moved = []
        now = self.store.now()
        self.announce_new()
        for a in self.store.list(open_only=True):
            if a.status not in (Status.ALERTED, Status.ESCALATED):   # acknowledged/responded -> ladder stops
                continue
            to = self.timeouts.get(a.severity)
            if to is None:
                continue
            lvl, started = current_level(a)
            if now - started >= to and lvl < len(LEVELS) - 1:
                if a.status == Status.ALERTED:
                    self.store.escalate(a.id, actor=None, reason=f"ladder_timeout_L{lvl + 1}")
                self._enter(a, lvl + 1, "ack_timeout")
                moved.append((a, lvl + 1))
        return moved


def ack_metrics(store: AlertStore) -> dict:
    """Time-to-acknowledge statistics computed from real audit events."""
    tta, by_sev, unacked, ladder_hist = [], {}, 0, {}
    for a in store.list():
        ack = next((e for e in a.audit if e.action == "acknowledged"), None)
        if ack:
            s = ack.detail["time_to_ack_seconds"]
            tta.append(s)
            by_sev.setdefault(a.severity.value, []).append(s)
        elif a.is_open():
            unacked += 1
        lvl = current_level(a)[0]
        ladder_hist[LEVELS[lvl]] = ladder_hist.get(LEVELS[lvl], 0) + 1

    def summ(xs):
        if not xs:
            return {"n": 0}
        xs = sorted(xs)
        return {"n": len(xs), "median_s": round(median(xs), 1), "p90_s": round(xs[min(len(xs) - 1, int(0.9 * len(xs)))], 1), "max_s": round(xs[-1], 1)}

    return {"overall": summ(tta), "by_severity": {k: summ(v) for k, v in by_sev.items()},
            "open_unacknowledged": unacked, "alerts_by_ladder_level": ladder_hist, "total_alerts": len(store.list())}
