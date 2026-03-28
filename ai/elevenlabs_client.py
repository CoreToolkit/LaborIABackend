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
