from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ai.azure_openai_client import AzureOpenAIClient
from exceptions.profile_exceptions import ProfileNotFoundError
from models.interview_session import InterviewSession
from models.question import Question
from services.group_interview_round_service import GroupInterviewRoundService
from services.group_interview_session_service import GroupInterviewSessionService
from services.profile_service import ProfileService
from utils.prompts.question_generation import build_group_question_generation_prompts

logger = logging.getLogger(__name__)

# Mensaje seguro expuesto al cliente cuando TTS falla.
# No expone detalles del proveedor (AB#325 sanitización).
_TTS_SAFE_ERROR_MSG = "El audio no está disponible en este momento. La pregunta se muestra en texto."


class TTSResult:
    """
    Resultado TTS devuelto por el orquestador.

    audio_b64   : audio mp3 en base64 o None si TTS falló (fallback)
    tts_status  : "ok" | "fallback"
    tts_error   : mensaje seguro para el cliente (nunca detalle crudo del proveedor)
    tts_elapsed_ms: tiempo de la llamada TTS en ms
    """
    __slots__ = ("audio_b64", "tts_status", "tts_error", "tts_elapsed_ms")

    def __init__(
        self,
        audio_b64: str | None,
        tts_status: str,
        tts_error: str | None = None,
        tts_elapsed_ms: int | None = None,
    ):
        self.audio_b64 = audio_b64
        self.tts_status = tts_status
        self.tts_error = tts_error
        self.tts_elapsed_ms = tts_elapsed_ms


class RoundEventPayloads:
    """
    Payloads de eventos websocket para una ronda.
    AB#323: la decisión de qué eventos emitir queda encapsulada en el orquestador,
    no en el router.
    """
    __slots__ = ("round_started", "question_generated", "audio_event")

    def __init__(
        self,
        round_started: dict,
        question_generated: dict,
        audio_event: dict,
    ):
        self.round_started = round_started
        self.question_generated = question_generated
        self.audio_event = audio_event


