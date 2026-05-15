# services/answer_evaluator.py
# ─────────────────────────────────────────────────────────────────────────────
# Implementa US-013: evaluación automática de respuestas con rúbrica.
#
# ARQUITECTURA:
#   - evaluate_answer()             → async, llama a Azure OpenAI, retorna dict
#   - run_evaluation_background()   → sync, wrapper para FastAPI BackgroundTasks
#   - Nunca lanza excepción al caller → siempre retorna fallback si algo falla
#
# RÚBRICA (Task-013-01):
#   Criterio         Peso    Pregunta que responde
#   ─────────────────────────────────────────────────────────────────────────
#   correctness       40%    ¿Los conceptos son técnicamente correctos?
#   completeness      30%    ¿Cubre los expected_topics de la pregunta?
#   clarity           20%    ¿La explicación es clara y ordenada?
#   examples          10%    ¿Incluye ejemplos, código o evidencia concreta?
#
#   Score final = round(correctness*0.40 + completeness*0.30 + clarity*0.20 + examples*0.10)
#
#   Niveles (aplican igual a cada criterio y al score final):
#     85–100  Excelente    Cubre el criterio sin gaps relevantes
#     70–84   Bueno        Correcto en lo esencial, detalles menores faltantes
#     50–69   Parcial      Base correcta pero incompleto o con errores no críticos
#     0–49    Insuficiente Incorrecto, vacío, o no responde la pregunta
#
# PATRÓN DE ROBUSTEZ:
#   - 2 intentos máximo, SOLO si el JSON viene malformado (no por "score bajo")
#   - Intento 2 baja temperature a 0.1 para forzar output más estructurado
#   - _log_score_discrepancy() → observabilidad pura, nunca modifica resultados
#   - score=-1 → fallo técnico (distinto de score=0 que es respuesta vacía)
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import json
import logging
import time
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ai.provider import LLMProvider
from core.database import SessionLocal
from models.evaluation import Evaluation, EvaluationStatus
from models.interview_session import InterviewSession
from services.metrics_service import UserMetricsService
from services.interview_flow import (
    EVENT_EVALUATION_RESOLVED,
    EVALUATION_COMPLETED,
    EVALUATION_FAILED,
    EVALUATION_PENDING,
    resolve_next_state,
    to_evaluation_status,
)

logger = logging.getLogger(__name__)

# ── Proveedor LLM (lazy init para no romper tests sin variables de entorno) ───
_azure_client: LLMProvider | None = None

EVAL_VERSION = "1.0"


# ── Prompts (Task-013-01 + Task-013-02) ──────────────────────────────────────
#
# Los pasos numerados (STEP 1 a STEP 5) no son decorativos.
# Los modelos siguen instrucciones secuenciales con mucha más fidelidad que párrafos
# de texto libre. STEP 2 fuerza al modelo a computar el score con la fórmula él mismo,
# eliminando la inconsistencia breakdown↔score sin necesidad de post-procesamiento.

_SYSTEM_PROMPT = """\
You are a strict and consistent technical interview evaluator.
You MUST follow these steps in order before outputting anything.

STEP 1 — Score each criterion independently (integer 0-100):
  - correctness  (40%): Are the technical concepts factually correct? No errors?
  - completeness (30%): Does the answer explicitly mention the expected topics listed?
  - clarity      (20%): Is the explanation clear, structured, and easy to follow?
  - examples     (10%): Does the answer include code, examples, or concrete evidence?

SCORING LEVELS (apply to each criterion):
  85-100  Excellent    — thorough coverage, no significant gaps
  70-84   Good         — mostly correct, only minor gaps
  50-69   Partial      — some correct parts, notable gaps or non-critical errors
  0-49    Insufficient — largely incorrect, empty, or does not address the criterion

STEP 2 — Compute the final score using this exact formula:
  final_score = round(correctness*0.40 + completeness*0.30 + clarity*0.20 + examples*0.10)

STEP 3 — Write feedback following these rules (no exceptions):
  If final_score >= 85:
    - strengths must have at least 1 specific item
    - correction must be null
  If 50 <= final_score < 70:
    - improvements[0] MUST start exactly with: "Correcto pero incompleto:"
    - explain specifically which expected topics were missing
  If final_score < 30:
    - improvements[0] MUST start exactly with: "Incorrecto:"
    - explain the specific conceptual error the candidate made
  Always write feedback in the same language as the candidate's answer.

STEP 4 — For topics_covered and topics_missing:
  Use ONLY topics from the "Expected topics" list provided.
  Mark a topic as covered only if the candidate explicitly addressed it.
  Do not invent topics that are not in the expected list.

STEP 5 — Output ONLY a valid JSON object. No markdown, no explanation, nothing outside the JSON.\
"""

