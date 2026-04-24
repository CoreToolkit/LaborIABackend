# tests/test_metrics_service.py
# Tests para UserMetricsService: calculate_average_score, score_by_category, analyze_weak_areas

from unittest.mock import MagicMock, patch

import pytest

from models.evaluation import Evaluation, EvaluationStatus
from services.metrics_service import UserMetricsService


def _make_evaluation(score: float, breakdown: dict | None = None, status=EvaluationStatus.COMPLETED) -> Evaluation:
    """Helper para crear un mock de Evaluation."""
    ev = MagicMock(spec=Evaluation)
    ev.score = score
    ev.status = status
    ev.score_breakdown = breakdown
    return ev


# ── calculate_average_score ───────────────────────────────────────────────────

class TestCalculateAverageScore:
    def _service_with_evals(self, evaluations: list) -> UserMetricsService:
        db = MagicMock()
        service = UserMetricsService(db)
        service._get_completed_evaluations = MagicMock(return_value=evaluations)
        return service

    def test_sin_evaluaciones_retorna_cero(self):
        service = self._service_with_evals([])
        assert service.calculate_average_score(user_id=1) == 0.0

    def test_una_evaluacion(self):
        service = self._service_with_evals([_make_evaluation(80.0)])
        assert service.calculate_average_score(user_id=1) == 80.0

    def test_multiples_evaluaciones(self):
        evals = [_make_evaluation(60.0), _make_evaluation(80.0), _make_evaluation(100.0)]
        service = self._service_with_evals(evals)
        assert service.calculate_average_score(user_id=1) == 80.0

    def test_redondeo_a_dos_decimales(self):
        evals = [_make_evaluation(70.0), _make_evaluation(80.0), _make_evaluation(90.0)]
        service = self._service_with_evals(evals)
        result = service.calculate_average_score(user_id=1)
        assert result == 80.0

    def test_excluye_score_negativo_via_query(self):
        # score=-1 es excluido por la query (_get_completed_evaluations filtra score >= 0)
        # Si la query devuelve vacío (como debería), retorna 0.0
        service = self._service_with_evals([])
        assert service.calculate_average_score(user_id=1) == 0.0

    def test_score_con_decimales(self):
        evals = [_make_evaluation(75.5), _make_evaluation(84.3)]
        service = self._service_with_evals(evals)
        assert service.calculate_average_score(user_id=1) == 79.9

    def test_fallback_score_negativo_en_lista(self):
        # Si por alguna razón score=-1 llega a la función, debe ser ignorado
        evals = [_make_evaluation(-1.0), _make_evaluation(80.0)]
        service = self._service_with_evals(evals)
        assert service.calculate_average_score(user_id=1) == 80.0

    def test_fallback_todos_scores_negativos_retorna_cero(self):
        # Si todos los scores son -1 (fallos técnicos), retorna 0.0
        evals = [_make_evaluation(-1.0), _make_evaluation(-1.0)]
        service = self._service_with_evals(evals)
        assert service.calculate_average_score(user_id=1) == 0.0

    def test_fallback_score_none_es_ignorado(self):
        # Score None no debe romper el cálculo
        evals = [_make_evaluation(None), _make_evaluation(60.0)]
        service = self._service_with_evals(evals)
        assert service.calculate_average_score(user_id=1) == 60.0


# ── score_by_category ─────────────────────────────────────────────────────────

