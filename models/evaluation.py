# models/evaluation.py
# ─────────────────────────────────────────────────────────────────────────────
# Modelo ORM para almacenar evaluaciones de respuestas de entrevista.
#
# CAMPOS CRÍTICOS:
#   status       — permite saber si la evaluación está en vuelo, completó o falló.
#                  Sin esto no puedes distinguir "aún procesando" de "falló silenciosamente".
#   eval_version — permite cambiar la rúbrica en el futuro sin invalidar datos históricos.
#   error_detail — cuando status=FAILED, guarda el mensaje de error para debug.
#   score=-1     — convenio: -1 = fallo técnico, 0 = respuesta vacía. Son conceptos distintos.
# ─────────────────────────────────────────────────────────────────────────────

import enum
import uuid

from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Integer, JSON
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base
from models.job_role import GUID


class EvaluationStatus(str, enum.Enum):
    PENDING   = "pending"    # Registro creado, evaluación aún no terminó
    COMPLETED = "completed"  # Azure OpenAI respondió correctamente
    FAILED    = "failed"     # Azure falló o devolvió JSON inválido


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )

    # FK a la pregunta que se está evaluando
    question_id = Column(
        ForeignKey("questions.id"),
        nullable=False,
        index=True,
    )

    # FK a la sesión de entrevista dueña de la pregunta
    interview_session_id = Column(
        Integer,
        ForeignKey("interview_sessions.id"),
        nullable=False,
        index=True,
    )

    # Respuesta textual del usuario
    user_answer_text = Column(Text, nullable=False)

    # Estado del proceso de evaluación
    status = Column(
        SAEnum(EvaluationStatus, name="evaluationstatus"),
        nullable=False,
        default=EvaluationStatus.PENDING,
    )

    # ── Resultados (null hasta status=COMPLETED) ──────────────────────────
    # Score de 0-100. -1 indica fallo técnico (distinto de 0 = respuesta vacía).
    score           = Column(Float, nullable=True)
    feedback        = Column(Text,  nullable=True)  # Texto formateado para el usuario
    score_breakdown = Column(JSON,  nullable=True)  # {"correctness": 80, "completeness": 70, ...}
    topics_covered  = Column(JSON,  nullable=True)  # ["topic_a", "topic_b"]
    topics_missing  = Column(JSON,  nullable=True)  # ["topic_c"]

    # ── Auditoría ─────────────────────────────────────────────────────────
    eval_version = Column(String, nullable=False, default="1.0")  # Para comparar versiones de rúbrica
    model_used   = Column(String, nullable=True)                  # Nombre del deployment Azure
    duration_ms  = Column(Float,  nullable=True)                  # Latencia de la llamada a Azure
    error_detail = Column(Text,   nullable=True)                  # Detalle del error si status=FAILED

    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones ORM
    question = relationship("Question", back_populates="evaluations")
    interview_session = relationship("InterviewSession", back_populates="evaluations")
