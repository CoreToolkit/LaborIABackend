# tests/test_recommendations.py
# TASK-027-03: LLM reason generation con fallback
# TASK-027-05: GET /api/recommendations endpoint

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.recommendations as recommendations_module
from core.database import get_db
from core.jwt import get_current_user
from services.recommendation_service import (
    RecommendationService,
    _fallback_reason,
    _generate_reason,
    _priority_from_gaps,
)


def _mock_user(user_id: int = 1):
    return {"id": user_id, "email": "test@example.com", "name": "Test"}


def _make_app(db_mock, user_id: int = 1):
    test_app = FastAPI()
    test_app.include_router(recommendations_module.router, prefix="/api")
    test_app.dependency_overrides[get_db] = lambda: db_mock
    test_app.dependency_overrides[get_current_user] = lambda: _mock_user(user_id)
    return TestClient(test_app)


def _make_match_result(score: float, role_name: str = "Backend Dev", gaps: list = None):
    role = MagicMock()
    role.id = uuid4()
    role.name = role_name
    role.role_skills = []  # sin skills → gaps vacíos por defecto

    mr = MagicMock()
    mr.total_score = score
    mr.job_role = role
    return mr


# ── _priority_from_gaps ───────────────────────────────────────────────────────

class TestPriorityFromGaps:
    def test_sin_gaps_es_low(self):
        assert _priority_from_gaps([]) == "low"

    def test_gap_requerido_es_high(self):
        gaps = [{"name": "Docker", "importance_weight": 8, "is_required": True}]
        assert _priority_from_gaps(gaps) == "high"

    def test_muchos_gaps_no_requeridos_es_medium(self):
        gaps = [
            {"name": "A", "importance_weight": 5, "is_required": False},
            {"name": "B", "importance_weight": 5, "is_required": False},
            {"name": "C", "importance_weight": 5, "is_required": False},
        ]
        assert _priority_from_gaps(gaps) == "medium"

    def test_pocos_gaps_no_requeridos_es_low(self):
        gaps = [{"name": "A", "importance_weight": 3, "is_required": False}]
        assert _priority_from_gaps(gaps) == "low"


# ── _fallback_reason ──────────────────────────────────────────────────────────

class TestFallbackReason:
    def test_contiene_nombre_del_rol(self):
        reason = _fallback_reason("Data Scientist", 75.0)
        assert "Data Scientist" in reason

    def test_contiene_score(self):
        reason = _fallback_reason("Backend Dev", 82.0)
        assert "82" in reason

    def test_retorna_string_no_vacio(self):
        reason = _fallback_reason("Any Role", 50.0)
        assert isinstance(reason, str)
        assert len(reason) > 0


# ── _generate_reason (LLM + fallback) ────────────────────────────────────────

class TestGenerateReason:
    @pytest.mark.asyncio
    async def test_retorna_texto_del_llm_cuando_funciona(self):
        with patch("services.recommendation_service.AzureOpenAIClient") as MockClient:
            instance = MockClient.return_value
            instance.ask = AsyncMock(return_value="Excelente match. Desarrolla tus habilidades en Docker.")

            result = await _generate_reason("Backend Dev", 85.0, [])

        assert result == "Excelente match. Desarrolla tus habilidades en Docker."

    @pytest.mark.asyncio
    async def test_fallback_cuando_llm_falla(self):
        with patch("services.recommendation_service.AzureOpenAIClient") as MockClient:
            instance = MockClient.return_value
            instance.ask = AsyncMock(side_effect=Exception("Azure no disponible"))

            result = await _generate_reason("Data Scientist", 70.0, [])

        # Debe retornar fallback, no lanzar excepción
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Data Scientist" in result

    @pytest.mark.asyncio
    async def test_fallback_cuando_llm_retorna_vacio(self):
        with patch("services.recommendation_service.AzureOpenAIClient") as MockClient:
            instance = MockClient.return_value
            instance.ask = AsyncMock(return_value="")

            result = await _generate_reason("Frontend Dev", 60.0, [])

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_no_bloquea_si_azure_no_configurado(self):
        with patch("services.recommendation_service.AzureOpenAIClient") as MockClient:
            MockClient.side_effect = RuntimeError("Faltan variables de entorno")

            # No debe lanzar excepción
            result = await _generate_reason("DevOps", 55.0, [])

        assert isinstance(result, str)


# ── GET /api/recommendations ──────────────────────────────────────────────────

class TestGetRecommendationsEndpoint:
    def _make_db(self, match_results: list):
        db = MagicMock()
        return db

    def test_usuario_sin_matches_retorna_lista_vacia(self):
        db = MagicMock()

        with patch("api.recommendations.RecommendationService") as MockService:
            instance = MockService.return_value
            instance.get_recommendations = AsyncMock(return_value=[])

            client = _make_app(db)
            response = client.get("/api/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_retorna_items_con_campos_requeridos(self):
        db = MagicMock()
        mock_items = [
            {
                "role_id": str(uuid4()),
                "role_name": "Backend Developer",
                "match_score": 85.0,
                "skill_gaps": [{"name": "Docker", "importance_weight": 8, "is_required": True}],
                "priority": "high",
                "reason": "Excelente compatibilidad con tu perfil.",
            }
        ]

        with patch("api.recommendations.RecommendationService") as MockService:
            instance = MockService.return_value
            instance.get_recommendations = AsyncMock(return_value=mock_items)

            client = _make_app(db)
            response = client.get("/api/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert "role_id" in item
        assert "role_name" in item
        assert "match_score" in item
        assert "skill_gaps" in item
        assert "priority" in item
        assert "reason" in item

    def test_multiples_matches(self):
        db = MagicMock()
        mock_items = [
            {
                "role_id": str(uuid4()),
                "role_name": f"Role {i}",
                "match_score": float(90 - i * 5),
                "skill_gaps": [],
                "priority": "low",
                "reason": "Buena opción para ti.",
            }
            for i in range(3)
        ]

        with patch("api.recommendations.RecommendationService") as MockService:
            instance = MockService.return_value
            instance.get_recommendations = AsyncMock(return_value=mock_items)

            client = _make_app(db)
            response = client.get("/api/recommendations")

        assert response.status_code == 200
        assert response.json()["total"] == 3

    def test_limit_param_se_pasa_al_servicio(self):
        db = MagicMock()

        with patch("api.recommendations.RecommendationService") as MockService:
            instance = MockService.return_value
            instance.get_recommendations = AsyncMock(return_value=[])

            client = _make_app(db)
            client.get("/api/recommendations?limit=5")

            instance.get_recommendations.assert_called_once_with(user_id=1, limit=5)

    def test_skill_gaps_estructura_correcta(self):
        db = MagicMock()
        mock_items = [
            {
                "role_id": str(uuid4()),
                "role_name": "DevOps",
                "match_score": 72.0,
                "skill_gaps": [
                    {"name": "Kubernetes", "importance_weight": 9, "is_required": True},
                    {"name": "Terraform", "importance_weight": 6, "is_required": False},
                ],
                "priority": "high",
                "reason": "Tienes buen potencial para este rol.",
            }
        ]

        with patch("api.recommendations.RecommendationService") as MockService:
            instance = MockService.return_value
            instance.get_recommendations = AsyncMock(return_value=mock_items)

            client = _make_app(db)
            response = client.get("/api/recommendations")

        gaps = response.json()["items"][0]["skill_gaps"]
        assert len(gaps) == 2
        assert gaps[0]["name"] == "Kubernetes"
        assert gaps[0]["is_required"] is True
