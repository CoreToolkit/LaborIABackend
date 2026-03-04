from fastapi import APIRouter

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.get("/google")
def google_login():
    return {"url": "https://accounts.google.com/..."}

@router.get("/google/callback")
def google_callback():
    return {"url": "https://accounts.google.com/..."}

@router.get("/microsoft")
def microsoft_login():
    return {"url": "https://accounts.microsoft.com/..."}

@router.get("/microsoft/callback")
def microsoft_callback():
    return {"url": "https://accounts.microsoft.com/..."}