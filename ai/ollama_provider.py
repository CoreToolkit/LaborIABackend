from ai.ollama_client import OllamaClient
from ai.provider import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, client: OllamaClient = None):
        self._client = client or OllamaClient()

    async def ask(
        self,
        question: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = 256,
        **kwargs,
    ) -> str:
        return await self._client.ask(
            question=question,
            system_prompt=system_prompt,
            temperature=temperature,
            num_predict=max_tokens,
        )
