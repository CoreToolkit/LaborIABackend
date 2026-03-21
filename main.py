import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
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

from api import auth
from api import profiles
from api import roles
from api import technologies
from api import ollama
from api import azure_openai
from api import matching
from middleware.auth_middleware import AuthMiddleware
# Carga variables desde .env

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Could not create tables: {e}")


app = FastAPI()

local_host_front = os.getenv("LOCAL_HOST_FRONT")
local_ip = os.getenv("LOCAL_IP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[local_host_front, local_ip],
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
    ],
)

app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(profiles.router, prefix="/api")
app.include_router(roles.router, prefix="/api")
app.include_router(technologies.router, prefix="/api")
app.include_router(matching.router, prefix="/api")
app.include_router(ollama.router, prefix="/api")
app.include_router(azure_openai.router, prefix="/api")


