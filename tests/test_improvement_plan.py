import os

os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.improvement_plan as plan_module
from core.database import get_db
from core.jwt import get_current_user
from services.improvement_plan_service import ImprovementPlanService


def _mock_user(user_id: int = 1):
    return {"id": user_id, "email": "test@example.com", "name": "Test"}


def _make_app(db_mock, user_id: int = 1):
    app = FastAPI()
    app.include_router(plan_module.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[get_current_user] = lambda: _mock_user(user_id)
    return TestClient(app)


def _make_item(skill="Python", priority="high", score=45.0, status="in_progress", ai_feedback=None):
    item = MagicMock()
    item.id = 1
    item.skill = skill
    item.priority = priority
    item.current_score = score
    item.target_score = 70.0
    item.status = status
    item.resources = [{"title": "Python Docs", "url": "https://docs.python.org", "type": "article"}]
    item.ai_feedback = ai_feedback
    item.completed_at = None
    return item


def _make_plan(version=1, items=None):
    plan = MagicMock()
    plan.id = 1
    plan.version = version
    plan.last_updated_at = "2026-05-07 10:00:00"
    plan.last_evaluation_count = 5
    plan.items = [_make_item()] if items is None else items
    return plan


# ── GET /api/improvement-plan/me ──────────────────────────────────────────────

class TestGetMyPlan:
    def test_retorna_plan_activo(self):
        db = MagicMock()
        plan = _make_plan()
        with patch("api.improvement_plan.ImprovementPlanService") as MockSvc:
            MockSvc.return_value.get_or_create_plan.return_value = plan
            client = _make_app(db)
            response = client.get("/api/improvement-plan/me")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 1
        assert len(data["items"]) == 1

    def test_respuesta_incluye_campos_requeridos(self):
        db = MagicMock()
        with patch("api.improvement_plan.ImprovementPlanService") as MockSvc:
            MockSvc.return_value.get_or_create_plan.return_value = _make_plan()
            client = _make_app(db)
            response = client.get("/api/improvement-plan/me")

        item = response.json()["items"][0]
        assert "skill" in item
        assert "priority" in item
        assert "current_score" in item
        assert "target_score" in item
        assert "status" in item
        assert "resources" in item
        assert "ai_feedback" in item

    def test_items_ordenados_por_prioridad(self):
        items = [
            _make_item(skill="React", priority="low"),
            _make_item(skill="Python", priority="high"),
            _make_item(skill="SQL", priority="medium"),
        ]
        db = MagicMock()
        with patch("api.improvement_plan.ImprovementPlanService") as MockSvc:
            MockSvc.return_value.get_or_create_plan.return_value = _make_plan(items=items)
            client = _make_app(db)
            response = client.get("/api/improvement-plan/me")

        result_skills = [i["skill"] for i in response.json()["items"]]
        assert result_skills == ["Python", "SQL", "React"]

    def test_plan_vacio_retorna_lista_vacia(self):
        db = MagicMock()
        with patch("api.improvement_plan.ImprovementPlanService") as MockSvc:
            MockSvc.return_value.get_or_create_plan.return_value = _make_plan(items=[])
            client = _make_app(db)
            response = client.get("/api/improvement-plan/me")

        assert response.status_code == 200
        assert response.json()["items"] == []


# ── POST /api/improvement-plan/refresh ───────────────────────────────────────

class TestRefreshPlan:
    def test_sin_cambios_no_actualiza(self):
        db = MagicMock()
        with patch("api.improvement_plan.ImprovementPlanService") as MockSvc:
            MockSvc.return_value.refresh.return_value = {
                "updated": False,
                "reason": "no_changes_detected",
                "plan": _make_plan(),
            }
            client = _make_app(db)
            response = client.post("/api/improvement-plan/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] is False
        assert data["reason"] == "no_changes_detected"

    def test_con_cambios_actualiza_y_retorna_plan(self):
        db = MagicMock()
        with patch("api.improvement_plan.ImprovementPlanService") as MockSvc:
            MockSvc.return_value.refresh.return_value = {
                "updated": True,
                "reason": "weekly_schedule",
                "plan": _make_plan(version=2),
            }
            client = _make_app(db)
            response = client.post("/api/improvement-plan/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] is True
        assert data["plan"]["version"] == 2

    def test_respuesta_incluye_campos_requeridos(self):
        db = MagicMock()
        with patch("api.improvement_plan.ImprovementPlanService") as MockSvc:
            MockSvc.return_value.refresh.return_value = {
                "updated": False,
                "reason": "no_changes_detected",
                "plan": _make_plan(),
            }
            client = _make_app(db)
            response = client.post("/api/improvement-plan/refresh")

        data = response.json()
        assert "updated" in data
        assert "reason" in data
        assert "plan" in data


# ── GET /api/improvement-plan/history ────────────────────────────────────────

class TestGetPlanHistory:
    def _make_history_entry(self, version=1, trigger="initial"):
        h = MagicMock()
        h.id = version
        h.version = version
        h.trigger = trigger
        h.snapshot = {"version": version, "items": []}
        h.created_at = "2026-05-07 10:00:00"
        return h

    def test_retorna_historial(self):
        db = MagicMock()
        entries = [self._make_history_entry(2, "weekly_schedule"), self._make_history_entry(1, "initial")]
        with patch("api.improvement_plan.ImprovementPlanService") as MockSvc:
            MockSvc.return_value.get_history.return_value = entries
            client = _make_app(db)
            response = client.get("/api/improvement-plan/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["trigger"] == "weekly_schedule"
        assert data[1]["trigger"] == "initial"

    def test_sin_historial_retorna_lista_vacia(self):
        db = MagicMock()
        with patch("api.improvement_plan.ImprovementPlanService") as MockSvc:
            MockSvc.return_value.get_history.return_value = []
            client = _make_app(db)
            response = client.get("/api/improvement-plan/history")

        assert response.status_code == 200
        assert response.json() == []

    def test_respuesta_incluye_campos_requeridos(self):
        db = MagicMock()
        with patch("api.improvement_plan.ImprovementPlanService") as MockSvc:
            MockSvc.return_value.get_history.return_value = [self._make_history_entry()]
            client = _make_app(db)
            response = client.get("/api/improvement-plan/history")

        entry = response.json()[0]
        assert "id" in entry
        assert "version" in entry
        assert "trigger" in entry
        assert "snapshot" in entry
        assert "created_at" in entry


# ── ImprovementPlanService — unit tests ──────────────────────────────────────

class TestScanLogic:
    def _make_service_db(self):
        return MagicMock()

    def test_scan_returns_no_update_when_no_changes(self):
        from datetime import datetime, timezone, timedelta
        service = ImprovementPlanService.__new__(ImprovementPlanService)
        service.db = MagicMock()

        plan = MagicMock()
        plan.last_evaluation_count = 10
        plan.last_updated_at = datetime.now(timezone.utc) - timedelta(days=2)
        plan.items = []

        with patch.object(service, "_count_total_evaluations", return_value=10), \
             patch("services.improvement_plan_service.UserMetricsService") as MockMetrics:
            MockMetrics.return_value.score_by_skill.return_value = {}
            result = service._scan(1, plan)

        assert result["needs_update"] is False
        assert result["reason"] == "no_changes_detected"

    def test_scan_triggers_on_weekly_schedule(self):
        from datetime import datetime, timezone, timedelta
        service = ImprovementPlanService.__new__(ImprovementPlanService)
        service.db = MagicMock()

        plan = MagicMock()
        plan.last_evaluation_count = 5
        plan.last_updated_at = datetime.now(timezone.utc) - timedelta(days=8)
        plan.items = []

        with patch.object(service, "_count_total_evaluations", return_value=5), \
             patch("services.improvement_plan_service.UserMetricsService") as MockMetrics:
            MockMetrics.return_value.score_by_skill.return_value = {}
            result = service._scan(1, plan)

        assert result["needs_update"] is True
        assert result["reason"] == "weekly_schedule"

    def test_scan_triggers_on_activity_threshold(self):
        from datetime import datetime, timezone, timedelta
        service = ImprovementPlanService.__new__(ImprovementPlanService)
        service.db = MagicMock()

        plan = MagicMock()
        plan.last_evaluation_count = 5
        plan.last_updated_at = datetime.now(timezone.utc) - timedelta(days=2)
        plan.items = []

        with patch.object(service, "_count_total_evaluations", return_value=8), \
             patch("services.improvement_plan_service.UserMetricsService") as MockMetrics:
            MockMetrics.return_value.score_by_skill.return_value = {}
            result = service._scan(1, plan)

        assert result["needs_update"] is True
        assert result["reason"] == "activity_threshold"

    def test_scan_triggers_when_skill_completed(self):
        from datetime import datetime, timezone, timedelta
        service = ImprovementPlanService.__new__(ImprovementPlanService)
        service.db = MagicMock()

        item = MagicMock()
        item.skill = "Python"
        item.status = "in_progress"
        item.current_score = 60.0
        item.target_score = 70.0

        plan = MagicMock()
        plan.last_evaluation_count = 5
        plan.last_updated_at = datetime.now(timezone.utc) - timedelta(days=2)
        plan.items = [item]

        with patch.object(service, "_count_total_evaluations", return_value=5), \
             patch("services.improvement_plan_service.UserMetricsService") as MockMetrics:
            MockMetrics.return_value.score_by_skill.return_value = {"python": 85.0}
            result = service._scan(1, plan)

        assert result["needs_update"] is True
        assert result["reason"] == "skills_completed"


class TestGetResourcesForSkill:
    def test_skill_conocida_retorna_recursos_especificos(self):
        from utils.improvement_resources import get_resources_for_skill
        resources = get_resources_for_skill("Python")
        assert len(resources) > 0
        assert all("title" in r and "url" in r and "type" in r for r in resources)

    def test_skill_desconocida_retorna_defaults(self):
        from utils.improvement_resources import get_resources_for_skill
        resources = get_resources_for_skill("Fortran")
        assert len(resources) > 0

    def test_case_insensitive(self):
        from utils.improvement_resources import get_resources_for_skill
        assert get_resources_for_skill("python") == get_resources_for_skill("Python")
