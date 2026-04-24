# tests/test_metrics_endpoint.py
# Tests para TASK-026-06: GET /api/metrics/user
# Tests para TASK-028-01: GET /evaluations/history/user
#
# Usa una app FastAPI aislada (sin AuthMiddleware) igual que los demás tests
# de controllers del proyecto (ver test_matching_controller.py, test_role_controller.py)

import os
from unittest.mock import MagicMock
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.metrics as metrics_module
import api.evaluations as evaluations_module
from core.database import get_db
from core.jwt import get_current_user


def _mock_user(user_id: int = 1):
    return {"id": user_id, "email": "test@example.com", "name": "Test"}


def _make_app_with_db(db_mock, user_id: int = 1):
    """Crea una app FastAPI aislada sin AuthMiddleware, con db y user mockeados."""
    test_app = FastAPI()
    test_app.include_router(metrics_module.router, prefix="/api")
    test_app.include_router(evaluations_module.router)
    test_app.dependency_overrides[get_db] = lambda: db_mock
    test_app.dependency_overrides[get_current_user] = lambda: _mock_user(user_id)
    return TestClient(test_app)


# ── GET /api/metrics/user ─────────────────────────────────────────────────────

class TestGetUserMetrics:
    def _make_db(self, existing_metrics=None, total_interviews=0):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing_metrics
        db.query.return_value.join.return_value.filter.return_value.scalar.return_value = total_interviews
        return db

    def test_usuario_sin_metricas_retorna_valores_en_cero(self):
        db = self._make_db(existing_metrics=None, total_interviews=0)

        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.calculate_average_score.return_value = 0.0
            instance.score_by_category.return_value = {}

            # Simular que db.refresh actualiza el objeto creado
            created_metrics = MagicMock()
            created_metrics.avg_score = 0.0
            created_metrics.score_by_skill = {}
            created_metrics.total_interviews = 0
            created_metrics.last_updated = None
            db.refresh.side_effect = lambda obj: None

            # Hacer que el segundo query (después del add) devuelva el objeto
            db.query.return_value.filter.return_value.first.side_effect = [None, created_metrics]

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/user")

        assert response.status_code == 200
        data = response.json()
        assert data["avg_score"] == 0.0
        assert data["score_by_skill"] == {}
        assert data["total_interviews"] == 0

    def test_usuario_con_metricas_existentes_las_actualiza(self):
        existing = MagicMock()
        existing.avg_score = 78.5
        existing.score_by_skill = {"correctness": 80.0}
        existing.total_interviews = 3
        existing.last_updated = "2026-05-01 10:00:00"

        db = self._make_db(existing_metrics=existing, total_interviews=3)
        db.refresh.side_effect = lambda obj: None

        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.calculate_average_score.return_value = 78.5
            instance.score_by_category.return_value = {"correctness": 80.0}

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/user")

        assert response.status_code == 200
        data = response.json()
        assert data["avg_score"] == 78.5
        assert "correctness" in data["score_by_skill"]
        assert data["total_interviews"] == 3

    def test_respuesta_incluye_campos_requeridos(self):
        existing = MagicMock()
        existing.avg_score = 50.0
        existing.score_by_skill = {}
        existing.total_interviews = 1
        existing.last_updated = "2026-05-01"

        db = self._make_db(existing_metrics=existing, total_interviews=1)
        db.refresh.side_effect = lambda obj: None

        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.calculate_average_score.return_value = 50.0
            instance.score_by_category.return_value = {}

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/user")

        assert response.status_code == 200
        data = response.json()
        assert "avg_score" in data
        assert "score_by_skill" in data
        assert "total_interviews" in data
        assert "last_updated" in data


# ── GET /evaluations/history/user ─────────────────────────────────────────────

class TestGetEvaluationHistory:
    def _make_eval_mock(self, score=80.0):
        ev = MagicMock()
        ev.id = uuid4()
        ev.score = score
        ev.feedback = "Buena respuesta"
        ev.score_breakdown = {"correctness": 80.0}
        ev.completed_at = "2026-05-01 10:00:00"
        ev.question = MagicMock()
        ev.question.question_text = "¿Qué es un decorador?"
        return ev

    def _make_db_with_evals(self, evals: list, total: int):
        db = MagicMock()
        chain = (
            db.query.return_value
            .join.return_value
            .options.return_value
            .filter.return_value
            .order_by.return_value
        )
        chain.count.return_value = total
        chain.offset.return_value.limit.return_value.all.return_value = evals
        return db

    def test_usuario_sin_historial_retorna_lista_vacia(self):
        db = self._make_db_with_evals([], 0)
        client = _make_app_with_db(db)
        response = client.get("/evaluations/history/user")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_retorna_evaluaciones_del_usuario(self):
        evals = [self._make_eval_mock(80.0), self._make_eval_mock(65.0)]
        db = self._make_db_with_evals(evals, 2)
        client = _make_app_with_db(db)
        response = client.get("/evaluations/history/user")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["question_text"] == "¿Qué es un decorador?"
        assert data["items"][0]["score"] == 80.0
        assert data["items"][0]["feedback"] == "Buena respuesta"
        assert data["items"][0]["score_breakdown"] == {"correctness": 80.0}

    def test_paginacion_limit_y_offset(self):
        db = self._make_db_with_evals([self._make_eval_mock()], 50)
        client = _make_app_with_db(db)
        response = client.get("/evaluations/history/user?limit=5&offset=10")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 10
        assert data["total"] == 50

    def test_score_negativo_se_retorna_como_null(self):
        ev = self._make_eval_mock(score=-1.0)
        db = self._make_db_with_evals([ev], 1)
        client = _make_app_with_db(db)
        response = client.get("/evaluations/history/user")

        assert response.status_code == 200
        assert response.json()["items"][0]["score"] is None

    def test_respuesta_incluye_campos_requeridos(self):
        db = self._make_db_with_evals([self._make_eval_mock()], 1)
        client = _make_app_with_db(db)
        response = client.get("/evaluations/history/user")

        item = response.json()["items"][0]
        assert "evaluation_id" in item
        assert "question_text" in item
        assert "score" in item
        assert "feedback" in item
        assert "score_breakdown" in item
        assert "completed_at" in item
