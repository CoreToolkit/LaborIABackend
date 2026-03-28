from pydantic import BaseModel


class ElevenLabsSpeechRequest(BaseModel):
    text: str


class ElevenLabsSpeechResponse(BaseModel):
    audio: str
