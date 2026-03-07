from fastapi import HTTPException, Request, status

from core import jwt as jwt_core


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
    # TODO: Integrar blacklist de tokens revocados
    return jwt_core.decode_token(token)
