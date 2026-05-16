import os
from types import SimpleNamespace

import pytest
from core.config import settings as app_settings

os.environ.setdefault("SPEECH_KEY", "test-speech-key")
os.environ.setdefault("SPEECH_REGION", "eastus")

import ai.azure_speech_service as azure_speech_service_module
from ai.azure_speech_client import AzureSpeechClient
from ai.azure_speech_service import AzureSpeechService


class _FakeSpeechConfig:
    def __init__(self, subscription, region):
        self.subscription = subscription
        self.region = region
        self.speech_recognition_language = None


class _FakeAudioConfig:
    def __init__(self, filename):
        self.filename = filename


class _FakeSpeechSdk:
    SpeechConfig = _FakeSpeechConfig
    audio = SimpleNamespace(AudioConfig=_FakeAudioConfig)
    ResultReason = SimpleNamespace(
        RecognizedSpeech="recognized",
        NoMatch="no-match",
        Canceled="canceled",
    )
    CancellationReason = SimpleNamespace(Error="error")


def test_azure_speech_client_delegates_to_service():
    calls = []

    class DummyService:
        def transcribe_audio(self, audio_bytes, filename=None, language=None):
            calls.append(
                {
                    "audio_bytes": audio_bytes,
                    "filename": filename,
                    "language": language,
                }
            )
            return "delegated text"

    client = AzureSpeechClient(DummyService())

    result = client.transcribe(b"audio-bytes", filename="clip.wav", language="es-CO")

    assert result == "delegated text"
    assert calls == [
        {
            "audio_bytes": b"audio-bytes",
            "filename": "clip.wav",
            "language": "es-CO",
        }
    ]


def test_azure_speech_client_delegates_diarization_to_service():
    calls = []

    class DummyService:
        def transcribe_with_diarization(self, audio_bytes):
            calls.append({"audio_bytes": audio_bytes})
            return {"text": "hola", "segments": [{"speaker": "speaker_1", "text": "hola"}]}

    client = AzureSpeechClient(DummyService())

    result = client.transcribe_with_diarization(b"audio-bytes")

    assert result["text"] == "hola"
    assert calls == [{"audio_bytes": b"audio-bytes"}]


def test_azure_speech_service_returns_text_when_transcription_succeeds(monkeypatch):
    captured = {}

    class Signal:
        def __init__(self):
            self.handlers = []

        def connect(self, handler):
            self.handlers.append(handler)

    class DummyRecognizer:
        def __init__(self):
            self.recognized = Signal()
            self.session_stopped = Signal()
            self.canceled = Signal()

        def start_continuous_recognition_async(self):
            def _run():
                # Simula un evento de reconocimiento exitoso
                for handler in self.recognized.handlers:
                    handler(SimpleNamespace(
                        result=SimpleNamespace(
                            reason=azure_speech_service_module.speechsdk.ResultReason.RecognizedSpeech,
                            text="Texto transcrito",
                        )
                    ))
                # Simula fin de sesión
                for handler in self.session_stopped.handlers:
                    handler(SimpleNamespace())
                return None

            return SimpleNamespace(get=_run)

        def stop_continuous_recognition_async(self):
            return SimpleNamespace(get=lambda: None)

    def fake_create_speech_recognizer(self, audio_config, language=None):
        captured["filename"] = audio_config.filename
        captured["language"] = language
        return DummyRecognizer()

    monkeypatch.setattr(azure_speech_service_module, "speechsdk", _FakeSpeechSdk)
    monkeypatch.setattr(AzureSpeechService, "create_speech_recognizer", fake_create_speech_recognizer)

    service = AzureSpeechService(speech_key="key", speech_region="region")

    result = service.transcribe_audio(
        b"fake audio bytes",
        filename="clip.wav",
        language="es-CO",
    )

    assert result == "Texto transcrito"
    assert captured["language"] == "es-CO"
    assert captured["filename"].endswith(".wav")
    assert not os.path.exists(captured["filename"])


