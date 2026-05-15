import os
import httpx
from dotenv import load_dotenv

load_dotenv()


class OllamaService:
    """
    Servicio para comunicación con Ollama.
    Maneja la instancia del modelo y la configuración de parámetros optimizados.
    """

    def __init__(
        self,
        base_url: str = None,
        model_name: str = None,
        timeout: int = None,
    ):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL")
        self.model_name = model_name or os.getenv("OLLAMA_MODEL")
        self.timeout = timeout if timeout is not None else int(os.getenv("OLLAMA_TIMEOUT", "120"))
        self.chat_endpoint = f"{self.base_url}/api/chat"
        self.generate_endpoint = f"{self.base_url}/api/generate"

    def _get_default_options(self) -> dict:
        """
        Retorna opciones optimizadas para evitar pensamiento excesivo y repeticiones.
        """
        return {
            "temperature": 0.1,          
            "num_predict": 512,          # Limita tokens de salida
            "repeat_penalty": 1.1,       # Penaliza repeticiones
            "top_p": 0.3,                # Top-p bajo = respuestas más enfocadas
            "top_k": 10,                 # Top-k bajo = menos divagación
            "num_ctx": 2048,             # Tamaño del contexto
        }

    async def health_check(self) -> bool:
        """Verifica si Ollama está disponible."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            print(f"Ollama no está disponible: {e}")
            return False

    async def chat(
        self,
        user_prompt: str,
        system_prompt: str,
        temperature: float = None,
        num_predict: int = None,
        stream: bool = False,
        think: bool = False,
    ) -> str:
        """
        Envía un mensaje al modelo y retorna la respuesta.

        Args:
            user_prompt: El mensaje del usuario
            system_prompt: Instrucciones del sistema
            temperature: Override de temperatura 
            num_predict: Override de tokens máximos 
            stream: Si True, retorna respuesta en streaming (no implementado aún)

        Returns:
            str: Contenido de la respuesta del modelo
        """
        options = self._get_default_options()

        if temperature is not None:
            options["temperature"] = temperature
        if num_predict is not None:
            options["num_predict"] = num_predict

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": stream,
            "think": think,
            "options": options,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.chat_endpoint, json=payload)
                response.raise_for_status()

                data = response.json()
                return data.get("message", {}).get("content", "").strip()

        except httpx.TimeoutException:
            raise Exception(f"Timeout: Ollama tardó más de {self.timeout}s en responder")
        except httpx.ConnectError:
            raise Exception(f"No se puede conectar a Ollama en {self.base_url}")
        except Exception as e:
            raise Exception(f"Error en Ollama: {str(e)}")

    async def generate(
        self,
        prompt: str,
        temperature: float = None,
        num_predict: int = None,
    ) -> str:
        """
        Modo generación simple.
        Útil para tareas más simples.
        """
        options = self._get_default_options()

        if temperature is not None:
            options["temperature"] = temperature
        if num_predict is not None:
            options["num_predict"] = num_predict

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.generate_endpoint, json=payload)
                response.raise_for_status()

                data = response.json()
                return data.get("response", "").strip()

        except httpx.TimeoutException:
            raise Exception(f"Timeout: Ollama tardó más de {self.timeout}s")
        except httpx.ConnectError:
            raise Exception(f"No se puede conectar a Ollama en {self.base_url}")
        except Exception as e:
            raise Exception(f"Error en Ollama: {str(e)}")
