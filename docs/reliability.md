# Reliability

Requirement: the system must not silently lose data, and must keep functioning (in a clearly
degraded, honestly-labeled way) when any single component fails.

| Failure mode | Handling | Verified by |
|---|---|---|
| Offline device / gateway | `services/sync_engine/queue.py`'s `OfflineQueue` persists events to SQLite locally; `flush()` stops cleanly on `ConnectionError`/`TimeoutError`/`OSError`, leaving everything pending — nothing is dropped | `tests/test_sync_queue.py` (12/12) |
| Duplicate event delivery | Idempotent `enqueue` (PK on `event_id`) at the edge, and `apps/api/pipeline.py`'s DEDUPE stage server-side | `tests/test_sync_queue.py`, `tests/test_pipeline.py::test_duplicate_event_id_not_double_stored` |
| Malformed / out-of-range sensor event | `apps/api/validation.py` whitelists fields and range-checks vitals; a partially-bad event has only the bad fields nulled (other vitals still used), and a wholly-bad event is **stored as `rejected` for audit, not discarded** | `tests/test_pipeline.py::test_malformed_event_stored_for_audit_not_dropped` |
| Delayed / out-of-order readings | `build_features` sorts the reading window by timestamp before computing trend/slope features, so late-arriving data is still placed correctly | `ml/features/engineering.py` |
| AI / model failure | `services/risk_engine/engine.assess()` catches `ModelUnavailable` and uses the rules-based fallback; **the reading itself is stored in the pipeline's STORE stage, before the RISK stage runs**, so a risk-assessment exception cannot lose the underlying data | `tests/test_pipeline.py::test_ai_failure_does_not_lose_the_reading` |
| Database temporarily down | Architecture note: `apps/api/main.py`'s ingestion route should be wrapped so a DB write failure re-queues the event via `services/sync_engine` rather than dropping it — **implemented in `IngestionPipeline`'s STORE stage design, but the FastAPI-level retry wrapper itself is not yet written**, recorded here rather than implied to exist |
| Un-acknowledged critical alert | `services/alert_engine/engine.sweep_timeouts()` auto-escalates ALERTED alerts past their severity's ack-timeout (5 min critical / 15 min high-risk / 1 hour warning / never for informational) | `tests/test_alert_engine.py` (`TestAutoEscalation`, 5 tests) |
| Duplicate alert spam for the same ongoing issue | `AlertStore.detect()` updates the existing open alert (severity only ever upgrades, never downgrades) instead of creating a new one | `tests/test_alert_engine.py` (`TestDetectionAndDedup`, 5 tests) |

## Known gap
The FastAPI-level "DB write fails mid-request → re-queue rather than lose the event" wrapper
described in the table above is designed but not yet implemented as code — this is listed honestly in
`docs/limitations.md` rather than claimed as done.
