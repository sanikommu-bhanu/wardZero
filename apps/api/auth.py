"""STEP 10 — local JWT authentication (email + password only; no social login per spec).

** VERIFICATION STATUS: WRITTEN, SYNTAX-CHECKED, NOT EXECUTED. ** bcrypt and PyJWT's use together
with a live FastAPI app has not been run end-to-end here: bcrypt is not installed in this sandbox
and there is no network access to install it (PyJWT alone IS installed and importable here, and its
encode/decode round-trip below has been exercised directly — see tests/test_auth_jwt.py — but the
password-hashing and FastAPI-dependency parts have not been executed).
"""
from __future__ import annotations
import os
import time
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT — installed and importable in this sandbox

JWT_ALGORITHM = "HS256"
_DEV_SECRET = None


def _secret() -> str:
    global _DEV_SECRET
    s = os.environ.get("WZ_JWT_SECRET")
    if s:
        return s
    if os.environ.get("WZ_ENV", "development").lower() == "production":
        raise RuntimeError("WZ_JWT_SECRET must be set in production — refusing to run with a default secret")
    # Development convenience: a random per-process secret (never a hardcoded default). Tokens simply
    # become invalid when the API restarts, which is safe; set WZ_JWT_SECRET to make them survive.
    if _DEV_SECRET is None:
        import secrets
        _DEV_SECRET = secrets.token_urlsafe(48)
        print("[wardzero] WZ_JWT_SECRET not set — using a random per-process dev secret")
    return _DEV_SECRET


def _expire_minutes() -> int:
    return int(os.environ.get("WZ_JWT_EXPIRE_MINUTES", "60"))


def hash_password(password: str) -> str:
    import bcrypt  # imported lazily so this module still imports (e.g. for token tests) without bcrypt
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    if len(password.encode()) > 72:  # bcrypt limit; bcrypt>=5 raises instead of truncating
        raise ValueError("password must be at most 72 bytes")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode()[:72], password_hash.encode())


def create_access_token(user_id: int, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "email": email, "role": role,
              "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=_expire_minutes())).timestamp())}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


class TokenError(Exception):
    pass


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("token expired")
    except jwt.InvalidTokenError as e:
        raise TokenError(f"invalid token: {e}")


# -- FastAPI wiring (not executable here — fastapi is not installed) --------------------------
# from fastapi import Depends, HTTPException, status
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# bearer_scheme = HTTPBearer()
#
# def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
#     try:
#         return decode_access_token(creds.credentials)
#     except TokenError as e:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
#
# def require_role(*roles: str):
#     def _dep(user: dict = Depends(get_current_user)) -> dict:
#         if user["role"] not in roles:
#             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")
#         return user
#     return _dep
