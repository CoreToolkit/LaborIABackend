from fastapi import APIRouter, WebSocket, WebSocketDisconnect
#from fastapi import APIRouter, Depends, HTTPException, Response, status
#from sqlalchemy.orm import Session
from services.websocket_service import manager
from services.group_interview_session_service import GroupInterviewSessionService
from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from core.database import SessionLocal
import json
import logging

logger = logging.getLogger(__name__)

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

    db = SessionLocal()
    room_id: str | None = None
    interview_session_id: int | None = None
    try:
        group_service = GroupInterviewSessionService(db)
        group_session, interview_session = group_service.join_group_session(
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

    # Task-066-06: Bloquear ingreso tardío si la sala ya inició o cerró
    # Verificar si el usuario ya estaba conectado antes
    already_connected = any(
        uid == str(parsed_user_id) 
        for uid, ws in manager.rooms.get(room_id, [])
    )
    
    logger.info(
        "Late-join check for session %s user %s: already_connected=%s status=%s",
        session_code,
        user_id,
        already_connected,
        group_status,
    )
    if (group_status in ["in_progress", "closed"]) and not already_connected:
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



