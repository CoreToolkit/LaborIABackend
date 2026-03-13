from sqlalchemy.orm import Session
from models.profile import Profile


class ProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: int) -> Profile | None:
        return self.db.query(Profile).filter(Profile.user_id == user_id).first()

    def get_by_id(self, profile_id: int) -> Profile | None:
        return self.db.query(Profile).filter(Profile.id == profile_id).first()

    def create(self, profile_data: dict) -> Profile:
        profile = Profile(**profile_data)
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def update(self, profile: Profile, update_data: dict) -> Profile:
        for key, value in update_data.items():
            if value is not None:
                setattr(profile, key, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def delete(self, profile: Profile) -> None:
        self.db.delete(profile)
        self.db.commit()
