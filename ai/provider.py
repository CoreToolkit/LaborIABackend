from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def ask(
        self,
        question: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = 256,
        **kwargs,
    ) -> str: ...
