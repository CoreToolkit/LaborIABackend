from __future__ import annotations

import base64
import logging
import time
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ai.provider import LLMProvider
from ai.question_deduplication import (
    MAX_GENERATION_ATTEMPTS,
    is_repeated_or_too_similar,
    merge_previous_questions,
)
from exceptions.profile_exceptions import ProfileNotFoundError
from models.interview_session import InterviewSession
from models.question import Question
from services.group_interview_round_service import GroupInterviewRoundService
from services.group_interview_session_service import GroupInterviewSessionService
from services.global_question_service import GlobalQuestionService
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
    def __init__(self, db, llm_provider: LLMProvider | None = None):
        self.db = db
        self.profile_service = ProfileService(db)
        self.group_session_service = GroupInterviewSessionService(db)
        self.round_service = GroupInterviewRoundService(db)
        self.global_question_service = GlobalQuestionService(db)
        if llm_provider is not None:
            self._llm_provider: LLMProvider | None = llm_provider
        else:
            try:
                from ai.provider_factory import create_llm_provider
                self._llm_provider = create_llm_provider()
            except Exception as exc:
                logger.warning("LLM provider not available: %s", exc)
                self._llm_provider = None

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
        Encadena: seleccionar participante → generar pregunta (IA) → TTS (ElevenLabs) → persistir ronda.

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

        # ── Seleccionar participante asignado (round-robin) ────────────────
        assigned_user_id = self._select_assigned_participant(group_session)

        # ── Obtener perfil del participante asignado para personalizar la pregunta ──
        if assigned_user_id is not None:
            try:
                profile = self.profile_service.get_profile_by_user_id(assigned_user_id)
                skills = self.profile_service.list_skills(assigned_user_id)
                experiences = self.profile_service.list_experiences(assigned_user_id)
            except (ProfileNotFoundError, Exception):
                # Fallback al perfil del host si el asignado no tiene perfil
                logger.warning(
                    "Perfil no encontrado para assigned_user_id=%s, usando perfil del host",
                    assigned_user_id,
                )
                profile = self.profile_service.get_profile_by_user_id(requester_id)
                if not profile:
                    raise ProfileNotFoundError()
                skills = self.profile_service.list_skills(requester_id)
                experiences = self.profile_service.list_experiences(requester_id)
        else:
            profile = self.profile_service.get_profile_by_user_id(requester_id)
            if not profile:
                raise ProfileNotFoundError()
            skills = self.profile_service.list_skills(requester_id)
            experiences = self.profile_service.list_experiences(requester_id)

        effective_difficulty = difficulty or group_session.difficulty or "adaptive"
        previous_rounds = self.round_service.round_repo.list_by_session_id(group_session.id)
        session_round_count = len(
            [item for item in previous_rounds if not self._is_intro_round(item)]
        )
        global_previous_questions = self.global_question_service.list_all_questions_texts()

        role_name = group_session.role.name if group_session.role else "rol tecnico"
        role_description = group_session.role.description if group_session.role else ""

        generated_question = ""
        generated_in_request: list[str] = []
        retried = False

        # AB#328: medir tiempo de generación de texto
        t0_text = time.monotonic()
        for attempt in range(MAX_GENERATION_ATTEMPTS):
            combined_previous = merge_previous_questions(
                global_previous_questions,
                generated_in_request,
            )

            system_prompt, prompt = build_group_question_generation_prompts(
                profile=profile,
                skills=skills,
                experiences=experiences,
                role_name=role_name,
                role_description=role_description,
                target_skill=target_skill,
                difficulty=effective_difficulty,
                previous_questions=combined_previous,
                round_index=session_round_count,
            )

            if attempt > 0:
                retried = True
                forbidden_examples = "\n".join(f"- {item}" for item in combined_previous[-8:])
                system_prompt = (
                    f"{system_prompt} Nunca repitas preguntas previas, incluso con redacciones similares. "
                    f"Preguntas prohibidas:\n{forbidden_examples}"
                )

            try:
                generated_question = await self._llm_provider.ask(
                    question=prompt,
                    system_prompt=system_prompt,
                    temperature=0.8,
                    max_tokens=180,
                )
            except Exception as exc:
                raise RuntimeError(f"Error al generar pregunta con IA: {exc}") from exc

            if generated_question and not is_repeated_or_too_similar(
                generated_question, combined_previous
            ):
                break

            if generated_question:
                generated_in_request.append(generated_question)

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
            "is_intro": False,
            "retried_for_uniqueness": retried,
        }
        if tts_result.tts_error:
            round_metadata["tts_error"] = tts_result.tts_error

        logger.info(
            "Round metadata | session=%s text_ms=%d tts_status=%s tts_ms=%s assigned_user=%s",
            session_code,
            text_elapsed_ms,
            tts_result.tts_status,
            tts_result.tts_elapsed_ms,
            assigned_user_id,
        )

        round_item = self.round_service.create_next_round(
            group_session_id=group_session.id,
            question_text=question_text,
            target_skill=target_skill,
            difficulty=effective_difficulty,
            created_by=requester_id,
            metadata_json=round_metadata,
            assigned_user_id=assigned_user_id,
        )

        self.global_question_service.record_question(question_text)

        # Task-066-07: persistir pregunta en tabla Question para cada InterviewSession del grupo
        self._persist_round_questions(group_session_id=group_session.id, round_item=round_item)

        # AB#323: construir payloads de eventos aquí, no en el router
        event_payloads = self._build_round_event_payloads(
            session_code=group_session.session_code,
            round_item=round_item,
            tts_result=tts_result,
        )

        return group_session, round_item, tts_result, event_payloads

    async def generate_intro_round(
        self,
        session_code: str,
        requester_id: int,
    ):
        """
        Genera y emite la introduccion inicial (una sola vez) con TTS.
        Retorna (group_session, round_item, tts_result, event_payloads) o None si ya existe una ronda.
        La intro no asigna participante (assigned_user_id=None).
        """
        group_session = self.group_session_service.get_group_session_by_code(session_code)

        if group_session.host_id != requester_id:
            raise PermissionError("Solo el host puede iniciar la introduccion")

        if group_session.status != "in_progress":
            raise ValueError("La sesión grupal debe estar en estado 'in_progress'")

        previous_rounds = self.round_service.round_repo.list_by_session_id(group_session.id)
        if previous_rounds:
            return None

        role_name = group_session.role.name if group_session.role else "rol tecnico"
        role_description = group_session.role.description if group_session.role else ""
        intro_text = self._build_intro_text(role_name=role_name, role_description=role_description)

        tts_result = await self._generate_tts_with_fallback(intro_text)

        round_metadata = {
            "text_generation_ms": 0,
            "tts_status": tts_result.tts_status,
            "tts_elapsed_ms": tts_result.tts_elapsed_ms,
            "is_intro": True,
        }
        if tts_result.tts_error:
            round_metadata["tts_error"] = tts_result.tts_error

        # La intro no tiene participante asignado (assigned_user_id=None)
        round_item = self.round_service.create_next_round(
            group_session_id=group_session.id,
            question_text=intro_text,
            target_skill=None,
            difficulty=group_session.difficulty or "intro",
            created_by=requester_id,
            metadata_json=round_metadata,
            assigned_user_id=None,
        )

        event_payloads = self._build_round_event_payloads(
            session_code=group_session.session_code,
            round_item=round_item,
            tts_result=tts_result,
        )

        return group_session, round_item, tts_result, event_payloads

    # ------------------------------------------------------------------
    # Selección de participante (round-robin)
    # ------------------------------------------------------------------

    def _select_assigned_participant(self, group_session) -> int | None:
        """
        Selecciona el participante al que corresponde responder en esta ronda
        usando un algoritmo round-robin estricto:

        1. Obtiene todos los user_id con InterviewSession en la sala.
        2. Obtiene el historial de assigned_user_id de rondas previas no-intro.
        3. Elige al que haya respondido menos veces. En empate: el que llegó primero
           (menor interview_session.id) y no sea el último asignado.
        4. Si solo hay 1 participante, siempre le toca a él.
        5. Si no hay participantes, retorna None.
        """
        interview_sessions = (
            self.db.query(InterviewSession)
            .filter(InterviewSession.group_interview_session_id == group_session.id)
            .order_by(InterviewSession.id.asc())
            .all()
        )

        if not interview_sessions:
            logger.warning(
                "No hay participantes con InterviewSession en la sesión %s; "
                "se omite asignación de participante.",
                group_session.id,
            )
            return None

        participant_ids: list[int] = [s.user_id for s in interview_sessions]

        if len(participant_ids) == 1:
            return participant_ids[0]

        # Historial de asignaciones previas (solo rondas no-intro)
        previous_assignments = self.round_service.round_repo.get_assigned_user_ids_in_session(
            group_session.id
        )

        last_assigned = previous_assignments[-1] if previous_assignments else None
        assignment_counts = Counter(previous_assignments)

        # Candidatos: todos los participantes con el menor número de asignaciones
        min_count = min(assignment_counts.get(uid, 0) for uid in participant_ids)
        candidates = [
            uid for uid in participant_ids
            if assignment_counts.get(uid, 0) == min_count
        ]

        # Si hay varios candidatos con el mismo conteo, excluir el último asignado
        # (para evitar dos veces seguidas la misma persona)
        if len(candidates) > 1 and last_assigned in candidates:
            candidates = [uid for uid in candidates if uid != last_assigned]

        # Elegir el primero en el orden de ingreso a la sala
        return candidates[0]

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
        Incluye assigned_user_id en todos los eventos para que el frontend
        pueda determinar quién debe grabar y responder.
        El router solo hace broadcast; la lógica de decisión queda aquí.
        """
        emitted_at = datetime.now(timezone.utc).isoformat()
        round_id = str(round_item.id)
        is_intro = self._is_intro_round(round_item)
        assigned_user_id = round_item.assigned_user_id  # None en la intro

        round_started = {
            "event": "round_started",
            "session_code": session_code,
            "round_id": round_id,
            "round_index": round_item.round_index,
            "is_intro": is_intro,
            "assigned_user_id": assigned_user_id,
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
            "is_intro": is_intro,
            "assigned_user_id": assigned_user_id,
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
                "is_intro": is_intro,
                "assigned_user_id": assigned_user_id,
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
                "is_intro": is_intro,
                "assigned_user_id": assigned_user_id,
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

    @staticmethod
    def _is_intro_round(round_item) -> bool:
        metadata = getattr(round_item, "metadata_json", None)
        if isinstance(metadata, dict):
            return bool(metadata.get("is_intro"))
        return False

    @staticmethod
    def _build_intro_text(*, role_name: str, role_description: str) -> str:
        role_name = role_name.strip() or "rol tecnico"
        role_description = role_description.strip()
        intro = (
            "Bienvenidos a la entrevista grupal de LaborIA. "
            f"Nos enfocaremos en el rol {role_name}. "
        )
        if role_description:
            intro += f"Este rol se centra en {role_description}. "
        intro += (
            "Hablaremos de tu experiencia, los retos mas comunes del rol y "
            "como abordarias situaciones reales. Empecemos."
        )
        return intro
