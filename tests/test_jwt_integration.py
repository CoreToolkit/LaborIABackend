# tests/test_jwt_integration.py
# TASK-031-01: Tests de integración JWT sobre endpoint protegido.
# Verifica que tokens válidos pasan y tokens con claims incorrectos son rechazados.

import os
from datetime import datetime, timezone, timedelta

import jwt as pyjwt
import pytest
from core.config import settings as app_settings
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "integration-secret")

import api.roles as roles_module
from core.database import get_db
from core import jwt as core_jwt


def _make_app():
    """App aislada con un endpoint protegido para tests de integración."""
    from unittest.mock import MagicMock
    test_app = FastAPI()
    test_app.include_router(roles_module.router, prefix="/api")
    # Mock db que devuelve lista vacía en lugar de None
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.count.return_value = 0
    mock_db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
    mock_db.query.return_value.count.return_value = 0
    mock_db.query.return_value.offset.return_value.limit.return_value.all.return_value = []
    test_app.dependency_overrides[get_db] = lambda: mock_db
    return test_app


def _valid_token(monkeypatch, *, issuer=None, audience=None) -> str:
    monkeypatch.setattr(app_settings, "JWT_SECRET", "integration-secret")
    if issuer:
        monkeypatch.setattr(app_settings, "JWT_ISSUER", issuer)
    else:
        monkeypatch.setattr(app_settings, "JWT_ISSUER", None)
    if audience:
        monkeypatch.setattr(app_settings, "JWT_AUDIENCE", audience)
    else:
        monkeypatch.setattr(app_settings, "JWT_AUDIENCE", None)
    return core_jwt.create_token({"email": "user@example.com", "id": 1, "name": "Test"})


def _raw_token(payload: dict, secret: str = "integration-secret") -> str:
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _now_plus(hours: int = 1):
    return datetime.now(timezone.utc) + timedelta(hours=hours)


# ── token válido → 200 (o 404/422 si no hay datos, pero no 401) ──────────────

def test_valid_token_passes_auth(monkeypatch):
    monkeypatch.setattr(app_settings, "JWT_SECRET", "integration-secret")
    monkeypatch.setattr(app_settings, "JWT_ISSUER", None)
    monkeypatch.setattr(app_settings, "JWT_AUDIENCE", None)

    token = _valid_token(monkeypatch)
    client = TestClient(_make_app())
    response = client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code != 401


def test_valid_token_with_iss_and_aud_passes(monkeypatch):
    monkeypatch.setattr(app_settings, "JWT_SECRET", "integration-secret")
    monkeypatch.setattr(app_settings, "JWT_ISSUER", "laboria-backend")
    monkeypatch.setattr(app_settings, "JWT_AUDIENCE", "laboria-frontend")

    token = _valid_token(monkeypatch, issuer="laboria-backend", audience="laboria-frontend")
    client = TestClient(_make_app())
    response = client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code != 401


# ── token sin claims obligatorios → 401 ──────────────────────────────────────

def test_token_without_sub_returns_401(monkeypatch):
    monkeypatch.setattr(app_settings, "JWT_SECRET", "integration-secret")
    monkeypatch.setattr(app_settings, "JWT_ISSUER", None)
    monkeypatch.setattr(app_settings, "JWT_AUDIENCE", None)

    now = datetime.now(timezone.utc)
    token = _raw_token({"email": "x@x.com", "exp": _now_plus(), "iat": now})
    client = TestClient(_make_app())
    response = client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_without_exp_returns_401(monkeypatch):
    monkeypatch.setattr(app_settings, "JWT_SECRET", "integration-secret")
    monkeypatch.setattr(app_settings, "JWT_ISSUER", None)
    monkeypatch.setattr(app_settings, "JWT_AUDIENCE", None)

    now = datetime.now(timezone.utc)
    token = _raw_token({"sub": "user@x.com", "iat": now})
    client = TestClient(_make_app())
    response = client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_without_iat_returns_401(monkeypatch):
    monkeypatch.setattr(app_settings, "JWT_SECRET", "integration-secret")
    monkeypatch.setattr(app_settings, "JWT_ISSUER", None)
    monkeypatch.setattr(app_settings, "JWT_AUDIENCE", None)

    token = _raw_token({"sub": "user@x.com", "exp": _now_plus()})
    client = TestClient(_make_app())
    response = client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


# ── token con claims incorrectos → 401 ───────────────────────────────────────

def test_token_with_wrong_iss_returns_401(monkeypatch):
    monkeypatch.setattr(app_settings, "JWT_SECRET", "integration-secret")
    monkeypatch.setattr(app_settings, "JWT_ISSUER", "laboria-backend")
    monkeypatch.setattr(app_settings, "JWT_AUDIENCE", None)

    now = datetime.now(timezone.utc)
    token = _raw_token({
        "sub": "user@x.com", "iss": "other-app",
        "exp": _now_plus(), "iat": now,
    })
    client = TestClient(_make_app())
    response = client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_with_wrong_aud_returns_401(monkeypatch):
    monkeypatch.setattr(app_settings, "JWT_SECRET", "integration-secret")
    monkeypatch.setattr(app_settings, "JWT_ISSUER", None)
    monkeypatch.setattr(app_settings, "JWT_AUDIENCE", "laboria-frontend")

    now = datetime.now(timezone.utc)
    token = _raw_token({
        "sub": "user@x.com", "aud": "other-frontend",
        "exp": _now_plus(), "iat": now,
    })
    client = TestClient(_make_app())
    response = client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_with_invalid_signature_returns_401(monkeypatch):
    monkeypatch.setattr(app_settings, "JWT_SECRET", "integration-secret")
    monkeypatch.setattr(app_settings, "JWT_ISSUER", None)
    monkeypatch.setattr(app_settings, "JWT_AUDIENCE", None)

    now = datetime.now(timezone.utc)
    token = _raw_token(
        {"sub": "user@x.com", "exp": _now_plus(), "iat": now},
        secret="wrong-secret",
    )
    client = TestClient(_make_app())
    response = client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_no_token_returns_401(monkeypatch):
    monkeypatch.setattr(app_settings, "JWT_SECRET", "integration-secret")
    monkeypatch.setattr(app_settings, "JWT_ISSUER", None)
    monkeypatch.setattr(app_settings, "JWT_AUDIENCE", None)

    client = TestClient(_make_app())
    response = client.get("/api/roles")

    assert response.status_code == 401
