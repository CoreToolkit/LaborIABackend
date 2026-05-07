from __future__ import annotations

import logging
from fastapi import WebSocket
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


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
        """
        Envía bytes a todos los participantes de la sala excepto sender_id.
        AB#327: cada conexión se intenta de forma independiente; un fallo no
        interrumpe la entrega al resto.
        """
        if room_id not in self.rooms:
            return
        uid_bytes = sender_id.encode("utf-8")
        framed = bytes([len(uid_bytes)]) + uid_bytes + data
        failed = 0
        for user_id, connection in list(self.rooms[room_id]):
            if user_id == sender_id:
                continue
            try:
                await connection.send_bytes(framed)
            except Exception:
                failed += 1
                logger.warning(
                    "broadcast_bytes: fallo al enviar a user=%s room=%s",
                    user_id,
                    room_id,
                )
        if failed:
            logger.warning(
                "broadcast_bytes: %d/%d conexiones fallaron en room=%s",
                failed,
                len(self.rooms.get(room_id, [])),
                room_id,
            )

    async def broadcast_text(self, message: str, room_id: str, sender_id: str = ""):
        """
        Envía texto a todos los participantes de la sala excepto sender_id.
        AB#327: cada conexión se intenta de forma independiente; un fallo no
        interrumpe la entrega al resto.
        """
        if room_id not in self.rooms:
            return
        failed = 0
        for user_id, connection in list(self.rooms[room_id]):
            if user_id == sender_id:
                continue
            try:
                await connection.send_text(message)
            except Exception:
                failed += 1
                logger.warning(
                    "broadcast_text: fallo al enviar a user=%s room=%s",
                    user_id,
                    room_id,
                )
        if failed:
            logger.warning(
                "broadcast_text: %d/%d conexiones fallaron en room=%s",
                failed,
                len(self.rooms.get(room_id, [])),
                room_id,
            )


# Shared manager instance for all WebSocket-related routers/services.
manager = ConnectionManager()