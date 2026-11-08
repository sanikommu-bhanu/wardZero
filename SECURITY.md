# Security Policy

WardZero AI is a clinical decision-support **prototype** built with synthetic demo data. It is not a
medical device and has not undergone a security audit or clinical validation.

## Reporting a vulnerability
Please open a private security advisory on the repository (GitHub → Security → Advisories) rather
than a public issue. Include: affected file/endpoint, reproduction steps, and impact. There is no
bug-bounty program for this prototype.

## Scope notes
- All demo patients and sensor readings are synthetic; there is no real patient data in this
  repository to protect, but the authentication/authorization/audit-logging code paths (see
  `docs/security.md`) are written as if it were, so they can be reviewed as production-representative.
- No third-party AI API receives any data — all inference is local (see `docs/free-services.md`).
- See `docs/limitations.md` for what is written-but-unexecuted in the current sandbox (SQLAlchemy,
  FastAPI, bcrypt) — do not treat those as verified secure until run and reviewed with the actual
  dependencies installed.

## Known weaknesses and fixes (most recent pass)
Fixed, but **not executed** here (fastapi is not installable in this sandbox) — review when run:
- `POST /auth/signup` previously accepted `role="administrator"` from any caller, i.e. anyone could
  self-register as an administrator. It now creates caregivers only and returns 403 for any other role.
- The `/ws` WebSocket previously accepted unauthenticated clients and broadcast patient vitals/alerts.
  It now requires a valid JWT in `?token=` and closes with code 1008 otherwise. Tokens in URLs can leak
  into access logs; disable query-string logging and keep `WZ_JWT_EXPIRE_MINUTES` short.
- CORS was `*`; it is now an allow-list from `WZ_CORS_ORIGINS`.

Still open:
- Only two roles exist (`caregiver`, `administrator`); no route enforces role beyond "authenticated".
- No rate limiting on sign-in/sign-up.
- Real devices would need per-device credentials; ingestion currently uses a user JWT.
- No CSRF/session hardening review, and no dependency vulnerability scan (no network).
