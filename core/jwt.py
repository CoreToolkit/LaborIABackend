import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidAudienceError, InvalidIssuerError, InvalidTokenError, MissingRequiredClaimError

from core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
REFRESH_TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer()

_ALLOWED_ALGORITHMS = {"HS256"}


def _get_issuer() -> str | None:
    return settings.JWT_ISSUER


def _get_audience() -> str | None:
    return settings.JWT_AUDIENCE


def create_token(data: dict) -> str:
    """
    Crea un access token JWT con claims obligatorios:
    iss, aud, sub, exp, iat, jti.
    """
    payload = data.copy()
    now = datetime.now(timezone.utc)

    payload["jti"] = str(uuid.uuid4())
    payload["exp"] = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload["iat"] = now

    issuer = _get_issuer()
    if issuer:
        payload["iss"] = issuer

    audience = _get_audience()
    if audience:
        payload["aud"] = audience

    if "sub" not in payload:
        sub = data.get("email") or str(data.get("id", ""))
        if sub:
            payload["sub"] = sub

    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    payload = data.copy()
    now = datetime.now(timezone.utc)
    payload["type"] = "refresh"
    payload["exp"] = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload["iat"] = now

    issuer = _get_issuer()
    if issuer:
        payload["iss"] = issuer

    audience = _get_audience()
    if audience:
        payload["aud"] = audience

    if "sub" not in payload:
        sub = data.get("email") or str(data.get("id", ""))
        if sub:
            payload["sub"] = sub

    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decodifica y valida un JWT.
    Rechaza con HTTP 401 si firma inválida, algoritmo no permitido,
    token expirado, iss/aud incorrectos, sub ausente, o iat ausente.
    """
    secret = settings.JWT_SECRET
    issuer = _get_issuer()
    audience = _get_audience()

    decode_kwargs: dict = {
        "algorithms": list(_ALLOWED_ALGORITHMS),
        "options": {"require": ["exp", "iat", "sub"]},
    }
    if issuer:
        decode_kwargs["issuer"] = issuer
    if audience:
        decode_kwargs["audience"] = audience

    try:
        header = pyjwt.get_unverified_header(token)
        if header.get("alg") not in _ALLOWED_ALGORITHMS:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        payload = pyjwt.decode(token, secret, **decode_kwargs)

        sub = payload.get("sub")
        if not sub or not str(sub).strip():
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        return payload

    except HTTPException:
        raise
    except (InvalidIssuerError, InvalidAudienceError, MissingRequiredClaimError):
        raise HTTPException(status_code=401, detail="Invalid token claims")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def decode_refresh_token(token: str) -> dict:
    data = decode_token(token)
    if data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return data


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    return decode_token(credentials.credentials)
