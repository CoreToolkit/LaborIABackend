import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.interviews as interviews_module
from core.database import get_db
from core.jwt import get_current_user


def _mock_user(user_id: int = 1):
    return {"id": user_id, "email": "test@example.com", "name": "Test"}


def _make_client(db_mock, user_id: int = 1) -> TestClient:
    app = FastAPI()
    app.include_router(interviews_module.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[get_current_user] = lambda: _mock_user(user_id)
    return TestClient(app)


def _base_report(session_score=72.5, has_previous=True, badges=None):
    return {
        "session_id": 1,
        "session_score": session_score,
        "total_questions": 3,
        "completed_questions": 3,
        "evaluations": [
            {
                "evaluation_id": "abc-123",
                "question_text": "¿Qué es un decorador en Python?",
                "category": "Python",
                "difficulty": "medium",
                "score": 72.5,
                "feedback": "Buena respuesta.",
                "score_breakdown": {"correctness": 80, "completeness": 70, "clarity": 70, "examples": 60},
                "topics_covered": ["decorators"],
                "topics_missing": [],
            }
        ],
        "comparison": {
            "has_previous": has_previous,
            "previous_session_id": 5 if has_previous else None,
            "previous_score": 55.0 if has_previous else None,
            "improvement": 17.5 if has_previous else None,
            "trend": "improved" if has_previous else "first_session",
        },
        "badges_unlocked": badges or [],
        "session_created_at": "2026-05-01 10:00:00+00:00",
    }


class TestGetSessionReport:
    def test_retorna_reporte_completo(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.get_session_report.return_value = _base_report()
            response = _make_client(db).get("/api/interviews/1/report")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == 1
        assert data["session_score"] == 72.5
        assert data["total_questions"] == 3
        MockService.return_value.get_session_report.assert_called_once_with(
            session_id=1,
            user_id=1,
            unlock_badges=False,
        )

    def test_desbloqueo_de_badges_requiere_parametro_explicito(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.get_session_report.return_value = _base_report()
            response = _make_client(db).get("/api/interviews/1/report?unlock_badges=true")

        assert response.status_code == 200
        MockService.return_value.get_session_report.assert_called_once_with(
            session_id=1,
            user_id=1,
            unlock_badges=True,
        )

    def test_404_si_sesion_no_existe(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.get_session_report.return_value = None
            response = _make_client(db).get("/api/interviews/999/report")

        assert response.status_code == 404

    def test_comparacion_con_sesion_anterior(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.get_session_report.return_value = _base_report(
                session_score=72.5, has_previous=True
            )
            response = _make_client(db).get("/api/interviews/1/report")

        data = response.json()
        assert data["comparison"]["has_previous"] is True
        assert data["comparison"]["previous_score"] == 55.0
        assert data["comparison"]["improvement"] == 17.5
        assert data["comparison"]["trend"] == "improved"

    def test_primera_sesion_sin_comparacion(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.get_session_report.return_value = _base_report(
                has_previous=False
            )
            response = _make_client(db).get("/api/interviews/1/report")

        data = response.json()
        assert data["comparison"]["has_previous"] is False
        assert data["comparison"]["trend"] == "first_session"
        assert data["comparison"]["improvement"] is None

    def test_badges_desbloqueados_en_sesion(self):
        db = MagicMock()
        badges = [{"id": 1, "name": "Primera Entrevista", "description": "...", "icon": "🎯"}]
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.get_session_report.return_value = _base_report(badges=badges)
            response = _make_client(db).get("/api/interviews/1/report")

        data = response.json()
        assert len(data["badges_unlocked"]) == 1
        assert data["badges_unlocked"][0]["name"] == "Primera Entrevista"

    def test_sin_badges_retorna_lista_vacia(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.get_session_report.return_value = _base_report(badges=[])
            response = _make_client(db).get("/api/interviews/1/report")

        assert response.json()["badges_unlocked"] == []

    def test_evaluaciones_incluyen_detalle_completo(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.get_session_report.return_value = _base_report()
            response = _make_client(db).get("/api/interviews/1/report")

        eval_item = response.json()["evaluations"][0]
        assert "question_text" in eval_item
        assert "score" in eval_item
        assert "feedback" in eval_item
        assert "score_breakdown" in eval_item
        assert "topics_covered" in eval_item
        assert "topics_missing" in eval_item

    def test_campos_requeridos_en_respuesta(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.get_session_report.return_value = _base_report()
            response = _make_client(db).get("/api/interviews/1/report")

        data = response.json()
        for field in ["session_id", "session_score", "total_questions",
                      "completed_questions", "evaluations", "comparison",
                      "badges_unlocked", "session_created_at"]:
            assert field in data


class TestListSessionReports:
    def test_retorna_historial_de_reportes(self):
        db = MagicMock()
        second_report = _base_report(session_score=80.0, has_previous=False)
        second_report["session_id"] = 2
        second_report["session_created_at"] = "2026-05-02 10:00:00+00:00"

        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.list_session_reports.return_value = [
                second_report,
                _base_report(),
            ]
            response = _make_client(db).get("/api/interviews/reports")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["session_id"] == 2
        assert data[1]["session_id"] == 1
        assert data[0]["session_score"] == 80.0
        assert data[0]["completed_questions"] == 3
        MockService.return_value.list_session_reports.assert_called_once_with(
            user_id=1,
            limit=3,
            offset=0,
        )

    def test_historial_usa_paginacion(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.list_session_reports.return_value = []
            response = _make_client(db).get("/api/interviews/reports?limit=5&offset=10")

        assert response.status_code == 200
        MockService.return_value.list_session_reports.assert_called_once_with(
            user_id=1,
            limit=5,
            offset=10,
        )

    def test_historial_vacio_retorna_lista_vacia(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.list_session_reports.return_value = []
            response = _make_client(db).get("/api/interviews/reports")

        assert response.status_code == 200
        assert response.json() == []


class TestListSessionReportsSummary:
    def test_retorna_resumen_ligero(self):
        db = MagicMock()
        first = {
            "session_id": 2,
            "session_score": 88.0,
            "session_created_at": "2026-05-02 10:00:00+00:00",
            "total_questions": 4,
            "completed_questions": 4,
            "trend": "improved",
            "improvement": 8.0,
            "previous_score": 80.0,
            "badges_count": 1,
        }

        second = {
            "session_id": 1,
            "session_score": 80.0,
            "session_created_at": "2026-05-01 10:00:00+00:00",
            "total_questions": 3,
            "completed_questions": 3,
            "trend": "first_session",
            "improvement": None,
            "previous_score": None,
            "badges_count": 0,
        }

        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.list_session_reports_summary.return_value = [first, second]
            response = _make_client(db).get("/api/interviews/reports/summary")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["session_id"] == 2
        assert data[0]["badges_count"] == 1

    def test_resumen_vacio_retorna_lista_vacia(self):
        db = MagicMock()
        with patch("api.interviews.ReportService") as MockService:
            MockService.return_value.list_session_reports_summary.return_value = []
            response = _make_client(db).get("/api/interviews/reports/summary")

        assert response.status_code == 200
        assert response.json() == []
