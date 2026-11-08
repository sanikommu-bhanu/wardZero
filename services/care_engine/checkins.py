"""Caregiver check-ins and missed-visit detection. Intervals are configurable DEMO defaults, not clinical standards:
the more at-risk the patient, the more often someone must have visited."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

DEFAULT_INTERVAL_MIN = {"HIGH": 60, "MEDIUM": 120, "LOW": 240, "UNKNOWN": 240}
GRACE_MIN = 10


def _parse(ts) -> datetime:
    d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def visit_status(last_checkin_ts, risk_level: str, now: datetime, intervals=None, grace_min=GRACE_MIN, since: datetime | None = None) -> dict:
    """`since`: when monitoring of this patient began, used when there is no check-in yet."""
    iv = (intervals or DEFAULT_INTERVAL_MIN).get((risk_level or "UNKNOWN").upper(), 240)
    ref = _parse(last_checkin_ts) if last_checkin_ts else since
    if ref is None:
        return {"state": "no_baseline", "interval_min": iv, "overdue_min": 0, "last_checkin": None}
    due = ref + timedelta(minutes=iv)
    overdue = (now - due).total_seconds() / 60.0
    state = "ok" if overdue < 0 else ("due" if overdue <= grace_min else "missed")
    return {"state": state, "interval_min": iv, "overdue_min": max(0, round(overdue, 1)),
            "due_at": due.isoformat(), "last_checkin": str(last_checkin_ts) if last_checkin_ts else None}


def sweep_missed_visits(repo, alert_store, patients: list[dict], now: datetime | None = None, intervals=None) -> list:
    """patients: [{id, risk_level, monitoring_since(optional ISO)}]. Raises a `missed_visit` alert (deduped by the
    alert store) for each patient whose visit is past due + grace. A check-in does not close the alert by itself;
    a caregiver resolves it."""
    now = now or datetime.now(timezone.utc)
    raised = []
    for p in patients:
        last = repo.last_checkin(p["id"])
        since = _parse(p["monitoring_since"]) if p.get("monitoring_since") else None
        st = visit_status(last["ts"] if last else None, p.get("risk_level", "UNKNOWN"), now, intervals, since=since)
        if st["state"] == "missed":
            a = alert_store.detect(p["id"], "missed_visit", {
                "risk_level": p.get("risk_level", "UNKNOWN"), "probability": 1.0, "recommended_escalation": "caregiver_review",
                "hard_threshold_breaches": [], "contributing_factors": [], "method": "care_schedule", "forecast": {}, "trend": {},
                "explanation": f"No caregiver check-in for {st['interval_min'] + st['overdue_min']:.0f} min "
                               f"(expected every {st['interval_min']} min for {p.get('risk_level', 'UNKNOWN')} risk)."})
            raised.append(a)
    return raised
