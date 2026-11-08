# Free Services & Dependencies

WardZero AI's core functionality has a **₹0 operating cost** and keeps working if every external
service below is unavailable. This file documents every dependency, categorized as:

- **REQUIRED — FREE**: needed for core functionality, and free with no credit card.
- **OPTIONAL — FREE EXTERNAL**: nice-to-have, genuinely free, system works without it.
- **LOCAL FALLBACK**: what runs instead when nothing external is available.

| Dependency | Category | Provider | Purpose | Free-tier status | Auth required | Credit card | Rate limits | Local fallback | Behavior when unavailable |
|---|---|---|---|---|---|---|---|---|---|
| Python 3.12 + NumPy/pandas/scikit-learn | REQUIRED — FREE | PSF / open source | ML training + inference | Free, open source, self-hosted | No | No | None | N/A — this *is* the local implementation | Core system cannot run without a Python runtime; not an "external API" in the paid-service sense |
| SHAP | OPTIONAL — FREE EXTERNAL | open source (pip) | Model explainability | Free, open source | No | No | None | `ml/explainability/explain.py` feature-occlusion attribution | Explanation method label switches from `"SHAP"` to `"feature occlusion fallback"`; system keeps working |
| XGBoost | OPTIONAL — FREE EXTERNAL | open source (pip) | Optionally stronger classifier | Free, open source | No | No | None | scikit-learn `GradientBoostingClassifier`/`RandomForestClassifier` | `ml/training/train.py` uses the scikit-learn model if xgboost isn't installed |
| SQLite | REQUIRED — FREE (dev) | public domain | Local database | Free, bundled with Python | No | No | None | N/A | Always available; this is the fallback itself |
| PostgreSQL | OPTIONAL — FREE EXTERNAL | open source / any self-host | Production database | Free if self-hosted (e.g. Docker) | Depends on host | No (self-hosted) | None (self-hosted) | SQLite (`WZ_DATABASE_URL` default) | System runs entirely on SQLite if no Postgres is configured |
| FastAPI / Uvicorn / Pydantic / SQLAlchemy / PyJWT / bcrypt | REQUIRED — FREE | open source (pip) | Web framework, auth, ORM | Free, open source, self-hosted | No | No | None | N/A | These are the local implementation, not an external paid API |
| Our own IoT simulator (`apps/simulator`) | REQUIRED — FREE | self-built | Software-simulated sensors | N/A (our code) | No | No | None | N/A | No physical hardware or third-party IoT platform is used at all |
| Our own NLP engine (`services/nlp_engine`) | REQUIRED — FREE | self-built | Multilingual caregiver-note understanding | N/A (our code) | No | No | None | N/A | Fully local lexicon + rule-based engine; no external NLP API call is made |
| Docker / GitHub Actions | OPTIONAL — FREE EXTERNAL | Docker Inc. / Microsoft | Packaging, CI | Free tier sufficient for this project's scale | GitHub account only | No | Generous free-tier minutes | Run `pytest`/`uvicorn` directly, no container | Project runs identically without Docker or CI; these only automate what can be done manually |
| ReportLab | REQUIRED — FREE | open source (pip) | PDF report generation | Free, open source | No | No | None | N/A | This is the (only) reporting implementation planned; no paid reporting API is used |

## Explicitly NOT used (per hard requirement)
No paid OpenAI/Anthropic/Gemini/Grok API, no paid medical API, no paid IoT platform (e.g. AWS IoT
Core beyond its always-free tier), no paid notification service (e.g. Twilio SMS), no paid mapping
API, no paid database service (e.g. managed RDS), and no feature requires a credit card to run in
its default configuration.

## Where this is enforced in code
- `apps/api/pipeline.py`'s risk stage calls `services.risk_engine.assess`, which always tries the
  **local** trained model first and falls back to a **local** rules engine on `ModelUnavailable` —
  it never calls an external inference API.
- `services/nlp_engine` is a local lexicon/rule engine; it does not call any external NLP service.
- `.env.example` has no field for any external paid API key; only `WZ_JWT_SECRET` (local secret) and
  `WZ_DATABASE_URL` (local or self-hosted Postgres) are required.
