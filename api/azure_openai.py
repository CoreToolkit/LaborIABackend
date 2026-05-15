from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from ai.azure_openai_client import AzureOpenAIClient
from ai.azure_openai_service import AzureOpenAIService
from ai.question_deduplication import (
    merge_previous_questions,
    is_repeated_or_too_similar,
    MAX_QUESTION_HISTORY,
    MAX_GENERATION_ATTEMPTS,
)
from core.database import get_db
from core.jwt import get_current_user
from exceptions.profile_exceptions import ProfileNotFoundError
from services.global_question_service import GlobalQuestionService
from services.profile_service import ProfileService
from services.skill_selector import get_session_used_skills, select_target_skill
from utils.prompts.question_generation import (
    build_question_generation_prompts,
    get_question_generation_options,
)

router = APIRouter(
    prefix="/ai/azure-openai",
    tags=["azure-openai"],
)

azure_openai_service = AzureOpenAIService()
azure_openai_client = AzureOpenAIClient(azure_openai_service)
_question_history_by_user: dict[int, list[str]] = {}


@router.get("/health")
async def health_check():
    is_healthy = await azure_openai_service.health_check()

    if is_healthy:
        return {
            "status": "healthy",
            "deployment": azure_openai_service.deployment_name,
            "api_version": azure_openai_service.api_version,
            "message": "Azure OpenAI esta disponible",
        }

    raise HTTPException(
        status_code=503,
        detail="Azure OpenAI no esta disponible o el deployment no responde",
    )


@router.post("/ask")
async def ask_model(body: dict):
    """
    Envia un prompt generico al deployment de Azure OpenAI.

    Body:
    {
        "prompt": "Pregunta o mensaje del usuario",
        "system_prompt": "Instruccion personalizada (opcional)",
        "temperature": 0.1,
        "max_tokens": 256,
        "top_p": 1.0
    }
    """
    try:
        prompt = body.get("prompt")
        if not prompt:
            raise HTTPException(status_code=400, detail="'prompt' es requerido")

        result = await azure_openai_client.ask(
            question=prompt,
            system_prompt=body.get("system_prompt"),
            temperature=body.get("temperature"),
            max_tokens=body.get("max_tokens", 256),
            top_p=body.get("top_p"),
        )
        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interview/question")
async def generate_interview_question(
    body: dict | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Generate one interview question using backend-owned profile context.
    Uses Azure OpenAI for question generation.

    Body (all optional):
    {
        "session_id": 42,
        "target_skill": "Python",
        "difficulty": "junior|mid|senior|adaptive",
        "previous_questions": ["..."],
        "temperature": 0.1,
        "max_tokens": 150
    }

    When target_skill is omitted the backend infers the next skill to cover from
    the user's profile, rotating through uncovered skills in the session.
    """
    try:
        body = body or {}

        profile_service = ProfileService(db)
        global_question_service = GlobalQuestionService(db)
        user_id = current_user["id"]

        profile = profile_service.get_profile_by_user_id(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail=ProfileNotFoundError.default_message)

        skills = profile_service.list_skills(user_id)
        experiences = profile_service.list_experiences(user_id)

        target_skill: str | None = body.get("target_skill")
        if not target_skill:
            session_id: int | None = body.get("session_id")
            used_skills: list[str] = (
                get_session_used_skills(db, session_id, user_id)
                if session_id
                else []
            )
            target_skill = select_target_skill(list(skills), used_skills)

        raw_previous = body.get("previous_questions") or []
        body_previous_questions: list[str] = []

        if isinstance(raw_previous, list):
            body_previous_questions = [str(item) for item in raw_previous if str(item).strip()]

        backend_history = _question_history_by_user.get(user_id, [])
        global_history = global_question_service.list_all_questions_texts()
        previous_questions = merge_previous_questions(
            body_previous_questions,
            backend_history,
            global_history,
        )
        prompt_history = merge_previous_questions(
            body_previous_questions,
            backend_history,
            global_history[-60:],
        )

        options = get_question_generation_options(
            {
                "temperature": body.get("temperature"),
                "num_predict": body.get("max_tokens"),
            }
        )

        result = ""
        retried = False
        generated_in_request: list[str] = []

        for attempt in range(MAX_GENERATION_ATTEMPTS):
            combined_previous = merge_previous_questions(previous_questions, generated_in_request)
            prompt_previous = merge_previous_questions(prompt_history, generated_in_request)

            system_prompt, prompt = build_question_generation_prompts(
                profile=profile,
                skills=skills,
                experiences=experiences,
                target_skill=target_skill,
                difficulty=body.get("difficulty"),
                previous_questions=prompt_previous,
            )

            if attempt > 0:
                retried = True
                forbidden_examples = "\n".join(f"- {item}" for item in combined_previous[-8:])
                system_prompt = (
                    f"{system_prompt} Never repeat previous questions, even if wording changes slightly. "
                    f"Forbidden questions:\n{forbidden_examples}"
                )

            result = await azure_openai_client.ask(
                question=prompt,
                system_prompt=system_prompt,
                temperature=max(float(options["temperature"]), 0.15) if attempt > 0 else options["temperature"],
                max_tokens=options["num_predict"],
            )

            if result and not is_repeated_or_too_similar(result, combined_previous):
                break

            if result:
                generated_in_request.append(result)

        if not result:
            raise HTTPException(status_code=502, detail="El modelo no devolvio una pregunta valida")

        user_history = list(backend_history)
        if not is_repeated_or_too_similar(result, user_history):
            user_history.append(result)
        _question_history_by_user[user_id] = user_history[-MAX_QUESTION_HISTORY:]

        global_question_service.record_question(result)

        return {
            "question": result,
            "meta": {
                "target_skill": target_skill,
                "difficulty": body.get("difficulty", "adaptive"),
                "skills_used": len(skills),
                "experiences_used": len(experiences),
                "retried_for_uniqueness": retried,
                "source": "azure_openai",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
