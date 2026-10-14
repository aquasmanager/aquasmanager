"""
Connexions WebSocket ouvertes par l'interface : diffusion des états en direct.
"""

import logging
from fastapi import WebSocket
from typing import List
from middleware.utc_json import mark_naive_datetimes_utc

class ConnectionManager:
    """
    Gestionnaire centralisé des connexions WebSocket pour FastAPI.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.register(websocket)

    def register(self, websocket: WebSocket):
        """Connexion déjà acceptée (et authentifiée) : reçoit désormais les diffusions."""
        self.active_connections.append(websocket)
        logging.info(f"🌐 Nouveau client WebSocket connecté. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info(f"🌐 Client WebSocket déconnecté. Restants: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        """Envoie un objet JSON à TOUS les clients connectés."""
        dead_connections = []
        data = mark_naive_datetimes_utc(data)
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                logging.error(f"❌ Erreur envoi WS (client mort): {e}")
                dead_connections.append(connection)

        # Nettoyage automatique des connexions mortes
        for connection in dead_connections:
            self.disconnect(connection)

# Instance unique partagée par toute l'API
ws_manager = ConnectionManager()