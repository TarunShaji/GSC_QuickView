from __future__ import annotations
"""
Supabase Auth — JWKS / ES256 JWT Verification
==============================================

Supabase JWT Signing Keys (ECC P-256 / ES256).
Tokens are verified against the public JWKS endpoint.
No secret stored server-side.

JWKS URL:  https://kmfbhxvchageejccfoat.supabase.co/auth/v1/.well-known/jwks.json
Algorithm: ES256
Audience:  "authenticated"
Issuer:    https://kmfbhxvchageejccfoat.supabase.co/auth/v1
user_id:   payload["sub"]
"""

import threading
import time
from typing import Optional

import requests
from fastapi import HTTPException, Request
from jose import jwt, JWTError

from src.settings import settings


def _supabase_issuer() -> str:
    return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"


def _jwks_url() -> str:
    return f"{_supabase_issuer()}/.well-known/jwks.json"


# ─── JWKS cache (in-memory, 6-hour TTL) ───────────────────────────────────────
_jwks_cache: Optional[dict] = None
_jwks_cache_ts: float = 0.0
_JWKS_TTL_SECONDS: int = 6 * 3600
_jwks_lock = threading.Lock()


def _get_jwks() -> dict:
    """Fetch (or return cached) JWKS from Supabase."""
    global _jwks_cache, _jwks_cache_ts

    with _jwks_lock:
        now = time.time()
        if _jwks_cache is not None and (now - _jwks_cache_ts) < _JWKS_TTL_SECONDS:
            return _jwks_cache

        try:
            resp = requests.get(_jwks_url(), timeout=5)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_cache_ts = now
            print(f"[SUPABASE_AUTH] JWKS refreshed ({len(_jwks_cache.get('keys', []))} key(s))")
            return _jwks_cache
        except Exception as e:
            if _jwks_cache is not None:
                print(f"[SUPABASE_AUTH] JWKS refresh failed ({e}), using stale cache")
                return _jwks_cache
            raise RuntimeError(f"Failed to fetch Supabase JWKS: {e}") from e


def _find_jwk(kid: str) -> dict:
    """Return the JWK matching the given key ID."""
    jwks = _get_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    raise HTTPException(status_code=401, detail="JWT signing key not found in JWKS")


# ─── Core verification ─────────────────────────────────────────────────────────

def verify_supabase_jwt(token: str) -> dict:
    """
    Verify a Supabase-issued JWT (ES256 / ECC P-256).

    Steps:
      1. Decode unverified header to get `kid`.
      2. Look up matching public key in cached JWKS.
      3. Verify signature, expiry, audience, and issuer.
      4. Return decoded payload on success.

    Raises:
      HTTPException 401 on any verification failure.
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid JWT header: {e}")

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="JWT header missing 'kid'")

    public_key_data = _find_jwk(kid)

    try:
        payload = jwt.decode(
            token,
            public_key_data,
            algorithms=["ES256"],
            audience="authenticated",
            issuer=_supabase_issuer(),
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"JWT verification failed: {e}")


# ─── FastAPI dependency ────────────────────────────────────────────────────────

def get_current_user_id(request: Request) -> str:
    """
    FastAPI dependency: extracts and verifies the Supabase Bearer token,
    returning the user's UUID (payload['sub']).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authorization header must be 'Bearer <token>'"
        )

    token = parts[1]
    payload = verify_supabase_jwt(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="JWT missing 'sub' claim")

    return user_id
