import gc
import os
import tempfile
import time
from pathlib import Path
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

    def create_speech_config(self, language: str = None):
        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region,
        )

        if language:
            speech_config.speech_recognition_language = language

        return speech_config

    def create_speech_recognizer(self, audio_config, language: str = None):
        """Crea un reconocedor base listo para una transcripcion futura."""
        return speechsdk.SpeechRecognizer(
            speech_config=self.create_speech_config(language=language),
            audio_config=audio_config,
        )

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = None,
        language: str = None,
    ) -> str:
        temp_path = None
        suffix = Path(filename or "").suffix
        audio_config = None
        recognizer = None
        result = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name

            audio_config = speechsdk.audio.AudioConfig(filename=temp_path)
            recognizer = self.create_speech_recognizer(audio_config, language=language)
            result = recognizer.recognize_once_async().get()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                return (result.text or "").strip()

            if result.reason == speechsdk.ResultReason.NoMatch:
                return ""

            if result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                detail = f"Azure Speech canceló la transcripcion: {cancellation_details.reason}"

                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    error_details = cancellation_details.error_details or "Sin detalles adicionales"
                    detail = f"{detail}. {error_details}"

                raise Exception(detail)

            return ""
        except Exception as e:
            raise Exception(f"Error en Azure Speech: {str(e)}")
        finally:
            result = None
            recognizer = None
            audio_config = None
            gc.collect()

            if temp_path and os.path.exists(temp_path):
                for attempt in range(5):
                    try:
                        os.remove(temp_path)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.1)
