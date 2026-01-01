"""
API v1 - Core Application Routes

Basic application endpoints: health checks, performance metrics, and root paths.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse
import time
import logging
import json
from datetime import datetime
from pathlib import Path

from web_app.infrastructure.monitoring.metrics import metrics_collector

router = APIRouter(tags=["core"])
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def index():
    """Main application page"""
    try:
        # Serve the main index.html file
        static_path = Path("web_app/static/index.html")
        if static_path.exists():
            return FileResponse(static_path)
        else:
            # Fallback HTML if file doesn't exist
            return HTMLResponse("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Kiosk Speech Interface</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
            </head>
            <body>
                <h1>Kiosk Speech Interface</h1>
                <p>The main application files are not found. Please check the static file configuration.</p>
                <p><a href="/troubleshooting">Troubleshooting Guide</a></p>
            </body>
            </html>
            """)
    except Exception as e:
        logger.error(f"Error serving index page: {e}")
        return HTMLResponse(
            f"<h1>Application Error</h1><p>Error loading application: {str(e)}</p>",
            status_code=500
        )


@router.get("/troubleshooting", response_class=HTMLResponse)
async def troubleshooting():
    """Troubleshooting guide page"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head><title>Troubleshooting - Kiosk Speech</title></head>
    <body>
        <h1>Troubleshooting Guide</h1>
        <h2>Common Issues</h2>
        <ul>
            <li>Check browser console for JavaScript errors</li>
            <li>Ensure microphone permissions are granted</li>
            <li>Verify WebSocket connection status</li>
            <li>Check server logs for backend errors</li>
        </ul>
        <p><a href="/">Back to Application</a></p>
    </body>
    </html>
    """)


@router.get("/health")
async def health_check():
    """Application health check endpoint"""
    try:
        start_time = time.time()
        
        # Basic health checks
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "uptime_seconds": time.time() - getattr(health_check, '_start_time', time.time()),
            "checks": {
                "api": "ok",
                "metrics": "ok"
            }
        }
        
        # Check metrics collector
        try:
            metrics_collector.get_basic_metrics()
            health_status["checks"]["metrics"] = "ok"
        except Exception as e:
            health_status["checks"]["metrics"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Check response time
        response_time_ms = (time.time() - start_time) * 1000
        health_status["response_time_ms"] = round(response_time_ms, 2)
        
        if response_time_ms > 1000:
            health_status["status"] = "slow"
            
        return health_status
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@router.get("/api/performance")
async def get_performance_metrics():
    """Get application performance metrics"""
    try:
        # Get metrics from metrics collector
        basic_metrics = metrics_collector.get_basic_metrics()
        
        return {
            "success": True,
            "metrics": basic_metrics,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# Initialize health check start time
if not hasattr(health_check, '_start_time'):
    health_check._start_time = time.time()


@router.get("/api/screens")
async def get_available_screens():
    """Get available screen configurations for screen selection"""
    try:
        # Load screen definitions from kiosk_data.json
        kiosk_data_path = Path("config/kiosk_data.json")
        
        if not kiosk_data_path.exists():
            logger.error("kiosk_data.json not found")
            return {
                "success": False,
                "error": "Screen configuration file not found",
                "screens": []
            }
        
        with open(kiosk_data_path, 'r') as f:
            kiosk_data = json.load(f)
        
        # Extract screen information
        screens = []
        for screen_id, screen_config in kiosk_data.get('screens', {}).items():
            screens.append({
                "name": screen_id,
                "display_name": screen_config.get('name', screen_id),
                "description": screen_config.get('description', ''),
                "elements_count": len(screen_config.get('elements', []))
            })
        
        return screens
        
    except Exception as e:
        logger.error(f"Error loading screen configurations: {e}")
        return {
            "success": False,
            "error": str(e),
            "screens": []
        }