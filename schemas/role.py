from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AliasPath, BaseModel, ConfigDict, Field, model_validator

from models.job_role import JobRoleCategory, RoleEnglishLevel, SeniorityLevel


class RoleRequirementCreateSchema(BaseModel):
    technology_id: int
    importance_weight: int = Field(ge=1, le=10)
    is_required: bool = False


class RoleRequirementDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    technology_id: int
    technology_name: str = Field(validation_alias=AliasPath("technology", "name"))
    importance_weight: int
    is_required: bool


class RoleResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: JobRoleCategory
    seniority_level: SeniorityLevel
    min_english_level: RoleEnglishLevel
    estimated_salary_min_cop: Decimal | None = None
    estimated_salary_max_cop: Decimal | None = None
    active: bool

    @model_validator(mode="after")
    def validate_salary_range(self):
        if (
            self.estimated_salary_min_cop is not None
            and self.estimated_salary_max_cop is not None
            and self.estimated_salary_min_cop > self.estimated_salary_max_cop
        ):
            raise ValueError("estimated_salary_min_cop must be less than or equal to estimated_salary_max_cop")
        return self


class RoleDetailSchema(RoleResponseSchema):
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    role_skills: list[RoleRequirementDetailSchema] = Field(default_factory=list)


class RoleCreateSchema(BaseModel):
    name: str
    description: str | None = None
    category: JobRoleCategory
    seniority_level: SeniorityLevel
    min_english_level: RoleEnglishLevel
    estimated_salary_min_cop: Decimal | None = None
    estimated_salary_max_cop: Decimal | None = None
    active: bool = True
    role_skills: list[RoleRequirementCreateSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_salary_range(self):
        if (
            self.estimated_salary_min_cop is not None
            and self.estimated_salary_max_cop is not None
            and self.estimated_salary_min_cop > self.estimated_salary_max_cop
        ):
            raise ValueError("estimated_salary_min_cop must be less than or equal to estimated_salary_max_cop")
        return self
