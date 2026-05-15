"""Seed 3 additional badges to reach 10 total.

Revision ID: 20260507_0012
Revises: 20260506_0011
Create Date: 2026-05-07
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260507_0012"
down_revision = "20260506_0011"
branch_labels = None
depends_on = None

_ADDITIONAL_BADGES = [
    {
        "name": "Veterano",
        "description": "Completaste 20 entrevistas de práctica",
        "icon": "🎖️",
        "condition_type": "total_interviews",
        "condition_value": "20",
    },
    {
        "name": "Excelente Promedio",
        "description": "Mantuviste un promedio general de 85 o más",
        "icon": "🌟",
        "condition_type": "avg_score_gte",
        "condition_value": "85",
    },
    {
        "name": "Remontada",
        "description": "Mejoraste tu score en 15 puntos o más respecto a tu sesión anterior",
        "icon": "🚀",
        "condition_type": "score_improvement_gte",
        "condition_value": "15",
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    for badge in _ADDITIONAL_BADGES:
        if is_pg:
            bind.execute(
                text(
                    "INSERT INTO badges (name, description, icon, condition_type, condition_value) "
                    "VALUES (:name, :description, :icon, :condition_type, :condition_value) "
                    "ON CONFLICT (name) DO NOTHING"
                ),
                badge,
            )
        else:
            bind.execute(
                text(
                    "INSERT OR IGNORE INTO badges "
                    "(name, description, icon, condition_type, condition_value) "
                    "VALUES (:name, :description, :icon, :condition_type, :condition_value)"
                ),
                badge,
            )


def downgrade() -> None:
    bind = op.get_bind()
    names = [b["name"] for b in _ADDITIONAL_BADGES]
    bind.execute(
        text("DELETE FROM badges WHERE name IN :names"),
        {"names": tuple(names)},
    )
