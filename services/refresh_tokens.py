import datetime as dt
import os
import secrets
from sqlalchemy.orm import Session

from models.refresh_token import RefreshToken, hash_token


REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 14))


def _utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


def create_refresh_token(db: Session | None, user_id: str) -> str:
    """
    Genera un refresh token aleatorio, lo almacena hasheado y devuelve la
    versión en texto plano para el cliente.
    """
    plain_token = secrets.token_urlsafe(64)
    expires_at = _utcnow() + dt.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    token_hash = hash_token(plain_token)

    # En tests algunos endpoints inyectan db=None; en ese caso solo devolvemos el token.
    if db is not None:
        db.add(
            RefreshToken(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        db.commit()

    return plain_token


def store_refresh_token(db: Session, user_id: str, token: str, expires_at: dt.datetime):
    """
    Compatibilidad: permite guardar un token ya generado (hash + expiración).
    """
    token_hash = hash_token(token)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    db.commit()


def revoke_refresh_token(db: Session, token: str):
    token_hash = hash_token(token)
    db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).delete()
    db.commit()


def get_valid_refresh_token(db: Session, token: str) -> RefreshToken | None:
    token_hash = hash_token(token)
    now = _utcnow()
    return (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.expires_at > now)
        .first()
    )


def is_refresh_token_valid(db: Session, token: str) -> bool:
    return get_valid_refresh_token(db, token) is not None
