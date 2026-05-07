import datetime as dt

import pytest

pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient
from dotenv import load_dotenv

from models.refresh_token import RefreshToken, hash_token
from models.user import User
from core.database import Base, engine, SessionLocal
from services import refresh_tokens as refresh_tokens_service
from main import app


client = TestClient(app)

# Ensure tables
Base.metadata.create_all(bind=engine)


def _seed_user(db) -> User:
    existing = db.query(User).filter(User.email == "user@example.com").first()
    if existing:
        return existing

    user = User(
        email="user@example.com",
        name="User",
        profile_picture=None,
        oauth_provider="google",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_refresh_missing_token():
    resp = client.post("/auth/refresh")
    assert resp.status_code == 400


def test_refresh_valid_token(monkeypatch):
    load_dotenv()
    db = SessionLocal()
    user = _seed_user(db)
    token = refresh_tokens_service.create_refresh_token(db, user_id=user.email)
    db.close()

    resp = client.post("/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body
    assert body["refresh_token"] != token


def test_refresh_invalid_token(monkeypatch):
    load_dotenv()
    invalid = "not-a-valid-refresh"

    resp = client.post("/auth/refresh", json={"refresh_token": invalid})
    assert resp.status_code == 401


def test_refresh_expired(monkeypatch):
    load_dotenv()
    monkeypatch.setattr(refresh_tokens_service, "REFRESH_TOKEN_EXPIRE_DAYS", -1)

    db = SessionLocal()
    user = _seed_user(db)
    expired = refresh_tokens_service.create_refresh_token(db, user_id=user.email)
    db.close()

    resp = client.post("/auth/refresh", json={"refresh_token": expired})
    assert resp.status_code == 401


def test_store_and_revoke_refresh_token(monkeypatch):
    load_dotenv()
    db = SessionLocal()
    user = _seed_user(db)
    token = "manual-token"
    expires_at = dt.datetime.utcnow() + dt.timedelta(days=1)
    refresh_tokens_service.store_refresh_token(db, user_id=user.email, token=token, expires_at=expires_at)
    assert refresh_tokens_service.is_refresh_token_valid(db, token)
    refresh_tokens_service.revoke_refresh_token(db, token)
    assert not refresh_tokens_service.is_refresh_token_valid(db, token)
    db.close()


def test_refresh_token_replay_attack_returns_revoked(monkeypatch):
    load_dotenv()
    db = SessionLocal()
    user = _seed_user(db)
    old_token = refresh_tokens_service.create_refresh_token(db, user_id=user.email)
    db.close()

    first_resp = client.post("/auth/refresh", json={"refresh_token": old_token})
    assert first_resp.status_code == 200
    new_token = first_resp.json()["refresh_token"]
    assert new_token != old_token

    replay_resp = client.post("/auth/refresh", json={"refresh_token": old_token})
    assert replay_resp.status_code == 401
    assert replay_resp.json()["detail"] == "Token has been revoked"


def test_refresh_cleans_expired_tokens_on_each_call(monkeypatch):
    load_dotenv()
    db = SessionLocal()
    user = _seed_user(db)
    expired_token = "expired-refresh-token"
    refresh_tokens_service.store_refresh_token(
        db,
        user_id=user.email,
        token=expired_token,
        expires_at=dt.datetime.utcnow() - dt.timedelta(minutes=1),
    )
    valid_token = refresh_tokens_service.create_refresh_token(db, user_id=user.email)
    db.close()

    resp = client.post("/auth/refresh", json={"refresh_token": valid_token})
    assert resp.status_code == 200

    db = SessionLocal()
    expired_record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_token(expired_token))
        .first()
    )
    db.close()
    assert expired_record is None
