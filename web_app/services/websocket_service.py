"""
WebSocket Connection Management Service

Handles WebSocket connections, message broadcasting, and session tracking.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Manages WebSocket connections for real-time communication"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """
        Accept new WebSocket connection and track session.
        
        Args:
            websocket: WebSocket connection
            client_id: Unique client identifier
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.user_sessions[client_id] = {
            "connected_at": datetime.now(),
            "message_count": 0,
            "last_activity": datetime.now()
        }
        logger.info(f"Client {client_id} connected")
    
    def disconnect(self, client_id: str):
        """
        Remove client connection and session tracking.
        
        Args:
            client_id: Client to disconnect
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.user_sessions:
            del self.user_sessions[client_id]
        logger.info(f"Client {client_id} disconnected")
    
    async def send_personal_message(self, message: Dict[str, Any], client_id: str) -> bool:
        """
        Send message to specific client.
        
        Args:
            message: Message dictionary to send
            client_id: Target client ID
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if client_id not in self.active_connections:
            return False
            
        try:
            await self.active_connections[client_id].send_text(json.dumps(message))
            self.user_sessions[client_id]["last_activity"] = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {client_id}: {e}")
            self.disconnect(client_id)
            return False
    
    async def broadcast_message(self, message: Dict[str, Any]) -> int:
        """
        Send message to all connected clients.
        
        Args:
            message: Message dictionary to broadcast
            
        Returns:
            Number of clients that received the message
        """
        if not self.active_connections:
            return 0
            
        successful_sends = 0
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
                self.user_sessions[client_id]["last_activity"] = datetime.now()
                successful_sends += 1
            except Exception as e:
                logger.error(f"Failed to broadcast to {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
        
        return successful_sends
    
    def update_session_activity(self, client_id: str):
        """
        Update session activity tracking for client.
        
        Args:
            client_id: Client to update
        """
        if client_id in self.user_sessions:
            self.user_sessions[client_id]["message_count"] += 1
            self.user_sessions[client_id]["last_activity"] = datetime.now()
    
    def get_session_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information for specific client.
        
        Args:
            client_id: Client to query
            
        Returns:
            Session information or None if client not found
        """
        if client_id not in self.user_sessions:
            return None
            
        session = self.user_sessions[client_id]
        return {
            "client_id": client_id,
            "connected_at": session["connected_at"].isoformat(),
            "message_count": session["message_count"],
            "last_activity": session["last_activity"].isoformat(),
            "is_connected": client_id in self.active_connections
        }
    
    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all active sessions.
        
        Returns:
            Dictionary mapping client IDs to session information
        """
        return {
            client_id: {
                "connected_at": session["connected_at"].isoformat(),
                "message_count": session["message_count"],
                "last_activity": session["last_activity"].isoformat(),
                "is_connected": client_id in self.active_connections
            }
            for client_id, session in self.user_sessions.items()
        }
    
    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections)
    
    def is_client_connected(self, client_id: str) -> bool:
        """Check if specific client is currently connected."""
        return client_id in self.active_connections