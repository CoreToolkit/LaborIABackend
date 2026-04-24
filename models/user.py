from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    profile_picture = Column(String, nullable=True)
    oauth_provider = Column(String, nullable=False)         
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationship 1-1
    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    interview_sessions = relationship("InterviewSession", back_populates="user")
    group_interview_sessions_hosted = relationship("GroupInterviewSession", back_populates="host")
    match_results = relationship("MatchResult", back_populates="user")
    user_metrics = relationship("UserMetrics", back_populates="user", uselist=False, cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan")
    user_badges = relationship("UserBadge", back_populates="user", cascade="all, delete-orphan")
