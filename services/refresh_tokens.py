import datetime as dt
import os
import secrets
from sqlalchemy.orm import Session

from models.refresh_token import RefreshToken, hash_token


REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 14))


def _utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


def create_refresh_token(db: Session | None, user_id: str) -> str:
    plain_token = secrets.token_urlsafe(64)
    expires_at = _utcnow() + dt.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    token_hash = hash_token(plain_token)

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


def cleanup_expired_refresh_tokens(db: Session) -> int:
    deleted = (
        db.query(RefreshToken)
        .filter(RefreshToken.expires_at <= _utcnow())
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def store_refresh_token(db: Session, user_id: str, token: str, expires_at: dt.datetime):
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
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if record:
        record.revoked_at = _utcnow()
        db.commit()


def get_refresh_token(db: Session, token: str) -> RefreshToken | None:
    token_hash = hash_token(token)
    return db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()


def get_valid_refresh_token(db: Session, token: str) -> RefreshToken | None:
    token_hash = hash_token(token)
    now = _utcnow()
    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.expires_at > now,
            RefreshToken.revoked_at.is_(None),
        )
        .first()
    )


def rotate_refresh_token(db: Session, record: RefreshToken) -> str:
    record.revoked_at = _utcnow()
    new_plain_token = secrets.token_urlsafe(64)
    db.add(
        RefreshToken(
            user_id=record.user_id,
            token_hash=hash_token(new_plain_token),
            expires_at=_utcnow() + dt.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    return new_plain_token


def is_refresh_token_valid(db: Session, token: str) -> bool:
    return get_valid_refresh_token(db, token) is not None
