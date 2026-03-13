from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()
    
    def change_last_login(self, user: User):
        user.last_login = func.now()
        self.db.commit()

    def create(self, email: str, name: str, profile_picture: str | None, oauth_provider: str) -> User:
        
        user = User(
            email=email,
            name=name,
            profile_picture=profile_picture,
            oauth_provider=oauth_provider,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
