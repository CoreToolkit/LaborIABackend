from ai.azure_speech_service import AzureSpeechService


class AzureSpeechClient:
    def __init__(self, service: AzureSpeechService = None):
        self.service = service or AzureSpeechService()

    def create_recognizer(self, audio_config):
        return self.service.create_speech_recognizer(audio_config)
