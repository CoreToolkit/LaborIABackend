import logging
import time
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from core.database import SessionLocal
from models.evaluation import Evaluation, EvaluationStatus
from models.interview_session import InterviewSession
from services.answer_evaluator import EVAL_VERSION, _format_feedback, evaluate_answer
from services.interview_flow import (
    EVALUATION_COMPLETED,
    EVALUATION_FAILED,
    EVALUATION_PENDING,
    EVENT_EVALUATION_RESOLVED,
    resolve_next_state,
    to_evaluation_status,
)
from services.metrics_service import UserMetricsService

logger = logging.getLogger(__name__)


async def run_evaluation_background(
    evaluation_id: str,
    question_text: str,
    expected_topics: list[str] | None,
    user_answer: str,
) -> None:
    """
    Wrapper ASYNC para FastAPI BackgroundTasks.
    Llama a evaluate_answer() y actualiza el registro Evaluation en DB al terminar.
    """
    start = time.monotonic()

    db: Session = SessionLocal()
    try:
        result = await evaluate_answer(question_text, expected_topics, user_answer)

        duration_ms  = round((time.monotonic() - start) * 1000, 1)
        is_fallback  = result.get("score") == -1

        update_data: dict[str, Any] = {
            "duration_ms":  duration_ms,
            "eval_version": EVAL_VERSION,
            "model_used":   None,
        }

        resolved_state = resolve_next_state(
            EVALUATION_PENDING,
            event=EVENT_EVALUATION_RESOLVED,
            evaluation_status=EvaluationStatus.FAILED if is_fallback else EvaluationStatus.COMPLETED,
            evaluation_id=evaluation_id,
        )
        if resolved_state is None:
            raise RuntimeError("Interview flow could not resolve evaluation outcome state")

        resolved_status = to_evaluation_status(resolved_state)
        if resolved_status is None:
            raise RuntimeError(f"Interview flow has no DB status mapping for state '{resolved_state}'")

        update_data["status"] = resolved_status

        if resolved_state == EVALUATION_FAILED:
            update_data["error_detail"] = "Azure OpenAI returned invalid or unparseable response"
        elif resolved_state == EVALUATION_COMPLETED:
            update_data["score"]           = result["score"]
            update_data["feedback"]        = _format_feedback(result)
            update_data["score_breakdown"] = result["score_breakdown"]
            update_data["topics_covered"]  = result["topics_covered"]
            update_data["topics_missing"]  = result["topics_missing"]
            update_data["completed_at"]    = func.now()

        db.query(Evaluation).filter(Evaluation.id == evaluation_id).update(update_data)
        db.commit()

        if resolved_state == EVALUATION_COMPLETED:
            try:
                evaluation = (
                    db.query(Evaluation)
                    .join(InterviewSession, Evaluation.interview_session_id == InterviewSession.id)
                    .filter(Evaluation.id == evaluation_id)
                    .first()
                )
                if evaluation and evaluation.interview_session:
                    user_id    = evaluation.interview_session.user_id
                    session_id = evaluation.interview_session_id

                    UserMetricsService(db).update_for_user(user_id)

                    total_q = len(evaluation.interview_session.questions)
                    completed_q = (
                        db.query(func.count(Evaluation.id))
                        .filter(
                            Evaluation.interview_session_id == session_id,
                            Evaluation.status == EvaluationStatus.COMPLETED,
                            Evaluation.score >= 0,
                        )
                        .scalar()
                        or 0
                    )

                    if total_q > 0 and completed_q >= total_q:
                        session_evals = (
                            db.query(Evaluation)
                            .filter(
                                Evaluation.interview_session_id == session_id,
                                Evaluation.status == EvaluationStatus.COMPLETED,
                                Evaluation.score >= 0,
                            )
                            .all()
                        )
                        valid = [e.score for e in session_evals if e.score is not None]
                        session_score = round(sum(valid) / len(valid), 2) if valid else None

                        from services.badge_service import BadgeService
                        BadgeService(db).check_and_unlock_badges(
                            user_id=user_id,
                            session_id=session_id,
                            session_score=session_score,
                        )
            except Exception as metrics_exc:
                logger.exception(
                    "run_evaluation_background: post-interview trigger failed for evaluation_id=%s — %s",
                    evaluation_id,
                    metrics_exc,
                )

    except Exception as exc:
        logger.error(
            "run_evaluation_background: failed for evaluation_id=%s — %s",
            evaluation_id, exc, exc_info=True,
        )
        try:
            failed_state = resolve_next_state(
                EVALUATION_PENDING,
                event=EVENT_EVALUATION_RESOLVED,
                evaluation_status=EvaluationStatus.FAILED,
                evaluation_id=evaluation_id,
            )
            failed_status = to_evaluation_status(failed_state or EVALUATION_FAILED) or EvaluationStatus.FAILED

            db.query(Evaluation).filter(Evaluation.id == evaluation_id).update({
                "status":       failed_status,
                "error_detail": str(exc)[:500],
            })
            db.commit()
        except Exception:
            logger.exception(
                "run_evaluation_background: could not update FAILED status for %s",
                evaluation_id,
            )
    finally:
        db.close()
