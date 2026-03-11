import pytest
import httpx
import base64

from core import microsoft


def test_user_from_id_token_parses_email_and_name():
    payload = base64.urlsafe_b64encode(b'{"email":"user@example.com","name":"Name"}').decode().rstrip("=")
    token = f"x.{payload}.y"
    user = microsoft.user_from_id_token(token)
    assert user["email"] == "user@example.com"
    assert user["name"] == "Name"


class DummyResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_fetch_user_from_graph_success(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        return DummyResponse(200, {"mail": "graph@example.com", "displayName": "Graph User"})

    monkeypatch.setattr(httpx, "get", fake_get)
    user = microsoft.fetch_user_from_graph("token")
    assert user["email"] == "graph@example.com"
    assert user["name"] == "Graph User"


def test_fetch_user_from_graph_failure(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        return DummyResponse(401, {"error": "unauthorized"})

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(Exception):
        microsoft.fetch_user_from_graph("token")


def test_exchange_code_for_tokens_success(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None):
        assert data["code"] == "abc"
        return DummyResponse(200, {"access_token": "at", "id_token": "id"})

    monkeypatch.setattr(httpx, "post", fake_post)
    tokens = microsoft.exchange_code_for_tokens(
        code="abc",
        client_id="cid",
        client_secret="secret",
        redirect_uri="http://localhost",
        tenant_id="common",
    )
    assert tokens["access_token"] == "at"


def test_exchange_code_for_tokens_failure(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None):
        return DummyResponse(400, {"error": "invalid"})

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(Exception):
        microsoft.exchange_code_for_tokens(
            code="abc",
            client_id="cid",
            client_secret="secret",
            redirect_uri="http://localhost",
            tenant_id="common",
        )
