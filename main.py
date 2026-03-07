import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from core.database import engine, Base
import models


try:
    from starlette.middleware.sessions import SessionMiddleware
except ImportError:  # pragma: no cover - fallback for test env without starlette extras installed
    class SessionMiddleware:  # type: ignore
        def __init__(self, app, **kwargs):
            self.app = app

        def __call__(self, scope, receive, send):
            return self.app(scope, receive, send)

from api import auth
from middleware.auth_middleware import AuthMiddleware
# Carga variables desde .env

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Could not create tables: {e}")


app = FastAPI()

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
        "/auth/refresh",
        "/auth/google",
        "/auth/google/callback",
        "/docs",
        "/openapi.json",
        "/health",
    ],
)

app.include_router(auth.router)


