from ai.elevenlabs_service import ElevenLabsService


class ElevenLabsClient:
    def __init__(self, service: ElevenLabsService = None):
        self.service = service or ElevenLabsService()

    async def health_check(self) -> bool:
        return await self.service.health_check()

    async def post(
        self,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ):
        return await self.service.post(
            path=path,
            json=json,
            params=params,
            headers=headers,
        )

    async def generate_speech(self, text: str) -> bytes:
        return await self.service.generate_speech(text)

    async def generate_speech_with_retry(self, text: str) -> bytes:
        """Genera audio TTS con reintentos limitados. Delega a ElevenLabsService."""
        return await self.service.generate_speech_with_retry(text)
