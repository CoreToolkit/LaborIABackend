from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GroupInterviewSessionCreateSchema(BaseModel):
    """Schema para crear una nueva sesión grupal de entrevista."""
    role_id: UUID = Field(..., description="ID del rol de trabajo para esta sesión")
    difficulty: str | None = Field(None, description="Nivel de dificultad (ej: beginner, intermediate, advanced)")


class GroupInterviewSessionResponseSchema(BaseModel):
    """Schema básico de respuesta para sesión grupal."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_code: str = Field(..., description="Código único para unirse a la sesión (ej: ABCD1234)")
    host_id: int
    role_id: UUID
    difficulty: str | None
    created_at: datetime | None
    updated_at: datetime | None


class GroupSessionHostResponse(BaseModel):
    """Schema para información del host en sesión grupal."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str


class GroupSessionRoleResponse(BaseModel):
    """Schema para información del rol en sesión grupal."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class GroupInterviewSessionDetailSchema(BaseModel):
    """Schema detallado con host, rol e información de participantes."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_code: str
    host_id: int
    host: GroupSessionHostResponse | None
    role_id: UUID
    role: GroupSessionRoleResponse | None
    difficulty: str | None
    created_at: datetime | None
    updated_at: datetime | None
    participant_count: int = Field(
        default=0,
        description="Número de sesiones de entrevista vinculadas a la sesión grupal"
    )
