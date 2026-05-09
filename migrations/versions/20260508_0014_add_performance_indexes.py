"""Add performance indexes for critical queries.

Revision ID: 20260508_0014
Revises: 20260507_0013
Create Date: 2026-05-08

Justificación de índices:
- idx_interview_session_user_created: Optimiza queries en ReportService.list_session_reports
  que filtran por (user_id, created_at). Reduce scans completos de tabla.
- idx_evaluation_session_status: Optimiza queries en ReportService y BadgeService que
  filtran evaluations por (interview_session_id, status). Reduce N+1 queries a lookups indexados.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260508_0014"
down_revision = "20260507_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Índice compuesto: (user_id, created_at) para ordenamiento rápido de sesiones por usuario
    op.create_index(
        'idx_interview_session_user_created',
        'interview_sessions',
        ['user_id', 'created_at'],
    )
    
    # Índice compuesto: (interview_session_id, status) para filtrado rápido de evaluaciones
    op.create_index(
        'idx_evaluation_session_status',
        'evaluations',
        ['interview_session_id', 'status'],
    )


def downgrade() -> None:
    op.drop_index('idx_interview_session_user_created')
    op.drop_index('idx_evaluation_session_status')
