from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from ai.provider import LLMProvider
from core.database import get_db

_llm_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Returns a cached LLMProvider singleton (created on first request)."""
    global _llm_provider
    if _llm_provider is None:
        from ai.provider_factory import create_llm_provider
        _llm_provider = create_llm_provider()
    return _llm_provider


def get_interview_session_service(db: Session = Depends(get_db)):
    from services.interview_session_service import InterviewSessionService
    return InterviewSessionService(db)


def get_group_orchestrator(
    db: Session = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
):
    from services.group_interview_orchestrator_service import GroupInterviewOrchestratorService
    return GroupInterviewOrchestratorService(db, llm_provider=llm_provider)
