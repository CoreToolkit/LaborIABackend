from fastapi import WebSocket
from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        self.rooms[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id not in self.rooms:
            return
        try:
            self.rooms[room_id].remove(websocket)
        except ValueError:
            pass

        if not self.rooms[room_id]: 
            del self.rooms[room_id]

    async def broadcast_bytes(self, data: bytes, room_id: str, sender: WebSocket):
        if room_id not in self.rooms:
            return
        for connection in self.rooms[room_id]:
            if connection != sender:
                await connection.send_bytes(data)

    async def broadcast_text(self, message: str, room_id: str, sender: WebSocket = None):
        if room_id not in self.rooms:
            return
        for connection in self.rooms[room_id]:
            if connection != sender:
                await connection.send_text(message)