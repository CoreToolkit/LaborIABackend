from fastapi import APIRouter, Request, HTTPException
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
    authorization_url = await oauth.google.create_authorization_url(redirect_uri=redirect_uri)

    return {
        "url": authorization_url['url'],
        "state": authorization_url['state']
    }

@router.get("/google/callback")
async def google_callback(request: Request):
    try:
        state = request.query_params.get("state")
        if state:
            import time
            redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
            request.session[f"_state_google_{state}"] = {
                "data": {"redirect_uri": redirect_uri},
                "exp": time.time() + 300
            }

        token = await oauth.google.authorize_access_token(request)
        resp = await oauth.google.userinfo(token=token)
        user = resp
        request.session['user'] = {
            "email": user["email"],
            "name": user["name"],
            "picture": user["picture"]
        }
        return {
            "message": "Login successful",
            "user": request.session['user']
        }
    except Exception as e:
        return {
            "message": "Login failed",
            "error": str(e)
        }

@router.post("/logout")
async def logout():
    return {"message": "Logged out successfully"}

@router.get("/me")
async def get_current_user(request:Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="No user logged in")
    return user

@router.get("/microsoft")
def microsoft_login():
    return {"url": "https://accounts.microsoft.com/..."}

@router.get("/microsoft/callback")
def microsoft_callback():
    return {"url": "https://accounts.microsoft.com/..."}