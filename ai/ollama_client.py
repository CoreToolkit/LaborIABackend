from ai.ollama_service import OllamaService


class OllamaClient:
    """
    Cliente para consumir el servicio de Ollama.
    """

    def __init__(self, service: OllamaService = None):
        self.service = service or OllamaService()

    async def ask(
        self,
        question: str,
        system_prompt: str = None,
        temperature: float = None,
        num_predict: int = 256,
    ) -> str:
        """
        Hacer una pregunta genérica al modelo.

        Args:
            question: La pregunta
            system_prompt: Instrucciones personalizadas 
            temperature: Control sobre aleatoriedad 
            num_predict: Máximo de tokens a generar

        Returns:
            str: Respuesta del modelo
        """
        if system_prompt is None:
            system_prompt = "Responde de forma concisa y directa."

        return await self.service.chat(
            user_prompt=question,
            system_prompt=system_prompt,
            temperature=temperature,
            num_predict=num_predict,
        )
