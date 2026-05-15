from ai.azure_openai_service import AzureOpenAIService


class AzureOpenAIClient:

    def __init__(self, service: AzureOpenAIService = None):
        self.service = service or AzureOpenAIService()

    async def ask(
        self,
        question: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = 256,
        top_p: float = None,
    ) -> str:
        
        if system_prompt is None:
            system_prompt = "Responde de forma concisa y directa."

        return await self.service.chat(
            user_prompt=question,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
