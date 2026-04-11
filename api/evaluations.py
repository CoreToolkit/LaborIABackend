# api/evaluations.py
# ─────────────────────────────────────────────────────────────────────────────
# Router FastAPI para US-013: evaluación de respuestas de entrevista.
#
# FLUJO:
#   1. Frontend envía POST /evaluations/answer con question_id + user_answer_text
#   2. Backend crea registro Evaluation en estado PENDING (respuesta inmediata 202)
#   3. BackgroundTask llama a Azure OpenAI para evaluar
#   4. Frontend hace polling a GET /evaluations/evaluation/{id} hasta status=completed
#
# POR QUÉ 202 ACCEPTED:
#   La evaluación con Azure tarda 1-4 segundos. Devolver 202 inmediatamente
#   con un evaluation_id permite al frontend mostrar un spinner mientras
#   el backend trabaja, sin bloquear la conexión HTTP.
# ─────────────────────────────────────────────────────────────────────────────

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from models.evaluation import Evaluation, EvaluationStatus
from models.question import Question
from services.answer_evaluator import run_evaluation_background
from services.interview_flow import (
    EVENT_EVALUATION_PENDING,
    EVALUATION_PENDING,
    QUESTION_CREATED,
    can_enter_evaluation_pending,
    resolve_next_state,
    state_from_evaluation_status,
)

router = APIRouter(
    prefix="/evaluations",
    tags=["evaluations"],
)


# ── Schemas de request/response ───────────────────────────────────────────────

class SubmitAnswerRequest(BaseModel):
    question_id: int
    user_answer_text: str


class SubmitAnswerResponse(BaseModel):
    evaluation_id: str
    status: str
    message: str


class EvaluationResponse(BaseModel):
    evaluation_id: str
    status: str
    score: float | None
    feedback: str | None
    score_breakdown: dict | None
    topics_covered: list | None
    topics_missing: list | None
    eval_version: str | None
    duration_ms: float | None
    evaluated_at: str | None
    completed_at: str | None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/answer", response_model=SubmitAnswerResponse, status_code=202)
async def submit_answer(
    body: SubmitAnswerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Recibe la respuesta del usuario a una pregunta de entrevista.

    Crea un registro Evaluation en estado PENDING y lanza la evaluación en
    background usando Azure OpenAI. El cliente debe hacer polling a
    GET /evaluations/evaluation/{evaluation_id} para obtener el resultado.

    Returns 202 Accepted inmediatamente con el evaluation_id.
    """
    user_answer = (body.user_answer_text or "").strip()

    if not body.question_id:
        raise HTTPException(status_code=400, detail="question_id es requerido")
    if not user_answer:
        raise HTTPException(status_code=400, detail="user_answer_text no puede estar vacío")
    if not can_enter_evaluation_pending(question_id=body.question_id, user_answer_text=user_answer):
        raise HTTPException(status_code=400, detail="No se puede iniciar evaluacion para la pregunta enviada")
    flow_target_state = resolve_next_state(
        QUESTION_CREATED,
        event=EVENT_EVALUATION_PENDING,
        question_id=body.question_id,
        user_answer_text=user_answer,
    )
    if flow_target_state != EVALUATION_PENDING:
        raise HTTPException(
            status_code=500,
            detail="Interview flow transition is not allowed: question_created -> evaluation_pending",
        )

    # Verificar que la pregunta existe
    question = db.query(Question).filter(Question.id == body.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")

    # Asegurar que la pregunta pertenece al usuario autenticado
    if not question.interview_session or question.interview_session.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="No autorizado para responder esta pregunta")

    # Crear registro en PENDING — respuesta inmediata al cliente
    evaluation = Evaluation(
        question_id=body.question_id,
        interview_session_id=question.interview_session_id,
        user_answer_text=user_answer,
        status=EvaluationStatus.PENDING,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    evaluation_flow_state = state_from_evaluation_status(evaluation.status)
    if evaluation_flow_state != EVALUATION_PENDING:
        raise HTTPException(
            status_code=500,
            detail="Interview flow validation failed for evaluation_pending",
        )

    # Disparar evaluación en background
    # La función run_evaluation_background es síncrona y gestiona su propio event loop.
    background_tasks.add_task(
        run_evaluation_background,
        evaluation_id=str(evaluation.id),
        question_text=question.question_text,
        expected_topics=question.expected_topics,  # JSON field con lista de temas esperados
        user_answer=user_answer,
    )

    return SubmitAnswerResponse(
        evaluation_id=str(evaluation.id),
        status=evaluation.status.value if isinstance(evaluation.status, EvaluationStatus) else str(evaluation.status),
        message="Respuesta recibida. La evaluación está en proceso.",
    )


@router.get("/evaluation/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(
    evaluation_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Consulta el resultado de una evaluación por su ID.

    El cliente hace polling a este endpoint hasta que status sea
    'completed' o 'failed'. Intervalo recomendado: 1-2 segundos.

    Campos de respuesta:
      - status: "pending" | "completed" | "failed"
      - score: 0-100 cuando completed. null cuando pending/failed.
              Nota: score=-1 en DB indica fallo técnico pero se retorna null aquí.
      - feedback: texto formateado para mostrar al usuario
      - score_breakdown: {correctness, completeness, clarity, examples}
      - topics_covered / topics_missing: listas de temas del expected_topics original
      - duration_ms: latencia de la llamada a Azure en milisegundos
    """
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    # Asegurar que el usuario solo consulte evaluaciones de sus sesiones
    if not evaluation.interview_session or evaluation.interview_session.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="No autorizado para ver esta evaluación")

    # Normalizar score: -1 (fallo técnico interno) se expone como null al cliente
    score_for_client = evaluation.score if (evaluation.score is not None and evaluation.score >= 0) else None

    return EvaluationResponse(
        evaluation_id=str(evaluation.id),
        status=evaluation.status.value if isinstance(evaluation.status, EvaluationStatus) else str(evaluation.status),
        score=score_for_client,
        feedback=evaluation.feedback,
        score_breakdown=evaluation.score_breakdown,
        topics_covered=evaluation.topics_covered,
        topics_missing=evaluation.topics_missing,
        eval_version=evaluation.eval_version,
        duration_ms=evaluation.duration_ms,
        evaluated_at=str(evaluation.evaluated_at) if evaluation.evaluated_at else None,
        completed_at=str(evaluation.completed_at) if evaluation.completed_at else None,
    )
