"""
Speech Web Bridge Service

Bridges the communication handlers with the speech domain services.
Provides a simple interface for chat and audio processing.
"""
import logging
from typing import Dict, Any

from web_app.domains.speech.services.chat_processor import ChatProcessor
from web_app.domains.speech.services.audio_processor import AudioProcessor

logger = logging.getLogger(__name__)


class SpeechWebBridge:
    """
    Simple bridge between WebSocket communication and speech domain services.
    
    Provides the interface expected by message handlers while delegating
    to the proper domain services.
    """
    
    def __init__(self, mcp_client, metrics_collector):
        self.chat_processor = ChatProcessor(mcp_client)
        self.audio_processor = AudioProcessor(mcp_client)
        
    async def process_chat_message(self, text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process chat message through ChatProcessor.
        
        Args:
            text: The chat message text
            context: Optional context information
            
        Returns:
            Processing result with response
        """
        try:
            result = await self.chat_processor.process_chat_message(text, context or {})
            logger.info(f"Chat message processed: {text[:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"Chat processing failed: {e}")
            return {
                "success": False,
                "error": f"Chat processing failed: {str(e)}",
                "fallback_response": "I'm sorry, I couldn't process that message right now."
            }
    
    async def process_audio_data(self, audio_data: str, client_id: str) -> Dict[str, Any]:
        """
        Process audio data through AudioProcessor.
        
        Args:
            audio_data: Base64 encoded audio data
            client_id: Client identifier
            
        Returns:
            Processing result with transcription
        """
        try:
            result = await self.audio_processor.process_audio_data(audio_data, client_id)
            logger.info(f"Audio processed for client {client_id}")
            return result
            
        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            return {
                "success": False,
                "error": f"Audio processing failed: {str(e)}",
                "fallback_response": "I couldn't process the audio data."
            }