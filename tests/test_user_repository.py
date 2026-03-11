from dotenv import load_dotenv
from core.database import SessionLocal, Base, engine
from repositories.user_repository import UserRepository


def test_user_repository_create_and_get():
    load_dotenv()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    repo = UserRepository(db)

    user = repo.create("repo@example.com", "Repo User", None, "google")
    fetched = repo.get_by_email("repo@example.com")
    assert fetched.id == user.id
    db.close()
