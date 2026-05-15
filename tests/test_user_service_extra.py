from dotenv import load_dotenv
from core.database import SessionLocal, Base, engine
from services.user_service import UserService
from models.user import User


def test_user_service_get_or_create_creates_once():
    load_dotenv()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    service = UserService(db)

    user = service.get_or_create_user("new@example.com", "New", None, "google")
    user2 = service.get_or_create_user("new@example.com", "New", None, "google")

    assert user.id == user2.id
    db.close()
