from sqlalchemy import Column, Integer, String, Text, Date, Numeric, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from core.database import Base


class EnglishLevel(enum.Enum):
    BASIC = "Basic"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    NATIVE = "Native"


class EmploymentType(enum.Enum):
    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    CONTRACT = "Contract"
    FREELANCE = "Freelance"
    INTERNSHIP = "Internship"


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    career = Column(String, nullable=True)
    university = Column(String, nullable=True)
    graduation_date = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    english_level = Column(Enum(EnglishLevel), nullable=True)
    preferred_location = Column(String, nullable=True)
    preferred_employment_type = Column(Enum(EmploymentType), nullable=True)
    salary_expectation = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="profile")  # 1-to-1
    experiences = relationship("Experience", back_populates="profile", cascade="all, delete-orphan")  # 1-to-many
    skills = relationship("Skill", back_populates="profile", cascade="all, delete-orphan")  # 1-to-many
