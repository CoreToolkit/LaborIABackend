from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base
from models.job_role import GUID


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_match_results_user_role"),
        CheckConstraint("total_score >= 0 AND total_score <= 100", name="ck_match_results_total_score_range"),
        Index("ix_match_results_user_id_total_score", "user_id", "total_score"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role_id = Column(GUID(), ForeignKey("job_roles.id"), nullable=False, index=True)
    total_score = Column(Numeric(5, 2), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    user = relationship("User", back_populates="match_results")
    job_role = relationship("JobRole", back_populates="match_results")
