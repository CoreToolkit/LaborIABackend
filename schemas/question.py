from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class QuestionCreateSchema(BaseModel):
    question_text: str
    interview_session_id: int
    category: str | None = None
    difficulty: str | None = None
    expected_topics: list[Any] | dict[str, Any] | None = None


class QuestionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_session_id: int
    question_text: str
    category: str | None
    difficulty: str | None
    expected_topics: list[Any] | dict[str, Any] | None
