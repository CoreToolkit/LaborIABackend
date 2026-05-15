import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base
from models.job_role import GUID


class GroupInterviewRoundStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    SKIPPED = "skipped"


class GroupInterviewRound(Base):
    __tablename__ = "group_interview_rounds"
    __table_args__ = (
        UniqueConstraint(
            "group_interview_session_id",
            "round_index",
            name="uq_group_interview_rounds_session_round_index",
        ),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    group_interview_session_id = Column(
        Integer,
        ForeignKey("group_interview_sessions.id"),
        nullable=False,
        index=True,
    )
    round_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=True)
    target_skill = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)
    status = Column(
        SAEnum(GroupInterviewRoundStatus, name="groupinterviewroundstatus"),
        nullable=False,
        default=GroupInterviewRoundStatus.ACTIVE,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    metadata_json = Column(JSON, nullable=True)

    group_interview_session = relationship("GroupInterviewSession", backref="rounds")
    creator = relationship("User", foreign_keys=[created_by])
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])