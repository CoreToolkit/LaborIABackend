from sqlalchemy.orm import Session
from models.experience import Experience
from models.profile import Profile
from models.skill import Skill


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

    def list_experiences_by_profile_id(self, profile_id: int) -> list[Experience]:
        return (
            self.db.query(Experience)
            .filter(Experience.profile_id == profile_id)
            .order_by(Experience.id.asc())
            .all()
        )

    def get_experience_by_id_and_profile_id(self, experience_id: int, profile_id: int) -> Experience | None:
        return (
            self.db.query(Experience)
            .filter(Experience.id == experience_id, Experience.profile_id == profile_id)
            .first()
        )

    def create_experience(self, experience_data: dict) -> Experience:
        experience = Experience(**experience_data)
        self.db.add(experience)
        self.db.commit()
        self.db.refresh(experience)
        return experience

    def update_experience(self, experience: Experience, update_data: dict) -> Experience:
        for key, value in update_data.items():
            setattr(experience, key, value)
        self.db.commit()
        self.db.refresh(experience)
        return experience

    def delete_experience(self, experience: Experience) -> None:
        self.db.delete(experience)
        self.db.commit()

    def list_skills_by_profile_id(self, profile_id: int) -> list[Skill]:
        return (
            self.db.query(Skill)
            .filter(Skill.profile_id == profile_id)
            .order_by(Skill.id.asc())
            .all()
        )

    def get_skill_by_id_and_profile_id(self, skill_id: int, profile_id: int) -> Skill | None:
        return (
            self.db.query(Skill)
            .filter(Skill.id == skill_id, Skill.profile_id == profile_id)
            .first()
        )

    def create_skill(self, skill_data: dict) -> Skill:
        skill = Skill(**skill_data)
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def update_skill(self, skill: Skill, update_data: dict) -> Skill:
        for key, value in update_data.items():
            setattr(skill, key, value)
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def delete_skill(self, skill: Skill) -> None:
        self.db.delete(skill)
        self.db.commit()
