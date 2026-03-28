import base64

from fastapi import APIRouter, Depends, HTTPException

from ai.elevenlabs_client import ElevenLabsClient
from ai.elevenlabs_service import ElevenLabsService
from core.jwt import get_current_user
from schemas.elevenlabs import ElevenLabsSpeechRequest, ElevenLabsSpeechResponse


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
    try:
        if elevenlabs_init_error:
            raise HTTPException(status_code=503, detail=elevenlabs_init_error)

        text = body.text
        if not text or not str(text).strip():
            raise HTTPException(status_code=400, detail="'text' es requerido")

        audio_bytes = await elevenlabs_client.generate_speech(str(text))
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return ElevenLabsSpeechResponse(audio=audio_base64)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
