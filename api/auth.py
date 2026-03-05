import os
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException

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
def microsoft_callback():
    return {"url": "https://accounts.microsoft.com/..."}
