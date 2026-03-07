import datetime as dt

import pytest
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient
from dotenv import load_dotenv

from core import jwt as core_jwt
from core.database import Base, engine, SessionLocal
from services.refresh_tokens import store_refresh_token
from main import app


client = TestClient(app)

# Ensure tables
Base.metadata.create_all(bind=engine)


def test_refresh_missing_token():
    resp = client.post("/auth/refresh")
    assert resp.status_code == 400


def test_refresh_valid_token(monkeypatch):
    load_dotenv()
    token = core_jwt.create_refresh_token({"email": "user@example.com", "name": "User"})

    db = SessionLocal()
    store_refresh_token(
        db,
        user_id="user@example.com",
        token=token,
        expires_at=dt.datetime.utcnow() + dt.timedelta(days=core_jwt.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.close()

    resp = client.post("/auth/refresh", params={"refresh_token": token})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body


def test_refresh_invalid_token(monkeypatch):
    load_dotenv()
    invalid = core_jwt.create_token({"email": "user@example.com"})

    resp = client.post("/auth/refresh", params={"refresh_token": invalid})
    assert resp.status_code == 401


def test_refresh_expired(monkeypatch):
    load_dotenv()
    monkeypatch.setattr(core_jwt, "REFRESH_TOKEN_EXPIRE_DAYS", -1)
    expired = core_jwt.create_refresh_token({"email": "user@example.com"})

    resp = client.post("/auth/refresh", params={"refresh_token": expired})
    assert resp.status_code == 401
