from fastapi import APIRouter, WebSocket, WebSocketDisconnect
#from fastapi import APIRouter, Depends, HTTPException, Response, status
#from sqlalchemy.orm import Session
from services.websocket_service import manager
from services.group_interview_session_service import GroupInterviewSessionService
from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from core.database import SessionLocal
import json

#from core.database import get_db
#from core.jwt import get_current_user


router = APIRouter(
    prefix="/ws", 
    tags=["WebSockets"]
    )

@router.websocket("/{session_code}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, session_code: str, user_id: str):
    try:
        parsed_user_id = int(user_id)
    except ValueError:
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
        await websocket.close(code=1008, reason="group_session_not_found")
        return
    except ValueError:
        await websocket.close(code=1008, reason="user_not_found")
        return
    except Exception:
        await websocket.close(code=1011, reason="internal_error")
        return
    finally:
        db.close()

    if not room_id or interview_session_id is None:
        await websocket.close(code=1011, reason="invalid_join_state")
        return

    # Task-066-06: Bloquear ingreso tardío si la sala ya inició o cerró
    # Verificar si el usuario ya estaba conectado antes
    already_connected = any(
        uid == str(parsed_user_id) 
        for uid, ws in manager.rooms.get(room_id, [])
    )
    
    if (group_status in ["in_progress", "closed"]) and not already_connected:
        await websocket.close(code=1008, reason="session_already_started")
        return

    await manager.connect(websocket, room_id, user_id)

    await manager.broadcast_text(
        json.dumps({
            "event": "user_joined",
            "user_id": user_id,
            "session_code": room_id,
            "interview_session_id": interview_session_id,
        }), room_id, sender_id=user_id
    )
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
        pass
    except RuntimeError:
        pass
    finally:
        manager.disconnect(websocket, room_id)
        await manager.broadcast_text(
            json.dumps({
                "event": "user_left",
                "user_id": user_id,
                "session_code": room_id,
            }), room_id, sender_id=user_id
        )



