"""In-memory repository used by the framework-independent pipeline and its tests.

This exists so STEP 8 (pipeline logic) can be written and fully unit-tested before STEP 9's
SQLAlchemy models exist / are runnable in this sandbox (sqlalchemy is not installed here — no
network access to pip install it). `database/repository_sql.py` (STEP 9) implements the same
method signatures against SQLAlchemy so the pipeline can be pointed at either backend unchanged.
"""
from __future__ import annotations
import itertools
from datetime import datetime, timezone


class InMemoryRepository:
    def __init__(self):
        self._readings: dict[str, list[dict]] = {}          # patient_id -> [reading, ...]
        self._seen_event_ids: set[str] = set()
        self._rejected: list[dict] = []
        self._timeline: dict[str, list[dict]] = {}           # patient_id -> [event, ...]
        self._risk_assessments: dict[str, list[dict]] = {}   # patient_id -> [assessment, ...]
        self._notes: dict[str, list[dict]] = {}               # patient_id -> [note, ...]  (STEP 12)
        self._device_events: dict[str, list[dict]] = {}       # device_id -> [event, ...]  (STEP 12)
        self._device_state: dict[str, dict] = {}              # device_id -> {connectivity, battery} (STEP 12)
        self._ids = itertools.count(1)

    # -- readings ---------------------------------------------------------
    def is_duplicate(self, event_id: str) -> bool:
        return event_id in self._seen_event_ids

    def store_reading(self, patient_id: str, reading: dict) -> None:
        self._seen_event_ids.add(reading["event_id"])
        self._readings.setdefault(patient_id, []).append(reading)

    def store_rejected(self, raw: dict, errors: list[str]) -> None:
        self._rejected.append({"raw": raw, "errors": errors})

    def readings_for(self, patient_id: str, limit: int | None = None) -> list[dict]:
        rs = self._readings.get(patient_id, [])
        return rs[-limit:] if limit else list(rs)

    # -- risk assessments ---------------------------------------------------------
    def store_risk_assessment(self, patient_id: str, assessment: dict) -> None:
        self._risk_assessments.setdefault(patient_id, []).append(assessment)

    def latest_risk_assessment(self, patient_id: str) -> dict | None:
        rs = self._risk_assessments.get(patient_id)
        return rs[-1] if rs else None

    # -- timeline ---------------------------------------------------------
    def add_timeline_event(self, patient_id: str, kind: str, detail: dict) -> dict:
        # `ts` added this pass: every event now carries a real wall-clock timestamp of when it was
        # recorded, not just "reading_received" events (whose `detail.timestamp` is the sensor's own
        # reading time, a different thing). Previously only id-ordering was available for the other
        # kinds; apps/web/src/components/Timeline.tsx and apps/api/reports_pdf.py both read this new
        # top-level field when present and fall back to their prior behavior when it's absent (e.g. on
        # events recorded before this change, or by any other repository implementation).
        event = {"id": next(self._ids), "patient_id": patient_id, "kind": kind, "detail": detail,
                "ts": datetime.now(timezone.utc).isoformat()}
        self._timeline.setdefault(patient_id, []).append(event)
        return event

    def timeline_for(self, patient_id: str) -> list[dict]:
        return list(self._timeline.get(patient_id, []))

    # -- caregiver notes (STEP 12 — additive, wraps services/nlp_engine output for storage only,
    # does not touch the NLP logic itself) ---------------------------------------------------
    def store_note(self, patient_id: str, note: dict) -> dict:
        note = {**note, "id": next(self._ids)}
        self._notes.setdefault(patient_id, []).append(note)
        return note

    def notes_for(self, patient_id: str) -> list[dict]:
        return list(self._notes.get(patient_id, []))

    # -- device state (STEP 12 — additive, populated by apps/api/simulator_manager.py so the
    # Devices screen and Digital Twin can show real connectivity/battery instead of fabricating it)
    def set_device_state(self, device_id: str, connectivity: str, battery: int | None) -> None:
        # `last_seen` added this pass (PROMPT 4 section 5 — device registry requires it): real
        # wall-clock time this device's state was last updated by an actual event, not a fabricated
        # "just now" shown regardless of when data really arrived.
        self._device_state[device_id] = {"connectivity": connectivity, "battery": battery,
                                         "last_seen": datetime.now(timezone.utc).isoformat()}

    def device_state(self, device_id: str) -> dict | None:
        return self._device_state.get(device_id)

    def store_device_event(self, device_id: str, event: dict) -> dict:
        event = {**event, "id": next(self._ids)}
        self._device_events.setdefault(device_id, []).append(event)
        return event

    def device_events_for(self, device_id: str, limit: int = 20) -> list[dict]:
        evs = self._device_events.get(device_id, [])
        return evs[-limit:] if limit else list(evs)

    def latest_reading(self, patient_id: str) -> dict | None:
        rs = self._readings.get(patient_id)
        return rs[-1] if rs else None

    # -- stats ---------------------------------------------------------
    def counts(self) -> dict:
        return {"patients_with_readings": len(self._readings),
               "total_readings": sum(len(v) for v in self._readings.values()),
               "rejected": len(self._rejected)}
