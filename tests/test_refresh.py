import pytest
from fastapi.testclient import TestClient

from core import jwt as core_jwt
from main import app


client = TestClient(app)


def test_refresh_missing_token():
    resp = client.post("/auth/refresh")
    assert resp.status_code == 400


def test_refresh_valid_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret")
    token = core_jwt.create_refresh_token({"email": "user@example.com", "name": "User"})

    resp = client.post("/auth/refresh", params={"refresh_token": token})

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body
    decoded = core_jwt.decode_token(body["access_token"])
    assert decoded["email"] == "user@example.com"


def test_refresh_invalid_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret")
    invalid = core_jwt.create_token({"email": "user@example.com"})  

    resp = client.post("/auth/refresh", params={"refresh_token": invalid})
    assert resp.status_code == 401


def test_refresh_expired(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret")

    monkeypatch.setattr(core_jwt, "REFRESH_TOKEN_EXPIRE_DAYS", -1)
    expired = core_jwt.create_refresh_token({"email": "user@example.com"})

    resp = client.post("/auth/refresh", params={"refresh_token": expired})
    assert resp.status_code == 401
