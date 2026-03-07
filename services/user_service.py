from sqlalchemy.orm import Session
from models.user import User
from repositories.user_repository import UserRepository


class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def get_or_create_user(self, email: str, name: str, profile_picture: str | None, oauth_provider: str) -> User:
        
        user = self.repo.get_by_email(email)
        if not user:
            user = self.repo.create(email, name, profile_picture, oauth_provider)
        return user
