"""
Basic Routes - Health checks, static pages, and core endpoints

Thin controllers for basic application functionality.
"""
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from web_app.services.websocket_service import WebSocketConnectionManager
from web_app.services.mcp_service import MCPService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_chat_interface():
    """Serve the main chat interface"""
    html_file = Path("web_app/static/index.html")
    if html_file.exists():
        return FileResponse(html_file)
    else:
        # Return basic HTML if static file not found
        return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Kiosk Speech Chat</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .status { text-align: center; color: #666; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 Kiosk Speech Chat Interface</h1>
        <div class="status">
            <p>Loading chat interface...</p>
            <p>Please check that the static files are properly configured.</p>
        </div>
    </div>
</body>
</html>
        """)


@router.get("/troubleshooting", response_class=HTMLResponse)
async def get_troubleshooting_page():
    """Serve the troubleshooting page"""
    html_file = Path("web_app/static/troubleshooting.html")
    if html_file.exists():
        return FileResponse(html_file)
    else:
        raise HTTPException(status_code=404, detail="Troubleshooting page not found")


@router.get("/health")
async def health_check(
    connection_manager: WebSocketConnectionManager,
    mcp_service: MCPService
):
    """Health check endpoint with service status"""
    try:
        # Check MCP service availability
        mcp_status = "initialized" if mcp_service.is_initialized() else "not_initialized"
        available_tools = await mcp_service.list_available_tools() if mcp_service.is_initialized() else []
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "active_connections": connection_manager.get_connection_count(),
            "services": {
                "mcp_service": mcp_status,
                "available_tools": available_tools,
                "websocket_manager": "active"
            }
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "active_connections": 0,
            "services": {
                "mcp_service": "error",
                "websocket_manager": "unknown"
            }
        }


@router.get("/api/sessions")
async def get_active_sessions(connection_manager: WebSocketConnectionManager):
    """Get information about active sessions"""
    return {
        "active_sessions": connection_manager.get_connection_count(),
        "sessions": connection_manager.get_all_sessions()
    }