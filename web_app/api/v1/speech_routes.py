"""
API v1 - Speech Domain Routes

REST endpoints for speech processing, MCP integration, and kiosk data management.
"""
from typing import Annotated, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
import json
import logging
from datetime import datetime

from web_app.vad_config import get_vad_config
from web_app.optimization import ModelConfigManager
from web_app.domains.communication import communication_integration
from web_app.infrastructure.monitoring.metrics import metrics_collector
from web_app.api.dependencies.domain_services import (
    get_configuration_service,
    get_speech_chat_processor,
    get_communication_service
)

router = APIRouter(prefix="/api/v1/speech", tags=["speech"])
logger = logging.getLogger(__name__)


@router.get("/vad-config")
async def get_vad_configuration():
    """Get VAD configuration for the web client"""
    try:
        vad_config = get_vad_config()
        return {
            "success": True,
            "config": vad_config.to_dict() if hasattr(vad_config, 'to_dict') else vad_config,
            "client_defaults": {
                "vadEnabled": getattr(vad_config, 'enabled', True),
                "vadSensitivity": getattr(vad_config, 'sensitivity', 0.001),
                "silenceTimeout": getattr(vad_config, 'silence_timeout', 800),
                "speechStartDelay": getattr(vad_config, 'speech_start_delay', 300),
                "consecutiveSilenceThreshold": getattr(vad_config, 'consecutive_silence_threshold', 2),
                "checkInterval": getattr(vad_config, 'check_interval', 100),
                "dynamicTimeout": {
                    "enabled": getattr(vad_config, 'dynamic_timeout_enabled', True),
                    "trigger_after_ms": getattr(vad_config, 'dynamic_timeout_trigger', 1500),
                    "reduction_factor": getattr(vad_config, 'dynamic_timeout_reduction', 0.6),
                    "minimum_timeout_ms": getattr(vad_config, 'dynamic_timeout_minimum', 600)
                }
            },
            "ui_settings": {
                "timeoutRange": {
                    "min": 1.5,
                    "max": 6.0,
                    "step": 0.5,
                    "default": 2.5
                }
            }
        }
    except Exception as e:
        logger.error(f"Failed to get VAD configuration: {e}")
        return {
            "success": False,
            "error": str(e),
            "client_defaults": {
                "vadEnabled": True,
                "vadSensitivity": 0.001,
                "silenceTimeout": 800,
                "speechStartDelay": 300,
                "consecutiveSilenceThreshold": 2,
                "checkInterval": 100,
                "dynamicTimeout": {
                    "enabled": True,
                    "trigger_after_ms": 1500,
                    "reduction_factor": 0.6,
                    "minimum_timeout_ms": 600
                }
            }
        }


@router.get("/kiosk-data")
async def get_kiosk_data():
    """Get kiosk data from MCP if available"""
    try:
        # Use communication integration to get kiosk data
        result = await communication_integration.get_kiosk_data()
        
        if result.get("success", False):
            return {
                "success": True,
                "data": result.get("data", {}),
                "timestamp": datetime.now().isoformat(),
                "source": "mcp"
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Failed to retrieve kiosk data"),
                "fallback": True,
                "data": {
                    "applications": [],
                    "desktop_items": [],
                    "system_info": {
                        "status": "unavailable",
                        "reason": "MCP service not responding"
                    }
                }
            }
    except Exception as e:
        logger.error(f"Error getting kiosk data: {e}")
        return {
            "success": False,
            "error": str(e),
            "fallback": True,
            "data": {
                "applications": [],
                "desktop_items": [],
                "system_info": {
                    "status": "error",
                    "reason": str(e)
                }
            }
        }


@router.post("/kiosk-data")
async def update_kiosk_data(request: Request):
    """Update kiosk data (placeholder for future implementation)"""
    try:
        data = await request.json()
        
        # Log the update request for now
        logger.info(f"Kiosk data update request: {json.dumps(data, indent=2)}")
        
        # Use communication integration to update kiosk data
        result = await communication_integration.update_kiosk_data(data)
        
        if result.get("success", False):
            return {
                "success": True,
                "message": "Kiosk data updated successfully",
                "updated_fields": list(data.keys()) if isinstance(data, dict) else []
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Failed to update kiosk data")
            }
            
    except Exception as e:
        logger.error(f"Error updating kiosk data: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/mcp-tool")
async def call_mcp_tool(request: Request):
    """Call MCP tool with provided arguments"""
    try:
        data = await request.json()
        tool_name = data.get("name")
        tool_args = data.get("arguments", {})
        
        if not tool_name:
            raise HTTPException(status_code=400, detail="Tool name is required")
        
        logger.info(f"MCP tool call: {tool_name} with args: {tool_args}")
        
        # Use communication integration to call MCP tool
        result = await communication_integration.call_mcp_tool(tool_name, tool_args)
        
        # Record metrics for MCP tool calls
        metrics_collector.record_mcp_tool_call(
            tool_name=tool_name,
            success=result.get("success", False),
            duration_ms=result.get("duration_ms", 0)
        )
        
        return result
        
    except Exception as e:
        logger.error(f"MCP tool call error: {e}")
        metrics_collector.record_mcp_tool_call(
            tool_name=data.get("name", "unknown") if 'data' in locals() else "unknown",
            success=False,
            duration_ms=0
        )
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/sessions")
async def get_active_sessions():
    """Get information about active WebSocket sessions"""
    try:
        # Use communication integration to get session info
        session_info = await communication_integration.get_session_statistics()
        
        return {
            "success": True,
            "sessions": session_info.get("sessions", []),
            "total_active": session_info.get("total_active", 0),
            "stats": session_info.get("stats", {}),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        return {
            "success": False,
            "error": str(e),
            "sessions": [],
            "total_active": 0
        }


@router.post("/feedback/command-history") 
async def submit_command_feedback(request: Request):
    """Submit feedback about command processing"""
    try:
        data = await request.json()
        
        # Log feedback for analysis
        logger.info(f"Command feedback: {json.dumps(data, indent=2)}")
        
        # Record metrics about user feedback
        command_type = data.get("command_type", "unknown")
        satisfaction = data.get("satisfaction", 0)
        
        metrics_collector.record_user_feedback(
            command_type=command_type,
            satisfaction_score=satisfaction,
            feedback_text=data.get("feedback", "")
        )
        
        return {
            "success": True,
            "message": "Feedback recorded successfully",
            "feedback_id": f"feedback_{datetime.now().isoformat()}"
        }
        
    except Exception as e:
        logger.error(f"Error processing feedback: {e}")
        return {
            "success": False,
            "error": str(e)
        }