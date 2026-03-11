import base64
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from main import app
import api.auth as auth_module
from core import jwt as core_jwt

client = TestClient(app)


def _make_id_token(payload: dict) -> str:
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    header = _b64(b"{}")
    body = _b64(json.dumps(payload).encode())
    return f"{header}.{body}.signature"


def test_microsoft_auth(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:3000/auth/callback")
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "organizations")

    response = client.get("/auth/microsoft")

    assert response.status_code == 200
    data = response.json()
    assert "url" in data

    parsed = urlparse(data["url"])
    query = parse_qs(parsed.query)

    assert "login.microsoftonline.com" in parsed.netloc
    assert parsed.path.startswith("/organizations/oauth2/v2.0/authorize")
    assert query.get("client_id") == ["test-client-id"]
    assert query.get("redirect_uri") == ["http://localhost:3000/auth/callback"]


def test_microsoft_auth_missing_required_env(monkeypatch):
    monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
    monkeypatch.delenv("MICROSOFT_REDIRECT_URI", raising=False)

    response = client.get("/auth/microsoft")

    assert response.status_code == 500
    assert response.json()["detail"].startswith("Missing MICROSOFT_CLIENT_ID or MICROSOFT_REDIRECT_URI")


def test_microsoft_auth_defaults_common_tenant(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:3000/auth/callback")
    monkeypatch.delenv("MICROSOFT_TENANT_ID", raising=False)

    response = client.get("/auth/microsoft")

    parsed = urlparse(response.json()["url"])

    assert parsed.path.startswith("/common/oauth2/v2.0/authorize")


def test_microsoft_exchange_success(monkeypatch):
    def override_db():
        yield None
    app.dependency_overrides[auth_module.get_db] = override_db

    class DummyUser:
        id = 1
        email = "user@example.com"
        name = "Example User"
        profile_picture = None

    class DummyService:
        def __init__(self, db):
            pass

        def get_or_create_user(self, **kwargs):
            return DummyUser()

    monkeypatch.setattr(auth_module, "UserService", DummyService)
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:3000/auth/callback")
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "organizations")
    monkeypatch.setenv("JWT_SECRET", "secret")

    id_token = _make_id_token({"email": "user@example.com", "name": "Example User"})

    def fake_post(url, data=None, headers=None, timeout=None):
        return DummyResponse(200, {"access_token": "access", "id_token": id_token})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(auth_module, "create_token", lambda payload: "test-jti-jwt")
    monkeypatch.setattr(auth_module, "fetch_user_from_graph", lambda access_token: {"email": "user@example.com", "name": "Example User"})

    response = client.get("/auth/microsoft/callback", params={"code": "abc123"})
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "test-jti-jwt"
    assert data["token_type"] == "bearer"


class DummyResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_microsoft_exchange_missing_code(monkeypatch):
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:3000/auth/callback")
    response = client.post("/auth/microsoft/exchange", json={})
    assert response.status_code == 400
    assert "authorization code" in response.json()["detail"].lower()


def test_me_without_token_returns_401():
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] in ("Authorization header missing or malformed", "Unauthorized")


#def test_logout_preflight_allowed_without_token():
    #resp = client.options(
    #    "/auth/logout",
    #    headers={
    #        "Origin": "http://localhost:3000",
    #        "Access-Control-Request-Method": "POST",
    #        "Access-Control-Request-Headers": "authorization",
    #    },
    #)
    #assert resp.status_code in (200, 204)


def test_logout_requires_token_on_post():
    resp = client.post("/auth/logout")
    assert resp.status_code == 401
