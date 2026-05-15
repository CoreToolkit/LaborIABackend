import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from core.database import engine, Base
import models
from fastapi.middleware.cors import CORSMiddleware


try:
    from starlette.middleware.sessions import SessionMiddleware
except ImportError:  # pragma: no cover - fallback for test env without starlette extras installed
    class SessionMiddleware:  # type: ignore
        def __init__(self, app, **kwargs):
            self.app = app

        def __call__(self, scope, receive, send):
            return self.app(scope, receive, send)

from api import auth, websockets
from api import profiles
from api import roles
from api import questions
from api import sessions
from api import group_interview_sessions
from api import technologies
from api import ollama
from api import azure_openai
from api import azure_speech
from api import elevenlabs
from api import matching
from api.evaluations import router as evaluations_router
from api.metrics import router as metrics_router
from api.recommendations import router as recommendations_router
from api.interviews import router as interviews_router
from api.badges import router as badges_router
from api.improvement_plan import router as improvement_plan_router
from middleware.auth_middleware import AuthMiddleware
from core.limiter import auth_rate_limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

if os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true":
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Could not create tables: {e}")


app = FastAPI()
app.state.limiter = auth_rate_limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

local_host_front = os.getenv("LOCAL_HOST_FRONT")
local_ip = os.getenv("LOCAL_IP")
front_ip = os.getenv("FRONTEND_URL")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[local_host_front, local_ip, front_ip],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("secret_key", "dev-secret-key"),
)

# Middleware de autenticación JWT (excluye rutas públicas)
app.add_middleware(
    AuthMiddleware,
    excluded_paths=[
        "/auth/microsoft",
        "/auth/microsoft/callback",
        "/auth/microsoft/exchange",
        "/auth/refresh",
        "/auth/google",
        "/auth/google/exchange",
        "/docs",
        "/openapi.json",
        "/health",
        "/api/ai/ollama/health",
        "/api/ai/ollama/ask",
        "/api/ai/azure-openai/health",
        "/api/ai/azure-openai/ask",
        "/api/ws",
    ],
)

app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(profiles.router, prefix="/api")
app.include_router(profiles.profile_alias_router, prefix="/api")
app.include_router(roles.router, prefix="/api")
app.include_router(questions.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(group_interview_sessions.router, prefix="/api")
app.include_router(technologies.router, prefix="/api")
app.include_router(matching.router, prefix="/api")
app.include_router(ollama.router, prefix="/api")
app.include_router(azure_openai.router, prefix="/api")
app.include_router(evaluations_router)
app.include_router(metrics_router, prefix="/api")
app.include_router(recommendations_router, prefix="/api")
app.include_router(interviews_router, prefix="/api")
app.include_router(azure_speech.router, prefix="/api")
app.include_router(elevenlabs.router, prefix="/api")
app.include_router(websockets.router, prefix="/api")
app.include_router(badges_router, prefix="/api")
app.include_router(improvement_plan_router, prefix="/api")


@app.get("/health/live", tags=["health"])
def live_check():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable"},
        )

    return {"status": "ready", "database": "ok"}


@app.get("/health", tags=["health"])
def health_check():
    return live_check()