class GroupInterviewOrchestratorService:
    def __init__(self, db):
        self.db = db
        self.profile_service = ProfileService(db)
        self.group_session_service = GroupInterviewSessionService(db)
        self.round_service = GroupInterviewRoundService(db)
        self.azure_client = AzureOpenAIClient()

        # ElevenLabs es opcional: si no está configurado, el flujo continúa sin TTS
        self._elevenlabs_client = None
        try:
            from ai.elevenlabs_client import ElevenLabsClient
            from ai.elevenlabs_service import ElevenLabsService
            self._elevenlabs_client = ElevenLabsClient(ElevenLabsService())
        except RuntimeError as exc:
            logger.warning("ElevenLabs no disponible, TTS deshabilitado: %s", exc)

    # ------------------------------------------------------------------
    # Flujo principal
    # ------------------------------------------------------------------

    async def generate_next_round_question(
        self,
        session_code: str,
        requester_id: int,
        target_skill: str | None = None,
        difficulty: str | None = None,
    ):
        """
        Encadena: generar pregunta (IA) → TTS (ElevenLabs con retry) → persistir ronda.

        Retorna: (group_session, round_item, tts_result, event_payloads)
        - tts_result.tts_status: "ok" | "fallback"
        - tts_result.audio_b64: audio mp3 en base64 o None
        - event_payloads: RoundEventPayloads con los 3 eventos listos para broadcast
        La entrevista NO se cae si TTS falla (fallback no bloqueante).
        """
        group_session = self.group_session_service.get_group_session_by_code(session_code)

        if group_session.host_id != requester_id:
            raise PermissionError("Solo el host puede generar la siguiente pregunta")

        if group_session.status != "in_progress":
            raise ValueError("La sesión grupal debe estar en estado 'in_progress'")

        profile = self.profile_service.get_profile_by_user_id(requester_id)
        if not profile:
            raise ProfileNotFoundError()

        skills = self.profile_service.list_skills(requester_id)
        experiences = self.profile_service.list_experiences(requester_id)

        effective_difficulty = difficulty or group_session.difficulty or "adaptive"
        previous_rounds = self.round_service.round_repo.list_by_session_id(group_session.id)
        previous_questions = [
            item.question_text.strip()
            for item in previous_rounds
            if item.question_text and item.question_text.strip()
        ]

        role_name = group_session.role.name if group_session.role else "rol tecnico"
        role_description = group_session.role.description if group_session.role else ""

        system_prompt, prompt = build_group_question_generation_prompts(
            profile=profile,
            skills=skills,
            experiences=experiences,
            role_name=role_name,
            role_description=role_description,
            target_skill=target_skill,
            difficulty=effective_difficulty,
            previous_questions=previous_questions,
            round_index=len(previous_questions),
        )

        # AB#328: medir tiempo de generación de texto
        t0_text = time.monotonic()
        try:
            generated_question = await self.azure_client.ask(
                question=prompt,
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=180,
            )
        except Exception as exc:
            raise RuntimeError(f"Error al generar pregunta con IA: {exc}") from exc
        text_elapsed_ms = int((time.monotonic() - t0_text) * 1000)

        if not generated_question or not generated_question.strip():
            raise RuntimeError("La IA no devolvió una pregunta válida")

        question_text = generated_question.strip()

        # AB#323 + AB#325: TTS encadenado con fallback no bloqueante
        tts_result = await self._generate_tts_with_fallback(question_text)

        # AB#328: construir metadata de trazabilidad para la ronda
        round_metadata = {
            "text_generation_ms": text_elapsed_ms,
            "tts_status": tts_result.tts_status,
            "tts_elapsed_ms": tts_result.tts_elapsed_ms,
        }
        if tts_result.tts_error:
            round_metadata["tts_error"] = tts_result.tts_error

        logger.info(
            "Round metadata | session=%s text_ms=%d tts_status=%s tts_ms=%s",
            session_code,
            text_elapsed_ms,
            tts_result.tts_status,
            tts_result.tts_elapsed_ms,
        )

        round_item = self.round_service.create_next_round(
            group_session_id=group_session.id,
            question_text=question_text,
            target_skill=target_skill,
            difficulty=effective_difficulty,
            created_by=requester_id,
            metadata_json=round_metadata,
        )

        # Task-066-07: persistir pregunta en tabla Question para cada InterviewSession del grupo
        self._persist_round_questions(group_session_id=group_session.id, round_item=round_item)

        # AB#323: construir payloads de eventos aquí, no en el router
        event_payloads = self._build_round_event_payloads(
            session_code=group_session.session_code,
            round_item=round_item,
            tts_result=tts_result,
        )

        return group_session, round_item, tts_result, event_payloads

    # ------------------------------------------------------------------
    # Persistencia de preguntas por ronda (Task-066-07)
    # ------------------------------------------------------------------

    def _persist_round_questions(self, *, group_session_id: int, round_item) -> None:
        """
        Crea un registro Question por cada InterviewSession participante del grupo.
        Operación best-effort: un fallo no interrumpe el flujo de la ronda.
        """
        try:
            interview_sessions = (
                self.db.query(InterviewSession)
                .filter(InterviewSession.group_interview_session_id == group_session_id)
                .all()
            )
            questions = [
                Question(
                    interview_session_id=iv_session.id,
                    question_text=round_item.question_text or "",
                    category=round_item.target_skill,
                    difficulty=round_item.difficulty,
                    expected_topics=None,
                    group_session_id=group_session_id,
                    round_index=round_item.round_index,
                )
                for iv_session in interview_sessions
            ]
            if questions:
                self.db.add_all(questions)
                self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception(
                "Error al persistir preguntas de ronda para group_session_id=%s",
                group_session_id,
            )

    # ------------------------------------------------------------------
    # Construcción de eventos (AB#323)
    # ------------------------------------------------------------------

    def _build_round_event_payloads(
        self,
        *,
        session_code: str,
        round_item,
        tts_result: TTSResult,
    ) -> RoundEventPayloads:
        """
        Construye los tres payloads de eventos para una ronda.
        El router solo hace broadcast; la lógica de decisión queda aquí.
        """
        emitted_at = datetime.now(timezone.utc).isoformat()
        round_id = str(round_item.id)

        round_started = {
            "event": "round_started",
            "session_code": session_code,
            "round_id": round_id,
            "round_index": round_item.round_index,
            "emitted_at": emitted_at,
        }

        question_generated = {
            "event": "question_generated",
            "session_code": session_code,
            "round_id": round_id,
            "round_index": round_item.round_index,
            "question_text": round_item.question_text,
            "target_skill": round_item.target_skill,
            "difficulty": round_item.difficulty,
            "emitted_at": emitted_at,
        }

        # AB#326: question_audio_ready solo si TTS ok; tts_error si falló
        if tts_result.tts_status == "ok":
            audio_event = {
                "event": "question_audio_ready",
                "session_code": session_code,
                "round_id": round_id,
                "round_index": round_item.round_index,
                "audio_b64": tts_result.audio_b64,
                "question_text": round_item.question_text,
                "emitted_at": emitted_at,
            }
        else:
            audio_event = {
                "event": "tts_error",
                "session_code": session_code,
                "round_id": round_id,
                "round_index": round_item.round_index,
                # AB#325: mensaje seguro, nunca detalle crudo del proveedor
                "tts_error": tts_result.tts_error or _TTS_SAFE_ERROR_MSG,
                "question_text": round_item.question_text,
                "emitted_at": emitted_at,
            }

        return RoundEventPayloads(
            round_started=round_started,
            question_generated=question_generated,
            audio_event=audio_event,
        )

    # ------------------------------------------------------------------
    # TTS con fallback (AB#323, AB#324, AB#325)
    # ------------------------------------------------------------------

    async def _generate_tts_with_fallback(self, text: str) -> TTSResult:
        """
        Intenta generar audio TTS con reintentos.
        Si falla: retorna TTSResult con tts_status="fallback", sin lanzar excepción.
        El mensaje de error expuesto al cliente es siempre el mensaje seguro.
        """
        if self._elevenlabs_client is None:
            logger.info("TTS deshabilitado (ElevenLabs no configurado), usando fallback de texto")
            return TTSResult(
                audio_b64=None,
                tts_status="fallback",
                tts_error=_TTS_SAFE_ERROR_MSG,
            )

        t0_tts = time.monotonic()
        try:
            audio_bytes = await self._elevenlabs_client.generate_speech_with_retry(text)
            tts_elapsed_ms = int((time.monotonic() - t0_tts) * 1000)
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            logger.info("TTS generado correctamente en %dms", tts_elapsed_ms)
            return TTSResult(audio_b64=audio_b64, tts_status="ok", tts_elapsed_ms=tts_elapsed_ms)
        except Exception as exc:
            tts_elapsed_ms = int((time.monotonic() - t0_tts) * 1000)
            # AB#325: loguear detalle interno pero NO exponer al cliente
            logger.warning(
                "TTS falló tras reintentos (%dms): %s. Continuando con fallback de texto.",
                tts_elapsed_ms,
                exc,
            )
            return TTSResult(
                audio_b64=None,
                tts_status="fallback",
                tts_error=_TTS_SAFE_ERROR_MSG,
                tts_elapsed_ms=tts_elapsed_ms,
            )
