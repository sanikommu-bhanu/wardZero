# API

Base URL (dev): `http://127.0.0.1:8000`. Full interactive schema at `/docs` (Swagger UI, auto-generated
by FastAPI) once the API is running with fastapi/uvicorn installed — **not runnable in this sandbox**,
see `docs/architecture.md`'s executability table.

All endpoints except `/health`, `/auth/signup`, `/auth/signin` require `Authorization: Bearer <jwt>`.

## Auth
| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/auth/signup` | `full_name, email, password, role` | `role` ∈ `caregiver, administrator`. No social login. |
| POST | `/auth/signin` | `email, password` | Returns `{access_token, token_type}` |

## Ingestion
| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/readings` | `raw_event, patient_context, note_signals?` | Runs the full VALIDATE→…→TIMELINE pipeline; returns the `IngestionResult` |

`raw_event` fields are whitelisted server-side (`apps/api/validation.ALLOWED_READING_FIELDS`); any
other field (including the simulator's internal `_true_severity`) is dropped, not forwarded.

## Alerts
| Method | Path | Notes |
|---|---|---|
| GET | `/alerts?patient_id=&open_only=` | List alerts |
| POST | `/alerts/{id}/acknowledge` | ALERTED/ESCALATED → ACKNOWLEDGED |
| POST | `/alerts/{id}/dismiss` `{reason}` | requires non-empty reason; only from ALERTED/ACKNOWLEDGED (otherwise 400 - resolve instead) |
| POST | `/alerts/{id}/resolve` `{note?}` | from ACKNOWLEDGED/ESCALATED/RESPONDED |
| POST | `/alerts/{id}/escalate` | manual escalation |
| POST | `/alerts/{id}/respond` `{note?}` | ACKNOWLEDGED/ESCALATED → RESPONDED |
| POST | `/alerts/{id}/note` `{note}` | append a note at any time |

Invalid lifecycle transitions return `400` with the reason (see `services/alert_engine/engine.py`'s
`InvalidTransition` messages).

## Timeline
| Method | Path | Notes |
|---|---|---|
| GET | `/patients/{id}/timeline` | append-only per-patient event history |

## Realtime
| Protocol | Path | Notes |
|---|---|---|
| WebSocket | `/ws` | Every `/readings` call broadcasts its notification (`vitals_update` or `alert`) to all connected clients — no manual refresh needed. |

## Response contract for risk assessments
```json
{
  "risk_level": "LOW | MEDIUM | HIGH",
  "probability": 0.0,
  "contributing_factors": [],
  "explanation": "",
  "trend": {},
  "recommended_escalation": "routine_monitoring | caregiver_review | escalate_to_doctor | emergency",
  "forecast": {"deterioration_24h_probability": 0.0, "deterioration_48h_probability": 0.0, "basis": ""},
  "method": "model | rules",
  "hard_threshold_breaches": [],
  "disclaimer": "Clinical decision-support prototype — not a medical diagnosis or emergency-response substitute."
}
```
