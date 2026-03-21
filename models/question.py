from sqlalchemy import Column, Integer, String, JSON

from core.database import Base


class Question(Base):
	__tablename__ = "questions"

	id = Column(Integer, primary_key=True, index=True)
	interview_session_id = Column(Integer, nullable=False, index=True)
	question_text = Column(String, nullable=False)
	category = Column(String, nullable=True)
	difficulty = Column(String, nullable=True)
	expected_topics = Column(JSON, nullable=True)
