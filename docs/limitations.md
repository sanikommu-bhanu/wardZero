# Known Limitations (honest, as of this session)

## Clinical / data
- **Not clinically validated.** All models are trained on synthetic data and must never be presented
  as, or mistaken for, a real diagnostic tool. The disclaimer
  *"Clinical decision-support prototype — not a medical diagnosis or emergency-response substitute"*
  must appear anywhere risk output is shown.
- Tamil, Telugu, Hindi, and Romanized-Hindi phrase lists in `services/nlp_engine/lexicon.py` have
  **not** been reviewed by a native speaker or clinician. Do not silently "correct" these mappings by
  guessing — get native-speaker/clinical review before trusting them in anything but a demo.
- `deteriorates_48h` model metrics are not trustworthy (positive class is ~0.6% of the test set).
- `risk_class` model's ~99.5% accuracy reflects an easy synthetic-label mapping, not real-world
  performance — must always be shown with that caveat, never as a bare number.

## Engineering — not yet built or not yet executable
- **Frontend built** (`apps/web/`, React + Vite + TS — 17 pages, 13 components) but **never compiled,
  bundled, or rendered in a browser** — `npm install` fails with `403 Forbidden` against the npm
  registry in this sandbox (no network). Internally consistent per a real import/export cross-check and
  a syntax-level transpile check across all 46 `.ts`/`.tsx` files (see `STATUS.md`), which is real
  evidence but not a substitute for `tsc --noEmit` or an actual render — type errors, prop mismatches,
  and hook-rule violations have not been checked.
- **SQLAlchemy database layer** (`database/*`): written and internally reviewed, **still not
  executed** — sqlalchemy is not installed in this sandbox and there is no network access to install
  it. The running app persists to `apps/api/repository.py`'s `InMemoryRepository` instead — **this is
  the single biggest gap relative to the original spec's "verify actual persistence" requirement**: data
  does not survive an API restart, and is shared across whatever browser tabs are open rather than
  being a real per-install database. Do not present this as "the database" to a judge; present it as
  "the tested in-memory store the SQLAlchemy layer is designed to be swapped in behind."
- **FastAPI HTTP/WebSocket layer** (`apps/api/main.py`, `ws_manager.py`): written, **not executed** —
  fastapi/uvicorn not installed, same reason. This now includes two new routes added this session
  (`/patients/{id}/readings`, `/reports/{id}/pdf`) — same verification status as the rest of the file.
- **bcrypt password hashing**: written, **not executed** — bcrypt not installed, same reason.
- **PDF report generation** (`apps/api/reports_pdf.py`): **written AND executed/verified** this
  session — `reportlab`/`pypdf` are installed in this sandbox now (they were not in earlier sessions).
  See `docs/reports.md`. This is the one item in this list that has moved from "not yet executable" to
  actually tested; everything else in this section is unchanged.
- **Alembic migrations**: not yet scaffolded; `database/session.init_db()` uses
  `create_all(checkfirst=True)`, which is a dev convenience, not a migration system.
- **DB-write-failure re-queue at the FastAPI route level**: designed (see `docs/reliability.md`) but
  not yet implemented as code.
- **Docker / GitHub Actions / Three.js digital twin / React Three Fiber / Vitest / Playwright**: none
  attempted — out of scope for the sessions so far, and several (npm packages, Docker builds) would
  also need network access this sandbox does not have.
- **SHAP**: confirmed unavailable in this sandbox; the occlusion-attribution fallback path is the one
  actually exercised and verified.
- **Historical vitals charts still read only from the live WebSocket buffer**, not the new
  `/patients/{id}/readings` endpoint — the endpoint exists and is wired into `lib/api.ts`, but no chart
  component consumes it yet. Charts are empty on page load until a simulation is actively running in
  that tab, same as before.

## Environment constraints, as of the most recent session
Python 3.12.3, Node v22.22.2 / npm 10.9.7 present, **no network access** (confirmed again this session
by a failed `pip install fastapi --break-system-packages` and a failed `npm ping`). Installed and
usable: numpy, pandas, scikit-learn, joblib, PyJWT, scikit-image, scipy, matplotlib, **reportlab,
pypdf** (new this session — not present in earlier sessions, which is why PDF export was previously
listed as unattempted here). The global `typescript` npm package is also present and can syntax-check
(not type-check) `.ts`/`.tsx` files without `npm install` — see `STATUS.md` item 6. Not installed and
not installable here: fastapi, pydantic, sqlalchemy, pytest, shap, uvicorn, alembic, bcrypt, httpx,
python-multipart, xgboost, and the frontend's own npm dependencies (vite, react-router-dom, recharts,
etc. — `@types/react` included).

## Added in the latest pass
- **MQTT: BLOCKED.** No broker or paho-mqtt here. Only payload normalization exists and is tested.
- **No real hardware.** Every device is simulated; the API can never report `real_hardware` today.
- **Roles:** only `caregiver` and `administrator`; no per-route role enforcement.
- **Security fixes unexecuted:** signup role restriction, WebSocket JWT check, CORS allow-list.

## Evaluation and Phase 4/5 additions (this pass)
- Synthetic evaluation now runs end to end (`evidence/eval_synthetic.md`); it is NOT clinical validation. See `docs/model_card.md`.
- Real-data loader (`ml/data/physionet.py`, `ml/evaluation/real_data_check.py`): tested on a synthetic fixture only; never run on PhysioNet data.
- Fixed: `threshold_for_alarm_budget` returned a threshold that still alarmed when the budget was unreachable.
- Dockerfiles, compose file and CI workflow are unexecuted. The light theme and Appearance setting have not been viewed in a browser.
- `tsc -b` / `vite build` still never run; `apps/api/main.py` new routes still never executed (fastapi not installed).
