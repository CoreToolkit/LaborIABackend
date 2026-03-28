import os
import httpx
from dotenv import load_dotenv

load_dotenv()


class ElevenLabsService:
    def __init__(
        self,
        api_key: str = None,
        timeout: int = None,
        voice_id: str = None,
        base_url: str = None,
    ):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.timeout = timeout or int(os.getenv("ELEVENLABS_TIMEOUT", "30"))
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID")
        self.base_url = base_url or "https://api.elevenlabs.io/v1"

        if not self.api_key:
            raise RuntimeError("Falta la variable de entorno de ElevenLabs: ELEVENLABS_API_KEY")

        self.headers = {
            "xi-api-key": self.api_key,
            "Accept": "application/json",
        }
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
        )

    async def health_check(self) -> bool:
        """Verifica que la configuracion base de ElevenLabs este cargada."""
        try:
            return bool(self.api_key and self.client)
        except Exception as e:
            print(f"ElevenLabs no esta disponible: {e}")
            return False

    async def post(
        self,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)

        try:
            response = await self.client.post(
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
