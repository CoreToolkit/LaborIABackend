import time
import pytest
import jwt as pyjwt
from datetime import datetime, timezone, timedelta

from core import jwt as core_jwt


# ── helpers ───────────────────────────────────────────────────────────────────

def _encode_raw(payload: dict, secret: str = "secret-key", algorithm: str = "HS256") -> str:
    """Crea un token sin pasar por create_token() para tests de claims faltantes."""
    return pyjwt.encode(payload, secret, algorithm=algorithm)


# ── roundtrip ─────────────────────────────────────────────────────────────────

def test_create_and_decode_access_token_roundtrip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    payload = {"email": "user@example.com", "name": "User"}

    token = core_jwt.create_token(payload)
    decoded = core_jwt.decode_token(token)

    assert decoded["email"] == payload["email"]
    assert decoded["name"] == payload["name"]
    assert "jti" in decoded
    assert "exp" in decoded
    assert "iat" in decoded
    assert "sub" in decoded


def test_access_token_expired(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    monkeypatch.setattr(core_jwt, "ACCESS_TOKEN_EXPIRE_HOURS", -1)

    token = core_jwt.create_token({"email": "user@example.com"})

    with pytest.raises(Exception):
        core_jwt.decode_token(token)


def test_decode_invalid_signature(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    now = datetime.now(timezone.utc)
    forged = _encode_raw(
        {"email": "user@example.com", "sub": "user@example.com",
         "exp": now + timedelta(hours=1), "iat": now},
        secret="other-secret",
    )

    with pytest.raises(Exception):
        core_jwt.decode_token(forged)


def test_create_and_decode_refresh_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    payload = {"email": "user@example.com"}
    token = core_jwt.create_refresh_token(payload)
    decoded = core_jwt.decode_refresh_token(token)
    assert decoded["email"] == payload["email"]
    assert decoded["type"] == "refresh"


# ── iss validation ────────────────────────────────────────────────────────────

def test_token_with_correct_iss_is_accepted(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.setenv("JWT_ISSUER", "laboria-backend")
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)

    token = core_jwt.create_token({"email": "user@example.com"})
    decoded = core_jwt.decode_token(token)
    assert decoded["iss"] == "laboria-backend"


def test_token_without_iss_rejected_when_issuer_configured(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.setenv("JWT_ISSUER", "laboria-backend")
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    now = datetime.now(timezone.utc)
    token = _encode_raw(
        {"sub": "user@example.com", "exp": now + timedelta(hours=1), "iat": now},
        secret="secret-key",
    )

    with pytest.raises(Exception) as exc_info:
        core_jwt.decode_token(token)
    assert exc_info.value.status_code == 401


def test_token_with_wrong_iss_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.setenv("JWT_ISSUER", "laboria-backend")
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    now = datetime.now(timezone.utc)
    token = _encode_raw(
        {"sub": "user@example.com", "iss": "other-app",
         "exp": now + timedelta(hours=1), "iat": now},
        secret="secret-key",
    )

    with pytest.raises(Exception) as exc_info:
        core_jwt.decode_token(token)
    assert exc_info.value.status_code == 401


# ── aud validation ────────────────────────────────────────────────────────────

def test_token_with_correct_aud_is_accepted(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.setenv("JWT_AUDIENCE", "laboria-frontend")

    token = core_jwt.create_token({"email": "user@example.com"})
    decoded = core_jwt.decode_token(token)
    assert decoded["aud"] == "laboria-frontend"


def test_token_without_aud_rejected_when_audience_configured(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.setenv("JWT_AUDIENCE", "laboria-frontend")
    now = datetime.now(timezone.utc)
    token = _encode_raw(
        {"sub": "user@example.com", "exp": now + timedelta(hours=1), "iat": now},
        secret="secret-key",
    )

    with pytest.raises(Exception) as exc_info:
        core_jwt.decode_token(token)
    assert exc_info.value.status_code == 401


def test_token_with_wrong_aud_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.setenv("JWT_AUDIENCE", "laboria-frontend")
    now = datetime.now(timezone.utc)
    token = _encode_raw(
        {"sub": "user@example.com", "aud": "other-frontend",
         "exp": now + timedelta(hours=1), "iat": now},
        secret="secret-key",
    )

    with pytest.raises(Exception) as exc_info:
        core_jwt.decode_token(token)
    assert exc_info.value.status_code == 401


# ── sub validation ────────────────────────────────────────────────────────────

def test_token_without_sub_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    now = datetime.now(timezone.utc)
    token = _encode_raw(
        {"email": "user@example.com", "exp": now + timedelta(hours=1), "iat": now},
        secret="secret-key",
    )

    with pytest.raises(Exception) as exc_info:
        core_jwt.decode_token(token)
    assert exc_info.value.status_code == 401


def test_token_with_empty_sub_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    now = datetime.now(timezone.utc)
    token = _encode_raw(
        {"sub": "   ", "exp": now + timedelta(hours=1), "iat": now},
        secret="secret-key",
    )

    with pytest.raises(Exception) as exc_info:
        core_jwt.decode_token(token)
    assert exc_info.value.status_code == 401


# ── exp / iat validation ──────────────────────────────────────────────────────

def test_token_without_exp_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    now = datetime.now(timezone.utc)
    token = _encode_raw(
        {"sub": "user@example.com", "iat": now},
        secret="secret-key",
    )

    with pytest.raises(Exception) as exc_info:
        core_jwt.decode_token(token)
    assert exc_info.value.status_code == 401


def test_token_without_iat_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    now = datetime.now(timezone.utc)
    token = _encode_raw(
        {"sub": "user@example.com", "exp": now + timedelta(hours=1)},
        secret="secret-key",
    )

    with pytest.raises(Exception) as exc_info:
        core_jwt.decode_token(token)
    assert exc_info.value.status_code == 401


# ── algorithm validation ──────────────────────────────────────────────────────

def test_token_with_disallowed_algorithm_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    now = datetime.now(timezone.utc)
    # RS256 no está en _ALLOWED_ALGORITHMS
    token = _encode_raw(
        {"sub": "user@example.com", "exp": now + timedelta(hours=1), "iat": now},
        secret="secret-key",
        algorithm="HS384",
    )

    with pytest.raises(Exception) as exc_info:
        core_jwt.decode_token(token)
    assert exc_info.value.status_code == 401


# ── error messages no exponen detalles sensibles ──────────────────────────────

def test_error_detail_does_not_expose_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "my-super-secret")
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)

    with pytest.raises(Exception) as exc_info:
        core_jwt.decode_token("invalid.token.here")

    detail = str(exc_info.value.detail)
    assert "my-super-secret" not in detail
    assert "HS256" not in detail
