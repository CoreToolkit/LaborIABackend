from sqlalchemy import Column, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import relationship

from core.database import Base


class Question(Base):
	__tablename__ = "questions"

	id = Column(Integer, primary_key=True, index=True)
	interview_session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False, index=True)
	question_text = Column(String, nullable=False)
	category = Column(String, nullable=True)
	difficulty = Column(String, nullable=True)
	expected_topics = Column(JSON, nullable=True)

	interview_session = relationship("InterviewSession", back_populates="questions")
	evaluations = relationship("Evaluation", back_populates="question", cascade="all, delete-orphan")
