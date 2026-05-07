import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_limiter():
    from core.limiter import auth_rate_limiter
    auth_rate_limiter.reset()
    yield


def _headers(ip: str) -> dict:
    return {"X-Forwarded-For": ip}


# ---------------------------------------------------------------------------
# TASK-031-02: Rate limiting 10 req/min por IP en endpoints de auth
# ---------------------------------------------------------------------------

def test_rate_limit_refresh_blocks_at_11(client):
    ip = "10.0.1.1"
    payload = {"refresh_token": "invalid-token"}

    for i in range(10):
        resp = client.post("/auth/refresh", json=payload, headers=_headers(ip))
        assert resp.status_code != 429, f"Request {i + 1} no debe ser bloqueada aún"

    resp = client.post("/auth/refresh", json=payload, headers=_headers(ip))
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.headers["Retry-After"] == "60"


def test_rate_limit_google_exchange_blocks_at_11(client):
    ip = "10.0.1.2"
    payload = {"code": "fake-code", "state": "fake-state"}

    for i in range(10):
        resp = client.post("/auth/google/exchange", json=payload, headers=_headers(ip))
        assert resp.status_code != 429, f"Request {i + 1} no debe ser bloqueada aún"

    resp = client.post("/auth/google/exchange", json=payload, headers=_headers(ip))
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.headers["Retry-After"] == "60"


def test_rate_limit_microsoft_exchange_blocks_at_11(client):
    ip = "10.0.1.3"
    payload = {"code": "fake-code", "state": "fake-state"}

    for i in range(10):
        resp = client.post("/auth/microsoft/exchange", json=payload, headers=_headers(ip))
        assert resp.status_code != 429, f"Request {i + 1} no debe ser bloqueada aún"

    resp = client.post("/auth/microsoft/exchange", json=payload, headers=_headers(ip))
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.headers["Retry-After"] == "60"


def test_different_ips_are_independent(client):
    """Dos IPs distintas tienen contadores independientes."""
    payload = {"refresh_token": "invalid-token"}

    for _ in range(11):
        client.post("/auth/refresh", json=payload, headers=_headers("10.0.2.1"))

    resp = client.post("/auth/refresh", json=payload, headers=_headers("10.0.2.2"))
    assert resp.status_code != 429


def test_non_auth_endpoint_not_rate_limited(client):
    """/auth/me no tiene rate limiting — siempre devuelve 401, nunca 429."""
    ip = "10.0.3.1"
    for _ in range(15):
        resp = client.get("/auth/me", headers=_headers(ip))
        assert resp.status_code == 401
        assert resp.status_code != 429
