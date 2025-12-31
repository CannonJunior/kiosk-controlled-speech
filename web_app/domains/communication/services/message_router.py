"""
Communication Domain - Message Routing Service

Routes and dispatches WebSocket messages to appropriate domain handlers.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
import asyncio

from web_app.domains.communication.models.websocket_connection import MessageEnvelope
from web_app.domains.communication.models.message_types import MessageType, validate_message_format

logger = logging.getLogger(__name__)


class MessageRouter:
    """
    Routes WebSocket messages to appropriate domain handlers.
    
    Responsibilities:
    - Parse and validate incoming messages
    - Route messages to registered handlers
    - Track message processing metrics
    - Handle routing errors gracefully
    """
    
    def __init__(self):
        # Message handlers registry
        self._handlers: Dict[MessageType, Callable] = {}
        
        # Message processing metrics
        self.routing_metrics = {
            "total_messages": 0,
            "successful_routes": 0,
            "failed_routes": 0,
            "validation_errors": 0,
            "unknown_message_types": 0,
            "processing_times": [],
            "start_time": datetime.now()
        }
        
        # Message type counts
        self._message_type_counts: Dict[str, int] = {}
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """
        Register a handler for a specific message type.
        
        Args:
            message_type: Type of message to handle
            handler: Async function to handle the message
        """
        self._handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type.value}")
    
    def unregister_handler(self, message_type: MessageType):
        """Remove handler for message type"""
        if message_type in self._handlers:
            del self._handlers[message_type]
            logger.info(f"Unregistered handler for message type: {message_type.value}")
    
    async def route_message(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        """
        Route message to appropriate handler.
        
        Args:
            envelope: Message envelope with routing information
            
        Returns:
            Processing result from handler
        """
        start_time = datetime.now()
        self.routing_metrics["total_messages"] += 1
        
        # Track message type frequency
        self._message_type_counts[envelope.message_type] = (
            self._message_type_counts.get(envelope.message_type, 0) + 1
        )
        
        try:
            # Validate message format
            is_valid, error_message = validate_message_format(
                envelope.message_type, 
                envelope.payload
            )
            
            if not is_valid:
                self.routing_metrics["validation_errors"] += 1
                return self._create_error_response(
                    f"Message validation failed: {error_message}",
                    error_code="VALIDATION_ERROR"
                )
            
            # Check if we have a handler for this message type
            try:
                message_type = MessageType(envelope.message_type)
            except ValueError:
                self.routing_metrics["unknown_message_types"] += 1
                return self._create_error_response(
                    f"Unknown message type: {envelope.message_type}",
                    error_code="UNKNOWN_MESSAGE_TYPE"
                )
            
            if message_type not in self._handlers:
                return self._create_error_response(
                    f"No handler registered for message type: {message_type.value}",
                    error_code="NO_HANDLER"
                )
            
            # Route to handler
            handler = self._handlers[message_type]
            try:
                result = await handler(envelope)
                self.routing_metrics["successful_routes"] += 1
                
                # Add routing metadata to result
                if isinstance(result, dict):
                    result["_routing_info"] = {
                        "message_type": envelope.message_type,
                        "client_id": envelope.client_id,
                        "routed_at": start_time.isoformat(),
                        "processing_time_ms": (datetime.now() - start_time).total_seconds() * 1000
                    }
                
                return result
                
            except Exception as e:
                logger.error(f"Handler error for {message_type.value}: {e}")
                self.routing_metrics["failed_routes"] += 1
                return self._create_error_response(
                    f"Handler error: {str(e)}",
                    error_code="HANDLER_ERROR"
                )
        
        finally:
            # Track processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            self.routing_metrics["processing_times"].append(processing_time)
            
            # Keep only last 1000 processing times
            if len(self.routing_metrics["processing_times"]) > 1000:
                self.routing_metrics["processing_times"] = self.routing_metrics["processing_times"][-1000:]
    
    async def route_from_raw_data(self, client_id: str, raw_data: str) -> Dict[str, Any]:
        """
        Parse raw WebSocket data and route to handler.
        
        Args:
            client_id: Client that sent the message
            raw_data: Raw JSON string from WebSocket
            
        Returns:
            Processing result or error response
        """
        envelope = MessageEnvelope.from_raw_data(client_id, raw_data)
        
        # Handle JSON decode errors
        if envelope.message_type == "error":
            self.routing_metrics["validation_errors"] += 1
            return self._create_error_response(
                envelope.payload.get("details", "JSON decode error"),
                error_code="JSON_DECODE_ERROR"
            )
        
        return await self.route_message(envelope)
    
    def _create_error_response(self, error_message: str, error_code: str = "ROUTING_ERROR") -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            "success": False,
            "error": error_message,
            "error_code": error_code,
            "timestamp": datetime.now().isoformat(),
            "type": "routing_error"
        }
    
    def get_routing_metrics(self) -> Dict[str, Any]:
        """Get message routing performance metrics"""
        processing_times = self.routing_metrics["processing_times"]
        uptime = (datetime.now() - self.routing_metrics["start_time"]).total_seconds()
        
        # Calculate statistics
        if processing_times:
            import statistics
            avg_time = statistics.mean(processing_times)
            median_time = statistics.median(processing_times)
            min_time = min(processing_times)
            max_time = max(processing_times)
        else:
            avg_time = median_time = min_time = max_time = 0.0
        
        return {
            "total_messages": self.routing_metrics["total_messages"],
            "successful_routes": self.routing_metrics["successful_routes"],
            "failed_routes": self.routing_metrics["failed_routes"],
            "validation_errors": self.routing_metrics["validation_errors"],
            "unknown_message_types": self.routing_metrics["unknown_message_types"],
            "success_rate": (
                self.routing_metrics["successful_routes"] / 
                max(1, self.routing_metrics["total_messages"]) * 100
            ),
            "uptime_seconds": uptime,
            "messages_per_second": self.routing_metrics["total_messages"] / max(1, uptime),
            "processing_time_stats": {
                "count": len(processing_times),
                "average_ms": avg_time * 1000,
                "median_ms": median_time * 1000,
                "min_ms": min_time * 1000,
                "max_ms": max_time * 1000
            },
            "message_type_distribution": self._message_type_counts,
            "registered_handlers": [handler_type.value for handler_type in self._handlers.keys()]
        }
    
    def get_handler_status(self) -> Dict[str, Any]:
        """Get status of registered message handlers"""
        return {
            "registered_handlers": len(self._handlers),
            "handler_types": [handler_type.value for handler_type in self._handlers.keys()],
            "missing_handlers": [
                msg_type.value for msg_type in MessageType 
                if msg_type not in self._handlers
            ]
        }