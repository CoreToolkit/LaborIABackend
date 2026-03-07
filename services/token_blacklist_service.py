import datetime as dt
from sqlalchemy.orm import Session

from models.token_blacklist import TokenBlacklist


def add_to_blacklist(db: Session, token_jti: str, expires_at: dt.datetime) -> None:
    db.add(
        TokenBlacklist(
            token_jti=token_jti,
            expires_at=expires_at,
        )
    )
    db.commit()


def is_token_blacklisted(db: Session, token_jti: str) -> bool:
    now = dt.datetime.utcnow()
    entry = (
        db.query(TokenBlacklist)
        .filter(TokenBlacklist.token_jti == token_jti, TokenBlacklist.expires_at > now)
        .first()
    )
    return entry is not None
