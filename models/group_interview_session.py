from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base
from models.job_role import GUID


class GroupInterviewSession(Base):
    __tablename__ = "group_interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_code = Column(String, nullable=False, unique=True, index=True)
    host_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role_id = Column(GUID(), ForeignKey("job_roles.id"), nullable=False, index=True)
    difficulty = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    host = relationship("User", back_populates="group_interview_sessions_hosted")
    role = relationship("JobRole", back_populates="group_interview_sessions")
    interview_sessions = relationship("InterviewSession", back_populates="group_interview_session")
