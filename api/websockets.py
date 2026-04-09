from fastapi import APIRouter, WebSocket, WebSocketDisconnect
#from fastapi import APIRouter, Depends, HTTPException, Response, status
#from sqlalchemy.orm import Session
from services.websocket_service import ConnectionManager
import json

#from core.database import get_db
#from core.jwt import get_current_user


router = APIRouter(
    prefix="/ws", 
    tags=["WebSockets"]
    )

manager = ConnectionManager()

@router.websocket("/{room_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, user_id:str):
    await manager.connect(websocket, room_id, user_id)

    await manager.broadcast_text(
        json.dumps({
            "event": "user_joined",
            "user_id": user_id
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
                "user_id": user_id
            }), room_id, sender_id=user_id
        )



