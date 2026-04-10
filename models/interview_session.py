from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationship many-to-1
    user = relationship("User", back_populates="interview_sessions")
    questions = relationship("Question", back_populates="interview_session", cascade="all, delete-orphan")  # 1-to-many
    evaluations = relationship("Evaluation", back_populates="interview_session", cascade="all, delete-orphan")
