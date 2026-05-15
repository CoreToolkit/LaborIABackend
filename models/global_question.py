from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from core.database import Base


class GlobalQuestion(Base):
    __tablename__ = "global_questions"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=False)
    question_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
