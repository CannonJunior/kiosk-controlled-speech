"""
Communication Domain - Message Handlers

Handles different types of WebSocket messages and routes them to appropriate services.
"""
import logging
from typing import Dict, Any

from web_app.domains.communication.models.websocket_connection import MessageEnvelope
from web_app.domains.communication.models.message_types import MessageType

logger = logging.getLogger(__name__)


class MessageHandlers:
    """
    Collection of message handlers for different WebSocket message types.
    
    Responsibilities:
    - Handle different message types (chat, audio, ping, etc.)
    - Interface with existing bridge services
    - Return standardized responses
    """
    
    def __init__(self, speech_bridge=None, text_reading_service=None, mcp_client=None):
        self.speech_bridge = speech_bridge
        self.text_reading_service = text_reading_service
        self.mcp_client = mcp_client
        
    async def handle_chat_message(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        """Handle chat message from client"""
        try:
            payload = envelope.payload
            text = payload.get("message", "")
            context = payload.get("context", {})
            processing_mode = payload.get("processing_mode", "llm")
            
            if not text.strip():
                return {
                    "success": False,
                    "error": "Empty message content",
                    "error_code": "EMPTY_MESSAGE"
                }
            
            # Process through speech bridge if available
            if self.speech_bridge:
                # Call existing chat processing logic
                result = await self.speech_bridge.process_chat_message(text, context)
                
                return {
                    "success": True,
                    "result": result,
                    "message_type": "chat_response",
                    "original_message": text
                }
            else:
                # Fallback response when bridge not available
                return {
                    "success": True,
                    "response": {
                        "type": "chat_response",
                        "response": {"text": f"Echo: {text}"},
                        "original_message": text
                    }
                }
                
        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            return {
                "success": False,
                "error": f"Chat processing failed: {str(e)}",
                "error_code": "CHAT_PROCESSING_ERROR"
            }
    
    async def handle_audio_data(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        """Handle audio data from client"""
        try:
            payload = envelope.payload
            audio_data = payload.get("audio")
            processing_mode = payload.get("processing_mode", "llm")
            
            if not audio_data:
                return {
                    "success": False,
                    "error": "No audio data provided",
                    "error_code": "MISSING_AUDIO_DATA"
                }
            
            # Process through speech bridge if available
            if self.speech_bridge:
                result = await self.speech_bridge.process_audio_data(audio_data, envelope.client_id)
                
                return {
                    "success": True,
                    "result": result,
                    "message_type": "transcription"
                }
            else:
                return {
                    "success": False,
                    "error": "Audio processing not available",
                    "error_code": "AUDIO_PROCESSOR_UNAVAILABLE"
                }
                
        except Exception as e:
            logger.error(f"Error handling audio data: {e}")
            return {
                "success": False,
                "error": f"Audio processing failed: {str(e)}",
                "error_code": "AUDIO_PROCESSING_ERROR"
            }
    
    async def handle_text_reading(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        """Handle text reading request from client"""
        try:
            payload = envelope.payload
            request_id = payload.get("request_id")
            text = payload.get("text")
            coordinates = payload.get("coordinates")
            element_id = payload.get("element_id")
            
            if not request_id:
                return {
                    "success": False,
                    "error": "Request ID is required",
                    "error_code": "MISSING_REQUEST_ID"
                }
            
            # Process through text reading service if available
            if self.text_reading_service:
                result = await self.text_reading_service.process_request(
                    request_id, text, coordinates, element_id, envelope.client_id
                )
                
                return {
                    "success": True,
                    "result": result,
                    "message_type": "text_reading"
                }
            else:
                return {
                    "success": False,
                    "error": "Text reading service not available",
                    "error_code": "TEXT_READING_UNAVAILABLE"
                }
                
        except Exception as e:
            logger.error(f"Error handling text reading: {e}")
            return {
                "success": False,
                "error": f"Text reading failed: {str(e)}",
                "error_code": "TEXT_READING_ERROR"
            }
    
    async def handle_ping(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        """Handle ping message from client"""
        return {
            "success": True,
            "response": {
                "type": "pong",
                "timestamp": envelope.timestamp.isoformat(),
                "client_id": envelope.client_id
            }
        }
    
    async def handle_mcp_tool_call(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        """Handle MCP tool call messages"""
        try:
            payload = envelope.payload
            tool_name = payload.get("tool")
            parameters = payload.get("parameters", {})
            
            if not tool_name:
                return {
                    "success": False,
                    "error": "Missing tool name",
                    "error_code": "MISSING_TOOL_NAME"
                }
            
            # Use MCP client directly if available
            if self.mcp_client:
                try:
                    # Call MCP tool through the client
                    result = await self.mcp_client.call_tool(tool_name, parameters)
                    
                    return {
                        "success": True,
                        "response": result,
                        "tool": tool_name,
                        "message_type": "mcp_tool_response"
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"MCP tool call failed: {str(e)}",
                        "tool": tool_name,
                        "error_code": "MCP_TOOL_ERROR"
                    }
            else:
                return {
                    "success": False,
                    "error": "MCP client not available",
                    "tool": tool_name,
                    "error_code": "MCP_NOT_AVAILABLE"
                }
                
        except Exception as e:
            logger.error(f"Error handling MCP tool call: {e}")
            return {
                "success": False,
                "error": f"MCP tool call processing failed: {str(e)}",
                "error_code": "MCP_PROCESSING_ERROR"
            }

    async def handle_connection(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        """Handle connection status messages"""
        return {
            "success": True,
            "message": "Connection acknowledged",
            "client_id": envelope.client_id
        }
    
    async def handle_unknown_message(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        """Handle unknown message types"""
        logger.warning(f"Unknown message type: {envelope.message_type} from {envelope.client_id}")
        return {
            "success": False,
            "error": f"Unknown message type: {envelope.message_type}",
            "error_code": "UNKNOWN_MESSAGE_TYPE"
        }


def create_message_handlers_with_bridge(speech_bridge, text_reading_service) -> MessageHandlers:
    """
    Factory function to create message handlers with bridge dependencies.
    
    Args:
        speech_bridge: SpeechWebBridge instance from main.py
        text_reading_service: TextReadingService instance
        
    Returns:
        Configured MessageHandlers instance
    """
    return MessageHandlers(speech_bridge, text_reading_service)