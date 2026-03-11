import pytest
from jose import jwt as jose_jwt

from core import jwt as core_jwt


def test_create_and_decode_access_token_roundtrip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    payload = {"email": "user@example.com", "name": "User"}

    token = core_jwt.create_token(payload)
    decoded = core_jwt.decode_token(token)

    assert decoded["email"] == payload["email"]
    assert decoded["name"] == payload["name"]
    assert "jti" in decoded
    assert "exp" in decoded


def test_access_token_expired(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    monkeypatch.setattr(core_jwt, "ACCESS_TOKEN_EXPIRE_HOURS", -1)

    token = core_jwt.create_token({"email": "user@example.com"})

    with pytest.raises(Exception):
        core_jwt.decode_token(token)


def test_decode_invalid_signature(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    forged = jose_jwt.encode({"email": "user@example.com"}, "other-secret", algorithm="HS256")

    with pytest.raises(Exception):
        core_jwt.decode_token(forged)


def test_create_and_decode_refresh_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-key")
    payload = {"email": "user@example.com"}
    token = core_jwt.create_refresh_token(payload)
    decoded = core_jwt.decode_refresh_token(token)
    assert decoded["email"] == payload["email"]
    assert decoded["type"] == "refresh"