_USER_TEMPLATE = """\
Question: {question}

Expected topics (evaluate coverage of EACH one explicitly):
{expected_topics_bullets}

Candidate answer:
{user_answer}

Now follow the 5 steps from your instructions and return this exact JSON:
{{
  "score": <integer 0-100, must equal round(correctness*0.40 + completeness*0.30 + clarity*0.20 + examples*0.10)>,
  "score_breakdown": {{
    "correctness": <integer 0-100>,
    "completeness": <integer 0-100>,
    "clarity": <integer 0-100>,
    "examples": <integer 0-100>
  }},
  "feedback": {{
    "strengths": [<string>, ...],
    "improvements": [<string>, ...],
    "correction": <string or null>
  }},
  "topics_covered": [<only topics from the expected list above that were explicitly addressed>],
  "topics_missing": [<only topics from the expected list above that were not addressed>]
}}\
"""


# ── Función principal (async) ─────────────────────────────────────────────────

async def evaluate_answer(
    question_text: str,
    expected_topics: list[str] | None,
    user_answer: str,
) -> dict[str, Any]:
    """
    Evalúa la respuesta del usuario usando Azure OpenAI con la rúbrica definida.

    Args:
        question_text:    Texto de la pregunta de entrevista.
        expected_topics:  Lista de temas que la respuesta debería cubrir.
        user_answer:      Texto de la respuesta del usuario.

    Returns:
        Dict con: score (0-100, o -1 si fallo técnico), score_breakdown,
        feedback (strengths/improvements/correction), topics_covered, topics_missing.

    Nunca lanza excepción — retorna _fallback_response() si todo falla.
    """
    if not user_answer or not user_answer.strip():
        return _empty_answer_response()

    client = _azure_client or _get_azure_client()
    if client is None:
        return _fallback_response()

    user_prompt = _build_user_prompt(question_text, expected_topics, user_answer)

    # 2 intentos máximo, SOLO si el JSON viene malformado.
    # NUNCA reintentamos porque el score "parece bajo" — eso sesgaría al evaluador.
    for attempt in range(2):
        try:
            raw: str = await client.ask(
                question=user_prompt,
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.2 if attempt == 0 else 0.1,
                max_tokens=600,
            )
            parsed = _parse_json(raw)
            result = _normalize(parsed)
            _log_score_discrepancy(result)  # Observabilidad pura, nunca modifica
            return result

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            # Solo reintentamos si el JSON vino roto
            if attempt == 1:
                logger.error(
                    "evaluate_answer: JSON parse failed after 2 attempts — %s", exc
                )
                return _fallback_response()
            logger.warning(
                "evaluate_answer: retrying after parse error on attempt %d — %s",
                attempt, exc,
            )

        except Exception as exc:
            # Error de red, Azure caído, timeout — no tiene sentido reintentar
            logger.error("evaluate_answer: Azure error — %s", exc, exc_info=True)
            return _fallback_response()

    return _fallback_response()


# ── Función para BackgroundTasks (síncrona) ───────────────────────────────────

def run_evaluation_background(
    evaluation_id: str,
    question_text: str,
    expected_topics: list[str] | None,
    user_answer: str,
) -> None:
    """
    Wrapper SÍNCRONO para FastAPI BackgroundTasks.
    Llama a evaluate_answer() y actualiza el registro Evaluation en DB al terminar.

    Por qué asyncio.new_event_loop():
        BackgroundTasks corre en el thread del servidor. Con un backend mixto
        (sync/async) como este, crear un loop propio es la forma más segura de
        ejecutar código async desde contexto sync. Si en el futuro se uniformiza
        todo a async def, este bloque se reemplaza por un simple await.
    """
    start = time.monotonic()

    db: Session = SessionLocal()
    try:
        loop   = asyncio.new_event_loop()
        result = loop.run_until_complete(
            evaluate_answer(question_text, expected_topics, user_answer)
        )
        loop.close()

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
                    user_id = evaluation.interview_session.user_id
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


# ── Helpers privados ──────────────────────────────────────────────────────────

def _build_user_prompt(
    question_text: str,
    expected_topics: list[str] | None,
    user_answer: str,
) -> str:
    """
    Construye el prompt de usuario con expected_topics como bullets.
    Los bullets hacen que el modelo trate cada tema como ítem a verificar uno por uno,
    en lugar de como contexto general (que es lo que ocurre con un string plano).
    """
    if expected_topics:
        bullets = "\n".join(f"- {t}" for t in expected_topics)
    else:
        bullets = "- (no specific topics required, evaluate general correctness)"

    return _USER_TEMPLATE.format(
        question=question_text,
        expected_topics_bullets=bullets,
        user_answer=user_answer.strip(),
    )


