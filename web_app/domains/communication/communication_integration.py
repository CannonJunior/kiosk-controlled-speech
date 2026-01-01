"""
Communication Domain Integration

Provides integration functions for connecting communication domain with existing services.
"""
import logging

from web_app.domains.communication.services.communication_service import CommunicationService
from web_app.infrastructure.monitoring.metrics import metrics_collector

logger = logging.getLogger(__name__)

# Global communication service instance
_communication_service: CommunicationService = None


def get_communication_service() -> CommunicationService:
    """Get or create communication service singleton"""
    global _communication_service
    
    if _communication_service is None:
        _communication_service = CommunicationService(metrics_collector)
        logger.info("Communication service created")
    
    return _communication_service


def configure_communication_handlers(speech_bridge=None, text_reading_service=None):
    """
    Configure communication handlers with bridge dependencies.
    
    Args:
        speech_bridge: SpeechWebBridge instance
        text_reading_service: TextReadingService instance
    """
    service = get_communication_service()
    service.configure_handlers(speech_bridge, text_reading_service)
    logger.info("Communication handlers configured")


async def handle_websocket_connection(websocket, client_id: str):
    """
    Handle WebSocket connection using communication service.
    
    Args:
        websocket: FastAPI WebSocket instance
        client_id: Unique client identifier
    """
    service = get_communication_service()
    await service.handle_websocket_connection(websocket, client_id)


def get_communication_status():
    """Get communication domain status"""
    service = get_communication_service()
    return service.get_communication_status()


def cleanup_inactive_resources():
    """Clean up inactive communication resources"""
    service = get_communication_service()
    return service.cleanup_inactive_resources()


async def call_mcp_tool(tool_name: str, parameters: dict):
    """
    Call an MCP tool through the communication service's MCP client.
    
    Args:
        tool_name: Name of the MCP tool to call
        parameters: Parameters to pass to the tool
        
    Returns:
        Result from the MCP tool call
    """
    from web_app.api.dependencies.domain_services import get_mcp_client
    
    mcp_client = get_mcp_client()
    if not mcp_client:
        return {
            "success": False,
            "error": "MCP client not available",
            "error_code": "MCP_CLIENT_UNAVAILABLE"
        }
    
    try:
        result = await mcp_client.call_tool(tool_name, parameters)
        return {
            "success": True,
            "result": result,
            "tool_name": tool_name
        }
    except Exception as e:
        logger.error(f"MCP tool call failed for {tool_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "tool_name": tool_name,
            "error_code": "MCP_TOOL_CALL_ERROR"
        }