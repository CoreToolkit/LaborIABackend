import uuid

import pytest

pytest.importorskip("sqlalchemy")

from core.database import Base, engine, SessionLocal
from models.user import User


Base.metadata.create_all(bind=engine)


def test_user_persist_and_defaults():
    db = SessionLocal()
    try:
        unique_email = f"model-{uuid.uuid4().hex}@example.com"
        user = User(
            email=unique_email,
            name="Model User",
            profile_picture=None,
            oauth_provider="google",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.created_at is not None
        assert user.last_login is not None
    finally:
        db.close()
