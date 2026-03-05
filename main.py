import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from api import auth

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("secret_key")
)

app.include_router(auth.router)