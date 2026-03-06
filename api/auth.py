import time
import os

from fastapi import APIRouter, Request, Depends
from core.oauth import oauth
from core.jwt import create_token, get_current_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.get("/google")
async def login_google(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    authorization_url = await oauth.google.create_authorization_url(redirect_uri=redirect_uri)
    return {
        "url": authorization_url["url"],
        "state": authorization_url["state"]
    }


@router.get("/google/callback")
async def google_callback(request: Request):
    try:
        state = request.query_params.get("state")
        if state:
            redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
            request.session[f"_state_google_{state}"] = {
                "data": {"redirect_uri": redirect_uri},
                "exp": time.time() + 300
            }

        token = await oauth.google.authorize_access_token(request)
        resp = await oauth.google.userinfo(token=token)

        access_token = create_token({
            "email": resp["email"],
            "name":  resp["name"],
            "picture": resp["picture"]
        })

        return {
            "message": "Login successful",
            "access_token": access_token,
            "token_type": "bearer"
        }
    except Exception as e:
        return {
            "message": "Login failed",
            "error": str(e)
        }


@router.post("/logout")
async def logout():
    return {"message": "Logged out. Discard your access_token on the client side."}


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user


@router.get("/microsoft")
def microsoft_login():
    return {"url": "https://accounts.microsoft.com/..."}


@router.get("/microsoft/callback")
def microsoft_callback():
    return {"url": "https://accounts.microsoft.com/..."}