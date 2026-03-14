from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SkillBase(BaseModel):
    name: str
    category: str | None = None
    level: str | None = None


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    level: str | None = None


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
    name: str
    category: str | None
    level: str | None
    created_at: datetime | None
    updated_at: datetime | None
