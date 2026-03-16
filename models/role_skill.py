from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression

from core.database import Base
from models.job_role import GUID


class RoleSkill(Base):
    __tablename__ = "role_skills"
    __table_args__ = (
        CheckConstraint(
            "importance_weight >= 1 AND importance_weight <= 10",
            name="ck_role_skills_importance_weight_range",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(GUID(), ForeignKey("job_roles.id"), nullable=False, index=True)
    technology_id = Column(Integer, ForeignKey("technologies.id"), nullable=False, index=True)
    importance_weight = Column(Integer, nullable=False)
    is_required = Column(Boolean, nullable=False, default=False, server_default=expression.false())

    job_role = relationship("JobRole", back_populates="role_skills")
    technology = relationship("Technology", back_populates="role_skills")
