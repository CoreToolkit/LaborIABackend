from ai.azure_openai_client import AzureOpenAIClient
from ai.provider import LLMProvider


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, client: AzureOpenAIClient = None):
        self._client = client or AzureOpenAIClient()

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
            max_tokens=max_tokens,
            top_p=kwargs.get("top_p"),
        )
