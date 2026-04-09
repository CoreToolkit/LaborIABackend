from fastapi import WebSocket
from typing import Dict, List, Tuple

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, List[Tuple[str, WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        self.rooms[room_id].append((user_id, websocket))

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id not in self.rooms:
            return
        try:
            self.rooms[room_id] = [(uid, ws) for uid, ws in self.rooms[room_id] if ws != websocket]
        except ValueError:
            pass

        if not self.rooms[room_id]: 
            del self.rooms[room_id]

    async def broadcast_bytes(self, data: bytes, room_id: str, sender_id: str = ""):
        if room_id not in self.rooms:
            return
        uid_bytes = sender_id.encode("utf-8")
        framed = bytes([len(uid_bytes)]) + uid_bytes + data
        for user_id, connection in self.rooms[room_id]:
            if user_id != sender_id:
                await connection.send_bytes(framed)

    async def broadcast_text(self, message: str, room_id: str, sender_id: str = ""):
        if room_id not in self.rooms:
            return
        for user_id, connection in self.rooms[room_id]:
            if user_id != sender_id:
                await connection.send_text(message)