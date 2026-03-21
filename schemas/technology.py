from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TechnologyBase(BaseModel):
    name: str


class TechnologyCreate(TechnologyBase):
    pass


class TechnologyUpdate(BaseModel):
    name: str


class TechnologyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime | None
