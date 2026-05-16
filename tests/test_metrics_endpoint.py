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
            created_metrics = MagicMock()
            created_metrics.avg_score = 0.0
            created_metrics.score_by_skill = {}
            created_metrics.score_by_category = {}
            created_metrics.total_interviews = 0
            created_metrics.last_updated = None
            instance.update_for_user.return_value = created_metrics

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/user")

        assert response.status_code == 200
        data = response.json()
        assert data["avg_score"] == 0.0
        assert data["score_by_skill"] == {}
        assert data["score_by_category"] == {}
        assert data["total_interviews"] == 0

    def test_usuario_con_metricas_existentes_las_actualiza(self):
        existing = MagicMock()
        existing.avg_score = 78.5
        existing.score_by_skill = {"correctness": 80.0}
        existing.score_by_category = {"correctness": 80.0, "completeness": 75.0}
        existing.total_interviews = 3
        existing.last_updated = "2026-05-01 10:00:00"

        db = self._make_db(existing_metrics=existing, total_interviews=3)

        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.update_for_user.return_value = existing

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
        existing.score_by_category = {}
        existing.total_interviews = 1
        existing.last_updated = "2026-05-01"

        db = self._make_db(existing_metrics=existing, total_interviews=1)

        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.update_for_user.return_value = existing

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/user")

        assert response.status_code == 200
        data = response.json()
        assert "avg_score" in data
        assert "score_by_skill" in data
        assert "score_by_category" in data
        assert "total_interviews" in data
        assert "last_updated" in data


class TestGetEmployabilityScore:
    def _make_metrics(self, employability_score=72.0, last_updated="2026-05-01 10:00:00"):
        m = MagicMock()
        m.employability_score = employability_score
        m.last_updated = last_updated
        return m

    def _employability_result(self, score=72.0, interviews=3, interview_score=80.0,
                               completeness=80.0, match=65.0):
        return {
            "score": score,
            "breakdown": {
                "interview_score": interview_score,
                "profile_completeness": completeness,
                "avg_match_score": match,
            },
            "total_interviews": interviews,
        }

    def test_retorna_score_con_breakdown(self):
        db = MagicMock()
        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.calculate_employability_score.return_value = self._employability_result()
            instance.update_for_user.return_value = self._make_metrics()

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/employability")

        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 72.0
        assert data["breakdown"]["interview_score"] == 80.0
        assert data["breakdown"]["profile_completeness"] == 80.0
        assert data["breakdown"]["avg_match_score"] == 65.0

    def test_sin_entrevistas_incluye_mensaje_motivacional(self):
        db = MagicMock()
        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.calculate_employability_score.return_value = self._employability_result(
                score=34.0, interviews=0, interview_score=0.0, completeness=100.0, match=70.0
            )
            instance.update_for_user.return_value = self._make_metrics(employability_score=34.0)

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/employability")

        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 34.0
        assert data["breakdown"]["interview_score"] == 0.0
        assert data["motivational_message"] is not None
        assert len(data["motivational_message"]) > 0

    def test_con_entrevistas_no_incluye_mensaje_motivacional(self):
        db = MagicMock()
        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.calculate_employability_score.return_value = self._employability_result(
                interviews=3
            )
            instance.update_for_user.return_value = self._make_metrics()

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/employability")

        assert response.status_code == 200
        assert response.json()["motivational_message"] is None

    def test_respuesta_incluye_campos_requeridos(self):
        db = MagicMock()
        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.calculate_employability_score.return_value = self._employability_result()
            instance.update_for_user.return_value = self._make_metrics()

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/employability")

        data = response.json()
        assert "score" in data
        assert "breakdown" in data
        assert "last_updated" in data
        assert "interview_score" in data["breakdown"]
        assert "profile_completeness" in data["breakdown"]
        assert "avg_match_score" in data["breakdown"]

    def test_requiere_autenticacion(self):
        test_app = FastAPI()
        test_app.include_router(metrics_module.router, prefix="/api")
        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/api/metrics/employability")
        assert response.status_code in (401, 422, 500)


class TestGetMetricsTimeline:
    def test_timeline_week_retorna_periodos(self):
        db = MagicMock()

        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.get_score_timeline.return_value = [
                {"period": "2026-03-30", "avg_score": 72.5, "count": 2},
                {"period": "2026-04-06", "avg_score": 80.0, "count": 3},
            ]

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/timeline?granularity=week")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["period"] == "2026-03-30"
        assert data[0]["avg_score"] == 72.5
        assert data[0]["count"] == 2

    def test_timeline_sin_historial_retorna_lista_vacia(self):
        db = MagicMock()

        from unittest.mock import patch
        with patch("api.metrics.UserMetricsService") as MockService:
            instance = MockService.return_value
            instance.get_score_timeline.return_value = []

            client = _make_app_with_db(db)
            response = client.get("/api/metrics/timeline")

        assert response.status_code == 200
        assert response.json() == []

    def test_timeline_granularity_invalida_retorna_422(self):
        db = MagicMock()
        client = _make_app_with_db(db)

        response = client.get("/api/metrics/timeline?granularity=day")
        assert response.status_code == 422


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
