import time
from threading import Lock

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

_bearer = HTTPBearer()

ALGORITHM = "ES256"
_JWKS_TTL = 3600  # refresh public keys every hour

# In-memory JWKS cache — shared across all requests in the process
_jwks_cache: dict = {"keys": [], "fetched_at": 0.0}
_jwks_lock = Lock()


def _jwks_url() -> str:
    return settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"


def _supabase_issuer() -> str:
    return settings.supabase_url.rstrip("/") + "/auth/v1"


def _get_jwks() -> list[dict]:
    """Return cached JWKS keys; re-fetch from Supabase if cache has expired."""
    now = time.monotonic()
    with _jwks_lock:
        if _jwks_cache["keys"] and now - _jwks_cache["fetched_at"] < _JWKS_TTL:
            return _jwks_cache["keys"]

        try:
            response = httpx.get(_jwks_url(), timeout=10)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # If we have stale keys, keep using them rather than locking out users
            if _jwks_cache["keys"]:
                return _jwks_cache["keys"]
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        keys: list[dict] = response.json().get("keys", [])
        _jwks_cache["keys"] = keys
        _jwks_cache["fetched_at"] = now
        return keys


def _decode_token(token: str) -> dict:
    """Decode and verify a Supabase-issued JWT (ES256 / P-256).

    Checks performed:
    - Signature  — ES256 with the matching public key from Supabase JWKS
    - Key ID     — `kid` in token header must match a key in JWKS
    - Expiry     — rejects tokens past `exp` claim
    - Issued-at  — rejects tokens with a future `iat` claim
    - Issuer     — `iss` must equal SUPABASE_URL/auth/v1
    Audience check is intentionally skipped: Supabase does not populate `aud`
    with a value that can be statically verified server-side.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    kid: str | None = header.get("kid")
    jwks_keys = _get_jwks()

    # Match the token's kid against the JWKS
    matching_key: dict | None = next(
        (k for k in jwks_keys if k.get("kid") == kid), None
    )
    if matching_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token,
            matching_key,          # JWK dict — python-jose constructs EC key automatically
            algorithms=[ALGORITHM],
            issuer=_supabase_issuer(),
            options={
                "verify_aud": False,  # Supabase does not set a verifiable aud
                "verify_exp": True,   # reject expired tokens
                "verify_iat": True,   # reject tokens with future issued-at
            },
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """FastAPI dependency — returns the decoded JWT payload or raises 401."""
    return _decode_token(credentials.credentials)
