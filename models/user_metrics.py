from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class UserMetrics(Base):
    __tablename__ = "user_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    total_interviews = Column(Integer, nullable=False, default=0)
    avg_score = Column(Numeric(5, 2), nullable=True)
    score_by_skill = Column(JSON, nullable=True)
    score_by_category = Column(JSON, nullable=True)
    employability_score = Column(Numeric(5, 2), nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="user_metrics")
