import base64
import json
import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from core.oauth import oauth


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.get("/google")
def google_login():
    return {"url": "https://accounts.google.com/..."}

@router.get("/google/callback")
def google_callback():
    return {"url": "https://accounts.google.com/..."}

def _decode_segment(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _user_from_id_token(id_token: str):
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            return None
        payload = json.loads(_decode_segment(parts[1]).decode("utf-8"))
        email = payload.get("email") or payload.get("preferred_username")
        name = payload.get("name") or payload.get("given_name")
        return {"email": email, "name": name}
    except Exception:
        return None


def _fetch_user_from_graph(access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=10)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to reach Microsoft Graph.") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Failed to fetch Microsoft user profile.")
    data = resp.json()
    return {"email": data.get("mail") or data.get("userPrincipalName"), "name": data.get("displayName")}


def _exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str, tenant_id: str):
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        resp = httpx.post(token_url, data=data, headers=headers, timeout=10)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to reach Microsoft token endpoint.") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Microsoft token exchange failed.")
    return resp.json()

@router.get(
    "/microsoft",
    summary="Iniciar login con Microsoft",
    description=(
        "Inicia el flujo OAuth2/OIDC con Microsoft Entra ID. "
        "Microsoft redirigirá con un `code` al redirect URI configurado."
    ),
)
def microsoft_login():
    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI")
    tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")

    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=500,
            detail="Missing MICROSOFT_CLIENT_ID or MICROSOFT_REDIRECT_URI environment variables.",
        )

    base_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": "openid profile email",
        "prompt": "select_account",
    }

    authorize_url = f"{base_url}?{urlencode(params)}"
    return {"url": authorize_url}

@router.get("/microsoft/callback")
def microsoft_callback(
    code: str | None = Query(None, description="Authorization code returned by Microsoft."),
    state: str | None = Query(None, description="Opaque state for CSRF protection."),
):
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code from Microsoft.")

    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
    redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI")
    tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")

    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(
            status_code=500,
            detail="Missing Microsoft OAuth environment variables.",
        )

    tokens = _exchange_code(code, client_id, client_secret, redirect_uri, tenant_id)

    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")

    if not access_token:
        raise HTTPException(status_code=401, detail="Microsoft response missing access token.")

    user = _user_from_id_token(id_token) if id_token else None
    if not user:
        user = _fetch_user_from_graph(access_token)

    if not user or not user.get("email"):
        raise HTTPException(status_code=500, detail="Unable to extract Microsoft user profile.")

    # Placeholder mientras JWT
    app_token = f"PENDING_APP_JWT::{user['email']}"

    return {"user": user, "token": app_token, "state": state}
