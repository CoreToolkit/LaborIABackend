"""Seed default badges.

Revision ID: 20260501_0010
Revises: 20260501_0009
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260501_0010"
down_revision = "20260501_0009"
branch_labels = None
depends_on = None

_DEFAULT_BADGES = [
    {
        "name": "Primera Entrevista",
        "description": "Completaste tu primera entrevista de práctica",
        "icon": "🎯",
        "condition_type": "total_interviews",
        "condition_value": "1",
    },
    {
        "name": "En Racha",
        "description": "Completaste 5 entrevistas de práctica",
        "icon": "🔥",
        "condition_type": "total_interviews",
        "condition_value": "5",
    },
    {
        "name": "Experto",
        "description": "Completaste 10 entrevistas de práctica",
        "icon": "🏆",
        "condition_type": "total_interviews",
        "condition_value": "10",
    },
    {
        "name": "Alto Rendimiento",
        "description": "Obtuviste un score de 80 o más en una sesión",
        "icon": "⭐",
        "condition_type": "session_score_gte",
        "condition_value": "80",
    },
    {
        "name": "Perfeccionista",
        "description": "Obtuviste un score de 95 o más en una sesión",
        "icon": "💎",
        "condition_type": "session_score_gte",
        "condition_value": "95",
    },
    {
        "name": "Comeback Kid",
        "description": "Mejoraste tu score en 30 puntos o más respecto a tu sesión anterior",
        "icon": "📈",
        "condition_type": "score_improvement_gte",
        "condition_value": "30",
    },
    {
        "name": "Consistente",
        "description": "Mantuviste un promedio general de 70 o más",
        "icon": "📊",
        "condition_type": "avg_score_gte",
        "condition_value": "70",
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    for badge in _DEFAULT_BADGES:
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
    names = [b["name"] for b in _DEFAULT_BADGES]
    bind.execute(
        text("DELETE FROM badges WHERE name IN :names"),
        {"names": tuple(names)},
    )
