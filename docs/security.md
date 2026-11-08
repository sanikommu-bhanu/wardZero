# Security

- **Authentication**: local JWT (HS256), email + password only, no social login (per spec).
  `apps/api/auth.py`. Secret comes from `WZ_JWT_SECRET` env var; `create_access_token` refuses to run
  with no secret set rather than defaulting to an insecure one.
- **Password storage**: bcrypt hash (`apps/api/auth.hash_password`), minimum 8 characters enforced.
  Never stored or logged in plaintext. **Not executed in this sandbox** — bcrypt is not installed here.
- **Authorization**: two roles, `caregiver` and `administrator` (`database.models.RoleEnum`).
  `require_role(...)` (sketched in `auth.py`, commented pending FastAPI availability) is the intended
  dependency for role-gated routes.
- **Input validation**: `apps/api/validation.py` whitelists every incoming sensor-event field (an
  allow-list, not a strip/deny-list), so unknown or internal-only fields (e.g. the simulator's
  `_true_severity`) cannot reach storage or any API response by construction.
- **Audit logging**: `database.models.AuditLog` and `services/alert_engine`'s per-alert `audit` list
  (every state transition, actor, and timestamp) both exist so caregiver actions are traceable.
- **CORS**: wide open (`allow_origins=["*"]`) in `apps/api/main.py` for this prototype/demo; a real
  deployment must restrict this to the actual frontend origin(s).
- **Secrets**: `.env.example` documents every required env var with placeholder (non-functional)
  values; `.env` itself is gitignored (already true in the pre-existing `.gitignore`).
- **No paid/third-party data exfiltration risk**: per `docs/free-services.md`, no patient data is
  ever sent to an external AI/ML API — all inference is local.

See `SECURITY.md` (repo root) for the vulnerability-reporting process.
