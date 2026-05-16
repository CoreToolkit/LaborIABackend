# tests/test_answer_evaluator.py
# ─────────────────────────────────────────────────────────────────────────────
# Tests para US-013: evaluación automática de respuestas.
#
# DOS CATEGORÍAS:
#   Tests unitarios  — mockean _azure_client.ask. No necesitan Azure.
#                      Se corren siempre en CI: pytest tests/test_answer_evaluator.py
#
#   Tests de integración — llaman a Azure OpenAI real. Marcados @pytest.mark.integration
#                          Correr con: pytest -m integration tests/test_answer_evaluator.py
#
# CASOS CONOCIDOS (DoR de US-013, Task-013-05):
#   Cubren los 3 Acceptance Criteria de la historia:
#     - Respuesta excelente → score 85-100
#     - Respuesta parcial   → score 50-70, feedback dice "Correcto pero incompleto"
#     - Respuesta incorrecta → score < 30, feedback dice "Incorrecto"
#     - Respuesta vacía     → score 0, sin llamada a Azure
#     - Respuesta con código → score 80-100
# ─────────────────────────────────────────────────────────────────────────────

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.answer_evaluator import (
    evaluate_answer,
    _format_feedback,
    _normalize,
    _parse_json,
    run_evaluation_background,
)


# ── Casos conocidos (Task-013-05) ─────────────────────────────────────────────

KNOWN_CASES = [
    {
        "id": "correct_complete",
        "question": "¿Qué es un decorador en Python y para qué se usa?",
        "expected_topics": [
            "función que envuelve otra función",
            "sintaxis @",
            "no modifica la función original",
        ],
        "user_answer": (
            "Un decorador es una función que recibe otra función como argumento y extiende "
            "su comportamiento sin modificarla directamente. Se usa con la sintaxis @nombre_decorador. "
            "Por ejemplo, @login_required verifica autenticación antes de ejecutar una vista. "
            "Son muy útiles para logging, control de acceso y caché."
        ),
        "score_min": 85,
        "score_max": 100,
    },
    {
        "id": "partial_rest_api",
        "question": "Explica los principales métodos HTTP usados en REST APIs.",
        "expected_topics": ["GET", "POST", "PUT", "DELETE", "PATCH", "idempotencia"],
        "user_answer": (
            "Los métodos HTTP principales son GET para obtener datos y POST para crear recursos."
        ),
        "score_min": 50,
        "score_max": 70,
    },
    {
        "id": "incorrect_bst",
        "question": "¿Cuál es la complejidad temporal de buscar en un árbol binario de búsqueda balanceado?",
        "expected_topics": ["O(log n)", "tiempo logarítmico", "árbol balanceado"],
        "user_answer": (
            "La búsqueda en un BST es O(1) porque puedes acceder a cualquier nodo directamente."
        ),
        "score_min": 0,
        "score_max": 30,
    },
    {
        "id": "empty",
        "question": "¿Qué es la inyección de dependencias?",
        "expected_topics": ["inversión de control", "acoplamiento débil", "testabilidad"],
        "user_answer": "",
        "score_min": 0,
        "score_max": 0,
    },
    {
        "id": "with_code_example",
        "question": "¿Cómo manejas errores en async/await en JavaScript?",
        "expected_topics": ["try/catch", "async/await", "manejo de errores"],
        "user_answer": (
            "Se usan bloques try/catch alrededor del await:\n"
            "```javascript\n"
            "try {\n"
            "  const data = await fetch(url);\n"
            "  return data.json();\n"
            "} catch (error) {\n"
            "  console.error('Error:', error);\n"
            "}\n"
            "```\n"
            "También se puede usar .catch() directamente en la promesa si no necesitas async/await."
        ),
        "score_min": 80,
        "score_max": 100,
    },
]


# ── Helpers para tests ────────────────────────────────────────────────────────

