import gc
import os
import tempfile
import time
from pathlib import Path
from typing import Any
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

    def create_conversation_transcriber(self, audio_config):
        """Crea transcriber para diarizacion basica si el SDK lo soporta."""
        transcription_api = getattr(speechsdk, "transcription", None)
        if transcription_api is None or not hasattr(transcription_api, "ConversationTranscriber"):
            return None

        return transcription_api.ConversationTranscriber(
            speech_config=self.create_speech_config(),
            audio_config=audio_config,
        )

    def transcribe_with_diarization(self, audio_bytes: bytes) -> dict[str, Any]:
        """
        Transcribe audio con diarizacion basica por speaker sobre archivo completo.

        Si el entorno no soporta diarizacion, hace fallback a un unico speaker.
        """
        temp_path = None
        audio_config = None
        transcriber = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name

            audio_config = speechsdk.audio.AudioConfig(filename=temp_path)
            transcriber = self.create_conversation_transcriber(audio_config)

            # Fallback seguro cuando la feature no esta disponible en SDK/entorno.
            if transcriber is None:
                base_text = self.transcribe_audio(audio_bytes=audio_bytes, filename="audio.wav")
                return self._single_speaker_result(base_text)

            segments: list[dict[str, Any]] = []
            done = False

            def handle_transcribed(evt):
                result = getattr(evt, "result", None)
                if result is None:
                    return

                text = (getattr(result, "text", None) or "").strip()
                if not text:
                    return

                speaker_id = getattr(result, "speaker_id", None) or getattr(result, "speakerId", None)
                segments.append({
                    "speaker": self._normalize_speaker_id(speaker_id),
                    "text": text,
                })

            def handle_stop(_):
                nonlocal done
                done = True

            transcriber.transcribed.connect(handle_transcribed)
            transcriber.session_stopped.connect(handle_stop)
            transcriber.canceled.connect(handle_stop)

            transcriber.start_transcribing_async().get()
            while not done:
                time.sleep(0.1)
            transcriber.stop_transcribing_async().get()

            if not segments:
                base_text = self.transcribe_audio(audio_bytes=audio_bytes, filename="audio.wav")
                return self._single_speaker_result(base_text)

            full_text = " ".join(segment["text"] for segment in segments).strip()
            return {
                "text": full_text,
                "segments": segments,
            }
        except Exception as e:
            raise Exception(f"Error en Azure Speech diarization: {str(e)}")
        finally:
            transcriber = None
            audio_config = None
            gc.collect()
            self._cleanup_temp_file(temp_path)

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
            self._cleanup_temp_file(temp_path)

    def _single_speaker_result(self, text: str) -> dict[str, Any]:
        normalized_text = (text or "").strip()
        if not normalized_text:
            return {
                "text": "",
                "segments": [],
            }

        return {
            "text": normalized_text,
            "segments": [
                {
                    "speaker": "speaker_1",
                    "text": normalized_text,
                }
            ],
        }

    def _normalize_speaker_id(self, speaker_id: Any) -> str:
        if speaker_id in (None, "", "Unknown"):
            return "speaker_unknown"
        return f"speaker_{speaker_id}"

    def _cleanup_temp_file(self, temp_path: str | None):
        if temp_path and os.path.exists(temp_path):
            for attempt in range(5):
                try:
                    os.remove(temp_path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.1)
