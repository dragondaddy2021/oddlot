"""Unit tests for JWT verification (app.core.security).

Run:  pip install pytest && pytest backend/tests
No network / Supabase needed: the JWKS lookup is monkeypatched.
"""
import base64
import json
import os
import sys
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

# app.core.config builds Settings() at import time, so dummy values are required.
for _k in (
    "ANTHROPIC_API_KEY", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "UPSTASH_REDIS_TOKEN", "FINMIND_API_TOKEN",
):
    os.environ.setdefault(_k, "test")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("UPSTASH_REDIS_URL", "https://example.upstash.io")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import security  # noqa: E402

ISSUER = "https://example.supabase.co/auth/v1"
KID = "test-key-1"


def _b64(n: int) -> str:
    return base64.urlsafe_b64encode(n.to_bytes(32, "big")).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def keypair():
    return ec.generate_private_key(ec.SECP256R1())


def _jwk(key, kid=KID):
    nums = key.public_key().public_numbers()
    return {"kty": "EC", "crv": "P-256", "alg": "ES256", "use": "sig",
            "kid": kid, "x": _b64(nums.x), "y": _b64(nums.y)}


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch, keypair):
    monkeypatch.setattr(security, "_get_jwks", lambda: [_jwk(keypair)])


def _token(key, *, kid=KID, alg="ES256", **overrides):
    now = int(time.time())
    claims = {"sub": "user-1", "iss": ISSUER, "iat": now, "exp": now + 3600}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


def _rejected(token):
    with pytest.raises(HTTPException) as e:
        security._decode_token(token)
    assert e.value.status_code == 401
    assert e.value.detail == "Invalid or expired token"  # never leak the reason


def test_valid_token(keypair):
    payload = security._decode_token(_token(keypair))
    assert payload["sub"] == "user-1"


def test_expired(keypair):
    _rejected(_token(keypair, exp=int(time.time()) - 10))


def test_future_iat(keypair):
    now = int(time.time())
    _rejected(_token(keypair, iat=now + 3600, exp=now + 7200))


def test_wrong_issuer(keypair):
    _rejected(_token(keypair, iss="https://evil.example.com/auth/v1"))


def test_missing_sub(keypair):
    _rejected(_token(keypair, sub=None))


def test_missing_exp(keypair):
    _rejected(_token(keypair, exp=None))


def test_unknown_kid(keypair):
    _rejected(_token(keypair, kid="other-key"))


def test_signed_by_attacker_key(keypair):
    attacker = ec.generate_private_key(ec.SECP256R1())
    _rejected(_token(attacker))  # valid structure, right kid, wrong signature


def test_alg_none():
    def b(o):
        return base64.urlsafe_b64encode(json.dumps(o).encode()).rstrip(b"=").decode()
    now = int(time.time())
    tok = (f"{b({'alg': 'none', 'typ': 'JWT', 'kid': KID})}."
           f"{b({'sub': 'x', 'iss': ISSUER, 'exp': now + 3600})}.")
    _rejected(tok)


def test_hs256_confusion_with_public_key(keypair):
    # classic algorithm-confusion attack: HMAC-sign using the *public* key bytes
    from cryptography.hazmat.primitives import serialization
    pub_pem = keypair.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    now = int(time.time())
    # PyJWT itself refuses to HMAC-sign with a PEM public key, so build it by hand.
    import hashlib
    import hmac

    def b(o):
        return base64.urlsafe_b64encode(json.dumps(o).encode()).rstrip(b"=").decode()
    signing_input = (f"{b({'alg': 'HS256', 'typ': 'JWT', 'kid': KID})}."
                     f"{b({'sub': 'x', 'iss': ISSUER, 'iat': now, 'exp': now + 3600})}")
    sig = base64.urlsafe_b64encode(
        hmac.new(pub_pem, signing_input.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    _rejected(f"{signing_input}.{sig}")


def test_tampered_payload(keypair):
    head, payload, sig = _token(keypair).split(".")
    pad = "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload + pad))
    claims["sub"] = "someone-else"
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    _rejected(f"{head}.{forged}.{sig}")


def test_garbage():
    for t in ("", "abc", "a.b.c", "....", "x" * 5000):
        _rejected(t)