class TestScoreByCategory:
    def _service_with_evals(self, evaluations: list) -> UserMetricsService:
        db = MagicMock()
        service = UserMetricsService(db)
        service._get_completed_evaluations = MagicMock(return_value=evaluations)
        return service

    def test_sin_evaluaciones_retorna_dict_vacio(self):
        service = self._service_with_evals([])
        assert service.score_by_category(user_id=1) == {}

    def test_una_evaluacion_con_breakdown(self):
        breakdown = {"correctness": 80.0, "completeness": 70.0, "clarity": 75.0, "examples": 60.0}
        service = self._service_with_evals([_make_evaluation(75.0, breakdown)])
        result = service.score_by_category(user_id=1)
        assert result["correctness"] == 80.0
        assert result["completeness"] == 70.0
        assert result["clarity"] == 75.0
        assert result["examples"] == 60.0

    def test_multiples_evaluaciones_promedia_por_categoria(self):
        b1 = {"correctness": 60.0, "completeness": 80.0}
        b2 = {"correctness": 80.0, "completeness": 60.0}
        service = self._service_with_evals([
            _make_evaluation(70.0, b1),
            _make_evaluation(70.0, b2),
        ])
        result = service.score_by_category(user_id=1)
        assert result["correctness"] == 70.0
        assert result["completeness"] == 70.0

    def test_ignora_evaluaciones_sin_breakdown(self):
        evals = [
            _make_evaluation(80.0, {"correctness": 80.0}),
            _make_evaluation(70.0, None),  # sin breakdown
        ]
        service = self._service_with_evals(evals)
        result = service.score_by_category(user_id=1)
        assert "correctness" in result
        assert result["correctness"] == 80.0

    def test_multiples_categorias_independientes(self):
        b1 = {"correctness": 90.0, "examples": 40.0}
        b2 = {"correctness": 70.0, "clarity": 85.0}
        service = self._service_with_evals([
            _make_evaluation(65.0, b1),
            _make_evaluation(77.5, b2),
        ])
        result = service.score_by_category(user_id=1)
        assert result["correctness"] == 80.0
        assert result["examples"] == 40.0
        assert result["clarity"] == 85.0


# ── analyze_weak_areas ────────────────────────────────────────────────────────

class TestAnalyzeWeakAreas:
    def _service_with_categories(self, categories: dict) -> UserMetricsService:
        db = MagicMock()
        service = UserMetricsService(db)
        service.score_by_category = MagicMock(return_value=categories)
        return service

    def test_sin_areas_debiles(self):
        service = self._service_with_categories({"correctness": 80.0, "clarity": 75.0})
        result = service.analyze_weak_areas(user_id=1)
        assert result == []

    def test_todas_las_areas_son_debiles(self):
        service = self._service_with_categories({"correctness": 35.0, "clarity": 45.0, "examples": 55.0})
        result = service.analyze_weak_areas(user_id=1)
        assert len(result) == 3

    def test_ordenado_por_score_ascendente(self):
        service = self._service_with_categories({"correctness": 55.0, "clarity": 30.0, "examples": 45.0})
        result = service.analyze_weak_areas(user_id=1)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores)

    def test_priority_high_cuando_score_menor_40(self):
        service = self._service_with_categories({"correctness": 35.0})
        result = service.analyze_weak_areas(user_id=1)
        assert result[0]["priority"] == "high"

    def test_priority_medium_cuando_score_entre_40_y_50(self):
        service = self._service_with_categories({"correctness": 45.0})
        result = service.analyze_weak_areas(user_id=1)
        assert result[0]["priority"] == "medium"

    def test_priority_low_cuando_score_entre_50_y_umbral(self):
        service = self._service_with_categories({"correctness": 55.0})
        result = service.analyze_weak_areas(user_id=1)
        assert result[0]["priority"] == "low"

    def test_umbral_configurable(self):
        service = self._service_with_categories({"correctness": 65.0, "clarity": 80.0})
        result = service.analyze_weak_areas(user_id=1, threshold=70.0)
        assert len(result) == 1
        assert result[0]["skill"] == "correctness"

    def test_estructura_de_cada_item(self):
        service = self._service_with_categories({"examples": 40.0})
        result = service.analyze_weak_areas(user_id=1)
        assert "skill" in result[0]
        assert "score" in result[0]
        assert "priority" in result[0]

    def test_umbral_default_es_60(self):
        service = self._service_with_categories({"correctness": 59.9, "clarity": 60.0})
        result = service.analyze_weak_areas(user_id=1)
        # 59.9 < 60 → débil; 60.0 no es < 60 → no débil
        assert len(result) == 1
        assert result[0]["skill"] == "correctness"
