import base64
import json
from typing import Dict, Optional

import httpx
from fastapi import HTTPException


def _decode_segment(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def user_from_id_token(id_token: str) -> Optional[Dict[str, str]]:
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            return None
        payload = json.loads(_decode_segment(parts[1]).decode("utf-8"))
        email = payload.get("email") or payload.get("preferred_username")
        name = payload.get("name") or payload.get("given_name")
        return {"email": email, "name": name}
    except Exception:
        return None


def fetch_user_from_graph(access_token: str) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=10)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to reach Microsoft Graph.") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Failed to fetch Microsoft user profile.")
    data = resp.json()
    return {"email": data.get("mail") or data.get("userPrincipalName"), "name": data.get("displayName")}


def exchange_code_for_tokens(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    tenant_id: str,
):
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        resp = httpx.post(token_url, data=data, headers=headers, timeout=10)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to reach Microsoft token endpoint.") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Microsoft token exchange failed.")
    return resp.json()
