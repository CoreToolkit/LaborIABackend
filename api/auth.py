
import time
import os
import datetime as dt
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.oauth import oauth
from core.jwt import (
    create_token,
    create_refresh_token,
    decode_refresh_token,
    decode_token,
    get_current_user,
    security,
)
from core.database import get_db
from services.user_service import UserService
from core.microsoft import (
    exchange_code_for_tokens,
    fetch_user_from_graph,
    user_from_id_token,
)
from services import token_blacklist_service

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.get("/google")
async def login_google(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    authorization_url = await oauth.google.create_authorization_url(redirect_uri=redirect_uri)
    return {
        "url": authorization_url["url"],
        "state": authorization_url["state"]
    }


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        state = request.query_params.get("state")
        if state:
            redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
            request.session[f"_state_google_{state}"] = {
                "data": {"redirect_uri": redirect_uri},
                "exp": time.time() + 300
            }

        token = await oauth.google.authorize_access_token(request)
        resp = await oauth.google.userinfo(token=token)

        db_user = UserService(db).get_or_create_user(
            email=resp["email"],
            name=resp["name"],
            profile_picture=resp.get("picture"),
            oauth_provider="google",
        )

        access_token = create_token({
            "id": db_user.id,
            "email": db_user.email,
            "name": db_user.name,
            "picture": db_user.profile_picture,
        })

        return {
            "message": "Login successful",
            "access_token": access_token,
            "token_type": "bearer"
        }
    except Exception as e:
        return {
            "message": "Login failed",
            "error": str(e)
        }


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials

    try:
        payload = decode_token(token)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    jti = payload.get("jti")
    exp_ts = payload.get("exp")
    expires_at = dt.datetime.fromtimestamp(exp_ts, dt.timezone.utc) if exp_ts else dt.datetime.utcnow()

    token_blacklist_service.add_to_blacklist(
        db=db,
        token_jti=jti,
        expires_at=expires_at,
    )

    return {"message": "Logout successful"}


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user


@router.post("/refresh")
async def refresh_token(refresh_token: str = Query(None, description="Application refresh token")):
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Missing refresh token")

    data = decode_refresh_token(refresh_token)
    user_email = data.get("email")
    user_name = data.get("name")

    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access = create_token({"email": user_email, "name": user_name})
    new_refresh = create_refresh_token({"email": user_email, "name": user_name})

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }

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
    db: Session = Depends(get_db),
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

    tokens = exchange_code_for_tokens(
        code=code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        tenant_id=tenant_id,
    )

    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")

    if not access_token:
        raise HTTPException(status_code=401, detail="Microsoft response missing access token.")

    user = user_from_id_token(id_token) if id_token else None
    if not user:
        user = fetch_user_from_graph(access_token)

    if not user or not user.get("email"):
        raise HTTPException(status_code=500, detail="Unable to extract Microsoft user profile.")

    db_user = UserService(db).get_or_create_user(
        email=user["email"],
        name=user.get("name") or "",
        profile_picture=None,
        oauth_provider="microsoft",
    )

    app_token = create_token(
        {
            "id": db_user.id,
            "email": db_user.email,
            "name": db_user.name,
            "picture": db_user.profile_picture,
        }
    )

    return {
        "message": "Login successful",
        "access_token": app_token,
        "token_type": "bearer",
    }