def _get_azure_client() -> LLMProvider | None:
    """Inicializa proveedor LLM bajo demanda para evitar errores al importar en tests."""
    global _azure_client

    if _azure_client is not None:
        return _azure_client

    try:
        from ai.provider_factory import create_llm_provider
        _azure_client = create_llm_provider()
    except Exception as exc:
        logger.error("answer_evaluator: LLM provider not available — %s", exc)
        return None

    return _azure_client


def _parse_json(raw: str) -> dict:
    """
    Parsea JSON desde la respuesta del LLM.
    Maneja el caso en que el modelo envuelva en ```json ... ``` a pesar del system prompt.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw   = parts[1].lstrip("json").strip() if len(parts) > 1 else raw
    return json.loads(raw)


def _normalize(data: dict) -> dict[str, Any]:
    """
    Asegura que todos los valores estén en rango válido [0, 100].
    El LLM puede devolver 150 o -5 — los clampeamos sin modificar la lógica.
    """
    def clamp(v: Any) -> int:
        return max(0, min(100, int(v or 0)))

    breakdown = data.get("score_breakdown") or {}

    return {
        "score": clamp(data.get("score", 50)),
        "score_breakdown": {
            "correctness":  clamp(breakdown.get("correctness",  50)),
            "completeness": clamp(breakdown.get("completeness", 50)),
            "clarity":      clamp(breakdown.get("clarity",      50)),
            "examples":     clamp(breakdown.get("examples",     50)),
        },
        "feedback":       data.get("feedback")       or {},
        "topics_covered": data.get("topics_covered") or [],
        "topics_missing": data.get("topics_missing") or [],
    }


def _log_score_discrepancy(result: dict) -> None:
    """
    Observabilidad pura — NO modifica el resultado.
    Si el score del modelo difiere >15 puntos del recalculado con la fórmula,
    loguea un warning. Esto permite detectar si el prompt necesita ajuste
    con datos reales de producción.
    """
    breakdown = result.get("score_breakdown") or {}
    if not breakdown:
        return

    recalc = round(
        breakdown.get("correctness",  0) * 0.40
        + breakdown.get("completeness", 0) * 0.30
        + breakdown.get("clarity",      0) * 0.20
        + breakdown.get("examples",     0) * 0.10
    )
    diff = abs(recalc - result["score"])
    if diff > 15:
        logger.warning(
            "Score discrepancy: model=%s recalculated=%s diff=%s | breakdown=%s",
            result["score"], recalc, diff, breakdown,
        )


def _format_feedback(result: dict) -> str:
    """
    Convierte el dict de feedback en texto legible para guardar en DB.
    Este texto es lo que el frontend muestra al usuario.
    """
    score = result["score"]
    fb    = result.get("feedback") or {}

    if score >= 85:
        header = "Excelente respuesta."
    elif score >= 70:
        header = "Buena respuesta."
    elif score >= 50:
        header = "Correcto pero incompleto."
    else:
        header = "Incorrecto."

    lines = [header]

    if fb.get("strengths"):
        lines.append("Fortalezas: " + "; ".join(fb["strengths"]))
    if fb.get("improvements"):
        lines.append("A mejorar: " + "; ".join(fb["improvements"]))
    if fb.get("correction"):
        lines.append(f"Corrección: {fb['correction']}")

    return "\n".join(lines)


def _empty_answer_response() -> dict[str, Any]:
    """Respuesta para usuario que no escribió nada. Score=0, sin llamar a Azure."""
    return {
        "score": 0,
        "score_breakdown": {
            "correctness": 0, "completeness": 0, "clarity": 0, "examples": 0,
        },
        "feedback": {
            "strengths":    [],
            "improvements": ["No se proporcionó respuesta."],
            "correction":   None,
        },
        "topics_covered": [],
        "topics_missing": [],
    }


def _fallback_response() -> dict[str, Any]:
    """
    Fallback para errores técnicos (Azure caído, JSON inválido, etc.).
    score=-1 distingue fallo técnico de score=0 (respuesta vacía).
    """
    return {
        "score": -1,
        "score_breakdown": {},
        "feedback": {
            "strengths":    [],
            "improvements": ["Error al evaluar automáticamente. Reintenta más tarde."],
            "correction":   None,
        },
        "topics_covered": [],
        "topics_missing": [],
    }
