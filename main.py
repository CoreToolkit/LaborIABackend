import os

from dotenv import load_dotenv
from fastapi import FastAPI

try:
    from starlette.middleware.sessions import SessionMiddleware
except ImportError:  # pragma: no cover - fallback for test env without starlette extras installed
    class SessionMiddleware:  # type: ignore
        def __init__(self, app, **kwargs):
            self.app = app

        def __call__(self, scope, receive, send):
            return self.app(scope, receive, send)

from api import auth

# Carga variables desde .env
load_dotenv()

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("secret_key", "dev-secret-key"),
)

app.include_router(auth.router)
