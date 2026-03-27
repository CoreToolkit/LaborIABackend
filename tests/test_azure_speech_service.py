import os
from types import SimpleNamespace

import pytest

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


def test_azure_speech_service_returns_text_when_transcription_succeeds(monkeypatch):
    captured = {}

    class DummyRecognizer:
        def recognize_once_async(self):
            return SimpleNamespace(
                get=lambda: SimpleNamespace(
                    reason=azure_speech_service_module.speechsdk.ResultReason.RecognizedSpeech,
                    text="Texto transcrito",
                )
            )

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
    class DummyRecognizer:
        def recognize_once_async(self):
            return SimpleNamespace(get=lambda: (_ for _ in ()).throw(Exception("provider failed")))

    def fake_create_speech_recognizer(self, audio_config, language=None):
        return DummyRecognizer()

    monkeypatch.setattr(azure_speech_service_module, "speechsdk", _FakeSpeechSdk)
    monkeypatch.setattr(AzureSpeechService, "create_speech_recognizer", fake_create_speech_recognizer)

    service = AzureSpeechService(speech_key="key", speech_region="region")

    with pytest.raises(Exception, match="Error en Azure Speech: provider failed"):
        service.transcribe_audio(b"fake audio bytes", filename="clip.wav")


def test_azure_speech_service_requires_configuration(monkeypatch):
    monkeypatch.delenv("SPEECH_KEY", raising=False)
    monkeypatch.delenv("SPEECH_REGION", raising=False)
    monkeypatch.setattr(azure_speech_service_module, "speechsdk", _FakeSpeechSdk)

    with pytest.raises(RuntimeError, match="Faltan variables de entorno de Azure Speech: SPEECH_KEY, SPEECH_REGION"):
        AzureSpeechService()
