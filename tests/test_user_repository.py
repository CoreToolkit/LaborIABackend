import os
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["JWT_SECRET"] = "test-secret"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from repositories.user_repository import UserRepository


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


def test_user_repository_create_and_get():
    db = TestSessionLocal()
    try:
        repo = UserRepository(db)

        user = repo.create("repo@example.com", "Repo User", None, "google")
        fetched = repo.get_by_email("repo@example.com")

        assert fetched is not None
        assert fetched.id == user.id
    finally:
        db.close()
