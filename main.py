from dotenv import load_dotenv
from fastapi import FastAPI
from api import auth

# Carga variables desde .env
load_dotenv()

app = FastAPI()

app.include_router(auth.router)
