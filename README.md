# WardZero AI

**"Always-aware intelligent home-care monitoring."**

`SENSE → UNDERSTAND → PREDICT → ALERT → RESPOND`

> Clinical decision-support prototype — not a medical diagnosis or emergency-response substitute.
> All patients and sensor readings in this repository are synthetic demo data.

WardZero AI combines a software-simulated IoT layer, local ML risk detection with explainability, a
multilingual caregiver-note NLP engine, an alert/escalation lifecycle, and an offline-first sync
layer into one integrated system — not three separate demos. See `docs/architecture.md` for the full
data-flow diagram.

## ₹0 cost
Every core dependency is free, open-source, and self-hostable; the system keeps working with every
external service unavailable. Full breakdown: `docs/free-services.md`.

## Quick start (needs internet once, for `pip`/`npm`)
```bash
# 1) Backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                       # optional; a random dev JWT secret is used if unset
uvicorn apps.api.main:app --reload --port 8000             # seeds 12 synthetic patients + demo users on first start

# 2) Frontend (second terminal)
cd apps/web && npm install && npm run dev                  # http://localhost:5173
```
Demo logins (seeded, synthetic): `caregiver.demo@wardzero.local` / `admin@wardzero.local`,
password `change-me-on-first-run` (override admin's with `WZ_ADMIN_PASSWORD`).

**Demo flow (Sensor -> Platform -> AI Risk -> Alert -> Response):** IoT Simulator page -> pick a patient and a
scenario (e.g. `breathing_deterioration`) -> Start -> watch Live Monitor vitals and the AI Risk explanation ->
an alert is raised -> Alerts page: Acknowledge / Escalate / Respond. Add a caregiver note on Caregiver Notes.

## Model results (honest reading — see `evidence/metrics.json`, reproduce with `python -m ml.training.train`)
Trained and evaluated on **synthetic** data from the same physiology engine as the simulator (no real patient
data is used or available offline). Patients, not rows, are split across train/val/test. Test split, 45 unseen patients:

| Model | Metric | Value | Baseline |
|---|---|---|---|
| Risk class (LOW/MED/HIGH) | macro-F1 | 0.98 | labels derive from simulator severity, so this is an *easy* task — not a real-world accuracy claim |
| Deterioration in 24h | ROC-AUC / PR-AUC | 0.96 / 0.96 | logistic regression 0.93 / 0.94, no-skill PR-AUC 0.48 |
| Deterioration in 48h | ROC-AUC / PR-AUC | 0.97 / 0.97 | logistic regression 0.91 / 0.93, no-skill PR-AUC 0.56 |

Training trajectories include delayed onset (0-60 h stable) and gradual vs acute courses, and rows without a full
look-ahead window are excluded rather than labeled negative. Real clinical validation (e.g. on MIMIC/eICU) has **not**
been done; every output carries a decision-support disclaimer.

## 5-minute demo script
1. Sign in (`caregiver.demo@wardzero.local`). Settings -> Appearance: try Light / Dark.
2. IoT Simulator: pick a patient, scenario `breathing_deterioration`, Start.
3. Live Monitor / AI Risk: watch the ML risk, the NEWS2 score beside it and the confidence label. Note the AI abstains
   until enough readings exist.
4. Alerts: acknowledge or let the escalation ladder time out; see time-to-acknowledge.
5. Chaos panel: cut the network, then restore. Readings queue offline and replay without loss or duplicates.
6. Caregiver Notes: enter a note in Hindi, Tamil or Telugu and see the extracted findings.
7. Offline evaluation: `python -m ml.evaluation.run_eval` (synthetic; see `docs/model_card.md`).

Docker: `cp .env.example .env && docker compose up --build` then open http://localhost:8080 (never run by the authors).

## Verification status
- **197 automated tests pass** (`PYTHONPATH=. python3 -m pytest -q`; includes resilience, clinical layer, evaluation metrics, real-data loader): NLP, data generator, training,
  inference, explainability, risk engine + rules fallback, alert lifecycle, ingestion pipeline, offline sync queue,
  PDF reports, JWT, and thread-safety of the WebSocket/simulator runtime.
- **Not executed in the build sandbox (no network):** the FastAPI route wiring, SQLAlchemy models/seed, and the React
  build (`tsc`/`vite`). They were reviewed line-by-line and several real bugs were fixed (see `STATUS.md`), but run them
  once on a networked machine and report any error. See `docs/limitations.md`.

## Repository layout
```
apps/simulator/     software IoT sensor simulator
apps/api/           ingestion pipeline, validation, auth, FastAPI app, websocket manager
apps/web/           React + Vite + TypeScript frontend (see "Frontend" section above)
ml/                 features, synthetic data generator, training, inference, explainability
services/
  nlp_engine/       multilingual caregiver-note understanding
  risk_engine/      model + rules-fallback + hard-threshold safety net
  alert_engine/     alert lifecycle, dedup, auto-escalation
  sync_engine/      offline-first durable event queue
database/           SQLAlchemy models, session, seed data
docs/               architecture, api, database, ai-ml, iot, reliability, security, free-services,
                    testing, limitations
evidence/           per-step metrics and evaluation notes
tests/              pytest suite (197 tests)
deploy: Dockerfile, apps/web/Dockerfile, docker-compose.yml, .github/workflows/ci.yml (all unexecuted)
```