def test_azure_speech_service_wraps_provider_errors(monkeypatch):
    class Signal:
        def __init__(self):
            self.handlers = []

        def connect(self, handler):
            self.handlers.append(handler)

    class DummyRecognizer:
        def __init__(self):
            self.recognized = Signal()
            self.session_stopped = Signal()
            self.canceled = Signal()

        def start_continuous_recognition_async(self):
            def _run():
                raise Exception("provider failed")

            return SimpleNamespace(get=_run)

        def stop_continuous_recognition_async(self):
            return SimpleNamespace(get=lambda: None)

    def fake_create_speech_recognizer(self, audio_config, language=None):
        return DummyRecognizer()

    monkeypatch.setattr(azure_speech_service_module, "speechsdk", _FakeSpeechSdk)
    monkeypatch.setattr(AzureSpeechService, "create_speech_recognizer", fake_create_speech_recognizer)

    service = AzureSpeechService(speech_key="key", speech_region="region")

    with pytest.raises(Exception, match="Error en Azure Speech: provider failed"):
        service.transcribe_audio(b"fake audio bytes", filename="clip.wav")


def test_azure_speech_service_requires_configuration(monkeypatch):
    monkeypatch.setattr(app_settings, "SPEECH_KEY", None)
    monkeypatch.setattr(app_settings, "SPEECH_REGION", None)
    monkeypatch.setattr(azure_speech_service_module, "speechsdk", _FakeSpeechSdk)

    with pytest.raises(RuntimeError, match="Faltan variables de entorno de Azure Speech: SPEECH_KEY, SPEECH_REGION"):
        AzureSpeechService()


def test_transcribe_with_diarization_falls_back_to_single_speaker(monkeypatch):
    monkeypatch.setattr(azure_speech_service_module, "speechsdk", _FakeSpeechSdk)
    monkeypatch.setattr(
        AzureSpeechService,
        "transcribe_audio",
        lambda self, audio_bytes, filename=None, language=None: "texto fallback",
    )

    service = AzureSpeechService(speech_key="key", speech_region="region")

    result = service.transcribe_with_diarization(b"fake audio bytes")

    assert result["text"] == "texto fallback"
    assert result["segments"] == [{"speaker": "speaker_1", "text": "texto fallback"}]


def test_transcribe_with_diarization_returns_speaker_segments(monkeypatch):
    class Signal:
        def __init__(self):
            self.handlers = []

        def connect(self, handler):
            self.handlers.append(handler)

        def emit(self, evt):
            for handler in self.handlers:
                handler(evt)

    class DummyTranscriber:
        def __init__(self):
            self.transcribed = Signal()
            self.session_stopped = Signal()
            self.canceled = Signal()

        def start_transcribing_async(self):
            def _run():
                self.transcribed.emit(
                    SimpleNamespace(result=SimpleNamespace(text="hola", speaker_id=1))
                )
                self.transcribed.emit(
                    SimpleNamespace(result=SimpleNamespace(text="mundo", speaker_id=2))
                )
                self.session_stopped.emit(SimpleNamespace())
                return None

            return SimpleNamespace(get=_run)

        def stop_transcribing_async(self):
            return SimpleNamespace(get=lambda: None)

    monkeypatch.setattr(azure_speech_service_module, "speechsdk", _FakeSpeechSdk)
    monkeypatch.setattr(
        AzureSpeechService,
        "create_conversation_transcriber",
        lambda self, audio_config: DummyTranscriber(),
    )

    service = AzureSpeechService(speech_key="key", speech_region="region")

    result = service.transcribe_with_diarization(b"fake audio bytes")

    assert result["text"] == "hola mundo"
    assert result["segments"] == [
        {"speaker": "speaker_1", "text": "hola"},
        {"speaker": "speaker_2", "text": "mundo"},
    ]
