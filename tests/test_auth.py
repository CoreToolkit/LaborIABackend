from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

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
