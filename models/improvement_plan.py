from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class ImprovementPlan(Base):
    __tablename__ = "improvement_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    last_evaluation_count = Column(Integer, nullable=False, default=0)
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("ImprovementPlanItem", back_populates="plan", cascade="all, delete-orphan")
    user = relationship("User", back_populates="improvement_plan")


class ImprovementPlanItem(Base):
    __tablename__ = "improvement_plan_items"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("improvement_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    skill = Column(String, nullable=False)
    priority = Column(String, nullable=False, default="medium")
    current_score = Column(Float, nullable=True)
    target_score = Column(Float, nullable=False, default=70.0)
    status = Column(String, nullable=False, default="pending")
    resources = Column(JSON, nullable=True)
    ai_feedback = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    plan = relationship("ImprovementPlan", back_populates="items")


class ImprovementPlanHistory(Base):
    __tablename__ = "improvement_plan_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    trigger = Column(String, nullable=False)
    snapshot = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="improvement_plan_history")
