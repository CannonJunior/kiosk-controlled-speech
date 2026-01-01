"""
API v1 - Admin and Debugging Routes

Administrative endpoints for configuration validation, system diagnostics, and debugging.
"""
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Request

from web_app.api.dependencies.domain_services import get_configuration_service
from web_app.domains.configuration.services.config_service import ConfigurationService
from web_app.domains.configuration.repositories.config_repository import ConfigurationFileRepository
from web_app.api.middleware.metrics_middleware import get_all_metrics

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/config/validate")
async def validate_all_configurations():
    """Validate all configuration files and return detailed results"""
    try:
        repo = ConfigurationFileRepository()
        config_files = repo.list_config_files()
        
        validation_results = {}
        summary = {
            "total_files": len(config_files),
            "valid_files": 0,
            "invalid_files": 0,
            "files_with_warnings": 0
        }
        
        for filename in config_files:
            validation = repo.validate_config_file(filename)
            validation_results[filename] = validation
            
            if validation["valid"]:
                summary["valid_files"] += 1
            else:
                summary["invalid_files"] += 1
            
            if validation.get("warnings"):
                summary["files_with_warnings"] += 1
        
        return {
            "success": True,
            "summary": summary,
            "validation_results": validation_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate configurations: {str(e)}")


@router.get("/config/validate/{filename}")
async def validate_specific_configuration(filename: str):
    """Validate a specific configuration file"""
    try:
        repo = ConfigurationFileRepository()
        validation = repo.validate_config_file(filename)
        
        if not validation:
            raise HTTPException(status_code=404, detail=f"Configuration file not found: {filename}")
        
        return {
            "success": True,
            "filename": filename,
            "validation": validation
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate configuration: {str(e)}")


@router.get("/config/files")
async def list_configuration_files():
    """List all configuration files with metadata"""
    try:
        repo = ConfigurationFileRepository()
        files = repo.list_config_files()
        
        file_details = {}
        for filename in files:
            file_info = repo.get_file_info(filename)
            if file_info:
                file_details[filename] = file_info
        
        summary = repo.get_config_summary()
        
        return {
            "success": True,
            "files": file_details,
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list configuration files: {str(e)}")


@router.post("/config/backup/cleanup")
async def cleanup_old_backups(max_backups: int = 10):
    """Clean up old backup files"""
    try:
        repo = ConfigurationFileRepository()
        removed_count = repo.cleanup_old_backups(max_backups)
        
        return {
            "success": True,
            "message": f"Cleaned up {removed_count} old backup files",
            "max_backups": max_backups,
            "removed_count": removed_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup backups: {str(e)}")


@router.get("/diagnostics/configuration")
async def get_configuration_diagnostics(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)] = None
):
    """Get comprehensive configuration diagnostics"""
    try:
        # Get configuration status
        config_status = config_service.get_configuration_status()
        
        # Get validation errors
        validation_errors = config_service.get_validation_errors()
        
        # Get available models and presets
        available_models = config_service.get_available_models()
        available_presets = config_service.get_available_presets()
        
        # Get current configurations
        current_model = config_service.get_model_configuration()
        vad_config = config_service.get_vad_configuration()
        
        # Check for potential issues
        issues = []
        
        if validation_errors:
            issues.extend([{"type": "validation", "message": error} for error in validation_errors])
        
        if not available_models:
            issues.append({"type": "configuration", "message": "No models available"})
        
        if not current_model:
            issues.append({"type": "configuration", "message": "No current model configured"})
        
        if vad_config.sensitivity <= 0 or vad_config.sensitivity > 1:
            issues.append({"type": "vad", "message": f"VAD sensitivity out of range: {vad_config.sensitivity}"})
        
        return {
            "success": True,
            "diagnostics": {
                "configuration_status": config_status,
                "validation_errors": validation_errors,
                "available_models": available_models,
                "available_presets": available_presets,
                "current_model": {
                    "name": current_model.name if current_model else None,
                    "description": current_model.description if current_model else None,
                    "temperature": current_model.temperature if current_model else None
                } if current_model else None,
                "vad_configuration": {
                    "enabled": vad_config.enabled,
                    "sensitivity": vad_config.sensitivity,
                    "silence_timeout_ms": vad_config.silence_timeout_ms
                },
                "issues": issues,
                "overall_health": "healthy" if not issues else "issues_detected"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration diagnostics: {str(e)}")


@router.get("/metrics/comprehensive")
async def get_comprehensive_system_metrics():
    """Get comprehensive system metrics for monitoring and debugging"""
    try:
        metrics = get_all_metrics()
        return {
            "success": True,
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system metrics: {str(e)}")


@router.get("/system/health")
async def get_system_health_check():
    """Comprehensive system health check"""
    try:
        # Configuration health
        config_service = ConfigurationService()
        config = config_service.load_configuration()
        config_errors = config_service.get_validation_errors()
        
        # File system health
        repo = ConfigurationFileRepository()
        config_summary = repo.get_config_summary()
        
        # Calculate health scores
        config_health_score = 100 - (len(config_errors) * 10)  # Deduct 10 points per error
        file_health_score = (config_summary["validation_summary"]["valid"] / max(1, config_summary["total_files"])) * 100
        
        overall_health = (config_health_score + file_health_score) / 2
        
        health_status = "healthy"
        if overall_health < 50:
            health_status = "critical"
        elif overall_health < 80:
            health_status = "warning"
        
        return {
            "success": True,
            "health": {
                "overall_status": health_status,
                "overall_score": round(overall_health, 1),
                "configuration": {
                    "status": "healthy" if config_health_score >= 80 else "issues",
                    "score": config_health_score,
                    "error_count": len(config_errors),
                    "available_models": len(config.models),
                    "available_presets": len(config.optimization_presets)
                },
                "files": {
                    "status": "healthy" if file_health_score >= 80 else "issues",
                    "score": file_health_score,
                    "total_files": config_summary["total_files"],
                    "valid_files": config_summary["validation_summary"]["valid"],
                    "invalid_files": config_summary["validation_summary"]["invalid"]
                }
            }
        }
    except Exception as e:
        return {
            "success": False,
            "health": {
                "overall_status": "critical",
                "error": str(e)
            }
        }


@router.post("/debug/analyze-query")
async def debug_analyze_query(request: Request):
    """Debug query complexity analysis with detailed breakdown"""
    try:
        from web_app.domains.configuration import create_configuration_domain
        
        data = await request.json()
        query = data.get("query", "")
        
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        
        # Create services for analysis
        config_service, optimization_service, _ = create_configuration_domain()
        app_config = config_service.load_configuration()
        
        # Perform detailed analysis
        analysis = optimization_service.analyze_query_complexity(query)
        
        # Additional debug information
        debug_info = {
            "raw_query": query,
            "normalized_query": query.lower().strip(),
            "word_count": len(query.split()),
            "available_models": list(app_config.models.keys()),
            "analysis_details": {
                "complexity_score": analysis.complexity_score,
                "recommended_model": analysis.recommended_model,
                "patterns_detected": {
                    "simple_patterns": analysis.has_simple_patterns,
                    "complex_keywords": analysis.has_complex_keywords,
                    "questions": analysis.has_questions,
                    "multiple_requirements": analysis.has_multiple_requirements
                }
            }
        }
        
        return {
            "success": True,
            "debug_analysis": debug_info,
            "full_analysis": analysis.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to debug analyze query: {str(e)}")