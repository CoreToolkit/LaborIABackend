import os
from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncAzureOpenAI

load_dotenv()


class AzureOpenAIService:
    def __init__(
        self,
        endpoint: str = None,
        api_key: str = None,
        api_version: str = None,
        deployment_name: str = None,
        timeout: int = None,
    ):
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        self.deployment_name = deployment_name or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.timeout = timeout if timeout is not None else int(os.getenv("AZURE_OPENAI_TIMEOUT", "60"))

        missing = []
        if not self.endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if not self.deployment_name:
            missing.append("AZURE_OPENAI_DEPLOYMENT")

        self.missing_config = missing
        self.configured = not missing

        self.client = (
            AsyncAzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version=self.api_version,
                timeout=self.timeout,
            )
            if self.configured
            else None
        )

    def _require_configuration(self) -> None:
        if self.configured:
            return

        raise RuntimeError(f"Faltan variables de entorno de Azure OpenAI: {', '.join(self.missing_config)}")

    async def health_check(self) -> bool:
        """Verifica conectividad con Azure OpenAI mediante una llamada minima."""
        if not self.configured:
            return False

        try:
            response = await self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": "Responde solo: OK"}],
                max_tokens=5,
                temperature=0,
            )
            return bool(response.choices and response.choices[0].message)
        except Exception as e:
            print(f"Azure OpenAI no esta disponible: {e}")
            return False

    async def chat(
        self,
        user_prompt: str,
        system_prompt: str,
        temperature: float = None,
        max_tokens: int = 256,
        top_p: float = None,
    ) -> str:
        self._require_configuration()

        kwargs = {
            "model": self.deployment_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        }

        if temperature is not None:
            kwargs["temperature"] = temperature
        if top_p is not None:
            kwargs["top_p"] = top_p

        try:
            response = await self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content if response.choices else ""
            return (content or "").strip()

        except APITimeoutError:
            raise Exception(f"Timeout: Azure OpenAI tardó mas de {self.timeout}s")
        except APIConnectionError:
            raise Exception("No se pudo conectar a Azure OpenAI")
        except APIStatusError as e:
            detail = e.response.text if e.response is not None else str(e)
            raise Exception(f"Azure OpenAI devolvio error HTTP: {detail}")
        except Exception as e:
            raise Exception(f"Error en Azure OpenAI: {str(e)}")
