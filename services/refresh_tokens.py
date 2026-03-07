import datetime as dt
from sqlalchemy.orm import Session

from models.refresh_token import RefreshToken, hash_token


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
    db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).delete()
    db.commit()


def is_refresh_token_valid(db: Session, token: str) -> bool:
    token_hash = hash_token(token)
    now = dt.datetime.utcnow()
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.expires_at > now)
        .first()
    )
    return record is not None
