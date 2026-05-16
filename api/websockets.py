from fastapi import APIRouter, WebSocket, WebSocketDisconnect
#from fastapi import APIRouter, Depends, HTTPException, Response, status
#from sqlalchemy.orm import Session
from services.websocket_service import manager
from services.group_interview_session_service import GroupInterviewSessionService
from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from core.database import SessionLocal
from core.config import settings
from services.token_service import validate_jwt_token
import json
import logging

logger = logging.getLogger(__name__)
WEBSOCKET_AUTH_REQUIRED = settings.WEBSOCKET_AUTH_REQUIRED

#from core.database import get_db
#from core.jwt import get_current_user


router = APIRouter(
    prefix="/ws", 
    tags=["WebSockets"]
    )

@router.websocket("/{session_code}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, session_code: str, user_id: str):
    logger.info("WebSocket connection attempt: %s/%s", session_code, user_id)
    try:
        parsed_user_id = int(user_id)
    except ValueError:
        logger.warning("Invalid user_id for websocket connection: %s", user_id)
        await websocket.close(code=1008, reason="invalid_user_id")
        return

    token = websocket.query_params.get("token")
    auth_header = websocket.headers.get("authorization")
    if not token and auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if not token:
        logger.warning("WebSocket connection missing token: %s/%s", session_code, user_id)
        if WEBSOCKET_AUTH_REQUIRED:
            await websocket.close(code=1008, reason="missing_token")
            return
    else:
        try:
            payload = validate_jwt_token(token)
            token_user_id = int(payload.get("id"))
        except Exception:
            logger.warning("WebSocket connection rejected by invalid token: %s/%s", session_code, user_id)
            await websocket.close(code=1008, reason="invalid_token")
            return

        if token_user_id != parsed_user_id:
            logger.warning(
                "WebSocket user mismatch: path_user=%s token_user=%s session=%s",
                parsed_user_id,
                token_user_id,
                session_code,
            )
            await websocket.close(code=1008, reason="user_mismatch")
            return

    db = SessionLocal()
    room_id: str | None = None
    interview_session_id: int | None = None
    try:
        group_service = GroupInterviewSessionService(db)
        group_session, interview_session, is_returning_participant = group_service.join_group_session(
            session_code=session_code,
            user_id=parsed_user_id,
        )
        # Extraer valores primitivos antes de cerrar sesión para evitar acceso a ORM detached.
        room_id = group_session.session_code
        interview_session_id = interview_session.id
        group_status = group_session.status
    except InterviewSessionNotFoundError:
        logger.warning("Group session not found for websocket connection: %s", session_code)
        await websocket.close(code=1008, reason="group_session_not_found")
        return
    except ValueError:
        logger.warning("User not found for websocket connection: %s", parsed_user_id)
        await websocket.close(code=1008, reason="user_not_found")
        return
    except Exception:
        logger.exception("Unexpected error joining websocket session %s for user %s", session_code, parsed_user_id)
        await websocket.close(code=1011, reason="internal_error")
        return
    finally:
        db.close()

    if not room_id or interview_session_id is None:
        logger.error(
            "Invalid websocket join state for session %s: room_id=%s interview_session_id=%s",
            session_code,
            room_id,
            interview_session_id,
        )
        await websocket.close(code=1011, reason="invalid_join_state")
        return

    # Task-066-06: Bloquear ingreso tardío.
    # - "closed" → siempre bloquear
    # - "in_progress" → permitir si el usuario ya era participante (is_returning_participant=True)
    #   o si ya tiene conexión WS activa en memoria (reconexión rápida sin recarga).
    # - "waiting" → siempre permitir
    already_connected = any(
        uid == str(parsed_user_id)
        for uid, ws in manager.rooms.get(room_id, [])
    )

    logger.info(
        "Late-join check for session %s user %s: already_connected=%s status=%s is_returning=%s",
        session_code,
        user_id,
        already_connected,
        group_status,
        is_returning_participant,
    )

    if group_status == "closed":
        logger.warning("Blocking join for closed session %s user %s", session_code, user_id)
        await websocket.close(code=1008, reason="session_already_started")
        return

    if group_status == "in_progress" and not already_connected and not is_returning_participant:
        logger.warning("Blocking late join for session %s user %s", session_code, user_id)
        await websocket.close(code=1008, reason="session_already_started")
        return

    await manager.connect(websocket, room_id, user_id)
    logger.info("WebSocket connected to room %s for user %s", room_id, user_id)

    broadcast_message = json.dumps({
        "event": "user_joined",
        "user_id": user_id,
        "session_code": room_id,
        "interview_session_id": interview_session_id,
    })
    await manager.broadcast_text(broadcast_message, room_id, sender_id="")
    logger.info("Broadcasted user_joined for session %s user %s", room_id, user_id)
    
    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            if "bytes" in message:
                await manager.broadcast_bytes(message["bytes"], room_id, sender_id=user_id)
            
            elif "text" in message:
                await manager.broadcast_text(message["text"], room_id, sender_id=user_id)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for user %s in session %s", user_id, room_id)
    except RuntimeError:
        logger.exception("Runtime error in websocket loop for user %s in session %s", user_id, room_id)
    finally:
        manager.disconnect(websocket, room_id)
        logger.info("User %s removed from room %s", user_id, room_id)
        await manager.broadcast_text(
            json.dumps({
                "event": "user_left",
                "user_id": user_id,
                "session_code": room_id,
            }), room_id, sender_id=""
        )



