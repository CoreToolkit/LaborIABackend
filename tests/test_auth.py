import base64
import json
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class DummyResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _make_id_token(payload: dict) -> str:
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    header = _b64(b"{}")
    body = _b64(json.dumps(payload).encode())
    return f"{header}.{body}.signature"


def test_auth():
    response = client.get("/auth/google")
    assert response.status_code == 200
    assert response.json() == {"url": "https://accounts.google.com/..."}


def test_microsoft_auth(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/microsoft/callback")
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
    assert query.get("redirect_uri") == ["http://localhost:8000/auth/microsoft/callback"]


def test_microsoft_auth_missing_required_env(monkeypatch):
    monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
    monkeypatch.delenv("MICROSOFT_REDIRECT_URI", raising=False)

    response = client.get("/auth/microsoft")

    assert response.status_code == 500
    assert response.json()["detail"].startswith("Missing MICROSOFT_CLIENT_ID or MICROSOFT_REDIRECT_URI")


def test_microsoft_auth_defaults_common_tenant(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/microsoft/callback")
    monkeypatch.delenv("MICROSOFT_TENANT_ID", raising=False)

    response = client.get("/auth/microsoft")

    parsed = urlparse(response.json()["url"])

    assert parsed.path.startswith("/common/oauth2/v2.0/authorize")


def test_microsoft_callback_missing_code():
    response = client.get("/auth/microsoft/callback")
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Missing authorization code")


def test_microsoft_callback_success_with_id_token(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/microsoft/callback")
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "organizations")

    id_token = _make_id_token({"email": "user@example.com", "name": "Example User"})

    def fake_post(url, data=None, headers=None, timeout=None):
        return DummyResponse(200, {"access_token": "access", "id_token": id_token})

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.get("/auth/microsoft/callback", params={"code": "abc123"})

    assert response.status_code == 200
    data = response.json()
    assert data["user"] == {"email": "user@example.com", "name": "Example User"}
    assert data["token"].startswith("PENDING_APP_JWT::user@example.com")


def test_microsoft_callback_fallback_graph(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/microsoft/callback")

    def fake_post(url, data=None, headers=None, timeout=None):
        return DummyResponse(200, {"access_token": "access-token"})

    def fake_get(url, headers=None, timeout=None):
        assert headers["Authorization"] == "Bearer access-token"
        return DummyResponse(200, {"mail": "graph@example.com", "displayName": "Graph User"})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)

    response = client.get("/auth/microsoft/callback", params={"code": "abc123"})

    assert response.status_code == 200
    data = response.json()
    assert data["user"] == {"email": "graph@example.com", "name": "Graph User"}


def test_microsoft_callback_token_exchange_failure(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/microsoft/callback")

    def fake_post(url, data=None, headers=None, timeout=None):
        return DummyResponse(400, {"error": "invalid_grant"})

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.get("/auth/microsoft/callback", params={"code": "abc123"})

    assert response.status_code == 401
    assert "token exchange" in response.json()["detail"]


def test_microsoft_callback_missing_access_token(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/microsoft/callback")

    def fake_post(url, data=None, headers=None, timeout=None):
        return DummyResponse(200, {"id_token": "header.payload.sig"})

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.get("/auth/microsoft/callback", params={"code": "abc123"})

    assert response.status_code == 401
    assert "missing access token" in response.json()["detail"].lower()
