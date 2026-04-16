from ai.azure_openai_client import AzureOpenAIClient
from exceptions.profile_exceptions import ProfileNotFoundError
from services.group_interview_round_service import GroupInterviewRoundService
from services.group_interview_session_service import GroupInterviewSessionService
from services.profile_service import ProfileService
from utils.prompts.question_generation import build_group_question_generation_prompts


class GroupInterviewOrchestratorService:
    def __init__(self, db):
        self.profile_service = ProfileService(db)
        self.group_session_service = GroupInterviewSessionService(db)
        self.round_service = GroupInterviewRoundService(db)
        self.azure_client = AzureOpenAIClient()

    async def generate_next_round_question(
        self,
        session_code: str,
        requester_id: int,
        target_skill: str | None = None,
        difficulty: str | None = None,
    ):
        group_session = self.group_session_service.get_group_session_by_code(session_code)

        if group_session.host_id != requester_id:
            raise PermissionError("Solo el host puede generar la siguiente pregunta")

        if group_session.status != "in_progress":
            raise ValueError("La sesión grupal debe estar en estado 'in_progress'")

        profile = self.profile_service.get_profile_by_user_id(requester_id)
        if not profile:
            raise ProfileNotFoundError()

        skills = self.profile_service.list_skills(requester_id)
        experiences = self.profile_service.list_experiences(requester_id)

        effective_difficulty = difficulty or group_session.difficulty or "adaptive"
        previous_rounds = self.round_service.round_repo.list_by_session_id(group_session.id)
        previous_questions = [
            item.question_text.strip()
            for item in previous_rounds
            if item.question_text and item.question_text.strip()
        ]

        role_name = group_session.role.name if group_session.role else "rol tecnico"
        role_description = group_session.role.description if group_session.role else ""

        system_prompt, prompt = build_group_question_generation_prompts(
            profile=profile,
            skills=skills,
            experiences=experiences,
            role_name=role_name,
            role_description=role_description,
            target_skill=target_skill,
            difficulty=effective_difficulty,
            previous_questions=previous_questions,
        )

        try:
            generated_question = await self.azure_client.ask(
                question=prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=180,
            )
        except Exception as exc:
            raise RuntimeError(f"Error al generar pregunta con IA: {exc}") from exc

        if not generated_question or not generated_question.strip():
            raise RuntimeError("La IA no devolvió una pregunta válida")

        round_item = self.round_service.create_next_round(
            group_session_id=group_session.id,
            question_text=generated_question.strip(),
            target_skill=target_skill,
            difficulty=effective_difficulty,
            created_by=requester_id,
        )

        return group_session, round_item