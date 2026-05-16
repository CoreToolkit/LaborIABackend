from __future__ import annotations

from datetime import datetime, timezone

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


def is_intro_round(round_item) -> bool:
    metadata = getattr(round_item, "metadata_json", None)
    return isinstance(metadata, dict) and bool(metadata.get("is_intro"))


def build_intro_text(*, role_name: str, role_description: str) -> str:
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


def build_round_event_payloads(
    *,
    session_code: str,
    round_item,
    tts_result: TTSResult,
) -> RoundEventPayloads:
    """
    Construye los tres payloads de eventos para una ronda.
    Incluye assigned_user_id en todos los eventos para que el frontend
    pueda determinar quién debe grabar y responder.
    """
    emitted_at = datetime.now(timezone.utc).isoformat()
    round_id = str(round_item.id)
    is_intro = is_intro_round(round_item)
    assigned_user_id = round_item.assigned_user_id

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
