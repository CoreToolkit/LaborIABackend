from fastapi import APIRouter, HTTPException

from ai.azure_speech_client import AzureSpeechClient
from ai.azure_speech_service import AzureSpeechService


router = APIRouter(
    prefix="/ai/azure-speech",
    tags=["azure-speech"],
)

azure_speech_init_error = None
azure_speech_service = None
azure_speech_client = None

try:
    azure_speech_service = AzureSpeechService()
    azure_speech_client = AzureSpeechClient(azure_speech_service)
except RuntimeError as exc:
    azure_speech_init_error = str(exc)


@router.get("/health")
async def health_check():
    if azure_speech_init_error:
        raise HTTPException(status_code=503, detail=azure_speech_init_error)

    is_healthy = await azure_speech_service.health_check()

    if is_healthy:
        return {
            "status": "healthy",
            "region": azure_speech_service.speech_region,
            "message": "Azure Speech esta configurado",
        }

    raise HTTPException(
        status_code=503,
        detail="Azure Speech no esta disponible o la configuracion no es valida",
    )
