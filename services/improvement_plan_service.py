from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.improvement_plan import ImprovementPlan, ImprovementPlanHistory, ImprovementPlanItem
from services.metrics_service import UserMetricsService
from utils.improvement_resources import get_resources_for_skill

logger = logging.getLogger(__name__)

SCORE_COMPLETION_THRESHOLD = 70.0
WEEKLY_UPDATE_DAYS = 7
ACTIVITY_TRIGGER_EVALUATIONS = 3


class ImprovementPlanService:
    def __init__(self, db: Session):
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def get_or_create_plan(self, user_id: int) -> ImprovementPlan:
        plan = self.db.query(ImprovementPlan).filter(ImprovementPlan.user_id == user_id).first()
        if not plan:
            plan = self._build_initial_plan(user_id)
        return plan

    def get_history(self, user_id: int) -> list[ImprovementPlanHistory]:
        return (
            self.db.query(ImprovementPlanHistory)
            .filter(ImprovementPlanHistory.user_id == user_id)
            .order_by(ImprovementPlanHistory.created_at.desc())
            .all()
        )

    def refresh(self, user_id: int, trigger: str = "manual") -> dict:
        """
        Scan → decide if update is needed → update if so.
        Returns {"updated": bool, "reason": str, "plan": ImprovementPlan}
        """
        plan = self.get_or_create_plan(user_id)
        scan = self._scan(user_id, plan)

        if not scan["needs_update"]:
            return {"updated": False, "reason": scan["reason"], "plan": plan}

        self._mark_completed_items(plan, scan["current_scores"])
        updated_plan = self._update_plan_with_ai(user_id, plan, trigger, scan)
        return {"updated": True, "reason": scan["reason"], "plan": updated_plan}

    # ── Scan ──────────────────────────────────────────────────────────────────

    def _scan(self, user_id: int, plan: ImprovementPlan) -> dict:
        """
        Check if an update is warranted without calling AI.
        Returns reason and current scores for use in subsequent steps.
        """
        metrics_service = UserMetricsService(self.db)
        current_scores: dict[str, float] = metrics_service.score_by_skill(user_id)
        total_evals = self._count_total_evaluations(user_id)

        new_evals_since_last = total_evals - plan.last_evaluation_count

        # Weekly trigger
        now = datetime.now(timezone.utc)
        last_updated = plan.last_updated_at
        if last_updated and last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)

        days_since_update = (now - last_updated).days if last_updated else WEEKLY_UPDATE_DAYS + 1

        if days_since_update >= WEEKLY_UPDATE_DAYS:
            return {"needs_update": True, "reason": "weekly_schedule", "current_scores": current_scores, "new_evals": new_evals_since_last}

        # Activity trigger
        if new_evals_since_last >= ACTIVITY_TRIGGER_EVALUATIONS:
            return {"needs_update": True, "reason": "activity_threshold", "current_scores": current_scores, "new_evals": new_evals_since_last}

        # Items completed trigger
        completed_skills = [
            item.skill for item in plan.items
            if item.status != "completed"
            and current_scores.get(item.skill.lower(), item.current_score or 0) >= item.target_score
        ]
        if completed_skills:
            return {"needs_update": True, "reason": "skills_completed", "current_scores": current_scores, "new_evals": new_evals_since_last}

        return {"needs_update": False, "reason": "no_changes_detected", "current_scores": current_scores, "new_evals": new_evals_since_last}

    # ── Build initial plan ────────────────────────────────────────────────────

    def _build_initial_plan(self, user_id: int) -> ImprovementPlan:
        metrics_service = UserMetricsService(self.db)
        weak_areas = metrics_service.analyze_weak_areas(user_id, threshold=SCORE_COMPLETION_THRESHOLD)
        current_scores = metrics_service.score_by_skill(user_id)
        total_evals = self._count_total_evaluations(user_id)

        recent_feedback = self._get_recent_evaluation_feedback(user_id, limit=5)
        ai_feedbacks: dict[str, str] = {}
        if weak_areas and recent_feedback:
            ai_feedbacks = self._call_ai_for_feedback(
                [a["skill"] for a in weak_areas], recent_feedback, current_scores
            )

        plan = ImprovementPlan(user_id=user_id, last_evaluation_count=total_evals)
        self.db.add(plan)
        self.db.flush()

        if not weak_areas:
            # No weak areas yet — add top skills from profile as pending improvement
            from services.profile_service import ProfileService
            skills = ProfileService(self.db).list_skills(user_id)
            for skill in list(skills)[:3]:
                skill_name = getattr(skill, "name", None)
                if not skill_name:
                    continue
                item = ImprovementPlanItem(
                    plan_id=plan.id,
                    skill=str(skill_name),
                    priority="low",
                    current_score=current_scores.get(str(skill_name).lower()),
                    target_score=SCORE_COMPLETION_THRESHOLD,
                    resources=get_resources_for_skill(str(skill_name)),
                )
                self.db.add(item)
        else:
            for area in weak_areas:
                item = ImprovementPlanItem(
                    plan_id=plan.id,
                    skill=area["skill"],
                    priority=area["priority"],
                    current_score=area["score"],
                    target_score=SCORE_COMPLETION_THRESHOLD,
                    resources=get_resources_for_skill(area["skill"]),
                    ai_feedback=ai_feedbacks.get(area["skill"].lower()),
                )
                self.db.add(item)

        self.db.commit()
        self.db.refresh(plan)
        self._save_history(user_id, plan, trigger="initial")
        return plan

    # ── Mark completed items ──────────────────────────────────────────────────

    def _mark_completed_items(self, plan: ImprovementPlan, current_scores: dict[str, float]) -> None:
        changed = False
        for item in plan.items:
            if item.status == "completed":
                continue
            score = current_scores.get(item.skill.lower())
            if score is not None:
                item.current_score = score
                if score >= item.target_score:
                    item.status = "completed"
                    item.completed_at = datetime.now(timezone.utc)
                    changed = True
                elif score > 0:
                    item.status = "in_progress"
                    changed = True
        if changed:
            self.db.flush()

    # ── AI update ────────────────────────────────────────────────────────────

    def _update_plan_with_ai(
        self,
        user_id: int,
        plan: ImprovementPlan,
        trigger: str,
        scan: dict,
    ) -> ImprovementPlan:
        """
        Uses Azure OpenAI to generate feedback on recurring failures and
        new resources for uncompleted/new weak skills. Falls back gracefully.
        """
        metrics_service = UserMetricsService(self.db)
        current_scores = scan["current_scores"]
        weak_areas = metrics_service.analyze_weak_areas(user_id, threshold=SCORE_COMPLETION_THRESHOLD)
        recent_feedback = self._get_recent_evaluation_feedback(user_id, limit=5)

        # Skills that still need work
        pending_skills = [a["skill"] for a in weak_areas]

        ai_feedbacks: dict[str, str] = {}
        if pending_skills and recent_feedback:
            ai_feedbacks = self._call_ai_for_feedback(pending_skills, recent_feedback, current_scores)

        # Rebuild items: keep completed, refresh pending/in_progress
        completed_items = [i for i in plan.items if i.status == "completed"]
        for item in list(plan.items):
            if item.status != "completed":
                self.db.delete(item)
        self.db.flush()

        for area in weak_areas:
            item = ImprovementPlanItem(
                plan_id=plan.id,
                skill=area["skill"],
                priority=area["priority"],
                current_score=area["score"],
                target_score=SCORE_COMPLETION_THRESHOLD,
                resources=get_resources_for_skill(area["skill"]),
                ai_feedback=ai_feedbacks.get(area["skill"].lower()),
            )
            self.db.add(item)

        total_evals = self._count_total_evaluations(user_id)
        plan.version += 1
        plan.last_evaluation_count = total_evals
        self.db.flush()
        self.db.commit()
        self.db.refresh(plan)

        self._save_history(user_id, plan, trigger=trigger)
        return plan

    def _call_ai_for_feedback(
        self,
        skills: list[str],
        recent_feedback: list[str],
        current_scores: dict[str, float],
    ) -> dict[str, str]:
        """
        Calls Azure OpenAI to get personalized feedback per skill based on
        recent evaluation feedback. Returns {skill_lower: feedback_text}.
        Falls back to empty dict on any error.
        """
        try:
            import asyncio
            from ai.azure_openai_client import AzureOpenAIClient
            from ai.azure_openai_service import AzureOpenAIService

            skills_summary = ", ".join(skills)
            scores_summary = "; ".join(f"{k}: {v:.1f}" for k, v in current_scores.items() if k in [s.lower() for s in skills])
            feedback_summary = "\n".join(f"- {f}" for f in recent_feedback[:5])

            system_prompt = (
                "Eres un coach técnico de entrevistas. Analiza el historial de feedback de un candidato "
                "e identifica patrones de falla recurrentes por skill. "
                "Responde en JSON con el formato: {\"skill_name\": \"feedback corto en español (max 2 oraciones)\"}. "
                "Solo incluye las skills con patrones de falla claros."
            )
            user_prompt = (
                f"Skills a mejorar: {skills_summary}\n"
                f"Scores actuales: {scores_summary}\n"
                f"Feedback reciente de evaluaciones:\n{feedback_summary}\n\n"
                "Genera feedback personalizado por skill basado en los patrones de falla detectados."
            )

            service = AzureOpenAIService()
            client = AzureOpenAIClient(service)

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    client.ask(question=user_prompt, system_prompt=system_prompt, max_tokens=400)
                )
            finally:
                loop.close()

            if not result:
                return {}

            # Parse JSON response — strip markdown fences if present
            clean = result.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(clean)
            return {k.lower(): v for k, v in parsed.items() if isinstance(v, str)}

        except Exception as exc:
            logger.warning("improvement_plan: AI feedback call failed: %s", exc)
            return {}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _count_total_evaluations(self, user_id: int) -> int:
        from models.evaluation import Evaluation, EvaluationStatus
        from models.interview_session import InterviewSession
        from sqlalchemy import func as sqlfunc

        return (
            self.db.query(sqlfunc.count(Evaluation.id))
            .join(InterviewSession, Evaluation.interview_session_id == InterviewSession.id)
            .filter(
                InterviewSession.user_id == user_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
            )
            .scalar()
            or 0
        )

    def _get_recent_evaluation_feedback(self, user_id: int, limit: int = 5) -> list[str]:
        from models.evaluation import Evaluation, EvaluationStatus
        from models.interview_session import InterviewSession

        rows = (
            self.db.query(Evaluation.feedback)
            .join(InterviewSession, Evaluation.interview_session_id == InterviewSession.id)
            .filter(
                InterviewSession.user_id == user_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
                Evaluation.feedback.isnot(None),
            )
            .order_by(Evaluation.id.desc())
            .limit(limit)
            .all()
        )
        return [row[0] for row in rows if row[0] and str(row[0]).strip()]

    def _save_history(self, user_id: int, plan: ImprovementPlan, trigger: str) -> None:
        snapshot = {
            "version": plan.version,
            "items": [
                {
                    "skill": item.skill,
                    "priority": item.priority,
                    "current_score": item.current_score,
                    "target_score": item.target_score,
                    "status": item.status,
                    "resources": item.resources,
                    "ai_feedback": item.ai_feedback,
                }
                for item in plan.items
            ],
        }
        history = ImprovementPlanHistory(
            user_id=user_id,
            version=plan.version,
            trigger=trigger,
            snapshot=snapshot,
        )
        self.db.add(history)
        self.db.commit()
