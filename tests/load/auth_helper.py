"""
Generación de JWT tokens para usuarios de prueba.
Replica exactamente la lógica de core/jwt.py: create_token().
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt as pyjwt

from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS


def generate_token(user: dict) -> str:
    """
    Genera un JWT válido para un usuario de prueba.
    Misma estructura que create_token() del backend.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "picture": None,
        "jti": str(uuid4()),
        "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": now,
        "sub": user["email"],
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def auth_headers(user: dict) -> dict:
    return {"Authorization": f"Bearer {generate_token(user)}"}
