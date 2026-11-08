# Database

## Status
`database/models.py`, `session.py`, and `seed.py` are **written and syntax-checked but not executed**
in this sandbox — SQLAlchemy is not installed and there is no network access to install it (confirmed
by a failed `pip install fastapi --break-system-packages` in this session; the base image ships
NumPy/pandas/scikit-learn/PyJWT and nothing else from `requirements.txt`). Until run in an environment
with `sqlalchemy` installed, `apps/api/pipeline.py` and `services/alert_engine` are exercised against
`apps/api/repository.InMemoryRepository`, which implements the same method signatures the SQL
repository will, so the swap is mechanical, not a rewrite.

## Entities (13, per spec)
`users, patients, patient_profiles, sensor_devices, sensor_readings, caregiver_notes,
risk_assessments, alerts, caregiver_actions, timeline_events, device_events, sync_queue, audit_logs`
— see `database/models.py` for full column definitions.

## SQLite ↔ PostgreSQL
`WZ_DATABASE_URL` (see `.env.example`) selects the backend:
- `sqlite:///./wardzero.db` — default, zero setup, used for local development.
- `postgresql+psycopg://user:pass@host:5432/wardzero` — production, self-hosted, still free (see
  `docs/free-services.md`).

Both use the same `database/models.py` schema; SQLAlchemy's dialect layer handles the SQL differences.
`database/session.make_engine()` sets `check_same_thread=False` only for the SQLite case, since that
flag is meaningless (and unsupported) for other dialects.

## Migrations
`database/session.init_db()` uses `Base.metadata.create_all(checkfirst=True)`, which is fine for local
dev and this prototype's demo, but is **not** a substitute for Alembic migrations in a real deployment
(schema changes after the first run won't be applied automatically). Alembic scaffolding is not yet
added — recorded here as a known gap rather than silently glossed over.

## Seed data
`database/seed.py` creates one administrator, one caregiver, and the primary **SYNTHETIC DEMO
PATIENT** "Ravi Kumar" (age 67, hypertension + diabetes), explicitly flagged
`is_synthetic_demo=True` on the `Patient` row and again in `PatientProfile.notes`. Re-running `seed()`
is safe — every insert is guarded by an existence check.

## Sync-queue duplication
`services/sync_engine/queue.py`'s SQLite table (edge/gateway-side, offline-first) and
`database/models.SyncQueueRow` (server-side) intentionally share the same column names. The edge
queue is the source of truth while offline; the server row is a durability mirror so an API restart
doesn't lose in-flight sync state.
