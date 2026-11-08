# WardZero AI — build status (honest, as of this session)

Environment used to build/verify: Python 3.12.3, no network access, packages available: numpy, pandas,
scikit-learn, joblib, PyJWT, scikit-image, scipy, matplotlib. NOT available and NOT installable here
(no network): fastapi, pydantic, sqlalchemy, pytest (stdlib `unittest` used instead), shap, uvicorn, alembic,
bcrypt, httpx, python-multipart. Node/npm are present but no frontend has been built yet.

## Done and verified by actually running the code in this sandbox
| # | Component | Verification |
|---|---|---|
| 0 | apps/simulator, ml/features (pre-existing) | smoke-tested by prior session |
| 0 | services/sync_engine/queue.py (pre-existing, was untested) | 12/12 new unit tests pass |
| 1 | services/nlp_engine (lexicon + engine) | 20/20 unit tests pass |
| 2 | ml/data/generator.py | 14/14 unit tests pass; full dataset generated (58,200 rows, 300 patients) |
| 3 | ml/training/train.py | 4/4 unit tests pass; full training run produced real artifacts + evidence/metrics.json |
| 4 | ml/inference/predict.py | 8/8 unit tests pass, against real Step 3 artifacts |
| 4 | ml/explainability/explain.py | 9/9 unit tests pass; SHAP confirmed unavailable here, occlusion path verified |
| 5 | services/risk_engine | 18/18 unit tests pass, both model path and genuine rules-fallback path (via a forced ModelUnavailable), plus the hard-threshold safety-net override |

Total: 85/85 automated tests passing (`PYTHONPATH=. python3 -m unittest discover -s tests`).

CAUTION when re-running the full suite: `tests/test_training.py` retrains a small model as a side effect,
which overwrites `ml/artifacts/` with a toy version. After running the full suite, re-run
`python -m ml.training.train` (no args) to restore the full-size artifacts that evidence/metrics.json
describes, before relying on `ml/artifacts/*.joblib` for anything else (this was done again in Step 5 and
confirmed the risk_engine/inference/explainability tests still pass against the restored artifacts).
See evidence/step4_*.md and evidence/step5_*.md.

## Done this session (continuing from the point above)
| # | Component | Verification |
|---|---|---|
| 6 | services/alert_engine/engine.py — full lifecycle (DETECTED→ALERTED→ACKNOWLEDGED→ESCALATED→RESPONDED→RESOLVED/DISMISSED), dedup, auto-escalation timeouts, time-to-ack tracking, audit trail | 24/24 unit tests pass |
| 7 | apps/api/validation.py + pipeline.py + repository.py — VALIDATE→DEDUPE→STORE→FEATURES→RISK→ALERT→NOTIFICATION→TIMELINE, framework-independent (no fastapi/pydantic import) | 17/17 unit tests pass, including that `_true_severity` never reaches storage and that an AI-stage exception doesn't lose the already-stored reading |
| 8 | apps/api/auth.py — JWT issuance/verification (PyJWT, installed here) | 4/4 unit tests pass |
| — | database/models.py, session.py, seed.py (SQLAlchemy, 13 entities) | **written, syntax-checked (`py_compile`), NOT executed** — sqlalchemy not installed, no network to install it (verified: `pip install fastapi --break-system-packages` fails with "No matching distribution found") |
| — | apps/api/main.py, ws_manager.py (FastAPI routes, JWT dependency wiring, WebSocket broadcast) | **written, syntax-checked, NOT executed** — fastapi/uvicorn not installed, same reason |
| — | apps/api/auth.py's bcrypt hash/verify functions | **written, NOT executed** — bcrypt not installed, same reason |

