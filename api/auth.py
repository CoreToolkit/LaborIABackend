
import datetime as dt
import time
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Body, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.config import settings
from core.oauth import oauth
from core.jwt import (
    create_token,
    decode_token,
    get_current_user,
    security,
)
from core.database import get_db
from core.limiter import AUTH_RATE_LIMIT, auth_rate_limiter
from repositories.user_repository import UserRepository
from services.user_service import UserService
from services import token_blacklist_service
from services import refresh_tokens as refresh_tokens_service
from core.microsoft import (
    exchange_code_for_tokens,
    fetch_user_from_graph,
    user_from_id_token,
)


async def _process_microsoft_code(code: str | None, state: str | None, db: Session):
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code from Microsoft.")

    client_id = settings.MICROSOFT_CLIENT_ID
    client_secret = settings.MICROSOFT_CLIENT_SECRET
    redirect_uri = settings.MICROSOFT_REDIRECT_URI
    tenant_id = settings.MICROSOFT_TENANT_ID

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
    refresh_token = refresh_tokens_service.create_refresh_token(db, user_id=db_user.email)

    return {
        "message": "Login successful",
        "access_token": app_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.get("/google")
async def login_google(request: Request):
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    authorization_url = await oauth.google.create_authorization_url(redirect_uri=redirect_uri)
    return {
        "url": authorization_url["url"],
        "state": authorization_url["state"]
    }


@router.post("/google/exchange")
@auth_rate_limiter.limit(AUTH_RATE_LIMIT)
async def google_exchange(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        code = data.get("code")
        state = data.get("state")

        redirect_uri = settings.GOOGLE_REDIRECT_URI
        token = await oauth.google.fetch_access_token(
            code=code,
            redirect_uri=redirect_uri
        )

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
        refresh_token = refresh_tokens_service.create_refresh_token(db, user_id=db_user.email)

        return {
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except Exception as e:
        return {
            "message": "Login failed",
            "error": str(e)
        }



@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        state = request.query_params.get("state")
        if state:
            redirect_uri = settings.GOOGLE_REDIRECT_URI
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
        refresh_token = refresh_tokens_service.create_refresh_token(db, user_id=db_user.email)

        return {
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
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
@auth_rate_limiter.limit(AUTH_RATE_LIMIT)
async def refresh_token(
    request: Request,
    refresh_token: str = Body(None, embed=True, description="Application refresh token"),
    db: Session = Depends(get_db),
):
    refresh_tokens_service.cleanup_expired_refresh_tokens(db)

    if not refresh_token:
        raise HTTPException(status_code=400, detail="Missing refresh token")

    record = refresh_tokens_service.get_refresh_token(db, refresh_token)
    if not record:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    if record.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Token has been revoked")
    if record.expires_at < dt.datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = UserRepository(db).get_by_email(record.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found for refresh token")

    new_refresh = refresh_tokens_service.rotate_refresh_token(db, record)
    new_access = create_token(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.profile_picture,
        }
    )

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
    client_id = settings.MICROSOFT_CLIENT_ID
    redirect_uri = settings.MICROSOFT_REDIRECT_URI
    tenant_id = settings.MICROSOFT_TENANT_ID

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


@router.post("/microsoft/exchange")
@auth_rate_limiter.limit(AUTH_RATE_LIMIT)
async def microsoft_exchange(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    code = data.get("code")
    state = data.get("state")
    return await _process_microsoft_code(code=code, state=state, db=db)


@router.get("/microsoft/callback")
async def microsoft_callback(
    code: str | None = Query(None, description="Authorization code returned by Microsoft."),
    state: str | None = Query(None, description="Opaque state for CSRF protection."),
    db: Session = Depends(get_db),
):
    return await _process_microsoft_code(code=code, state=state, db=db)
