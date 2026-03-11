import pytest
from starlette.requests import Request
from services.token_service import extract_bearer_token


def _make_request(headers: dict) -> Request:
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    return Request(scope, receive=lambda: None)


def test_extract_bearer_token_success():
    req = _make_request({"authorization": "Bearer abc"})
    assert extract_bearer_token(req) == "abc"


@pytest.mark.parametrize("header", [None, "", "Token abc", "Bearer "])
def test_extract_bearer_token_errors(header):
    headers = {}
    if header is not None:
        headers["authorization"] = header
    req = _make_request(headers)
    with pytest.raises(Exception):
        extract_bearer_token(req)