def _make_azure_response(
    score: int,
    correctness: int = 80,
    completeness: int = 80,
    strengths: list[str] | None = None,
    improvements: list[str] | None = None,
) -> str:
    """Genera una respuesta JSON simulada de Azure OpenAI para tests unitarios."""
    return json.dumps({
        "score": score,
        "score_breakdown": {
            "correctness":  correctness,
            "completeness": completeness,
            "clarity":      80,
            "examples":     70,
        },
        "feedback": {
            "strengths":    strengths or ["Buen manejo del concepto principal"],
            "improvements": improvements or ["Podría agregar más ejemplos concretos"],
            "correction":   None,
        },
        "topics_covered": ["topic_a"],
        "topics_missing":  ["topic_b"],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS UNITARIOS (sin Azure — siempre corren en CI)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmptyAnswer:
    """Respuesta vacía debe retornar score 0 inmediatamente sin llamar a Azure."""

    @pytest.mark.asyncio
    async def test_empty_string_returns_zero_no_api_call(self):
        with patch("services.answer_evaluator._azure_client") as mock_client:
            result = await evaluate_answer("¿Qué es REST?", ["stateless"], "")
        mock_client.ask.assert_not_called()
        assert result["score"] == 0

    @pytest.mark.asyncio
    async def test_whitespace_only_treated_as_empty(self):
        with patch("services.answer_evaluator._azure_client") as mock_client:
            result = await evaluate_answer("¿Qué es REST?", ["stateless"], "   \n\t  ")
        mock_client.ask.assert_not_called()
        assert result["score"] == 0

    @pytest.mark.asyncio
    async def test_empty_answer_has_improvement_message(self):
        result = await evaluate_answer("¿Qué es REST?", ["stateless"], "")
        improvements = result["feedback"].get("improvements", [])
        assert len(improvements) > 0
        assert "no se proporcionó" in improvements[0].lower()


class TestResultStructure:
    """El dict de resultado siempre debe tener los 5 campos requeridos."""

    @pytest.mark.asyncio
    async def test_all_required_fields_present(self):
        with patch("services.answer_evaluator._azure_client") as mock_client:
            mock_client.ask = AsyncMock(return_value=_make_azure_response(75))
            result = await evaluate_answer(
                "¿Qué es una closure?",
                ["scope léxico", "función interna", "variables capturadas"],
                "Una closure es una función que recuerda su scope léxico.",
            )

        assert "score" in result
        assert "score_breakdown" in result
        assert "feedback" in result
        assert "topics_covered" in result
        assert "topics_missing" in result

    @pytest.mark.asyncio
    async def test_score_breakdown_has_four_criteria(self):
        with patch("services.answer_evaluator._azure_client") as mock_client:
            mock_client.ask = AsyncMock(return_value=_make_azure_response(75))
            result = await evaluate_answer("Pregunta", ["topic"], "Respuesta")

        breakdown = result["score_breakdown"]
        assert all(k in breakdown for k in ["correctness", "completeness", "clarity", "examples"])

    @pytest.mark.asyncio
    async def test_score_in_valid_range(self):
        with patch("services.answer_evaluator._azure_client") as mock_client:
            mock_client.ask = AsyncMock(return_value=_make_azure_response(75))
            result = await evaluate_answer("Pregunta", ["topic"], "Respuesta")

        assert 0 <= result["score"] <= 100


class TestScoreClamping:
    """El LLM puede devolver valores fuera de rango — deben clampearse a [0, 100]."""

    @pytest.mark.asyncio
    async def test_score_above_100_is_clamped(self):
        bad_response = json.dumps({
            "score": 150,
            "score_breakdown": {
                "correctness": 200, "completeness": 90, "clarity": 80, "examples": 70,
            },
            "feedback": {}, "topics_covered": [], "topics_missing": [],
        })
        with patch("services.answer_evaluator._azure_client") as mock_client:
            mock_client.ask = AsyncMock(return_value=bad_response)
            result = await evaluate_answer("Pregunta", ["topic"], "Respuesta válida")

        assert result["score"] == 100
        assert result["score_breakdown"]["correctness"] == 100

    @pytest.mark.asyncio
    async def test_score_below_0_is_clamped(self):
        bad_response = json.dumps({
            "score": -10,
            "score_breakdown": {
                "correctness": -5, "completeness": -10, "clarity": 50, "examples": 50,
            },
            "feedback": {}, "topics_covered": [], "topics_missing": [],
        })
        with patch("services.answer_evaluator._azure_client") as mock_client:
            mock_client.ask = AsyncMock(return_value=bad_response)
            result = await evaluate_answer("Pregunta", ["topic"], "Respuesta válida")

        assert result["score"] == 0
        assert result["score_breakdown"]["correctness"] == 0


class TestFallbacks:
    """Errores técnicos deben retornar fallback con score=-1, nunca lanzar excepción."""

    @pytest.mark.asyncio
    async def test_azure_connection_error_returns_fallback(self):
        with patch("services.answer_evaluator._azure_client") as mock_client:
            mock_client.ask = AsyncMock(side_effect=Exception("Connection timeout"))
            result = await evaluate_answer("Pregunta", ["topic"], "Respuesta cualquiera")

        assert result["score"] == -1

    @pytest.mark.asyncio
    async def test_malformed_json_returns_fallback(self):
        with patch("services.answer_evaluator._azure_client") as mock_client:
            mock_client.ask = AsyncMock(return_value="Lo siento, no puedo evaluar esto.")
            result = await evaluate_answer("Pregunta", ["topic"], "Respuesta")

        assert result["score"] == -1

    @pytest.mark.asyncio
    async def test_fallback_does_not_raise_exception(self):
        """La función NUNCA debe lanzar excepción, incluso con error grave."""
        with patch("services.answer_evaluator._azure_client") as mock_client:
            mock_client.ask = AsyncMock(side_effect=RuntimeError("Unexpected error"))
            try:
                result = await evaluate_answer("Pregunta", ["topic"], "Respuesta")
                # Si llegamos aquí, no lanzó excepción — correcto
                assert result["score"] == -1
            except Exception as e:
                pytest.fail(f"evaluate_answer lanzó excepción inesperada: {e}")


class TestRunEvaluationBackground:
    @pytest.mark.asyncio
    async def test_actualiza_metricas_del_usuario_si_la_evaluacion_completa(self):
        db = MagicMock()
        update_query = MagicMock()
        select_query = MagicMock()

        db.query.side_effect = [update_query, select_query]
        update_query.filter.return_value.update.return_value = 1

        evaluation = MagicMock()
        evaluation.interview_session = MagicMock()
        evaluation.interview_session.user_id = 42
        select_query.join.return_value.filter.return_value.first.return_value = evaluation

        with patch("services.answer_evaluator.SessionLocal", return_value=db), \
             patch("services.answer_evaluator.evaluate_answer", AsyncMock(return_value={
                 "score": 88,
                 "score_breakdown": {"correctness": 90, "completeness": 85, "clarity": 80, "examples": 78},
                 "feedback": {"strengths": ["ok"], "improvements": [], "correction": None},
                 "topics_covered": ["t1"],
                 "topics_missing": [],
             })), \
             patch("services.answer_evaluator.UserMetricsService") as MockMetricsService:
            await run_evaluation_background(
                evaluation_id="123e4567-e89b-12d3-a456-426614174000",
                question_text="What is Python?",
                expected_topics=["syntax"],
                user_answer="A language",
            )

        MockMetricsService.return_value.update_for_user.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_no_actualiza_metricas_si_la_evaluacion_falla(self):
        db = MagicMock()
        update_query = MagicMock()
        db.query.return_value = update_query
        update_query.filter.return_value.update.return_value = 1

        with patch("services.answer_evaluator.SessionLocal", return_value=db), \
             patch("services.answer_evaluator.evaluate_answer", AsyncMock(return_value={"score": -1})), \
             patch("services.answer_evaluator.UserMetricsService") as MockMetricsService:
            await run_evaluation_background(
                evaluation_id="123e4567-e89b-12d3-a456-426614174001",
                question_text="What is Python?",
                expected_topics=["syntax"],
                user_answer="A language",
            )

        MockMetricsService.return_value.update_for_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_markdown_wrapped_json_is_parsed_correctly(self):
        """El modelo a veces devuelve ```json ... ``` — debe parsearse igual."""
        wrapped = "```json\n" + _make_azure_response(72) + "\n```"
        with patch("services.answer_evaluator._azure_client") as mock_client:
            mock_client.ask = AsyncMock(return_value=wrapped)
            result = await evaluate_answer("Pregunta", ["topic"], "Respuesta válida")

        assert result["score"] == 72


class TestFormatFeedback:
    """_format_feedback debe producir el header correcto según el score."""

    def test_header_excellent(self):
        result = {"score": 90, "feedback": {}}
        text = _format_feedback(result)
        assert "excelente" in text.lower()

    def test_header_good(self):
        result = {"score": 75, "feedback": {}}
        text = _format_feedback(result)
        assert "buena" in text.lower()

    def test_header_partial(self):
        result = {"score": 55, "feedback": {}}
        text = _format_feedback(result)
        assert "incompleto" in text.lower()

    def test_header_incorrect(self):
        result = {"score": 20, "feedback": {}}
        text = _format_feedback(result)
        assert "incorrecto" in text.lower()

    def test_strengths_included_in_output(self):
        result = {
            "score": 90,
            "feedback": {
                "strengths": ["Buena comprensión", "Ejemplo claro"],
                "improvements": [],
                "correction": None,
            },
        }
        text = _format_feedback(result)
        assert "Buena comprensión" in text

    def test_correction_included_when_present(self):
        result = {
            "score": 20,
            "feedback": {
                "strengths": [],
                "improvements": ["Incorrecto: la complejidad es O(log n)"],
                "correction": "La complejidad correcta es O(log n) en BST balanceado.",
            },
        }
        text = _format_feedback(result)
        assert "O(log n)" in text


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS DE INTEGRACIÓN (requieren Azure OpenAI real)
# Ejecutar con: pytest -m integration tests/test_answer_evaluator.py -v -s
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [c for c in KNOWN_CASES if c["id"] != "empty"],
    ids=[c["id"] for c in KNOWN_CASES if c["id"] != "empty"],
)
async def test_known_case_score_in_expected_range(case):
    """
    Llama a Azure OpenAI real y verifica que el score caiga en el rango esperado.

    Si este test falla consistentemente fuera del rango, revisar los logs de
    _log_score_discrepancy para identificar qué criterio está fuera de calibración
    y ajustar el _SYSTEM_PROMPT o _USER_TEMPLATE.
    """
    result = await evaluate_answer(
        question_text=case["question"],
        expected_topics=case["expected_topics"],
        user_answer=case["user_answer"],
    )

    # Si score=-1, hubo fallo técnico — no es un fallo de evaluación
    assert result["score"] != -1, (
        f"Fallo técnico en caso '{case['id']}'. "
        f"Verificar conexión con Azure OpenAI."
    )

    score = result["score"]
    assert case["score_min"] <= score <= case["score_max"], (
        f"Caso '{case['id']}': score={score} fuera del rango "
        f"[{case['score_min']}, {case['score_max']}]\n"
        f"Feedback: {result.get('feedback')}\n"
        f"Breakdown: {result.get('score_breakdown')}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_answer_with_real_service_returns_zero_without_api_call():
    """
    Caso vacío: score=0 sin llamar a Azure (verificado también en integración).
    Este test no consume cuota porque la respuesta vacía se intercepta antes.
    """
    result = await evaluate_answer(
        question_text="¿Qué es la inyección de dependencias?",
        expected_topics=["inversión de control", "acoplamiento débil"],
        user_answer="",
    )
    assert result["score"] == 0
    assert result["topics_covered"] == []
