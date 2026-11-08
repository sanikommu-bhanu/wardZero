# Testing

Run all automated tests (stdlib `unittest`, since `pytest` is not installed in this sandbox — no
network access to install it):

```
PYTHONPATH=. python3 -m unittest discover -s tests
```

## Current result (this session, actually run)
**130/130 tests passing.**

| Module | Tests | Status |
|---|---|---|
| `services/sync_engine/queue.py` | 12 | pass |
| `services/nlp_engine` | 20 | pass |
| `ml/data/generator.py` | 14 | pass |
| `ml/training/train.py` | 4 | pass |
| `ml/inference/predict.py` | 8 | pass |
| `ml/explainability/explain.py` | 9 | pass |
| `services/risk_engine` | 18 | pass |
| `services/alert_engine` (new this session) | 24 | pass |
| `apps/api/pipeline.py` + `validation.py` (new this session) | 17 | pass |
| `apps/api/auth.py` JWT round-trip (new this session) | 4 | pass |

## Not run — and why
- `database/*` (SQLAlchemy models/session/seed) — sqlalchemy is not installed; no network access to
  install it (confirmed via a failed `pip install fastapi --break-system-packages` in this session).
  Reviewed for internal consistency; not executed against a real database.
- `apps/api/main.py`, `apps/api/ws_manager.py` (FastAPI routes + WebSocket) — fastapi/uvicorn not
  installed, same reason. Reviewed; not executed.
- `apps/api/auth.py`'s `hash_password`/`verify_password` — bcrypt not installed, same reason. The
  JWT-issuance half of the same file IS tested (PyJWT is installed).
- The full `pytest`/`Vitest`/`Playwright` suites named in the spec's stack — none of `pytest`,
  Node test runners for a not-yet-built frontend, or Playwright can run without network access to
  install them; stdlib `unittest` was used as the closest available equivalent, and is not a
  substitute for `pytest`'s fixtures/parametrization once network access is available.

## Caveat when re-running the full suite
`tests/test_training.py` retrains a small model as a side effect and overwrites `ml/artifacts/` with
a toy-sized version. After running the full suite, restore the full-size artifacts with:
```
python3 -m ml.training.train
```
before relying on `ml/artifacts/*.joblib` for anything else. This was done in this session and
re-verified (`risk_engine`, `inference`, `alert_engine`, and `pipeline` tests still pass against the
restored artifacts).
