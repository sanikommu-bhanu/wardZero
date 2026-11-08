"""Idempotent batch ingestion for offline-queue replay (framework independent; main.py wraps it).

Each item is {"event": {...}, "context": {...}}. Every item gets a per-event result; one bad item never
fails the batch, and replaying a batch any number of times stores each event_id exactly once."""
from __future__ import annotations

from datetime import datetime

MAX_BATCH = 500


def _sensor_epoch(ts) -> float:
    """Sort key matching apps/api/sqlite_repo._epoch: numbers numerically, ISO-8601 strings by instant.
    (Sorting str(timestamp) put 1000.0 before 999.0 and so replayed events out of clinical order.)"""
    if ts is None:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def ingest_batch(pipeline, items: list[dict], notifier=None) -> dict:
    if len(items) > MAX_BATCH:
        raise ValueError(f"batch too large (max {MAX_BATCH})")
    # replay in sensor-time order so features see a clinically ordered stream
    ordered = sorted(items, key=lambda it: _sensor_epoch((it.get("event") or {}).get("timestamp")))
    results, counts = [], {"accepted": 0, "duplicate": 0, "rejected": 0, "error": 0}
    for it in ordered:
        ev = it.get("event") or {}
        try:
            r = pipeline.ingest(ev, it.get("context") or {}, it.get("note_signals"))
            st = r.status
            if notifier and r.notification:
                notifier(r.notification)
        except Exception as exc:  # AI-stage failure must not lose the already-stored reading or the rest of the batch
            st, r = "error", None
            results.append({"event_id": ev.get("event_id"), "status": "error", "detail": str(exc)})
            counts["error"] += 1
            continue
        counts[st] += 1
        results.append({"event_id": ev.get("event_id"), "status": st, "errors": r.errors})
    return {"results": results, "counts": counts}
