from fastapi import APIRouter, Depends, HTTPException
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from ai.ollama_service import OllamaService
from ai.ollama_client import OllamaClient
from core.database import get_db
from core.jwt import get_current_user
from exceptions.profile_exceptions import ProfileNotFoundError
from services.profile_service import ProfileService
from utils.prompts.question_generation import (
    build_question_generation_prompts,
    get_question_generation_options,
)

router = APIRouter(
    prefix="/ai/ollama", 
    tags=["ollama"]
    )

ollama_service = OllamaService()
ollama_client = OllamaClient(ollama_service)
_question_history_by_user: dict[int, list[str]] = {}
_MAX_QUESTION_HISTORY = 30
_MAX_GENERATION_ATTEMPTS = 3
_SIMILARITY_THRESHOLD = 0.82


def _normalize_question(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _merge_previous_questions(*question_lists: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for questions in question_lists:
        for question in questions:
            normalized = _normalize_question(question)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(question)

    return merged


def _question_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_question(a), _normalize_question(b)).ratio()


def _is_repeated_or_too_similar(question: str, previous_questions: list[str]) -> bool:
    normalized_question = _normalize_question(question)
    if not normalized_question:
        return True

    for prev in previous_questions:
        normalized_prev = _normalize_question(prev)
        if normalized_question == normalized_prev:
            return True
        if _question_similarity(normalized_question, normalized_prev) >= _SIMILARITY_THRESHOLD:
            return True

    return False


@router.get("/health")
async def health_check():
    is_healthy = await ollama_service.health_check()

    if is_healthy:
        return {
            "status": "healthy",
            "model": ollama_service.model_name,
            "message": f"Ollama está activo con modelo {ollama_service.model_name}",
        }
    else:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama no está disponible en {ollama_service.base_url}",
        )


@router.post("/ask")
async def ask_model(body: dict):
    """
    Envía un prompt genérico al modelo.
    
    Body:
    {
        "prompt": "Pregunta o mensaje del usuario",
        "system_prompt": "Instrucción personalizada (opcional)",
        "temperature": 0.1 ,
        "num_predict": 256
    }
    """
    try:
        prompt = body.get("prompt")
        if not prompt:
            raise HTTPException(status_code=400, detail="'prompt' es requerido")

        result = await ollama_client.ask(
            question=prompt,
            system_prompt=body.get("system_prompt"),
            temperature=body.get("temperature"),
            num_predict=body.get("num_predict", 256),
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

    Body (all optional):
    {
        "target_skill": "Python",
        "difficulty": "junior|mid|senior|adaptive",
        "previous_questions": ["..."],
        "temperature": 0.1,
        "num_predict": 120
    }
    """
    try:
        body = body or {}

        profile_service = ProfileService(db)
        user_id = current_user["id"]

        profile = profile_service.get_profile_by_user_id(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail=ProfileNotFoundError.default_message)

        skills = profile_service.list_skills(user_id)
        experiences = profile_service.list_experiences(user_id)

        raw_previous = body.get("previous_questions") or []
        body_previous_questions: list[str] = []

        if isinstance(raw_previous, list):
            body_previous_questions = [str(item) for item in raw_previous if str(item).strip()]

        backend_history = _question_history_by_user.get(user_id, [])
        previous_questions = _merge_previous_questions(body_previous_questions, backend_history)

        options = get_question_generation_options(
            {
                "temperature": body.get("temperature"),
                "num_predict": body.get("num_predict"),
            }
        )

        result = ""
        retried = False
        generated_in_request: list[str] = []

        for attempt in range(_MAX_GENERATION_ATTEMPTS):
            combined_previous = _merge_previous_questions(previous_questions, generated_in_request)

            system_prompt, prompt = build_question_generation_prompts(
                profile=profile,
                skills=skills,
                experiences=experiences,
                target_skill=body.get("target_skill"),
                difficulty=body.get("difficulty"),
                previous_questions=combined_previous,
            )

            if attempt > 0:
                retried = True
                forbidden_examples = "\n".join(f"- {item}" for item in combined_previous[-8:])
                system_prompt = (
                    f"{system_prompt} Never repeat previous questions, even if wording changes slightly. "
                    f"Forbidden questions:\n{forbidden_examples}"
                )

            result = await ollama_client.ask(
                question=prompt,
                system_prompt=system_prompt,
                temperature=max(float(options["temperature"]), 0.15) if attempt > 0 else options["temperature"],
                num_predict=options["num_predict"],
            )

            if result and not _is_repeated_or_too_similar(result, combined_previous):
                break

            if result:
                generated_in_request.append(result)

        if not result:
            raise HTTPException(status_code=502, detail="El modelo no devolvio una pregunta valida")

        user_history = list(backend_history)
        if not _is_repeated_or_too_similar(result, user_history):
            user_history.append(result)
        _question_history_by_user[user_id] = user_history[-_MAX_QUESTION_HISTORY:]

        return {
            "question": result,
            "meta": {
                "target_skill": body.get("target_skill"),
                "difficulty": body.get("difficulty", "adaptive"),
                "skills_used": len(skills),
                "experiences_used": len(experiences),
                "retried_for_uniqueness": retried,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

