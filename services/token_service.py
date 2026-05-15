from fastapi import HTTPException, Request, status

from core import jwt as jwt_core
from core.database import SessionLocal
from services import token_blacklist_service


def extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or malformed",
        )
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is empty",
        )
    return token


def validate_jwt_token(token: str) -> dict:
    payload = jwt_core.decode_token(token)

    db = SessionLocal()
    try:
        try:
            is_revoked = token_blacklist_service.is_token_blacklisted(db, payload.get("jti"))
        except Exception:
            is_revoked = False  # Si falla la BD, no bloqueamos pero registramos en futuro

        if is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )
    finally:
        db.close()

    return payload
