"""
API v1 - Configuration Domain Routes

REST endpoints for VAD configuration, model optimization, and performance settings.
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request

from web_app.api.dependencies.domain_services import (
    get_configuration_service, get_optimization_service, get_cache_service
)
from web_app.domains.configuration.services.config_service import ConfigurationService
from web_app.domains.configuration.services.optimization_service import OptimizationService
from web_app.domains.configuration.services.cache_service import CacheService
from web_app.api.middleware.metrics_middleware import config_metrics_collector

router = APIRouter(prefix="/api/v1/config", tags=["configuration"])


@router.get("/vad")
async def get_vad_configuration(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Get VAD configuration for the web client"""
    try:
        vad_config = config_service.get_vad_configuration()
        return {
            "success": True,
            "config": {
                "client_defaults": vad_config.to_client_config(),
                "ui_settings": {
                    "timeoutRange": {
                        "min": 1.5,
                        "max": 6.0,
                        "step": 0.5,
                        "default": 2.5
                    }
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load VAD config: {str(e)}")


@router.get("/models/current")
async def get_current_model_config(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Get current model configuration"""
    try:
        model_config = config_service.get_model_configuration()
        
        if not model_config:
            return {
                "success": False,
                "error": "No current model configuration found",
                "current_model": "unknown"
            }
        
        return {
            "success": True,
            "model": {
                "name": model_config.name,
                "description": model_config.description,
                "temperature": model_config.temperature,
                "max_tokens": model_config.max_tokens,
                "estimated_latency": model_config.estimated_latency
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "current_model": "unknown"
        }


@router.get("/models/available")
async def get_available_models(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Get list of available model configurations"""
    try:
        models = config_service.get_available_models()
        model_details = {}
        
        for model_key in models:
            model_config = config_service.get_model_configuration(model_key)
            if model_config:
                model_details[model_key] = {
                    "name": model_config.name,
                    "description": model_config.description,
                    "temperature": model_config.temperature,
                    "max_tokens": model_config.max_tokens,
                    "estimated_latency": model_config.estimated_latency
                }
        
        return {
            "success": True,
            "models": model_details
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available models: {str(e)}")


@router.post("/models/current")
async def set_current_model(
    request: Request,
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Set current model configuration"""
    try:
        data = await request.json()
        model_key = data.get("model_key")
        
        if not model_key:
            raise HTTPException(status_code=400, detail="model_key is required")
        
        success = config_service.update_current_model(model_key)
        
        if not success:
            raise HTTPException(status_code=400, detail=f"Invalid model key: {model_key}")
        
        return {
            "success": True,
            "message": f"Model updated to {model_key}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update model: {str(e)}")


@router.get("/optimization/presets")
async def get_optimization_presets(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Get all optimization presets with their model configurations"""
    try:
        presets = config_service.get_available_presets()
        preset_details = {}
        
        for preset_name in presets:
            preset = config_service.get_optimization_preset(preset_name)
            if preset:
                preset_details[preset_name] = preset.to_dict()
        
        return {
            "success": True,
            "presets": preset_details
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get optimization presets: {str(e)}")


@router.post("/optimization/preset/{preset}")
async def set_optimization_preset(
    preset: str,
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Set optimization preset"""
    try:
        preset_config = config_service.get_optimization_preset(preset)
        
        if not preset_config:
            available_presets = config_service.get_available_presets()
            raise HTTPException(
                status_code=400, 
                detail=f"Unknown preset: {preset}. Available: {available_presets}"
            )
        
        # Update model to match preset
        success = config_service.update_current_model("default")  # This would be enhanced to use preset model
        
        return {
            "success": True,
            "message": f"Optimization preset set to {preset}",
            "preset_config": preset_config.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set preset: {str(e)}")


@router.get("/status")
async def get_configuration_status(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Get configuration loading status and validation errors"""
    try:
        status = config_service.get_configuration_status()
        return {
            "success": True,
            "status": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration status: {str(e)}")


@router.post("/reload")
async def reload_configuration(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Force reload configuration from files"""
    try:
        config = config_service.reload_configuration()
        validation_errors = config_service.get_validation_errors()
        
        # Record metrics
        config_metrics_collector.record_config_load(success=len(validation_errors) == 0)
        
        return {
            "success": True,
            "message": "Configuration reloaded successfully",
            "validation_errors": validation_errors,
            "available_models": config_service.get_available_models()
        }
    except Exception as e:
        config_metrics_collector.record_config_load(success=False)
        raise HTTPException(status_code=500, detail=f"Failed to reload configuration: {str(e)}")


# === CACHE MANAGEMENT ENDPOINTS ===

@router.get("/cache/statistics")
async def get_cache_statistics(
    cache_service: Annotated[CacheService, Depends(get_cache_service)] = None
):
    """Get comprehensive cache performance statistics"""
    try:
        stats = cache_service.get_comprehensive_statistics()
        return {
            "success": True,
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache statistics: {str(e)}")


@router.post("/cache/clear")
async def clear_all_caches(
    cache_service: Annotated[CacheService, Depends(get_cache_service)] = None
):
    """Clear all caches"""
    try:
        cache_service.clear_all_caches()
        return {
            "success": True,
            "message": "All caches cleared successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear caches: {str(e)}")


# === OPTIMIZATION ANALYTICS ENDPOINTS ===

@router.get("/analytics/performance")
async def get_performance_analytics(
    optimization_service: Annotated[OptimizationService, Depends(get_optimization_service)] = None
):
    """Get performance analytics and optimization insights"""
    try:
        stats = optimization_service.get_performance_statistics()
        return {
            "success": True,
            "analytics": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance analytics: {str(e)}")


@router.post("/analytics/query-complexity")
async def analyze_query_complexity(
    request: Request,
    optimization_service: Annotated[OptimizationService, Depends(get_optimization_service)] = None
):
    """Analyze query complexity and get model recommendations"""
    try:
        data = await request.json()
        query = data.get("query", "")
        
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        
        analysis = optimization_service.analyze_query_complexity(query)
        config_metrics_collector.record_query_complexity(analysis.complexity_score)
        
        return {
            "success": True,
            "analysis": analysis.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze query: {str(e)}")


@router.get("/analytics/recommendations")
async def get_optimization_recommendations(
    optimization_service: Annotated[OptimizationService, Depends(get_optimization_service)] = None
):
    """Get optimization recommendations based on usage patterns"""
    try:
        # Get recent performance data
        stats = optimization_service.get_performance_statistics()
        
        # Generate basic recommendations
        recommendations = []
        
        performance = stats.get("performance", {})
        cache_stats = performance.get("cache", {})
        complexity = performance.get("complexity", {})
        
        # Cache performance recommendations
        hit_rate = cache_stats.get("hit_rate_percent", 0)
        if hit_rate < 50:
            recommendations.append({
                "type": "cache_optimization",
                "priority": "high",
                "message": f"Cache hit rate is low ({hit_rate:.1f}%). Consider increasing cache TTL or size.",
                "action": "increase_cache_settings"
            })
        elif hit_rate > 85:
            recommendations.append({
                "type": "cache_optimization", 
                "priority": "info",
                "message": f"Excellent cache performance ({hit_rate:.1f}% hit rate).",
                "action": "maintain_current_settings"
            })
        
        # Model complexity recommendations
        avg_complexity = complexity.get("average_complexity", 0)
        if avg_complexity < 2.5:
            recommendations.append({
                "type": "model_optimization",
                "priority": "medium",
                "message": f"Average query complexity is low ({avg_complexity:.1f}). Consider using 'speed' preset.",
                "action": "switch_to_speed_preset"
            })
        elif avg_complexity > 4.0:
            recommendations.append({
                "type": "model_optimization",
                "priority": "medium", 
                "message": f"Average query complexity is high ({avg_complexity:.1f}). Consider using 'accuracy' preset.",
                "action": "switch_to_accuracy_preset"
            })
        
        return {
            "success": True,
            "recommendations": recommendations,
            "performance_summary": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


# === DOMAIN METRICS ENDPOINTS ===

@router.get("/metrics/domain")
async def get_configuration_domain_metrics():
    """Get Configuration Domain specific metrics"""
    try:
        metrics = config_metrics_collector.get_configuration_metrics()
        return {
            "success": True,
            "domain": "configuration",
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get domain metrics: {str(e)}")