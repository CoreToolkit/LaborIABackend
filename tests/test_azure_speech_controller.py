import os

import pytest

pytest.importorskip("fastapi")

os.environ["JWT_SECRET"] = "test-secret"
os.environ.setdefault("SPEECH_KEY", "test-speech-key")
os.environ.setdefault("SPEECH_REGION", "eastus")

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.azure_speech as azure_speech_module


app = FastAPI()
app.include_router(azure_speech_module.router, prefix="/api")
client = TestClient(app)


@pytest.fixture(autouse=True)
def override_current_user(monkeypatch):
    app.dependency_overrides[azure_speech_module.get_current_user] = lambda: {
        "id": 1,
        "email": "speech@example.com",
        "name": "Speech Test User",
    }
    monkeypatch.setattr(azure_speech_module, "azure_speech_init_error", None)
    yield
    app.dependency_overrides.clear()


def test_transcribe_audio_returns_result_for_valid_request(monkeypatch):
    calls = []

    class DummyClient:
        def transcribe(self, audio_bytes, filename=None, language=None):
            calls.append(
                {
                    "audio_bytes": audio_bytes,
                    "filename": filename,
                    "language": language,
                }
            )
            return "Hola mundo"

    monkeypatch.setattr(azure_speech_module, "azure_speech_client", DummyClient())

    response = client.post(
        "/api/ai/azure-speech/transcribe",
        files={"file": ("sample.wav", b"fake-audio-content", "audio/wav")},
        data={"language": "es-CO"},
    )

    assert response.status_code == 200
    assert response.json() == {"result": "Hola mundo"}
    assert calls == [
        {
            "audio_bytes": b"fake-audio-content",
            "filename": "sample.wav",
            "language": "es-CO",
        }
    ]


def test_transcribe_audio_returns_400_when_file_is_empty(monkeypatch):
    class DummyClient:
        def transcribe(self, audio_bytes, filename=None, language=None):
            raise AssertionError("transcribe should not be called for empty files")

    monkeypatch.setattr(azure_speech_module, "azure_speech_client", DummyClient())

    response = client.post(
        "/api/ai/azure-speech/transcribe",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "'file' es requerido"


def test_transcribe_audio_returns_422_when_file_is_missing():
    response = client.post("/api/ai/azure-speech/transcribe", data={"language": "es-CO"})

    assert response.status_code == 422


def test_transcribe_audio_returns_500_when_service_fails(monkeypatch):
    class DummyClient:
        def transcribe(self, audio_bytes, filename=None, language=None):
            raise Exception("service exploded")

    monkeypatch.setattr(azure_speech_module, "azure_speech_client", DummyClient())

    response = client.post(
        "/api/ai/azure-speech/transcribe",
        files={"file": ("sample.wav", b"fake-audio-content", "audio/wav")},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "service exploded"


def test_transcribe_audio_returns_503_when_integration_is_not_initialized(monkeypatch):
    monkeypatch.setattr(
        azure_speech_module,
        "azure_speech_init_error",
        "Faltan variables de entorno de Azure Speech: SPEECH_KEY, SPEECH_REGION",
    )

    response = client.post(
        "/api/ai/azure-speech/transcribe",
        files={"file": ("sample.wav", b"fake-audio-content", "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Faltan variables de entorno de Azure Speech: SPEECH_KEY, SPEECH_REGION"
