"""
Communication Domain - Message Type Definitions

Defines all WebSocket message types and their validation schemas.
"""
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


class MessageType(Enum):
    """Enumeration of supported WebSocket message types"""
    CONNECTION = "connection"
    CHAT_MESSAGE = "chat_message"
    AUDIO_DATA = "audio_data"
    TRANSCRIPTION = "transcription"
    CHAT_RESPONSE = "chat_response"
    TEXT_READING = "text_reading"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    STATUS = "status"
    PERFORMANCE = "performance"


@dataclass
class MessageSchema:
    """Schema definition for message validation"""
    message_type: MessageType
    required_fields: List[str]
    optional_fields: List[str]
    field_types: Dict[str, type]
    
    def validate_message(self, payload: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate message payload against schema.
        
        Args:
            payload: Message payload to validate
            
        Returns:
            (is_valid, error_message)
        """
        # Check required fields
        for field in self.required_fields:
            if field not in payload:
                return False, f"Missing required field: {field}"
        
        # Check field types
        for field, expected_type in self.field_types.items():
            if field in payload:
                value = payload[field]
                if not isinstance(value, expected_type):
                    return False, f"Field '{field}' must be of type {expected_type.__name__}, got {type(value).__name__}"
        
        return True, None


# Message schema definitions
MESSAGE_SCHEMAS = {
    MessageType.CONNECTION: MessageSchema(
        message_type=MessageType.CONNECTION,
        required_fields=["status"],
        optional_fields=["client_id", "message"],
        field_types={"status": str, "client_id": str, "message": str}
    ),
    
    MessageType.CHAT_MESSAGE: MessageSchema(
        message_type=MessageType.CHAT_MESSAGE,
        required_fields=["message"],
        optional_fields=["context", "processing_mode"],
        field_types={
            "message": str, 
            "context": dict, 
            "processing_mode": str
        }
    ),
    
    MessageType.AUDIO_DATA: MessageSchema(
        message_type=MessageType.AUDIO_DATA,
        required_fields=["audio"],
        optional_fields=["context", "processing_mode"],
        field_types={
            "audio": str,  # base64 encoded audio data
            "context": dict,
            "processing_mode": str
        }
    ),
    
    MessageType.TRANSCRIPTION: MessageSchema(
        message_type=MessageType.TRANSCRIPTION,
        required_fields=["text"],
        optional_fields=["confidence", "timestamp"],
        field_types={
            "text": str,
            "confidence": float,
            "timestamp": str
        }
    ),
    
    MessageType.CHAT_RESPONSE: MessageSchema(
        message_type=MessageType.CHAT_RESPONSE,
        required_fields=["response"],
        optional_fields=["original_message", "timestamp"],
        field_types={
            "response": dict,
            "original_message": str,
            "timestamp": str
        }
    ),
    
    MessageType.TEXT_READING: MessageSchema(
        message_type=MessageType.TEXT_READING,
        required_fields=["request_id"],
        optional_fields=["text", "coordinates", "element_id"],
        field_types={
            "request_id": str,
            "text": str,
            "coordinates": dict,
            "element_id": str
        }
    ),
    
    MessageType.PING: MessageSchema(
        message_type=MessageType.PING,
        required_fields=[],
        optional_fields=["timestamp"],
        field_types={"timestamp": str}
    ),
    
    MessageType.ERROR: MessageSchema(
        message_type=MessageType.ERROR,
        required_fields=["error"],
        optional_fields=["details", "error_code", "severity"],
        field_types={
            "error": str,
            "details": str,
            "error_code": str,
            "severity": str
        }
    ),
    
    MessageType.STATUS: MessageSchema(
        message_type=MessageType.STATUS,
        required_fields=["status"],
        optional_fields=["details", "timestamp"],
        field_types={
            "status": str,
            "details": dict,
            "timestamp": str
        }
    ),
    
    MessageType.PERFORMANCE: MessageSchema(
        message_type=MessageType.PERFORMANCE,
        required_fields=["metrics"],
        optional_fields=["timestamp", "domain"],
        field_types={
            "metrics": dict,
            "timestamp": str,
            "domain": str
        }
    )
}


def get_message_schema(message_type: str) -> Optional[MessageSchema]:
    """Get message schema by string type"""
    try:
        msg_type = MessageType(message_type)
        return MESSAGE_SCHEMAS.get(msg_type)
    except ValueError:
        return None


def validate_message_format(message_type: str, payload: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate message format against its schema.
    
    Args:
        message_type: Type of message to validate
        payload: Message payload
        
    Returns:
        (is_valid, error_message)
    """
    schema = get_message_schema(message_type)
    if not schema:
        return False, f"Unknown message type: {message_type}"
    
    return schema.validate_message(payload)