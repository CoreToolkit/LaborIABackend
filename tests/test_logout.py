import datetime as dt

import pytest
import api.auth as auth_module
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient
from dotenv import load_dotenv
import os

from core import jwt as core_jwt
from core.database import Base, engine, SessionLocal
from main import app

client = TestClient(app)

Base.metadata.create_all(bind=engine)


def test_logout_blacklists_token():
    load_dotenv()
    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides = {}
    app.dependency_overrides[auth_module.get_db] = override_db

    access_token = core_jwt.create_token({"email": "user@example.com", "name": "User"})

    # Antes del logout, token sirve
    resp_ok = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp_ok.status_code == 200

    # Logout
    resp_logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert resp_logout.status_code == 200
    assert resp_logout.json()["message"].startswith("Logout successful")

    # Después del logout, el mismo token debe ser rechazado
    resp_fail = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp_fail.status_code == 401
