"""
Communication Domain - WebSocket Connection Management

Manages WebSocket connections, client sessions, and connection lifecycle.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import WebSocket

from web_app.domains.communication.models.websocket_connection import (
    WebSocketConnection, ClientSession, MessageEnvelope
)

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    WebSocket connection manager for real-time communication.
    
    Responsibilities:
    - Accept and track WebSocket connections
    - Manage client sessions and lifecycle
    - Send messages to specific clients or broadcast
    - Handle connection cleanup and error recovery
    """
    
    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.connection_stats = {
            "total_connections": 0,
            "current_connections": 0,
            "total_messages_sent": 0,
            "total_messages_received": 0,
            "connection_errors": 0,
            "start_time": datetime.now()
        }
    
    async def accept_connection(self, websocket: WebSocket, client_id: str) -> bool:
        """
        Accept new WebSocket connection and initialize session.
        
        Args:
            websocket: FastAPI WebSocket instance
            client_id: Unique client identifier
            
        Returns:
            True if connection accepted successfully
        """
        try:
            await websocket.accept()
            
            # Create connection wrapper
            connection = WebSocketConnection(
                client_id=client_id,
                websocket=websocket
            )
            
            # Store connection
            self.connections[client_id] = connection
            
            # Update stats
            self.connection_stats["total_connections"] += 1
            self.connection_stats["current_connections"] += 1
            
            logger.info(f"WebSocket connection accepted for client: {client_id}")
            
            # Send welcome message
            await self.send_to_client(client_id, {
                "type": "connection",
                "status": "connected", 
                "client_id": client_id,
                "message": "Welcome to Kiosk Speech Chat! You can type or use voice input."
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to accept WebSocket connection for {client_id}: {e}")
            self.connection_stats["connection_errors"] += 1
            return False
    
    def disconnect_client(self, client_id: str):
        """
        Disconnect and clean up client connection.
        
        Args:
            client_id: Client to disconnect
        """
        if client_id in self.connections:
            connection = self.connections[client_id]
            connection.disconnect()
            del self.connections[client_id]
            
            self.connection_stats["current_connections"] -= 1
            logger.info(f"Client {client_id} disconnected and cleaned up")
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """
        Send message to specific client.
        
        Args:
            client_id: Target client
            message: Message to send
            
        Returns:
            True if sent successfully, False if failed
        """
        if client_id not in self.connections:
            logger.warning(f"Attempted to send to unknown client: {client_id}")
            return False
        
        connection = self.connections[client_id]
        success = await connection.send_message(message)
        
        if success:
            self.connection_stats["total_messages_sent"] += 1
        else:
            # Connection failed, clean up
            logger.warning(f"Failed to send message to {client_id}, cleaning up connection")
            self.disconnect_client(client_id)
        
        return success
    
    async def broadcast_message(self, message: Dict[str, Any], exclude_clients: Optional[List[str]] = None) -> int:
        """
        Broadcast message to all connected clients.
        
        Args:
            message: Message to broadcast
            exclude_clients: List of client IDs to exclude from broadcast
            
        Returns:
            Number of clients that received the message
        """
        exclude_clients = exclude_clients or []
        sent_count = 0
        failed_clients = []
        
        for client_id, connection in list(self.connections.items()):
            if client_id not in exclude_clients:
                success = await connection.send_message(message)
                if success:
                    sent_count += 1
                    self.connection_stats["total_messages_sent"] += 1
                else:
                    failed_clients.append(client_id)
        
        # Clean up failed connections
        for client_id in failed_clients:
            self.disconnect_client(client_id)
        
        if failed_clients:
            logger.warning(f"Broadcast failed to {len(failed_clients)} clients: {failed_clients}")
        
        return sent_count
    
    def get_client_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get information about specific client"""
        if client_id not in self.connections:
            return None
        
        return self.connections[client_id].get_connection_info()
    
    def get_all_clients_info(self) -> List[Dict[str, Any]]:
        """Get information about all connected clients"""
        return [
            connection.get_connection_info() 
            for connection in self.connections.values()
        ]
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection manager statistics"""
        uptime = (datetime.now() - self.connection_stats["start_time"]).total_seconds()
        
        stats = self.connection_stats.copy()
        stats.update({
            "uptime_seconds": uptime,
            "uptime_hours": uptime / 3600,
            "active_client_ids": list(self.connections.keys()),
            "average_messages_per_connection": (
                stats["total_messages_sent"] / max(1, stats["total_connections"])
            ),
            "messages_per_second": stats["total_messages_sent"] / max(1, uptime)
        })
        
        return stats
    
    def is_client_connected(self, client_id: str) -> bool:
        """Check if client is currently connected"""
        return client_id in self.connections and self.connections[client_id].is_active
    
    def get_client_session(self, client_id: str) -> Optional[ClientSession]:
        """Get client session information"""
        if client_id not in self.connections:
            return None
        return self.connections[client_id].session
    
    def cleanup_inactive_connections(self, idle_timeout_seconds: float = 300.0):
        """
        Clean up connections that have been idle for too long.
        
        Args:
            idle_timeout_seconds: Idle time before cleanup (default: 5 minutes)
        """
        idle_clients = []
        
        for client_id, connection in list(self.connections.items()):
            if connection.session.get_idle_time() > idle_timeout_seconds:
                idle_clients.append(client_id)
        
        for client_id in idle_clients:
            logger.info(f"Cleaning up idle connection: {client_id}")
            self.disconnect_client(client_id)
        
        return len(idle_clients)