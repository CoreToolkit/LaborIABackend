from ai.azure_speech_service import AzureSpeechService


class AzureSpeechClient:
    def __init__(self, service: AzureSpeechService = None):
        self.service = service or AzureSpeechService()

    def create_recognizer(self, audio_config):
        return self.service.create_speech_recognizer(audio_config)

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = None,
        language: str = None,
    ) -> str:
        return self.service.transcribe_audio(
            audio_bytes=audio_bytes,
            filename=filename,
            language=language,
        )

    def transcribe_with_diarization(self, audio_bytes: bytes) -> dict:
        return self.service.transcribe_with_diarization(audio_bytes=audio_bytes)
