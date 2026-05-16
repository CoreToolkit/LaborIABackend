import os

os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.badges as badges_module
from core.database import get_db
from core.jwt import get_current_user


def _mock_user(user_id: int = 1):
    return {"id": user_id, "email": "test@example.com", "name": "Test"}


def _make_app(db_mock, user_id: int = 1):
    app = FastAPI()
    app.include_router(badges_module.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[get_current_user] = lambda: _mock_user(user_id)
    return TestClient(app)


def _badge_dict(
    badge_id=1,
    name="Primera Entrevista",
    description="Completaste tu primera entrevista",
    icon="🎯",
    condition_type="total_interviews",
    condition_value="1",
    is_unlocked=False,
    progress=0.0,
):
    return {
        "id": badge_id,
        "name": name,
        "description": description,
        "icon": icon,
        "condition_type": condition_type,
        "condition_value": condition_value,
        "is_unlocked": is_unlocked,
        "progress": progress,
    }


class TestGetMyBadges:
    def test_usuario_sin_badges_retorna_lista_vacia(self):
        db = MagicMock()
        with patch("api.badges.BadgeService") as MockService:
            MockService.return_value.get_user_badges_with_progress.return_value = []
            client = _make_app(db)
            response = client.get("/api/badges/me")

        assert response.status_code == 200
        assert response.json() == []

    def test_retorna_badges_con_campos_requeridos(self):
        badge = _badge_dict(is_unlocked=True, progress=1.0)
        db = MagicMock()
        with patch("api.badges.BadgeService") as MockService:
            MockService.return_value.get_user_badges_with_progress.return_value = [badge]
            client = _make_app(db)
            response = client.get("/api/badges/me")

        assert response.status_code == 200
        item = response.json()[0]
        assert "id" in item
        assert "name" in item
        assert "description" in item
        assert "icon" in item
        assert "condition_type" in item
        assert "condition_value" in item
        assert "is_unlocked" in item
        assert "progress" in item

    def test_badge_desbloqueado_tiene_progress_1(self):
        badge = _badge_dict(is_unlocked=True, progress=1.0)
        db = MagicMock()
        with patch("api.badges.BadgeService") as MockService:
            MockService.return_value.get_user_badges_with_progress.return_value = [badge]
            client = _make_app(db)
            response = client.get("/api/badges/me")

        item = response.json()[0]
        assert item["is_unlocked"] is True
        assert item["progress"] == 1.0

    def test_badge_bloqueado_tiene_progress_parcial(self):
        badge = _badge_dict(is_unlocked=False, progress=0.4)
        db = MagicMock()
        with patch("api.badges.BadgeService") as MockService:
            MockService.return_value.get_user_badges_with_progress.return_value = [badge]
            client = _make_app(db)
            response = client.get("/api/badges/me")

        item = response.json()[0]
        assert item["is_unlocked"] is False
        assert item["progress"] == 0.4

    def test_retorna_multiples_badges(self):
        badges = [
            _badge_dict(badge_id=1, is_unlocked=True, progress=1.0),
            _badge_dict(badge_id=2, name="En Racha", is_unlocked=False, progress=0.6),
            _badge_dict(badge_id=3, name="Experto", is_unlocked=False, progress=0.2),
        ]
        db = MagicMock()
        with patch("api.badges.BadgeService") as MockService:
            MockService.return_value.get_user_badges_with_progress.return_value = badges
            client = _make_app(db)
            response = client.get("/api/badges/me")

        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_requiere_autenticacion(self):
        app = FastAPI()
        app.include_router(badges_module.router, prefix="/api")
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/badges/me")
        assert response.status_code in (401, 422, 500)
