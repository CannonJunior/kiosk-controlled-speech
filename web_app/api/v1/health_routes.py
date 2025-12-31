"""
API v1 - Health Check Routes

System health monitoring endpoints for all domains and infrastructure.
"""
from typing import Annotated
from fastapi import APIRouter, Depends

from web_app.api.dependencies.domain_services import (
    get_mcp_client, get_metrics_collector, get_configuration_service
)
from web_app.infrastructure.mcp.mcp_client import EnhancedMCPClient
from web_app.infrastructure.monitoring.metrics import MetricsCollector
from web_app.domains.configuration.services.config_service import ConfigurationService

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "kiosk-speech-web-interface",
        "version": "1.0.0",
        "timestamp": "2024-01-01T00:00:00Z"
    }


@router.get("/mcp")
async def mcp_health_check(
    mcp_client: Annotated[EnhancedMCPClient, Depends(get_mcp_client)] = None
):
    """Check MCP services health and tool availability"""
    try:
        health_info = await mcp_client.health_check()
        return {
            "success": True,
            "mcp_health": health_info
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "mcp_health": {
                "status": "error",
                "available_tools": [],
                "servers": {}
            }
        }


@router.get("/metrics")
async def metrics_health_check(
    metrics: Annotated[MetricsCollector, Depends(get_metrics_collector)] = None
):
    """Get system-wide performance metrics and health dashboard"""
    try:
        dashboard = metrics.get_health_dashboard()
        return {
            "success": True,
            "metrics": dashboard
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "metrics": {}
        }


@router.get("/configuration")
async def configuration_health_check(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Check configuration loading status and validation"""
    try:
        status = config_service.get_configuration_status()
        validation_errors = config_service.get_validation_errors()
        
        is_healthy = status.get("loaded", False) and len(validation_errors) == 0
        
        return {
            "success": True,
            "configuration_health": {
                "status": "healthy" if is_healthy else "warning",
                "loaded": status.get("loaded", False),
                "validation_errors": validation_errors,
                "available_models": status.get("available_models", []),
                "available_presets": status.get("available_presets", [])
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "configuration_health": {
                "status": "error",
                "loaded": False
            }
        }


@router.get("/domains")
async def domains_health_check(
    metrics: Annotated[MetricsCollector, Depends(get_metrics_collector)] = None
):
    """Check health of all extracted domains"""
    try:
        domain_health = {}
        
        # Check each domain's metrics
        domains = ["speech", "communication", "configuration", "annotation"]
        
        for domain in domains:
            domain_metrics = metrics.get_domain_metrics(domain)
            if domain_metrics:
                success_rate = float(domain_metrics.get("success_rate", "0%").rstrip('%'))
                avg_response = domain_metrics.get("response_times", {}).get("avg", 0)
                
                if success_rate >= 95 and avg_response <= 1.0:
                    status = "excellent"
                elif success_rate >= 90 and avg_response <= 2.0:
                    status = "good"
                elif success_rate >= 80 and avg_response <= 5.0:
                    status = "acceptable"
                else:
                    status = "poor"
                
                domain_health[domain] = {
                    "status": status,
                    "success_rate": f"{success_rate:.1f}%",
                    "avg_response_time": f"{avg_response:.3f}s",
                    "request_count": domain_metrics.get("request_count", 0)
                }
            else:
                domain_health[domain] = {
                    "status": "unknown",
                    "success_rate": "0%",
                    "avg_response_time": "0.000s",
                    "request_count": 0
                }
        
        # Calculate overall system health
        statuses = [domain["status"] for domain in domain_health.values()]
        if all(status in ["excellent", "good"] for status in statuses):
            overall_status = "healthy"
        elif any(status == "poor" for status in statuses):
            overall_status = "degraded"
        else:
            overall_status = "warning"
        
        return {
            "success": True,
            "domains_health": {
                "overall_status": overall_status,
                "domain_details": domain_health,
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "domains_health": {
                "overall_status": "error",
                "domain_details": {}
            }
        }


@router.get("/comprehensive")
async def comprehensive_health_check(
    mcp_client: Annotated[EnhancedMCPClient, Depends(get_mcp_client)] = None,
    metrics: Annotated[MetricsCollector, Depends(get_metrics_collector)] = None,
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Comprehensive health check of all system components"""
    try:
        # Get health from all components
        mcp_health_result = await mcp_health_check(mcp_client)
        metrics_health_result = await metrics_health_check(metrics)
        config_health_result = await configuration_health_check(config_service)
        domains_health_result = await domains_health_check(metrics)
        
        # Determine overall system health
        component_statuses = [
            mcp_health_result.get("success", False),
            metrics_health_result.get("success", False),
            config_health_result.get("success", False),
            domains_health_result.get("success", False)
        ]
        
        if all(component_statuses):
            overall_status = "healthy"
        elif any(component_statuses):
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return {
            "success": True,
            "comprehensive_health": {
                "overall_status": overall_status,
                "components": {
                    "mcp": mcp_health_result,
                    "metrics": metrics_health_result,
                    "configuration": config_health_result,
                    "domains": domains_health_result
                },
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "comprehensive_health": {
                "overall_status": "error",
                "components": {}
            }
        }