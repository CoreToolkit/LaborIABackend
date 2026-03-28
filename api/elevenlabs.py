from fastapi import APIRouter, Depends, HTTPException

from ai.elevenlabs_client import ElevenLabsClient
from ai.elevenlabs_service import ElevenLabsService
from core.jwt import get_current_user


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
