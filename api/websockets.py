from fastapi import APIRouter, WebSocket, WebSocketDisconnect
#from fastapi import APIRouter, Depends, HTTPException, Response, status
#from sqlalchemy.orm import Session
from services.websocket_service import ConnectionManager
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

manager = ConnectionManager()

@router.websocket("/{session_code}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, session_code: str, user_id: str):
    try:
        parsed_user_id = int(user_id)
    except ValueError:
        await websocket.close(code=1008, reason="invalid_user_id")
        return

    db = SessionLocal()
    try:
        group_service = GroupInterviewSessionService(db)
        group_session, interview_session = group_service.join_group_session(
            session_code=session_code,
            user_id=parsed_user_id,
        )
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

    room_id = group_session.session_code
    await manager.connect(websocket, room_id, user_id)

    await manager.broadcast_text(
        json.dumps({
            "event": "user_joined",
            "user_id": user_id,
            "session_code": room_id,
            "interview_session_id": interview_session.id,
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



