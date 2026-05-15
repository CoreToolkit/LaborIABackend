from pydantic import BaseModel


class ElevenLabsSpeechRequest(BaseModel):
    text: str


class ElevenLabsSpeechResponse(BaseModel):
    audio: str | None
    tts_status: str = "ok"
    tts_error: str | None = None
