from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, model_validator


class ExperienceBase(BaseModel):
    position: str
    company: str
    start_date: date
    end_date: date | None = None
    description: str | None = None
    currently_working: bool = False

    @model_validator(mode="after")
    def validate_dates(self):
        if self.currently_working and self.end_date is not None:
            raise ValueError("end_date must be null when currently_working is true")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class ExperienceCreate(ExperienceBase):
    pass


class ExperienceUpdate(BaseModel):
    position: str | None = None
    company: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    currently_working: bool | None = None

    @model_validator(mode="after")
    def validate_partial_dates(self):
        if self.currently_working is True and self.end_date is not None:
            raise ValueError("end_date must be null when currently_working is true")
        if self.start_date is not None and self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class ExperienceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
    position: str
    company: str
    start_date: date
    end_date: date | None
    description: str | None
    currently_working: bool
    created_at: datetime | None
    updated_at: datetime | None
