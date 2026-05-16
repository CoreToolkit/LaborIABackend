from ai.provider import LLMProvider
from core.config import settings


def create_llm_provider() -> LLMProvider:
    """
    Returns an LLMProvider based on settings.LLM_PROVIDER.
    Set LLM_PROVIDER=ollama in .env to switch to Ollama; defaults to "azure".
    """
    if settings.LLM_PROVIDER == "ollama":
        from ai.ollama_provider import OllamaProvider
        return OllamaProvider()
    from ai.azure_openai_provider import AzureOpenAIProvider
    return AzureOpenAIProvider()
