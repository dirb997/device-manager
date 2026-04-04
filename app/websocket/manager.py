from typing import List, Dict
from fastapi import WebSocket
import json
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.device_connections: Dict[str, WebSocket] = {}  # device_id -> websocket
    
    async def connect(self, websocket: WebSocket, device_id: str = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if device_id:
            self.device_connections[device_id] = websocket
    
    def disconnect(self, websocket: WebSocket, device_id: str = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if device_id and device_id in self.device_connections:
            del self.device_connections[device_id]
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Clean up failed connections
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

manager = ConnectionManager()