Total: **130/130 automated tests passing** (`PYTHONPATH=. python3 -m unittest discover -s tests`), up from 85.
All ml/artifacts/*.joblib were re-verified full-size after the suite's training side-effect (see caution below).

## Not yet built
- React frontend — NOT STARTED (out of scope per the spec's stop condition; explicitly deferred).
- Alembic migrations, Docker, GitHub Actions, ReportLab PDF reports, Three.js digital twin, Vitest,
  Playwright — NOT ATTEMPTED (several would need network access this sandbox doesn't have).
- The FastAPI-route-level "DB write fails mid-request → re-queue" reliability wrapper — designed
  (docs/reliability.md) but not implemented as code.
See docs/limitations.md for the complete, itemized list.

## Known limitations already surfaced (see evidence/*.md for detail)
- Tamil/Telugu/Hindi lexicon entries are unreviewed by a native speaker or clinician.
- deteriorates_48h model metrics are not trustworthy — positive class prevalence is ~0.6% of the test set.
- risk_class model's 99.5% accuracy reflects an easy synthetic-label mapping, not real-world performance;
  this caveat must be surfaced anywhere the number is shown to a user.

## Frontend — built this session (React + Vite + TypeScript, apps/web/)

**Note on the gap above:** the backend sections above (through "130/130 tests") describe the state as
of an earlier session. Between that point and this one, `apps/api/main.py` gained the STEP 12 routes
(`/patients`, `/devices`, `/caregivers`, `/analytics/summary`, `/system/health`, `/notes/analyze`,
`/simulator/*`, `/scenarios`, `/reports/{id}`) and `database/seed.py` gained 12 synthetic demo
patients, and the test count is now 134 — none of that is reflected in the sections above because
this session was scoped to the frontend only and told explicitly not to touch or re-verify backend
code. Re-running the suite here reproduces **134 tests, 132 passing / 2 failing**
(`test_risk_engine.TestAssessWithModel`), which matches the documented `ml/artifacts` toy-model
side-effect from `tests/test_training.py` described above — pre-existing, out of this session's scope,
not something this session touched or fixed.

### What exists now in apps/web/src/
- **Design system**: `styles/globals.css` — the original bronze/glass dark theme, extended (same
  token set, no new colors) with styles for every component below: vital/patient/alert/sensor cards,
  tabs, segmented filters, data tables, modal/drawer, command palette, digital-twin room view + pulse
  rings, risk gauge, toggle switch, timeline, finding badges, auth split-screen, kpi tiles, chips.
- **Helpers**: `lib/avatars.ts` (decorative patient portraits + room/auth background images — real
  Unsplash CDN URLs, each verified by fetching the source page's `og:image` tag, not guessed),
  `lib/format.ts` (vital metadata/ranges mirrored exactly from `ml/features/schema.py` +
  `services/risk_engine/rules.py` HARD_THRESHOLDS, time/number formatting).
- **`context/RealtimeContext.tsx`** — additively extended (no existing export changed): a session-only
  `vitalsHistory` buffer and `riskAssessments` cache, both populated *only* from real `sim_reading`
  WebSocket broadcasts. This was necessary because of a real API gap found while building — see below.
- **13 shared components** (`components/`): VitalCard, PatientCard, AlertCard, SensorCard, Timeline,
  AIExplanation, ForecastChart, LiveChart, DataTable, FilterBar (+SegmentedFilter/SearchInput),
  Modal+Drawer, CommandPalette (Cmd/Ctrl+K), ErrorBoundary.
- **17 pages** (`pages/`): SignIn, SignUp, Dashboard, Patients, PatientDetail, LiveMonitor,
  DigitalTwin, AIRisk, Alerts, IoTSimulator, CaregiverNotes, Analytics, Caregivers, Devices, Reports,
  Settings, SystemHealth.
- **`main.tsx` / `App.tsx`** — router wiring: public `/sign-in` `/sign-up`, `RequireAuth` gate
  redirecting to `/sign-in` (preserving the attempted location) for everything else, `AuthProvider` >
  `ToastProvider` > `RealtimeProvider` nesting (required in that order — `RealtimeProvider` calls
  `useAuth()` internally), `CommandPalette` mounted once at the top, `ErrorBoundary` wrapping
  everything so a render crash shows a recoverable screen instead of a blank page.

### Real API gaps discovered while wiring the frontend (not backend bugs — this session did not touch
backend code — but they shaped the frontend design and are worth recording)
1. **No historical-readings endpoint.** `GET /patients` / `/patients/{id}` return exactly one
   `latest_reading` point per vital; there is no endpoint to fetch a time series. The *only* place
   multi-point vitals history exists is the `sim_reading` WebSocket broadcast. Consequence: every
   chart (LiveMonitor, PatientDetail's vitals tab, VitalCard sparklines) draws from an in-memory,
   session-only buffer that starts empty on every page load and only fills once a simulation is
   actually running — this is the correct, honest behavior per the "no hardcoded/fake data" brief, not
   a bug. Empty states say so explicitly rather than showing a flat or fabricated line.
2. **No full explainable risk assessment on the patient endpoints.** `GET /patients` only returns
   `risk_level` / `risk_probability` scalars. The full object (`contributing_factors`, `forecast`,
   `explanation`, `disclaimer`) only ever travels on a `sim_reading` WS message or as a snapshot
   attached to an alert. AIRisk.tsx sources it from the realtime buffer with an alert-history fallback,
   and shows an honest empty state if neither exists yet for a patient.
3. **`patient.connectivity` is actually simulator run status** (`"running"/"paused"/"stopped"/
   "no_data"` from `_sim.status()`), not a sensor online/offline flag — a naming choice already in
   `apps/api/main.py`, not something this session introduced. `StatusIndicator`'s existing generic
   status mapping already handles all four values sensibly, so no frontend workaround was needed.
4. **No PDF export endpoint.** No `reportlab`/PDF route exists anywhere in `apps/api/main.py` despite a
   docstring in the `/reports/{patient_id}` handler mentioning one. Per the original spec, Reports.tsx
   does **not** show a "Download PDF" button — it renders the report on screen and offers a genuine
   "Export JSON" (client-side `Blob` download of the real response), with a visible note explaining why
   there's no PDF button.
5. **No create/update endpoints for patients or caregiver profiles.** Dashboard's "Add Patient" quick
   action and Settings' profile section say so explicitly instead of presenting a form with nowhere to
   submit, or silently doing nothing.

### Verification status — read carefully, same honesty convention as the rest of this file
**Nothing here was compiled, bundled, or run in a browser.** `node` (v22.22.2) and `npm` (10.9.7) are
present in this sandbox, but `npm install` fails immediately with `403 Forbidden` against
`registry.npmjs.org` (confirmed by actually running it, not assumed) — there is no network path to
install `@types/react`, `vite`, etc., so `tsc -b` / `vite build` / any dev server could not be run.
**What was actually done instead, in this sandbox:**
- Every one of the 13 shared components and 17 pages was hand-written against the *real* shapes of
  `lib/api.ts`, `context/AuthContext.tsx`, `context/RealtimeContext.tsx`, and the actual backend routes
  (re-read from `apps/api/main.py`, `repository.py`, `pipeline.py`, `services/risk_engine/engine.py`,
  `services/alert_engine/engine.py`, `services/nlp_engine/engine.py`, `apps/simulator/scenarios.py`,
  `database/seed.py`) — not assumed from memory.
- A script-based static check ran across **every** `.ts`/`.tsx` file in `apps/web/src/` and found:
  brace/paren/bracket balance is correct in every file; no duplicate JSX attributes anywhere (this
  caught and fixed one real bug — a duplicate `className` in `Reports.tsx`); no un-escaped `\uXXXX`
  sequences left inside plain JSX attribute strings (this caught and fixed one real bug — a password
  placeholder in `SignIn.tsx`); and — the most substantial check — **every local `import { X } from
  "../wherever"` across the entire src tree was resolved to its target file and cross-checked against
  that file's actual exports**, catching typos or wrong names before they'd surface as a build error.
  All of the above came back clean on the final pass.
- This is real evidence the code is internally *consistent*, but it is **not** a substitute for
  `tsc --noEmit` or an actual browser render, which would additionally catch: type mismatches, prop
  type errors, hook-rule violations, and runtime-only issues. Those genuinely have not been checked.
- **To actually run this app**, on a machine with normal npm registry access:
  ```bash
  cd apps/web && npm install && npm run dev
  # in another terminal, with the (separately unverified — see above) backend deps installed:
  uvicorn apps.api.main:app --reload
  ```

### Not built (explicitly out of scope per the original spec, or no backend support to wire to)
- Any Three.js / true-3D digital twin — DigitalTwin.tsx is an honest 2D room view with live-data
  markers over a real photo backdrop, and explicitly labels camera/motion as unavailable rather than
  inventing sensors the backend doesn't have.
- Per-vital simulator toggles as a real control — the simulator drives all vitals together
  server-side, so IoTSimulator.tsx's vital switches are labeled "display only" rather than pretending
  to be functional.

## This session — engineering hardening + integration pass (continuing from the point above)

Same environment, same constraint, reconfirmed by actually re-running the failing commands rather than
assuming the prior session's findings still held: `pip install fastapi --break-system-packages` and
`npm ping` both still fail (no network). fastapi, pydantic, sqlalchemy, pytest, shap, uvicorn, bcrypt,
httpx are still not installed. One thing **did** change: `reportlab` (4.4.10) and `pypdf` (5.9.0) are
now available in this sandbox — they were not in the prior sessions — which is what made item 3 below
possible and genuinely tested rather than another "written, not executed" entry.

1. **Fixed a real bug: the test suite was silently overwriting the production ML model.**
  `tests/test_training.py` called `train_all()` with no output-path override, so every test run
  clobbered `ml/artifacts/*.joblib` with a small toy model (n=8 patients/scenario) trained for the
  test. `train_all()` now takes optional `artifact_dir`/`evidence_path` params (defaulting to the
  original real paths, so `python -m ml.training.train` is unchanged); the test now trains into a
  `tempfile.mkdtemp()` and cleans it up. Re-ran `python -m ml.training.train` to restore the full-size
  artifacts, then reran the full suite: **134/134 tests pass** (previously 132/134 — the 2 failures
  were exactly this side effect, now structurally impossible instead of "remember to fix it after").
2. **Fixed a real frontend bug:** `AIExplanation.tsx` checked `f.direction === "worsening"` to color
  contributing-factor arrows, but `services/risk_engine/rules.py` and `ml/explainability/explain.py`
  only ever emit `"increases_risk"` / `"decreases_risk"`. The check never matched, so every factor
  rendered as a green down-arrow regardless of its real direction. Fixed to match the actual field
  values; verified by reading both sides of the contract side by side (grepped the emitting code, not
  assumed from memory).
3. **Closed the PDF export gap (gap #4 above) for real, not just "installed the library."**
  `apps/api/reports_pdf.py` is a new, framework-independent (no fastapi import) reportlab renderer of
  the exact dict `GET /reports/{patient_id}` returns. Verified with an actual generation run in this
  sandbox: built a realistic fixture report, rendered it, confirmed the output starts with `%PDF`, then
  parsed it back out with `pypdf` and asserted the real patient name, SYNTHETIC DEMO PATIENT banner,
  risk level, contributing factors, hard-threshold breach, forecast percentages, timeline row, alert
  row, caregiver note, and disclaimer text all actually appear in the extracted text — not just that
  the function returned without raising. `GET /reports/{patient_id}/pdf` wraps it with the same
  "written, not executed" FastAPI plumbing as every other route in `main.py` (fastapi itself still
  isn't installed here), but the rendering logic underneath it is genuinely tested. `Reports.tsx`'s
  "Download PDF" button and `reportsApi.downloadPdf()` in `lib/api.ts` now call it for real; the old
  "PDF would be fake" notice was removed because it's no longer true.
4. **Closed the historical-readings gap (gap #1 above), partially.** `_repo.readings_for()` already
  stored every accepted reading (exercised indirectly by `tests/test_pipeline.py`) but nothing exposed
  it over HTTP. Added `GET /patients/{id}/readings`. This does **not** make storage persistent —
  `_repo` is still the in-memory `InMemoryRepository`, so history still resets on API restart and is
  shared process-wide rather than per-browser-tab — but it does mean a page reload (or a second browser
  tab) can now see reading history from *this process's* lifetime instead of only whatever arrived over
  that one tab's WebSocket connection. `patientsApi.readings()` added to `lib/api.ts`; **not yet wired
  into any chart component** (LiveMonitor/VitalCard/PatientDetail still read only from the realtime WS
  buffer) — that consumption work is still open.
5. **Timeline events now carry a real timestamp.** `add_timeline_event()` previously stored
  `{id, patient_id, kind, detail}` with no top-level clock time (id-ordering was the only signal,
  documented honestly in `Timeline.tsx`'s comments). Added a `ts` field (`datetime.now(timezone.utc)`)
  at write time. `Timeline.tsx` and `reports_pdf.py` both prefer `ts` now and fall back to the old
  `detail.timestamp` (only ever present on `reading_received` events) for events recorded before this
  change. Confirmed safe against the existing test (`test_pipeline.TestTimeline` only asserts on
  `kind`, not exact dict shape).
6. **Found and used a real way to syntax-check the frontend that the prior session didn't have:**
  the global `typescript` npm package (present in this sandbox, unrelated to the project's own,
  uninstallable `node_modules`) exposes `ts.transpileModule()`, which parses/transpiles a single file
  without needing module resolution or `@types/*` packages. Ran it across **all 46 `.ts`/`.tsx` files**
  in `apps/web/src/` after the changes above. First run caught a real, self-inflicted bug (an editing
  mistake had duplicated ~30 lines of `Reports.tsx`'s JSX after its closing brace); fixed, reran, all
  46 files now transpile cleanly. **This is still not `tsc --noEmit`** — it catches syntax errors, not
  type errors, unresolved imports, or hook-rule violations — but it is strictly more verification than
  "written, not executed," and is a real gap-closer worth reusing in future sessions on this project.
7. **Security scan** (repo-wide grep for API keys / secrets / hardcoded passwords / private-key
  headers, excluding legitimate token-handling code and test fixtures): clean, nothing found.
  `.env` is in `.gitignore` and does not exist in this deliverable; `.env.example` holds only
  placeholders (`change-me-to-a-long-random-string`, etc.); `apps/api/auth.py`'s `_secret()` refuses to
  start without a real `WZ_JWT_SECRET` set rather than falling back to a default.
8. Removed a stray, empty, literally-named `{lib,components,pages,styles,context}` directory left over
  from an earlier shell command that ran under a shell without brace expansion.

**Net result: 134/134 backend tests pass, all 46 frontend files pass a real (if partial) syntax check,
one production ML-model-corrupting bug and one UI-polarity bug are fixed, and PDF export — previously
documented as impossible in this environment — now genuinely works and is tested.** The FastAPI app
and the bundled/browser-rendered frontend remain unexecuted here for the same reason as before: fastapi,
sqlalchemy, and the project's own npm dependencies are still not installable without network access.
See `docs/reports.md` for the PDF feature specifically, and `docs/limitations.md` for the full,
up-to-date gap list.


## Latest pass — device registry, adapter layer, security fixes (see docs/integration-audit.md)
Verified by running: **156/156 backend tests pass**; all 46 frontend `.ts/.tsx` files transpile
(syntax only). Not runnable here: FastAPI, SQLAlchemy, bcrypt, MQTT, a browser, npm.

1. `apps/api/device_adapter.py` + `tests/test_device_adapter.py`: simulated and HTTP adapters are driven
   through a real `IngestionPipeline` and produce identical stored readings (the "same ingestion path"
   claim is now a test). `MqttDeviceAdapter.normalize()` is tested; its `connect()` raises
   `NotImplementedError` — **there is no MQTT transport in this build.**
2. Device registry fields (manufacturer, device_model, firmware_version, protocol, registered_at) added
   to `SensorDevice` and the seed; `last_seen` is tracked from real events (`TestDeviceState`);
   `/devices` returns `connection_status` (`simulated` / `offline` / `unknown`); `SensorCard` shows it.
   No signal-strength field — the simulator has no such data.
3. Security fixes: self-service administrator sign-up closed; WebSocket now needs a JWT; CORS allow-list.
   These are written but unexecuted (fastapi absent).
4. New docs: `docs/integration-audit.md` (component-by-component status), `SECURITY.md` updated.

**Not done from the PROMPT 4 spec:** persistent DB in the running app, MQTT transport, Three.js twin,
IndexedDB offline queue + sync UI, model-metadata screen, scheduled alert-timeout sweep, device-failure
alerts, DOCTOR/VIEWER roles, rate limiting, standalone Timeline/Security-Roles screens, and the
5-stage deterioration demo with a single start button. The spec text was also truncated at section 28,
so anything after it was not seen.


## Latest pass — bug-hunt of unexecuted code + ML realism (161/161 tests)
Fixed by reading the never-run code paths: (1) `EmailStr` needed the missing `email-validator` package and rejects
`.local` domains, so every seeded user would have been refused at sign-in — replaced with a regex-validated string;
(2) simulator start/pause ran in FastAPI's worker thread where `asyncio.ensure_future` has no loop — now bound to the
server loop at startup (`bind_loop`, `_spawn`); (3) `POST /readings` WebSocket broadcasts were silently dropped for
the same reason — now thread-safe via `run_coroutine_threadsafe`; (4) simulator ingested every tick with an EMPTY
patient context (age/comorbidities lost) — now uses the run's context; (5) missing `WZ_JWT_SECRET` caused a 500 on
sign-in — dev mode now uses a random per-process secret (production still refuses); (6) bcrypt >72-byte passwords and
`age=None` crashes. ML: 48h model previously had a 0.6% positive rate (meaningless metrics); regenerated data with
delayed/gradual onset, excluded unlabeled look-ahead rows, added PR-AUC, Brier and logistic-regression baselines.
Regression tests: `tests/test_threadsafe_runtime.py`.

## Session: Phase 1 partial (stopped early at user's request)
Environment: no network, so `pip install -r requirements.txt` and `npm install` FAILED (fastapi, sqlalchemy, bcrypt, httpx, shap, all npm deps missing). uvicorn/`tsc -b`/`vite build` were NOT run. Smoke test via curl/Playwright NOT possible.
Done and verified by running:
- apps/api/sqlite_repo.py: durable SQLite (WAL, synchronous=FULL) repository + SqliteAlertStore; main.py now uses it (main.py itself still unexecuted).
- services/alert_engine: persistence hook + Alert.from_dict.
- tests/test_e2e_flow.py: simulator -> pipeline -> alert -> ack/escalate/respond/resolve -> restart -> data survives (2 tests pass).
- Inference n_jobs=1 (single-row predict ~5x faster).
- Frontend: RealtimeContext.hydrateHistory wired into LiveMonitor and PatientDetail (GET /patients/{id}/readings). Type-checked only against stubbed third-party modules (no real @types/react), esbuild bundle of local imports OK. Not a real tsc -b / vite build.
Observed issue: an alert fires on the very first reading (WARNING) - needs abstain-on-insufficient-data (Phase 4).
NOT started: Phases 2-5 (PWA/offline queue/chaos, NEWS2, equipment, ladder, notifiers, dataset eval, model card, Hindi/Tamil/Telugu, Docker/CI). Datasets not downloaded.

## Session 2 (stopped at user's request; Phases 2-3 done, Phase 4 partial, Phase 5 not started)
Still no network: pip/npm installs, uvicorn, `tsc -b`, `vite build`, curl smoke test and dataset downloads (PhysioNet unreachable, curl 000) were NOT possible.
Phase 2 (verified): tests/test_resilience.py (9 pass, incl. SIGKILL durability, network cut, duplicates, late events, dropout, batch replay); apps/web queueCore tests (`npm test`, 4 pass, plain Node); service worker, manifest, IndexedDB queue, ChaosPanel (UI not run in a browser).
Phase 3 (verified by tests/test_phase3.py, test_news2.py, 191 tests pass at commit): NEWS2 baseline, abstain-on-insufficient-data (fixes alert-on-first-reading), equipment sims, escalation ladder + time-to-ack metrics, check-ins/missed visits, Telegram/ntfy/in-app dispatcher. main.py routes for these are unexecuted (no fastapi).
Phase 4 (NOT finished): ml/evaluation/metrics.py and run_eval.py are written but were never run to completion, so NO evaluation numbers exist yet. Real-data loaders, model card, Hindi/Tamil/Telugu NLP set: not started.
Phase 5: not started.


## Latest pass (offline-only; still no network, no fastapi/sqlalchemy/npm deps)
**Verified by running:** 197 pytest tests pass (191 prior + 6 new); 4 browser-queue tests pass in Node; evaluation run
completes (`evidence/eval_synthetic.md`: ML ROC-AUC 0.964 vs NEWS2 0.782 on SYNTHETIC data, 45 test patients; calibration
imperfect, ECE 0.086). A new test caught and fixed a bug in `threshold_for_alarm_budget`.
**Written, NOT executed:** `ml/data/physionet.py` + `ml/evaluation/real_data_check.py` (tested on a synthetic fixture only,
never on PhysioNet data); Dockerfiles, docker-compose, CI workflow; light theme + Appearance setting (transpile
syntax-checked only, not type-checked or viewed in a browser); Mermaid diagram; README demo script; `docs/model_card.md`.
**Correction:** the earlier hand-off said real-data loaders and a model card "work"; neither was in the zip, so both were
written fresh in this pass. **Still not done:** uvicorn/`tsc -b`/`vite build`/curl smoke test, main.py new routes,
real-dataset results, native-speaker review of Hindi/Tamil/Telugu.

## v6 correction (follow-up pass)
The v5 hand-off said "197 tests pass", but 6 of them (`tests/test_real_data_loader.py`) used pytest's `tmp_path`
fixture and pytest is not installed in the offline sandbox, so `unittest discover` silently skipped them (191 ran).
They are now `unittest.TestCase` tests using `tempfile`, run under both unittest and pytest, and were actually run:
**197/197 pass via `PYTHONPATH=. python3 -m unittest discover -s tests`**. Browser queue tests: 4/4 pass in Node.
All 52 `.ts/.tsx` files transpile (syntax only). ml/artifacts unchanged by the suite.
Still NOT run (no network): FastAPI/uvicorn, `tsc -b`, `vite build`, curl smoke test, Docker/CI, real PhysioNet data.

## v7 (follow-up pass: fixed what could be fixed offline)
Still no network (pip/npm fail), so fastapi/sqlalchemy/bcrypt/npm deps remain uninstalled. New this pass:
- **`tools/offline_smoke/`**: fastapi/pydantic stand-ins + fake DB so `apps/api/main.py` is actually imported and its
  routes called (auth, ingestion, batch replay, alert lifecycle, equipment, check-ins, notes, simulator, WebSocket).
  `python3 tools/offline_smoke/run_smoke.py` -> 28/28 pass. It is NOT FastAPI: no 422/CORS/Starlette/SQLAlchemy-route coverage.
- **Bug: offline-queue replay order.** `apps/api/replay.py` sorted by `str(timestamp)`, so numeric timestamps
  replayed out of order (1000.0 before 999.0). Now sorted by instant (numbers and ISO-8601). 3 regression tests.
- **Bug: WebSocket leaked dead sockets** on any non-`WebSocketDisconnect` exception; cleanup now in `finally`.
- **Safety: alerts can no longer be dismissed once ESCALATED/RESPONDED** (the engine docstring always said
  dismiss is only from ALERTED/ACKNOWLEDGED; the code allowed any open state). There was no way to close a
  RESPONDED alert except dismissing it, so added `POST /alerts/{id}/resolve`, `alertsApi.resolve` and a Resolve
  button (shown for RESPONDED); Dismiss now only shows for ALERTED/ACKNOWLEDGED. 3 new engine tests.
- Static scan for undefined names across all Python files: clean. All 52 `.ts/.tsx` files transpile (syntax only).
- Tests: **203/203** (`PYTHONPATH=. python3 -m unittest discover -s tests`).
NOT done / unchanged: uvicorn, `tsc -b`, `vite build`, curl smoke, Docker/CI first run, real PhysioNet data,
native-speaker review of Hindi/Tamil/Telugu notes, model retraining on real data.
