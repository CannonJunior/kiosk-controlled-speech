#!/usr/bin/env python3
"""
WebSocket Error Handling
Standardized error handling for WebSocket connections
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from fastapi import WebSocket
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for WebSocket errors"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WebSocketError(Exception):
    """Custom WebSocket error with structured information"""
    
    def __init__(self, 
                 message: str, 
                 error_code: str = "WEBSOCKET_ERROR",
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 context: Optional[Dict[str, Any]] = None,
                 recoverable: bool = True):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.context = context or {}
        self.recoverable = recoverable
        self.timestamp = datetime.now()


class WebSocketErrorHandler:
    """Centralized WebSocket error handling and recovery"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}  # client_id -> error count
        self.error_handlers: Dict[str, Callable] = {}  # error_code -> handler function
        self.max_errors_per_client = 10
        
    def register_error_handler(self, error_code: str, handler: Callable):
        """Register a custom error handler for specific error codes"""
        self.error_handlers[error_code] = handler
        
    async def handle_error(self, 
                          websocket: WebSocket, 
                          client_id: str, 
                          error: Exception,
                          connection_manager = None) -> bool:
        """
        Handle WebSocket errors with standardized logging and recovery
        
        Returns:
            bool: True if connection should continue, False if it should disconnect
        """
        
        # Convert to WebSocketError if not already
        if not isinstance(error, WebSocketError):
            ws_error = WebSocketError(
                message=str(error),
                error_code=type(error).__name__,
                severity=ErrorSeverity.MEDIUM,
                context={"original_error": str(error)}
            )
        else:
            ws_error = error
            
        # Track error count for this client
        self.error_counts[client_id] = self.error_counts.get(client_id, 0) + 1
        
        # Log error with structured information
        self._log_error(ws_error, client_id)
        
        # Check if client has exceeded error limit
        if self.error_counts[client_id] >= self.max_errors_per_client:
            await self._send_error_limit_exceeded(websocket, client_id, connection_manager)
            return False  # Disconnect client
            
        # Try custom error handler first
        if ws_error.error_code in self.error_handlers:
            try:
                return await self.error_handlers[ws_error.error_code](
                    websocket, client_id, ws_error, connection_manager
                )
            except Exception as handler_error:
                logger.error(f"Error handler failed for {ws_error.error_code}: {handler_error}")
        
        # Apply default error handling based on severity
        return await self._apply_default_handling(websocket, client_id, ws_error, connection_manager)
    
    def _log_error(self, error: WebSocketError, client_id: str):
        """Log error with appropriate severity level"""
        log_data = {
            "client_id": client_id,
            "error_code": error.error_code,
            "message": error.message,
            "severity": error.severity.value,
            "recoverable": error.recoverable,
            "context": error.context,
            "timestamp": error.timestamp.isoformat(),
            "error_count": self.error_counts.get(client_id, 0)
        }
        
        if error.severity == ErrorSeverity.LOW:
            logger.debug(f"WebSocket error: {json.dumps(log_data)}")
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"WebSocket error: {json.dumps(log_data)}")
        else:  # HIGH or CRITICAL
            logger.error(f"WebSocket error: {json.dumps(log_data)}")
    
    async def _apply_default_handling(self, 
                                     websocket: WebSocket, 
                                     client_id: str, 
                                     error: WebSocketError,
                                     connection_manager = None) -> bool:
        """Apply default error handling based on severity"""
        
        if error.severity == ErrorSeverity.LOW:
            # Low severity - continue connection, maybe send warning
            if error.recoverable:
                await self._send_error_message(websocket, client_id, error, connection_manager, include_recovery=True)
            return True
            
        elif error.severity == ErrorSeverity.MEDIUM:
            # Medium severity - send error message, continue connection if recoverable
            await self._send_error_message(websocket, client_id, error, connection_manager, include_recovery=error.recoverable)
            return error.recoverable
            
        elif error.severity == ErrorSeverity.HIGH:
            # High severity - send error, usually disconnect unless specifically recoverable
            await self._send_error_message(websocket, client_id, error, connection_manager, include_recovery=False)
            return error.recoverable
            
        else:  # CRITICAL
            # Critical - always disconnect
            await self._send_error_message(websocket, client_id, error, connection_manager, include_recovery=False)
            return False
    
    async def _send_error_message(self, 
                                 websocket: WebSocket, 
                                 client_id: str, 
                                 error: WebSocketError,
                                 connection_manager = None,
                                 include_recovery: bool = False):
        """Send structured error message to client"""
        error_message = {
            "type": "error",
            "error_code": error.error_code,
            "message": error.message,
            "severity": error.severity.value,
            "recoverable": error.recoverable,
            "timestamp": datetime.now().isoformat(),
            "client_id": client_id
        }
        
        if include_recovery and error.recoverable:
            error_message["recovery_suggestion"] = self._get_recovery_suggestion(error)
        
        try:
            if connection_manager:
                await connection_manager.send_personal_message(error_message, client_id)
            else:
                await websocket.send_text(json.dumps(error_message))
        except Exception as send_error:
            logger.error(f"Failed to send error message to client {client_id}: {send_error}")
    
    async def _send_error_limit_exceeded(self, 
                                        websocket: WebSocket, 
                                        client_id: str,
                                        connection_manager = None):
        """Send error limit exceeded message before disconnecting"""
        message = {
            "type": "error",
            "error_code": "ERROR_LIMIT_EXCEEDED",
            "message": f"Too many errors ({self.max_errors_per_client}). Disconnecting for system stability.",
            "severity": "critical",
            "recoverable": False,
            "timestamp": datetime.now().isoformat(),
            "client_id": client_id
        }
        
        try:
            if connection_manager:
                await connection_manager.send_personal_message(message, client_id)
            else:
                await websocket.send_text(json.dumps(message))
        except Exception as send_error:
            logger.error(f"Failed to send error limit message to client {client_id}: {send_error}")
    
    def _get_recovery_suggestion(self, error: WebSocketError) -> str:
        """Get recovery suggestion based on error type"""
        suggestions = {
            "JSON_DECODE_ERROR": "Please check that your message is valid JSON format",
            "MISSING_MESSAGE_TYPE": "Please include 'type' field in your message",
            "INVALID_AUDIO_FORMAT": "Please ensure audio data is in base64 format",
            "TRANSCRIPTION_FAILED": "Try speaking more clearly or checking microphone settings",
            "MCP_SERVICE_ERROR": "Service temporarily unavailable, please try again",
            "PROCESSING_ERROR": "An error occurred processing your request, please try again"
        }
        
        return suggestions.get(error.error_code, "Please try your request again")
    
    def reset_error_count(self, client_id: str):
        """Reset error count for a client (e.g., after successful operation)"""
        if client_id in self.error_counts:
            self.error_counts[client_id] = 0
    
    def get_client_error_count(self, client_id: str) -> int:
        """Get current error count for a client"""
        return self.error_counts.get(client_id, 0)
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        total_clients_with_errors = len([c for c in self.error_counts.values() if c > 0])
        total_errors = sum(self.error_counts.values())
        
        return {
            "total_errors": total_errors,
            "clients_with_errors": total_clients_with_errors,
            "max_errors_per_client": self.max_errors_per_client,
            "error_counts_by_client": dict(self.error_counts),
            "registered_handlers": list(self.error_handlers.keys())
        }


# Global instance for use across the application
websocket_error_handler = WebSocketErrorHandler()