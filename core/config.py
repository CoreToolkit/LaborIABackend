from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_PRE_PING: bool = True
    AUTO_CREATE_TABLES: bool = False

    # Auth
    JWT_SECRET: str
    JWT_ISSUER: Optional[str] = None
    JWT_AUDIENCE: Optional[str] = None
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    secret_key: str = "dev-secret-key"

    # OAuth - Google
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # OAuth - Microsoft
    MICROSOFT_CLIENT_ID: Optional[str] = None
    MICROSOFT_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_REDIRECT_URI: Optional[str] = None
    MICROSOFT_TENANT_ID: str = "common"

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = None
    AZURE_OPENAI_TIMEOUT: int = 60
    AZURE_OPENAI_MAX_CONCURRENT: int = 5
    AZURE_OPENAI_ACQUIRE_TIMEOUT: int = 10

    # Azure Speech
    SPEECH_KEY: Optional[str] = None
    SPEECH_REGION: Optional[str] = None
    AZURE_SPEECH_MAX_CONCURRENT: int = 5
    AZURE_SPEECH_ACQUIRE_TIMEOUT: int = 5

    # ElevenLabs
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_VOICE_ID: Optional[str] = None
    ELEVENLABS_MODEL_ID: str = "eleven_flash_v2_5"
    ELEVENLABS_TIMEOUT: int = 30
    ELEVENLABS_MAX_RETRIES: int = 2
    ELEVENLABS_MAX_CONCURRENT: int = 5
    ELEVENLABS_ACQUIRE_TIMEOUT: int = 5

    # Ollama
    OLLAMA_BASE_URL: Optional[str] = None
    OLLAMA_MODEL: Optional[str] = None
    OLLAMA_TIMEOUT: int = 120

    # LLM provider selection ("azure" | "ollama"); defaults to "azure"
    LLM_PROVIDER: str = "azure"

    # App / CORS
    MAX_AUDIO_UPLOAD_BYTES: int = 10 * 1024 * 1024
    WEBSOCKET_AUTH_REQUIRED: bool = False
    ADMIN_EMAILS: str = ""
    LOCAL_HOST_FRONT: Optional[str] = None
    LOCAL_IP: Optional[str] = None
    FRONTEND_URL: Optional[str] = None

    # Matching weights (Defer Binding: cambian sin tocar código)
    SKILL_MATCH_WEIGHT: float = 0.50
    EXPERIENCE_MATCH_WEIGHT: float = 0.25
    EDUCATION_MATCH_WEIGHT: float = 0.15
    PREFERENCES_MATCH_WEIGHT: float = 0.10

    # Feature flags (Defer Binding: toggle features without code changes)
    ENABLE_TTS: bool = True
    ENABLE_BADGES: bool = True
    ENABLE_LLM_REASON_GENERATION: bool = True


settings = Settings()
