"""
Speech Domain - Text Reading Service

Handles text reading requests and audio generation for extracted text.
Integrates with the broader speech processing capabilities.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TextReadingService:
    """
    Service for processing text reading requests and generating audio responses.
    
    Responsibilities:
    - Identify text reading requests from user input
    - Extract text from specified regions
    - Generate audio for text-to-speech
    - Provide structured text reading results
    """
    
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        
        # Text reading patterns
        self._reading_patterns = [
            "read the text",
            "read text",
            "what does it say",
            "read aloud",
            "tell me what",
            "read this"
        ]
        
        # Available regions for text extraction
        self._default_regions = [
            "top_banner",
            "bottom_banner", 
            "main_content",
            "sidebar",
            "full_screen"
        ]
    
    def is_text_reading_request(self, message: str) -> bool:
        """
        Determine if the message is a text reading request.
        
        Args:
            message: User input message
            
        Returns:
            True if this is a text reading request
        """
        message_lower = message.lower().strip()
        return any(pattern in message_lower for pattern in self._reading_patterns)
    
    async def process_text_reading_request(self, message: str) -> Dict[str, Any]:
        """
        Process a text reading request and return structured results.
        
        Args:
            message: User input message requesting text reading
            
        Returns:
            Dictionary with text reading results or error information
        """
        try:
            # Extract region from message
            region = self._extract_region_from_message(message)
            
            if not region:
                return {
                    "success": False,
                    "error": "Could not determine which region to read",
                    "available_regions": self._default_regions,
                    "suggestion": "Try: 'read the text in the top banner'"
                }
            
            # Extract text from specified region
            text_result = await self._extract_text_from_region(region)
            
            if not text_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to extract text from {region}",
                    "region": region
                }
            
            extracted_text = text_result.get("text", "").strip()
            
            if not extracted_text:
                return {
                    "success": False,
                    "error": f"No text found in {region}",
                    "region": region
                }
            
            # Generate audio for the extracted text
            audio_result = await self._generate_audio_for_text(extracted_text)
            
            # Prepare successful response
            result = {
                "success": True,
                "region": region,
                "text": extracted_text,
                "word_count": len(extracted_text.split()),
                "confidence": text_result.get("confidence", 0.95)
            }
            
            # Add audio information
            if audio_result.get("success"):
                result.update({
                    "audio_generated": True,
                    "audio_path": audio_result.get("audio_path"),
                    "audio_duration": audio_result.get("duration", 0)
                })
            else:
                result.update({
                    "audio_generated": False,
                    "audio_error": audio_result.get("error", "Audio generation failed")
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Text reading processing error: {e}")
            return {
                "success": False,
                "error": f"Text reading failed: {str(e)}"
            }
    
    def _extract_region_from_message(self, message: str) -> Optional[str]:
        """
        Extract the target region from the user's message.
        
        Args:
            message: User input message
            
        Returns:
            Region name or None if not found
        """
        message_lower = message.lower()
        
        # Check for specific region mentions
        region_mappings = {
            "top": "top_banner",
            "bottom": "bottom_banner",
            "banner": "bottom_banner",  # Default to bottom
            "main": "main_content",
            "content": "main_content",
            "sidebar": "sidebar",
            "side": "sidebar",
            "everything": "full_screen",
            "all": "full_screen",
            "screen": "full_screen"
        }
        
        for keyword, region in region_mappings.items():
            if keyword in message_lower:
                return region
        
        # Default to main content if no specific region mentioned
        return "main_content"
    
    async def _extract_text_from_region(self, region: str) -> Dict[str, Any]:
        """
        Extract text from specified screen region using MCP tools.
        
        Args:
            region: Target region for text extraction
            
        Returns:
            Result with extracted text or error information
        """
        try:
            # Use screen detector to extract text from region
            result_raw = await self.mcp_client.call_tool(
                "screen_detector_extract_text_from_region", {
                    "region": region
                }
            )
            
            # Parse result (assuming parse_tool_result is available)
            from web_app.utils.mcp_utils import parse_tool_result
            return parse_tool_result(result_raw)
            
        except Exception as e:
            logger.error(f"Text extraction error for region {region}: {e}")
            return {
                "success": False,
                "error": f"Failed to extract text: {str(e)}"
            }
    
    async def _generate_audio_for_text(self, text: str) -> Dict[str, Any]:
        """
        Generate audio file for the extracted text using TTS.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Result with audio generation information
        """
        try:
            # Use text-to-speech MCP tool if available
            result_raw = await self.mcp_client.call_tool(
                "text_to_speech_generate", {
                    "text": text,
                    "voice": "default",
                    "speed": 1.0
                }
            )
            
            # Parse result
            from web_app.utils.mcp_utils import parse_tool_result
            return parse_tool_result(result_raw)
            
        except Exception as e:
            logger.warning(f"Audio generation error: {e}")
            return {
                "success": False,
                "error": f"Audio generation failed: {str(e)}"
            }
    
    def format_text_reading_response(self, result: Dict[str, Any]) -> str:
        """
        Format text reading result into user-friendly response.
        
        Args:
            result: Text reading processing result
            
        Returns:
            Formatted response string
        """
        if result["success"]:
            response_text = "📖 **Text Reading Results**\n\n"
            response_text += f"**Region:** {result['region']}\n"
            response_text += f"**Confidence:** {int(result['confidence'] * 100)}%\n"
            response_text += f"**Word Count:** {result['word_count']}\n\n"
            response_text += f"**Extracted Text:**\n{result['text']}\n\n"
            
            if result.get('audio_generated'):
                response_text += "🔊 **Audio generated and ready to play**\n"
                response_text += f"Duration: ~{result.get('audio_duration', 0)}s"
            else:
                response_text += f"⚠️ Text extracted but audio generation failed: {result.get('audio_error', 'Unknown error')}"
            
            return response_text
        else:
            error_text = "❌ **Text Reading Failed**\n\n"
            error_text += f"**Error:** {result['error']}\n\n"
            
            if "available_regions" in result:
                error_text += "**Available regions:**\n"
                for region in result['available_regions']:
                    error_text += f"• {region}\n"
                error_text += "\n**Try:** 'Read the text in the bottom banner'"
            elif "suggestion" in result:
                error_text += f"**Suggestion:** {result['suggestion']}"
            
            return error_text