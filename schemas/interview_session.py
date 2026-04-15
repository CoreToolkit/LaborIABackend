from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InterviewSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime | None
    updated_at: datetime | None


class SessionQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_session_id: int
    question_text: str
    category: str | None
    difficulty: str | None
    expected_topics: list[Any] | dict[str, Any] | None


class SessionEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question_id: int
    interview_session_id: int
    user_answer_text: str
    status: str
    score: float | None
    feedback: str | None
    score_breakdown: dict[str, Any] | None
    topics_covered: list[Any] | None
    topics_missing: list[Any] | None
    eval_version: str
    model_used: str | None
    duration_ms: float | None
    error_detail: str | None
    evaluated_at: datetime | None
    completed_at: datetime | None


class InterviewSessionDetailResponse(InterviewSessionResponse):
    questions: list[SessionQuestionResponse]
    evaluations: list[SessionEvaluationResponse]
