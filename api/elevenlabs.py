import base64
import logging

from fastapi import APIRouter, Depends, HTTPException

from ai.elevenlabs_client import ElevenLabsClient
from ai.elevenlabs_service import ElevenLabsService
from core.jwt import get_current_user
from schemas.elevenlabs import ElevenLabsSpeechRequest, ElevenLabsSpeechResponse

logger = logging.getLogger(__name__)

# Mensajes seguros expuestos al cliente. No exponen detalles del proveedor.
_ERR_TTS_UNAVAILABLE = "El servicio de síntesis de voz no está disponible en este momento."
_ERR_TTS_INVALID_INPUT = "El texto proporcionado no es válido para síntesis de voz."


router = APIRouter(
    prefix="/ai/elevenlabs",
    tags=["elevenlabs"],
)

elevenlabs_init_error = None
elevenlabs_service = None
elevenlabs_client = None

try:
    elevenlabs_service = ElevenLabsService()
    elevenlabs_client = ElevenLabsClient(elevenlabs_service)
except RuntimeError as exc:
    elevenlabs_init_error = str(exc)


@router.get("/health")
async def health_check(current_user: dict = Depends(get_current_user)):
    if elevenlabs_init_error:
        raise HTTPException(status_code=503, detail=elevenlabs_init_error)

    is_healthy = await elevenlabs_client.health_check()

    if is_healthy:
        response = {
            "status": "healthy",
            "message": "ElevenLabs esta configurado",
            "model_id": elevenlabs_service.model_id,
        }

        if elevenlabs_service.voice_id:
            response["voice_id"] = elevenlabs_service.voice_id

        return response

    raise HTTPException(
        status_code=503,
        detail="ElevenLabs no esta disponible o la configuracion no es valida",
    )


@router.post("/speech")
async def generate_speech(
    body: ElevenLabsSpeechRequest,
    current_user: dict = Depends(get_current_user),
) -> ElevenLabsSpeechResponse:
    if elevenlabs_init_error:
        raise HTTPException(status_code=503, detail=_ERR_TTS_UNAVAILABLE)

    try:
        audio_bytes = await elevenlabs_client.generate_speech(body.text)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        return ElevenLabsSpeechResponse(audio=audio_base64)
    except HTTPException:
        raise
    except ValueError:
        # Error de validación de entrada (texto vacío, demasiado largo, etc.)
        raise HTTPException(status_code=400, detail=_ERR_TTS_INVALID_INPUT)
    except Exception as exc:
        # Loguear detalle interno pero NO exponer al cliente
        logger.warning("ElevenLabs speech generation failed: %s", exc)
        raise HTTPException(status_code=503, detail=_ERR_TTS_UNAVAILABLE)
