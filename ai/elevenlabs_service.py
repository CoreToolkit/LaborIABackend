import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MAX_TTS_TEXT_LENGTH = 500
_DEFAULT_TIMEOUT = 30
_DEFAULT_MAX_RETRIES = 2
_RETRY_BACKOFF_BASE = 1.0  # segundos; espera = base * intento


class ElevenLabsService:
    def __init__(
        self,
        api_key: str = None,
        timeout: int = None,
        voice_id: str = None,
        model_id: str = None,
        base_url: str = None,
        max_retries: int = None,
    ):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.timeout = timeout or int(os.getenv("ELEVENLABS_TIMEOUT", str(_DEFAULT_TIMEOUT)))
        self.max_retries = max_retries if max_retries is not None else int(
            os.getenv("ELEVENLABS_MAX_RETRIES", str(_DEFAULT_MAX_RETRIES))
        )
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID")
        self.model_id = model_id or os.getenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
        self.base_url = base_url or "https://api.elevenlabs.io/v1"

        if not self.api_key:
            raise RuntimeError("Falta la variable de entorno de ElevenLabs: ELEVENLABS_API_KEY")

        self.headers = {
            "xi-api-key": self.api_key,
            "Accept": "application/json",
        }
        # El cliente se crea por llamada en post() para evitar problemas de
        # ciclo de vida con httpx.AsyncClient (AB#325 revisión de recursos).
        self._client_defaults = {
            "base_url": self.base_url,
            "headers": self.headers,
            "timeout": self.timeout,
        }

    async def health_check(self) -> bool:
        """Verifica que la configuracion base de ElevenLabs este cargada."""
        try:
            return bool(self.api_key)
        except Exception as e:
            logger.warning("ElevenLabs no esta disponible: %s", e)
            return False

    async def post(
        self,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """
        Realiza POST con timeout explícito usando un cliente por llamada.
        Sin reintentos (usar generate_speech_with_retry para eso).
        El cliente se cierra correctamente al salir del bloque async with.
        """
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)

        try:
            async with httpx.AsyncClient(**self._client_defaults) as client:
                response = await client.post(
                    path,
                    json=json,
                    params=params,
                    headers=request_headers,
                )
                response.raise_for_status()
                return response
        except httpx.TimeoutException:
            raise Exception(f"Timeout: ElevenLabs tardó más de {self.timeout}s")
        except httpx.ConnectError:
            raise Exception(f"No se puede conectar a ElevenLabs en {self.base_url}")
        except httpx.HTTPStatusError as e:
            detail = e.response.text if e.response is not None else str(e)
            raise Exception(f"ElevenLabs devolvió error HTTP: {detail}")
        except Exception as e:
            raise Exception(f"Error en ElevenLabs: {str(e)}")

    async def generate_speech(self, text: str) -> bytes:
        """Genera audio TTS sin reintentos. Lanza excepción en caso de fallo."""
        normalized_text = (text or "").strip()
        if not normalized_text:
            raise ValueError("'text' es requerido")

        if len(normalized_text) > MAX_TTS_TEXT_LENGTH:
            raise ValueError(f"'text' no puede superar {MAX_TTS_TEXT_LENGTH} caracteres")

        if not self.voice_id:
            raise RuntimeError("Falta la variable de entorno de ElevenLabs: ELEVENLABS_VOICE_ID")

        response = await self.post(
            path=f"/text-to-speech/{self.voice_id}",
            json={
                "text": normalized_text,
                "model_id": self.model_id,
            },
            params={"output_format": "mp3_44100_128"},
            headers={"Accept": "audio/mpeg"},
        )

        audio_bytes = response.content
        if not audio_bytes:
            raise Exception("ElevenLabs no devolvió audio válido")

        return audio_bytes

    async def generate_speech_with_retry(self, text: str) -> bytes:
        """
        Genera audio TTS con reintentos limitados y backoff.

        Reintentos: max_retries (default 2). No reintenta errores de validación (ValueError).
        Lanza la última excepción si todos los intentos fallan.
        """
        last_exc: Exception | None = None
        attempts = self.max_retries + 1  # 1 intento base + reintentos

        for attempt in range(attempts):
            try:
                return await self.generate_speech(text)
            except ValueError:
                # Error de validación de entrada: no tiene sentido reintentar
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < attempts - 1:
                    wait = _RETRY_BACKOFF_BASE * (attempt + 1)
                    logger.warning(
                        "ElevenLabs TTS fallo (intento %d/%d): %s. Reintentando en %.1fs...",
                        attempt + 1,
                        attempts,
                        exc,
                        wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        "ElevenLabs TTS fallo definitivamente tras %d intentos: %s",
                        attempts,
                        exc,
                    )

        raise last_exc
