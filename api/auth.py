from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from core.oauth import oauth
import os


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.get("/google")
async def login_google(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri
    )

@router.get("/google/callback")
async def google_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = token["userinfo"]
    return {
        "email": user["email"],
        "name": user["name"],
        "picture": user["picture"]
    }

@router.get("/microsoft")
def microsoft_login():
    return {"url": "https://accounts.microsoft.com/..."}

@router.get("/microsoft/callback")
def microsoft_callback():
    return {"url": "https://accounts.microsoft.com/..."}