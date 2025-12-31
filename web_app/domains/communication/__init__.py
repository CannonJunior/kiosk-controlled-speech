"""
Communication Domain - Domain Package

Exports main communication services and models for domain integration.
"""
from .services.websocket_manager import WebSocketManager
from .services.message_router import MessageRouter
from .services.session_service import SessionService
from .models.websocket_connection import WebSocketConnection, ClientSession, MessageEnvelope
from .models.message_types import MessageType, MESSAGE_SCHEMAS, validate_message_format

__all__ = [
    "WebSocketManager",
    "MessageRouter", 
    "SessionService",
    "WebSocketConnection",
    "ClientSession",
    "MessageEnvelope",
    "MessageType",
    "MESSAGE_SCHEMAS",
    "validate_message_format"
]