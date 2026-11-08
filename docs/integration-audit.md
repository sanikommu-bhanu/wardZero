# WardZero AI — integration audit (PROMPT 4, section 1)

Written after reading the repository and re-running the checks below, not from memory of earlier
sessions. **Verification status vocabulary:** `TESTED` = executed in this sandbox by a passing test or
a real run; `SYNTAX-ONLY` = parses, never executed; `WRITTEN` = code exists, not executed; `BLOCKED` =
cannot be done in this sandbox; `NOT BUILT` = does not exist.

**Sandbox constraints (re-verified):** no network. `pip install` and `npm ping` both fail. Not
installed and not installable: fastapi, pydantic, sqlalchemy, pytest, shap, uvicorn, bcrypt, httpx,
paho-mqtt, and the frontend's npm dependencies (vite, react-router-dom, recharts, three, ...). Installed
and used: numpy, pandas, scikit-learn, PyJWT, reportlab, pypdf, and a global `typescript` package (syntax
check only). No MQTT broker and no browser are available.

## Component audit

| Component | Current state | Evidence | Required integration | Action taken | Verification |
|---|---|---|---|---|---|
| Ingestion pipeline (validate → dedupe → store → features → risk → alert → notify) | Real, one code path | `apps/api/pipeline.py` `IngestionPipeline.ingest`; `tests/test_pipeline.py` | none | none | TESTED |
| Simulator and HTTP share one ingestion path | Yes. `SimulatorManager` calls `pipeline.ingest()`, `POST /readings` calls the same method | `simulator_manager.py:157`, `main.py` `/readings` | Prove equivalence, not just claim it | Added `apps/api/device_adapter.py` + `tests/test_device_adapter.py`, which drive `SimulatedDeviceAdapter` and `HttpDeviceAdapter` through a real pipeline and assert identical stored readings | TESTED |
| Sensor validation | Whitelist + physical-range checks; unknown fields dropped; `_true_severity` stripped. Out-of-range values are **dropped and reported, not clamped** | `apps/api/validation.py`, `TestValidation` | Sequence numbers, stale-timestamp checks (spec §6) | none | TESTED (basic). Sequence/stale-timestamp checks NOT BUILT |
| Duplicate protection | Duplicate `event_id` returns status `duplicate`, no double alert | `test_pipeline.py`, `test_sync_queue.py` | idempotency at DB level | none | TESTED in memory; SQL unique key WRITTEN |
| Rejected-event audit | Rejected events kept in memory (`store_rejected`); sync queue keeps rejected events for audit | `repository.py`, `test_sync_queue.py` | dedicated `rejected_events` table (spec §21) | none | in-memory TESTED; table NOT BUILT |
| Device registry | `SensorDevice` had only id/type/location/status/battery | `database/models.py` | manufacturer, model, firmware, protocol, registered_at, last_seen, honest connection state (spec §5) | Added those columns (additive, nullable), seed values clearly labelled "simulated", `last_seen` tracked from real events, `/devices` returns an honest `connection_status` (`simulated` / `offline` / `unknown`; `real_hardware` cannot occur while `is_simulated` is always true). `signal_strength` deliberately **not** added — the simulator has no such signal and an empty column invites fabricated values | `last_seen` TESTED; model/seed/route WRITTEN |
| Separate Device vs Sensor tables (spec §5) | One row per vital type per patient conflates them | `database/seed.py` | split into two tables | **Not done** — cascading change to repository, API, simulator, frontend, none of it runnable here | NOT BUILT |
| MQTT ingestion | Nothing existed | grep for `mqtt` found none in app code | Mosquitto + paho-mqtt consumer | Added `MqttDeviceAdapter.normalize()` for both payload shapes in spec §4 (tested). `connect()` raises `NotImplementedError` with the reason. No client loop written, because it could not be run | `normalize` TESTED; transport **BLOCKED** |
| HTTP ingestion | `POST /readings` (authenticated) | `main.py` | spec names `/api/v1/iot/events` | none — same behavior, different path name | WRITTEN (route), pipeline TESTED |
| Device authentication for real hardware | Ingest uses user JWT only | `main.py` | per-device credentials | none | NOT BUILT |
| WebSocket live stream | Broadcast + dead-connection cleanup exist. The endpoint accepted **unauthenticated** clients | `apps/api/ws_manager.py`, `main.py` | auth; typed events (`sensor_update`, `risk_update`, …) | Now requires a valid JWT via `?token=` and closes with 1008 otherwise; client sends the token. Event naming was not changed (existing types: `alert`, `vitals_update`, `sim_reading`, `device_event`) | WRITTEN (fastapi absent); client SYNTAX-ONLY |
| Frontend live status | LIVE / reconnect indicator in `RealtimeContext` | `apps/web/src/lib/ws.ts` | truthful "last update" | not re-audited beyond syntax | SYNTAX-ONLY |
| Feature engineering / ML inference / risk class / 24h+48h forecast | Real trained scikit-learn models, artifacts in `ml/artifacts` | `ml/training/train.py`, `tests/test_inference.py`, `test_risk_engine.py` | none | Fixed a real defect: the test suite overwrote these artifacts with a toy model on every run (`tests/test_training.py`); training now takes an output dir and the test uses a temp dir | TESTED |
| Model metadata in UI/API (spec §9) | Metrics in `evidence/metrics.json` (real, produced by training); `manifest.json` in artifacts | `ml/training/train.py` | expose version/training date/feature count/metrics/inference mode via API and UI | **Not done.** Inference mode (`method: model|rules`) is already exposed; model version/training date/metrics are not | PARTIAL |
| Explainability | SHAP if installed, otherwise deterministic occlusion; method reported | `ml/explainability/`, `test_explainability.py` | never label occlusion as SHAP | Verified the reported method is what is used. Fixed a UI bug: arrows were always green ↓ because the UI checked `"worsening"` while the backend emits `"increases_risk"` | occlusion path TESTED; SHAP BLOCKED |
| Safety override | Hard thresholds force HIGH / emergency regardless of model | `services/risk_engine/`, `test_risk_engine.py` (model and rules paths) | UI banner "SAFETY OVERRIDE ACTIVE" | not re-audited in UI | backend TESTED |
| AI failure behavior | Reading stored *before* risk assessment; test forces the assessor to raise | `test_pipeline.py::test_ai_failure_does_not_lose_the_reading` | UI states "AI MODEL UNAVAILABLE / RULE-BASED FALLBACK ACTIVE"; recovery notice; live toggle | Not added. The rules fallback exists and is tested; there is no demo control that disables the model at runtime | backend TESTED; demo control NOT BUILT |
| Alert engine | State machine DETECTED→ALERTED→ACKNOWLEDGED→ESCALATED→RESPONDED→RESOLVED, dedup, timeout auto-escalation (`sweep_timeouts`), time-to-ack, audit trail, invalid-transition errors | `services/alert_engine/engine.py`, `test_alert_engine.py` | distinguish device failure from patient deterioration (spec §17) | not done — no device-failure alert type | TESTED; device-failure alerts NOT BUILT |
| `sweep_timeouts` scheduling | Method exists and is tested; nothing calls it periodically in the API | grep in `main.py` | background task | not done | **NOT WIRED** |
| Caregiver workflow | Acknowledge / note / escalate / respond / dismiss routes; timeline events | `main.py` alert routes | resolve route in UI | not re-audited | routes WRITTEN |
| Multilingual NLP | English, Tamil, Telugu, Hindi, Romanized Hindi with negation/uncertainty | `services/nlp_engine`, `test_nlp_engine.py` | linguistic validation by native speakers | untouched by design. **Not clinically or linguistically validated** | TESTED (rules only) |
| Offline queue / sync | Python queue: persist, idempotent enqueue, ordered flush, retry, no loss on connection error | `services/sync_engine/queue.py`, `test_sync_queue.py` | IndexedDB queue in the browser; sync UI (queued/uploaded/duplicates/failed) | **Not built.** The queue is server-side Python; no API route exposes it and the frontend has no IndexedDB. The "offline demo" from spec §15 does not exist end to end | queue logic TESTED; UI/API/IndexedDB NOT BUILT |
| Database | 13 SQLAlchemy models with indexes; app runs on an **in-memory repository** | `database/models.py`, `apps/api/repository.py` | SQL-backed repository; alembic | **Not done** — cannot execute SQLAlchemy here | models WRITTEN; not executed |
| Auth | PyJWT + bcrypt, refuses to start without `WZ_JWT_SECRET` | `apps/api/auth.py`, `test_auth_jwt.py` | roles ADMIN/DOCTOR/CAREGIVER/VIEWER; route-level authorization | Fixed **privilege escalation**: `/auth/signup` accepted `role="administrator"` from any caller. It now only creates caregivers (403 otherwise); Administrator option removed from the sign-up form. Only two roles exist (`caregiver`, `administrator`) and no route checks role beyond "logged in" | JWT TESTED; route + bcrypt WRITTEN |
| CORS | `allow_origins=["*"]` | `main.py` | explicit allow-list | Now `WZ_CORS_ORIGINS` (default: local Vite origins) | WRITTEN |
| Rate limiting | None | grep | limit sign-in/sign-up | **Not done** | NOT BUILT |
| Secrets | No hardcoded secrets found; `.env` ignored; `.env.example` placeholders only | repo grep | — | added `WZ_CORS_ORIGINS` placeholder | scan done |
| PDF reports | Did not exist | — | spec Prompt 3 | Added `apps/api/reports_pdf.py` (reportlab), 11 tests parse the PDF back out; route + button added | renderer TESTED; route/button WRITTEN/SYNTAX-ONLY |
| Digital Twin | 2D room view driven by live device/vital state, labels unavailable sensors instead of inventing them | `apps/web/src/pages/DigitalTwin.tsx` | Three.js / R3F 3D view (spec §13) | **Not built** — `three` cannot be installed here and a 3D scene could not be rendered or checked | 2D SYNTAX-ONLY; 3D **BLOCKED** |
| Deterministic deterioration demo (5 stages) | Scenarios exist in `apps/simulator/scenarios.py` and run through the real pipeline via the simulator routes | `SCENARIOS`, `/simulator/*` | named stages 0–4 with a single "START PATIENT DETERIORATION DEMO" button; seeded reproducibility | Not re-audited or extended in this pass | PARTIAL — needs verification |
| Frontend screens | 17 pages. Timeline lives inside Patient Detail; there is no standalone Security/Roles page | `apps/web/src/pages/` | all 18 screens reachable | not done | 46 files SYNTAX-ONLY; never bundled or rendered |
| Frontend tests (Vitest/Playwright) | None | — | — | none | NOT BUILT (need npm/browser) |
| CI | workflow exists | `.github/workflows` | — | not run | NOT RUN |

## Honest summary
The backend logic (ingestion, validation, features, models, explanations, risk, alerts, NLP, sync queue,
PDF) is real and covered by the unit tests — **156 tests pass**. Everything that needs FastAPI, SQLAlchemy,
bcrypt, MQTT, a browser, or npm has **never been run**. The largest gaps against the spec are: no
persistent database in the running app, no MQTT transport, no 3D twin, no browser-side offline queue, no
model-metadata screen, no scheduled alert-timeout sweep, and only two roles.

Do not describe this project as having real IoT hardware connected: every device is simulated.
