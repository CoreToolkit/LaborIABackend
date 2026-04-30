# services/recommendation_service.py
# ─────────────────────────────────────────────────────────────────────────────
# RecommendationService: genera recomendaciones de roles personalizadas
# combinando MatchResult (score) + skill_gaps + reason generado por LLM.
#
# TASK-027-03: LLM genera el campo reason en español (máx 2 oraciones).
#              Fallback a texto genérico si Azure falla — nunca bloquea.
# TASK-027-05: get_recommendations() retorna lista ordenada por score desc
#              con { role_id, role_name, match_score, skill_gaps, priority }.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from ai.azure_openai_client import AzureOpenAIClient
from repositories.match_result_repository import MatchResultRepository
from repositories.profile_repository import ProfileRepository
from services.matching_service import MatchingService
from utils.string_normalization import normalize_skill_name

logger = logging.getLogger(__name__)

_REASON_SYSTEM_PROMPT = (
    "Eres un asistente de orientación profesional. "
    "Responde siempre en español. "
    "Genera exactamente 2 oraciones cortas y motivadoras explicando por qué "
    "este rol es una buena opción para el candidato según su score de match y sus brechas de habilidades."
)


def _detect_skill_gaps_top3(normalized_user_skills: set[str], role) -> list[dict]:
    """Retorna top 3 skill gaps (name, importance_weight) para el rol dado."""
    all_gaps = MatchingService._detect_skill_gaps_for_role(normalized_user_skills, role)
    # Ordenar por importance_weight desc y tomar top 3
    sorted_gaps = sorted(all_gaps, key=lambda g: g["importance_weight"], reverse=True)
    return [{"name": g["name"], "importance_weight": g["importance_weight"]} for g in sorted_gaps[:3]]


def _priority_from_gaps(skill_gaps: list[dict]) -> str:
    """Determina prioridad según cantidad y peso de skill gaps."""
    if not skill_gaps:
        return "low"
    required_gaps = [g for g in skill_gaps if g.get("is_required")]
    if required_gaps:
        return "high"
    if len(skill_gaps) >= 3:
        return "medium"
    return "low"


async def _generate_reason(role_name: str, match_score: float, skill_gaps: list[dict]) -> str:
    """
    Llama a Azure OpenAI para generar el campo reason.
    Fallback a texto genérico si falla — nunca lanza excepción.
    """
    try:
        client = AzureOpenAIClient()

        gaps_text = ""
        if skill_gaps:
            gap_names = ", ".join(g["name"] for g in skill_gaps[:3])
            gaps_text = f" Las principales brechas son: {gap_names}."

        prompt = (
            f"El candidato tiene un match de {match_score:.0f}% para el rol '{role_name}'.{gaps_text} "
            f"Genera la recomendación."
        )

        reason = await client.ask(
            question=prompt,
            system_prompt=_REASON_SYSTEM_PROMPT,
            max_tokens=120,
            temperature=0.7,
        )
        return reason.strip() if reason else _fallback_reason(role_name, match_score)

    except Exception as exc:
        logger.warning("LLM reason generation failed for role '%s': %s", role_name, exc)
        return _fallback_reason(role_name, match_score)


def _fallback_reason(role_name: str, match_score: float) -> str:
    """Texto genérico cuando Azure falla."""
    return (
        f"Tu perfil tiene un {match_score:.0f}% de compatibilidad con el rol de {role_name}. "
        f"Trabajar en las brechas identificadas puede aumentar significativamente tus posibilidades."
    )


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db
        self.match_repo = MatchResultRepository(db)
        self.profile_repo = ProfileRepository(db)

    async def get_recommendations(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[dict]:
        """
        Retorna recomendaciones de roles ordenadas por match_score desc.
        Cada ítem incluye: role_id, role_name, match_score, skill_gaps, priority, reason.
        El campo reason se genera con LLM; si falla usa fallback genérico.
        """
        match_results = self.match_repo.list_top_recommendations_by_user_id(user_id, limit=limit)

        if not match_results:
            return []

        # Obtener skills del usuario para calcular gaps
        profile = self.profile_repo.get_by_user_id(user_id)
        normalized_skills: set[str] = set()
        if profile:
            skills = self.profile_repo.list_skills_by_profile_id(profile.id)
            normalized_skills = {
                normalize_skill_name(s.name)
                for s in skills
                if normalize_skill_name(s.name)
            }
        # Generar reasons en paralelo para no bloquear
        async def _build_item(match_result) -> dict:
            role = match_result.job_role
            if role is None:
                return None

            match_score = float(match_result.total_score)
            skill_gaps = MatchingService._detect_skill_gaps_for_role(normalized_skills, role)
            priority = _priority_from_gaps(skill_gaps)
            reason = await _generate_reason(role.name, match_score, skill_gaps)

            return {
                "role_id": str(role.id),
                "role_name": role.name,
                "match_score": match_score,
                "skill_gaps": skill_gaps,
                "priority": priority,
                "reason": reason,
            }

        tasks = [_build_item(mr) for mr in match_results]
        items = await asyncio.gather(*tasks)
        return [item for item in items if item is not None]
