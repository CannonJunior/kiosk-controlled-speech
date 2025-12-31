"""
Communication Domain - Main Communication Service

Orchestrates all communication components for real-time client-server interaction.
"""
import logging
from typing import Dict, Any, Optional, Callable
from fastapi import WebSocket, WebSocketDisconnect

from web_app.domains.communication.services.websocket_manager import WebSocketManager
from web_app.domains.communication.services.message_router import MessageRouter
from web_app.domains.communication.services.session_service import SessionService
from web_app.domains.communication.models.message_types import MessageType
from web_app.infrastructure.monitoring.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class CommunicationService:
    """
    Main service orchestrating all communication domain functionality.
    
    Responsibilities:
    - Coordinate WebSocket management, routing, and sessions
    - Provide unified interface for real-time communication
    - Integrate with infrastructure monitoring and metrics
    - Handle WebSocket endpoint lifecycle
    """
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.websocket_manager = WebSocketManager()
        self.message_router = MessageRouter()
        self.session_service = SessionService()
        self.metrics = metrics_collector
        
        # Track communication metrics
        self._domain_name = "communication"
        
    def register_message_handler(self, message_type: MessageType, handler: Callable):
        """Register handler for specific message type"""
        self.message_router.register_handler(message_type, handler)
    
    async def handle_websocket_connection(self, websocket: WebSocket, client_id: str):
        """
        Handle complete WebSocket connection lifecycle.
        
        Args:
            websocket: FastAPI WebSocket instance
            client_id: Unique client identifier
        """
        connection_start = self._get_current_time()
        
        try:
            # Accept connection and create session
            success = await self.websocket_manager.accept_connection(websocket, client_id)
            if not success:
                logger.error(f"Failed to accept WebSocket connection for {client_id}")
                return
            
            # Create user session
            self.session_service.create_session(
                client_id, 
                initial_context={"connection_type": "websocket", "endpoint": "/ws"}
            )
            
            # Record successful connection
            connection_time = self._get_processing_time(connection_start)
            self.metrics.record_domain_request(
                self._domain_name, 
                True, 
                connection_time,
                context={"operation": "connection", "client_id": client_id}
            )
            
            # Main message processing loop
            while True:
                try:
                    # Receive message from client
                    data = await websocket.receive_text()
                    await self._process_received_message(client_id, data)
                    
                except WebSocketDisconnect:
                    logger.info(f"Client {client_id} disconnected normally")
                    break
                except Exception as e:
                    logger.error(f"Error processing message from {client_id}: {e}")
                    # Send error response to client
                    await self._send_error_response(client_id, str(e))
        
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected during setup")
        except Exception as e:
            logger.error(f"WebSocket connection error for {client_id}: {e}")
            connection_time = self._get_processing_time(connection_start)
            self.metrics.record_domain_request(
                self._domain_name,
                False,
                connection_time, 
                context={"operation": "connection_error", "error": str(e)}
            )
        finally:
            # Cleanup connection and session
            self.websocket_manager.disconnect_client(client_id)
            self.session_service.remove_session(client_id)
            logger.info(f"Cleaned up connection and session for {client_id}")
    
    async def _process_received_message(self, client_id: str, raw_data: str):
        """Process received WebSocket message"""
        message_start = self._get_current_time()
        
        try:
            # Update session activity
            self.session_service.update_session_activity(
                client_id, 
                {"message_received": True, "data_length": len(raw_data)}
            )
            
            # Route message to appropriate handler
            result = await self.message_router.route_from_raw_data(client_id, raw_data)
            
            # Record successful message processing
            processing_time = self._get_processing_time(message_start)
            self.metrics.record_domain_request(
                self._domain_name,
                result.get("success", False),
                processing_time,
                context={
                    "operation": "message_processing",
                    "client_id": client_id,
                    "message_type": result.get("_routing_info", {}).get("message_type", "unknown")
                }
            )
            
            # Send response if handler provided one
            if result and "response" in result:
                await self.send_message_to_client(client_id, result["response"])
            
        except Exception as e:
            processing_time = self._get_processing_time(message_start)
            self.metrics.record_domain_request(
                self._domain_name,
                False,
                processing_time,
                context={"operation": "message_error", "error": str(e)}
            )
            raise
    
    async def send_message_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific client"""
        send_start = self._get_current_time()
        
        try:
            success = await self.websocket_manager.send_to_client(client_id, message)
            send_time = self._get_processing_time(send_start)
            
            self.metrics.record_domain_request(
                self._domain_name,
                success,
                send_time,
                context={
                    "operation": "send_message",
                    "client_id": client_id,
                    "message_type": message.get("type", "unknown")
                }
            )
            
            if success:
                self.session_service.record_processing_activity(
                    client_id,
                    "message_sent",
                    {"message_type": message.get("type"), "success": True}
                )
            
            return success
            
        except Exception as e:
            send_time = self._get_processing_time(send_start)
            self.metrics.record_domain_request(
                self._domain_name,
                False,
                send_time,
                context={"operation": "send_error", "error": str(e)}
            )
            return False
    
    async def broadcast_message(self, message: Dict[str, Any], exclude_clients: Optional[list] = None) -> int:
        """Broadcast message to all connected clients"""
        broadcast_start = self._get_current_time()
        
        try:
            sent_count = await self.websocket_manager.broadcast_message(message, exclude_clients)
            broadcast_time = self._get_processing_time(broadcast_start)
            
            self.metrics.record_domain_request(
                self._domain_name,
                sent_count > 0,
                broadcast_time,
                context={
                    "operation": "broadcast",
                    "sent_count": sent_count,
                    "message_type": message.get("type", "unknown")
                }
            )
            
            return sent_count
            
        except Exception as e:
            broadcast_time = self._get_processing_time(broadcast_start)
            self.metrics.record_domain_request(
                self._domain_name,
                False,
                broadcast_time,
                context={"operation": "broadcast_error", "error": str(e)}
            )
            return 0
    
    async def _send_error_response(self, client_id: str, error_message: str):
        """Send error response to client"""
        error_response = {
            "type": "error",
            "error": error_message,
            "timestamp": self._get_current_time().isoformat()
        }
        await self.send_message_to_client(client_id, error_response)
    
    def get_communication_status(self) -> Dict[str, Any]:
        """Get comprehensive communication domain status"""
        return {
            "websocket_manager": self.websocket_manager.get_connection_stats(),
            "message_router": self.message_router.get_routing_metrics(),
            "session_service": self.session_service.get_session_statistics(),
            "domain_metrics": self.metrics.get_domain_metrics(self._domain_name)
        }
    
    def cleanup_inactive_resources(self):
        """Clean up inactive connections and sessions"""
        # Cleanup idle connections (5 minute timeout)
        cleaned_connections = self.websocket_manager.cleanup_inactive_connections(300.0)
        
        # Cleanup expired sessions (30 minute timeout)
        cleaned_sessions = self.session_service.cleanup_expired_sessions()
        
        if cleaned_connections > 0 or cleaned_sessions > 0:
            logger.info(f"Cleanup: {cleaned_connections} connections, {cleaned_sessions} sessions")
        
        return {"connections_cleaned": cleaned_connections, "sessions_cleaned": cleaned_sessions}
    
    def _get_current_time(self):
        """Get current datetime for timing operations"""
        from datetime import datetime
        return datetime.now()
    
    def _get_processing_time(self, start_time) -> float:
        """Calculate processing time in seconds"""
        return (self._get_current_time() - start_time).total_seconds()