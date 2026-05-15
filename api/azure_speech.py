import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from ai.azure_speech_client import AzureSpeechClient
from ai.azure_speech_service import AzureSpeechService
from core.jwt import get_current_user


router = APIRouter(
    prefix="/ai/azure-speech",
    tags=["azure-speech"],
)

MAX_AUDIO_UPLOAD_BYTES = int(os.getenv("MAX_AUDIO_UPLOAD_BYTES", str(10 * 1024 * 1024)))
_READ_CHUNK_SIZE = 1024 * 1024


async def _read_upload_file_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = await file.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_AUDIO_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"El archivo de audio supera el limite de {MAX_AUDIO_UPLOAD_BYTES} bytes",
            )
        chunks.append(chunk)

    return b"".join(chunks)

azure_speech_init_error = None
azure_speech_service = None
azure_speech_client = None

try:
    azure_speech_service = AzureSpeechService()
    azure_speech_client = AzureSpeechClient(azure_speech_service)
except RuntimeError as exc:
    azure_speech_init_error = str(exc)


@router.get("/health")
async def health_check(current_user: dict = Depends(get_current_user)):
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


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        if azure_speech_init_error:
            raise HTTPException(status_code=503, detail=azure_speech_init_error)

        audio_bytes = await _read_upload_file_limited(file)
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="'file' es requerido")

        result = await run_in_threadpool(
            azure_speech_client.transcribe,
            audio_bytes,
            file.filename,
            language,
        )

        if not result:
            raise HTTPException(status_code=502, detail="Azure Speech no devolvio una transcripcion valida")

        return {"result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await file.close()


@router.post("/transcribe/diarization")
async def transcribe_audio_with_diarization(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        if azure_speech_init_error:
            raise HTTPException(status_code=503, detail=azure_speech_init_error)

        audio_bytes = await _read_upload_file_limited(file)
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="'file' es requerido")

        result = await run_in_threadpool(
            azure_speech_client.transcribe_with_diarization,
            audio_bytes,
        )

        if not isinstance(result, dict):
            raise HTTPException(status_code=502, detail="Azure Speech no devolvio diarizacion valida")

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await file.close()
