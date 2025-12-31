"""
API Routes - WebSocket Communication Endpoints

FastAPI routes for real-time WebSocket communication with client applications.
"""
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from web_app.domains.communication.services.communication_service import CommunicationService
from web_app.infrastructure.monitoring.metrics import metrics_collector

logger = logging.getLogger(__name__)

# Create router for WebSocket endpoints
router = APIRouter()

# Initialize communication service with metrics
communication_service = CommunicationService(metrics_collector)


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time communication with clients.
    
    Args:
        websocket: FastAPI WebSocket instance
        client_id: Unique client identifier
    """
    logger.info(f"WebSocket connection request from client: {client_id}")
    
    # Delegate to communication service for full lifecycle management
    await communication_service.handle_websocket_connection(websocket, client_id)


@router.get("/communication/status")
async def get_communication_status():
    """Get communication domain status and metrics"""
    try:
        status = communication_service.get_communication_status()
        return JSONResponse(content={
            "success": True,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get communication status: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@router.post("/communication/cleanup")
async def cleanup_inactive_resources():
    """Manually trigger cleanup of inactive connections and sessions"""
    try:
        cleanup_result = communication_service.cleanup_inactive_resources()
        return JSONResponse(content={
            "success": True,
            "cleanup_result": cleanup_result,
            "timestamp": metrics_collector._get_current_time().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to cleanup resources: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@router.get("/communication/metrics")
async def get_communication_metrics():
    """Get detailed communication domain metrics"""
    try:
        metrics = communication_service.get_communication_status()
        return JSONResponse(content={
            "success": True,
            "metrics": metrics,
            "timestamp": metrics_collector._get_current_time().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get communication metrics: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


# Export communication service for use in main.py during transition
def get_communication_service() -> CommunicationService:
    """Get the communication service instance for external use"""
    return communication_service