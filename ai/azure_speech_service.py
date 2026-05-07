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

        # Silencio inicial: dar hasta 15s antes de rendirse si el usuario
        # tarda en empezar a hablar (por defecto son 5s → causa 422).
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,
            "15000",
        )

        # Silencio al final del habla: cuánto esperar tras la última palabra
        # antes de cerrar el segmento. 2000ms da margen para pausas naturales
        # entre frases sin cortar la respuesta prematuramente.
        speech_config.set_property(
            speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs,
            "2000",
        )

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

    def transcribe_compressed_audio(self, audio_bytes: bytes, language: str = None) -> str:
        """
        Transcribe audio comprimido (webm/opus del navegador) usando PushAudioInputStream.
        El método estándar transcribe_audio falla con webm porque espera cabecera WAV.
        """
        push_stream = None
        recognizer = None

        try:
            container_formats = [
                getattr(speechsdk.AudioStreamContainerFormat, "WEBM_OPUS", None),
                getattr(speechsdk.AudioStreamContainerFormat, "ANY", None),
                getattr(speechsdk.AudioStreamContainerFormat, "OGG_OPUS", None),
            ]
            container_format = next((f for f in container_formats if f is not None), None)

            if container_format is None:
                raise Exception("El SDK de Azure Speech no soporta formatos de audio comprimido en este entorno.")

            stream_format = speechsdk.audio.AudioStreamFormat.get_compressed_format_for_pull_stream(container_format)
            push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
            audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.create_speech_config(language=language),
                audio_config=audio_config,
            )

            push_stream.write(audio_bytes)
            push_stream.close()
            push_stream = None

            result = recognizer.recognize_once_async().get()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                return (result.text or "").strip()

            if result.reason == speechsdk.ResultReason.NoMatch:
                return ""

            if result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                detail = f"Azure Speech canceló: {cancellation.reason}"
                if cancellation.reason == speechsdk.CancellationReason.Error:
                    detail += f". {cancellation.error_details or ''}"
                raise Exception(detail)

            return ""
        except Exception as e:
            raise Exception(f"Error en Azure Speech (compressed): {str(e)}")
        finally:
            recognizer = None
            if push_stream:
                try:
                    push_stream.close()
                except Exception:
                    pass
            gc.collect()

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = None,
        language: str = None,
    ) -> str:
        """
        Transcribe el audio completo usando reconocimiento continuo.
        """
        temp_path = None
        suffix = Path(filename or "").suffix or ".wav"
        audio_config = None
        recognizer = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name

            audio_config = speechsdk.audio.AudioConfig(filename=temp_path)
            recognizer = self.create_speech_recognizer(audio_config, language=language)

            all_text_parts: list[str] = []
            done_event = False
            recognition_error: Exception | None = None

            def on_recognized(evt):
                result = getattr(evt, "result", None)
                if result is None:
                    return
                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    text = (result.text or "").strip()
                    if text:
                        all_text_parts.append(text)

            def on_session_stopped(_):
                nonlocal done_event
                done_event = True

            def on_canceled(evt):
                nonlocal done_event, recognition_error
                done_event = True
                result = getattr(evt, "result", None)
                if result is None:
                    return
                if result.reason == speechsdk.ResultReason.Canceled:
                    cancellation = result.cancellation_details
                    if cancellation.reason == speechsdk.CancellationReason.Error:
                        detail = f"Azure Speech canceló la transcripcion: {cancellation.reason}. {cancellation.error_details or ''}"
                        recognition_error = Exception(detail)

            recognizer.recognized.connect(on_recognized)
            recognizer.session_stopped.connect(on_session_stopped)
            recognizer.canceled.connect(on_canceled)

            recognizer.start_continuous_recognition_async().get()

            # Esperar a que el SDK termine de procesar todo el archivo
            timeout_s = 120
            elapsed = 0.0
            while not done_event and elapsed < timeout_s:
                time.sleep(0.1)
                elapsed += 0.1

            recognizer.stop_continuous_recognition_async().get()

            if recognition_error:
                raise recognition_error

            return " ".join(all_text_parts).strip()

        except Exception as e:
            raise Exception(f"Error en Azure Speech: {str(e)}")
        finally:
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
