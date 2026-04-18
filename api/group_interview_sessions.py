import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from exceptions.profile_exceptions import ProfileNotFoundError
from models.group_interview_round import GroupInterviewRound, GroupInterviewRoundStatus
from schemas.group_interview_session import (
    GroupInterviewSessionCreateSchema,
    GroupInterviewSessionDetailSchema,
    GroupInterviewSessionResponseSchema,
)
from schemas.group_interview_round import (
    GroupInterviewNextRoundRequestSchema,
    GroupInterviewRoundNextResponseSchema,
)
from services.group_interview_orchestrator_service import GroupInterviewOrchestratorService
from services.group_interview_session_service import GroupInterviewSessionService
from services.websocket_service import manager


router = APIRouter(
    prefix="/group-sessions",
    tags=["Group Interview Sessions"],
)

logger = logging.getLogger(__name__)


def _session_timestamp(session) -> str:
    if session.updated_at:
        return session.updated_at.astimezone(timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


async def _broadcast_group_event(session_code: str, event_payload: dict):
    try:
        await manager.broadcast_text(
            json.dumps(event_payload),
            session_code,
        )
    except Exception:
        logger.exception("Failed broadcasting event for group session %s", session_code)


@router.post("")
def create_group_session(
    request: GroupInterviewSessionCreateSchema,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Crear una nueva sesión grupal de entrevista."""
    service = GroupInterviewSessionService(db)
    
    try:
        new_group_session = service.create_group_session(
            host_id=current_user["id"],
            role_id=request.role_id,
            difficulty=request.difficulty,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        ) from exc
    
    response.status_code = status.HTTP_201_CREATED
    return GroupInterviewSessionResponseSchema.model_validate(new_group_session).model_dump(mode="json")


@router.get("/discover")
def list_active_sessions(
    limit: int = 50,
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Listar sesiones grupales activas disponibles para unirse.
    (Útil para descubrir sesiones de otros usuarios)
    """
    service = GroupInterviewSessionService(db)
    sessions = service.list_active_sessions(limit=limit)
    
    if response:
        response.status_code = status.HTTP_200_OK
    
    return [
        GroupInterviewSessionResponseSchema.model_validate(session).model_dump(mode="json")
        for session in sessions
    ]


@router.get("")
def list_my_group_sessions(
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Listar todas mis sesiones grupales como host."""
    service = GroupInterviewSessionService(db)
    sessions = service.list_my_group_sessions(current_user["id"])
    
    response.status_code = status.HTTP_200_OK
    return [
        GroupInterviewSessionResponseSchema.model_validate(session).model_dump(mode="json")
        for session in sessions
    ]


@router.get("/{session_code}")
def get_group_session_by_code(
    session_code: str,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Obtener sesión grupal por su código único.
    """
    service = GroupInterviewSessionService(db)
    
    try:
        session = service.get_group_session_by_code(session_code)
    except InterviewSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message
        ) from exc
    
    response.status_code = status.HTTP_200_OK
    detail_payload = {
        "id": session.id,
        "session_code": session.session_code,
        "host_id": session.host_id,
        "host": session.host,
        "role_id": session.role_id,
        "role": session.role,
        "difficulty": session.difficulty,
        "status": session.status,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "participant_count": len(session.interview_sessions or []),
    }
    return GroupInterviewSessionDetailSchema.model_validate(detail_payload).model_dump(mode="json")


@router.post("/{session_code}/start")
async def start_group_session(
    session_code: str,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Iniciar una sesión grupal (solo el host y en estado waiting)."""
    service = GroupInterviewSessionService(db)

    try:
        session = service.start_group_session(session_code, current_user["id"])
    except InterviewSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    await _broadcast_group_event(
        session.session_code,
        {
            "event": "interview_started",
            "session_code": session.session_code,
            "status": session.status,
            "started_by": current_user["id"],
            "started_at": _session_timestamp(session),
        },
    )

    response.status_code = status.HTTP_200_OK
    return GroupInterviewSessionResponseSchema.model_validate(session).model_dump(mode="json")


@router.post("/{session_code}/close")
async def close_group_session(
    session_code: str,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Cerrar una sesión grupal (solo el host y en estado in_progress)."""
    service = GroupInterviewSessionService(db)

    try:
        session = service.close_group_session(session_code, current_user["id"])
    except InterviewSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    await _broadcast_group_event(
        session.session_code,
        {
            "event": "interview_closed",
            "session_code": session.session_code,
            "status": session.status,
            "closed_by": current_user["id"],
            "closed_at": _session_timestamp(session),
        },
    )

    response.status_code = status.HTTP_200_OK
    return GroupInterviewSessionResponseSchema.model_validate(session).model_dump(mode="json")


@router.post("/{session_code}/rounds/next", response_model=GroupInterviewRoundNextResponseSchema)
async def create_next_round(
    session_code: str,
    body: GroupInterviewNextRoundRequestSchema,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    orchestrator = GroupInterviewOrchestratorService(db)

    try:
        group_session, round_item, tts_result, event_payloads = await orchestrator.generate_next_round_question(
            session_code=session_code,
            requester_id=current_user["id"],
            target_skill=body.target_skill,
            difficulty=body.difficulty,
        )
    except InterviewSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    emitted_at = datetime.now(timezone.utc).isoformat()  # noqa: F841 — reservado para logs futuros
    await _broadcast_group_event(
        group_session.session_code,
        event_payloads.round_started,
    )
    await _broadcast_group_event(
        group_session.session_code,
        event_payloads.question_generated,
    )
    # AB#326 + AB#327: question_audio_ready o tts_error, construidos en el orquestador
    await _broadcast_group_event(
        group_session.session_code,
        event_payloads.audio_event,
    )

    return {
        "round_id": str(round_item.id),
        "round_index": round_item.round_index,
        "question_text": round_item.question_text,
        "target_skill": round_item.target_skill,
        "difficulty": round_item.difficulty,
        "status": round_item.status.value if hasattr(round_item.status, "value") else str(round_item.status),
        "created_at": round_item.created_at,
    }


@router.delete("/{group_session_id}")
def delete_group_session(
    group_session_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Eliminar una sesión grupal (solo el host puede hacerlo)."""
    service = GroupInterviewSessionService(db)
    
    try:
        success = service.delete_group_session(group_session_id, current_user["id"])
    except InterviewSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc)
        ) from exc
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudo eliminar la sesión"
        )
    
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.get("/{session_code}/state")
def get_group_session_state(
    session_code: str,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Task-066-08: Obtener estado completo de sesión para reconexión.
    Retorna la ronda activa actual o la última ronda para que participante pueda continuar.
    """
    service = GroupInterviewSessionService(db)
    
    try:
        session = service.get_group_session_by_code(session_code)
    except InterviewSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message
        ) from exc
    
    # Obtener ronda activa, o la última si no hay activa
    active_round = db.query(GroupInterviewRound).filter(
        GroupInterviewRound.group_interview_session_id == session.id,
        GroupInterviewRound.status == GroupInterviewRoundStatus.ACTIVE,
    ).first()
    
    current_round_data = None
    if active_round:
        current_round_data = {
            "round_index": active_round.round_index,
            "question_text": active_round.question_text,
            "target_skill": active_round.target_skill,
            "difficulty": active_round.difficulty,
            "status": active_round.status.value if hasattr(active_round.status, "value") else str(active_round.status),
        }
    else:
        # Si no hay ronda activa, obtener la última
        last_round = db.query(GroupInterviewRound).filter(
            GroupInterviewRound.group_interview_session_id == session.id,
        ).order_by(GroupInterviewRound.round_index.desc()).first()
        
        if last_round:
            current_round_data = {
                "round_index": last_round.round_index,
                "question_text": last_round.question_text,
                "target_skill": last_round.target_skill,
                "difficulty": last_round.difficulty,
                "status": last_round.status.value if hasattr(last_round.status, "value") else str(last_round.status),
            }
    
    # Contar total de rondas
    total_rounds = db.query(GroupInterviewRound).filter(
        GroupInterviewRound.group_interview_session_id == session.id,
    ).count()
    
    response.status_code = status.HTTP_200_OK
    return {
        "session_code": session.session_code,
        "status": session.status,
        "role_id": str(session.role_id),
        "current_round": current_round_data,
        "total_rounds": total_rounds,
    }
