"""STEP 8 — the ingestion pipeline, framework-independent so it can be unit-tested without
FastAPI/SQLAlchemy (neither is installed in this sandbox — no network access).

    VALIDATE -> DEDUPE -> STORE -> FEATURE ENGINEERING -> RISK -> ALERT -> NOTIFICATION -> TIMELINE

apps/api/routes.py (written but NOT executable here — see STATUS.md) wraps `IngestionPipeline.ingest`
in a FastAPI POST /readings endpoint and broadcasts the returned notification over the websocket.

Every stage is a plain method so each can be tested in isolation as well as end-to-end. Nothing here
imports fastapi/pydantic/sqlalchemy.
"""
from __future__ import annotations

from ml.features.engineering import build_features
from services.risk_engine.engine import assess, ESCALATION_LEVELS
from services.risk_engine.news2 import news2, escalation_from_news2
from services.alert_engine.engine import AlertStore, Alert

# Any risk assessment whose recommended_escalation is in this set produces an alert. Everything
# below "caregiver_review" is stored (it's still valuable data + timeline history) but does not
# page anyone — this is what keeps the alert stream from drowning caregivers in noise.
# Minimum readings in the feature window before the ML estimate is trusted. Below this the system ABSTAINS from an
# ML risk level (trend features are meaningless on 1-5 points) and relies on hard thresholds + NEWS2 only.
MIN_READINGS_FOR_ML = 6

ALERTABLE_ESCALATIONS = {"caregiver_review", "escalate_to_doctor", "emergency"}


class IngestionResult:
    def __init__(self, status: str, reading: dict | None = None, errors: list[str] | None = None,
                risk_assessment: dict | None = None, alert: Alert | None = None,
                notification: dict | None = None, quality: dict | None = None):
        self.status = status  # "accepted" | "duplicate" | "rejected"
        self.reading = reading
        self.errors = errors or []
        self.risk_assessment = risk_assessment
        self.alert = alert
        self.notification = notification
        self.quality = quality

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reading": self.reading,
            "errors": self.errors,
            "risk_assessment": self.risk_assessment,
            "alert": self.alert.to_dict() if self.alert else None,
            "notification": self.notification,
            "quality": self.quality,
        }


class IngestionPipeline:
    def __init__(self, repository, alert_store: AlertStore | None = None, notifier=None,
                validator=None, feature_window: int = 30):
        from .validation import validate_event
        self.repo = repository
        self.alerts = alert_store or AlertStore()
        # notifier(notification_dict) -> None. Default: append to an in-process outbox that the
        # websocket layer (STEP 11) drains and broadcasts. Free/local — no external push service.
        self._outbox: list[dict] = []
        self.notifier = notifier or self._outbox.append
        self.validate_event = validator or validate_event
        self.feature_window = feature_window

    @property
    def outbox(self) -> list[dict]:
        return list(self._outbox)

    def ingest(self, raw_event: dict, patient_context: dict, note_signals: dict | None = None) -> IngestionResult:
        # 1. VALIDATE
        result = self.validate_event(raw_event)
        if not result.ok:
            # Malformed events are still stored for audit (STEP 12: never silently lose data),
            # just not turned into a reading.
            self.repo.store_rejected(raw_event, result.errors)
            return IngestionResult("rejected", errors=result.errors)

        clean = result.clean
        patient_id = clean["patient_id"]

        # 2. DEDUPE
        if self.repo.is_duplicate(clean["event_id"]):
            return IngestionResult("duplicate", reading=clean, errors=result.errors)

        # 3. STORE
        self.repo.store_reading(patient_id, clean)
        self.repo.add_timeline_event(patient_id, "reading_received",
                                     {"event_id": clean["event_id"], "timestamp": clean.get("timestamp")})

        # 4. FEATURE ENGINEERING
        readings = self.repo.readings_for(patient_id, limit=self.feature_window)
        windowed = [{**r, "t": _to_epoch(r.get("timestamp"))} for r in readings]
        features, quality = build_features(windowed, patient_context, note_signals)

        # 5. RISK
        assessment = assess(features)
        assessment_d = assessment.to_dict()
        _augment(assessment_d, clean, len(readings), context=patient_context, note_signals=note_signals)
        self.repo.store_risk_assessment(patient_id, assessment_d)
        self.repo.add_timeline_event(patient_id, "risk_assessed",
                                     {"risk_level": assessment_d["risk_level"],
                                      "recommended_escalation": assessment_d["recommended_escalation"],
                                      "method": assessment_d["method"]})

        # 6. ALERT
        alert = None
        if assessment_d["recommended_escalation"] in ALERTABLE_ESCALATIONS or assessment_d["hard_threshold_breaches"]:
            alert = self.alerts.detect(patient_id, "risk_deterioration", assessment_d)
            self.repo.add_timeline_event(patient_id, "alert_" + alert.status.value.lower(),
                                         {"alert_id": alert.id, "severity": alert.severity.value})

        # 7. NOTIFICATION
        notification = None
        if alert is not None:
            notification = {"type": "alert", "patient_id": patient_id, "alert": alert.to_dict()}
        else:
            notification = {"type": "vitals_update", "patient_id": patient_id,
                            "risk_level": assessment_d["risk_level"]}
        self.notifier(notification)

        # 8. TIMELINE already updated in steps 3/5/6 above.
        return IngestionResult("accepted", reading=clean, risk_assessment=assessment_d,
                               alert=alert, notification=notification, quality=quality)


def _augment(a: dict, reading: dict, n_readings: int, context: dict, note_signals: dict | None) -> None:
    """Adds the transparent NEWS2 baseline, a confidence label, and abstain-on-insufficient-data to the ML assessment.
    NEWS2 can only RAISE the recommended escalation (safety net), never lower it."""
    confused = bool((note_signals or {}).get("confusion"))
    n2 = news2(reading, new_confusion=confused)
    a["news2"] = n2
    a["n_readings_used"] = n_readings
    a["abstained"] = False
    a["abstain_reason"] = None
    if n_readings < MIN_READINGS_FOR_ML:
        a["abstained"] = True
        a["abstain_reason"] = (f"only {n_readings} reading(s) available (need {MIN_READINGS_FOR_ML}) - "
                               "AI trend risk not computed; showing NEWS2 and safety thresholds only")
        a["ml_risk_level_suppressed"] = a["risk_level"]
        a["risk_level"] = "UNKNOWN"
        a["probability"] = 0.0
        a["forecast"] = {**a["forecast"], "deterioration_24h_probability": None, "deterioration_48h_probability": None,
                         "basis": "abstained: insufficient data"}
        a["recommended_escalation"] = "emergency" if a["hard_threshold_breaches"] else "routine_monitoring"
        a["explanation"] = "AI risk not available yet: " + a["abstain_reason"] + "."
    p = a["probability"]
    a["confidence_label"] = "n/a" if a["abstained"] else ("high" if p >= 0.8 else "moderate" if p >= 0.6 else "low")
    n2_esc = escalation_from_news2(n2)
    if ESCALATION_LEVELS.index(n2_esc) > ESCALATION_LEVELS.index(a["recommended_escalation"]):
        a["recommended_escalation"] = n2_esc
        a["explanation"] += f" NEWS2 baseline raised escalation to {n2_esc} (score {n2['score']})."


def _to_epoch(ts) -> float:
    """Accept epoch seconds (already numeric) or ISO-8601 strings."""
    if ts is None:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0
