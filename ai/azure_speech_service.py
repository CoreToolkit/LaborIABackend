import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

load_dotenv()


class AzureSpeechService:
    def __init__(
        self,
        speech_key: str = None,
        speech_region: str = None,
    ):
        self.speech_key = speech_key or os.getenv("SPEECH_KEY")
        self.speech_region = speech_region or os.getenv("SPEECH_REGION")

        missing = []
        if not self.speech_key:
            missing.append("SPEECH_KEY")
        if not self.speech_region:
            missing.append("SPEECH_REGION")

        if missing:
            raise RuntimeError(f"Faltan variables de entorno de Azure Speech: {', '.join(missing)}")

        self.speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region,
        )

    async def health_check(self) -> bool:
        """Verifica que la configuracion base de Azure Speech este cargada."""
        try:
            return self.speech_config is not None
        except Exception as e:
            print(f"Azure Speech no esta disponible: {e}")
            return False

    def create_speech_recognizer(self, audio_config):
        """Crea un reconocedor base listo para una transcripcion futura."""
        return speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=audio_config,
        )
