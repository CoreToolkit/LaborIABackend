from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GroupInterviewNextRoundRequestSchema(BaseModel):
    target_skill: str | None = Field(
        None,
        description="Habilidad objetivo para enfocar la siguiente pregunta",
    )
    difficulty: str | None = Field(
        None,
        description="Dificultad para la siguiente pregunta. Si no se envia, se usa la de la sala",
    )


class GroupInterviewRoundNextResponseSchema(BaseModel):
    round_id: UUID
    round_index: int
    question_text: str
    target_skill: str | None
    difficulty: str | None
    status: str
    created_at: datetime | None