"""
Infrastructure Layer - Health Checking and System Monitoring

Comprehensive health checking for all system components and external dependencies.
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check operation"""
    component: str
    status: HealthStatus
    response_time_ms: float
    message: str = ""
    details: Dict[str, Any] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.details is None:
            self.details = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "component": self.component,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }


class BaseHealthCheck:
    """Base class for health check implementations"""
    
    def __init__(self, component_name: str, timeout_seconds: float = 5.0):
        self.component_name = component_name
        self.timeout_seconds = timeout_seconds
        
    async def check(self) -> HealthCheckResult:
        """Perform the health check"""
        start_time = time.time()
        
        try:
            # Run the actual health check with timeout
            await asyncio.wait_for(self._perform_check(), timeout=self.timeout_seconds)
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                component=self.component_name,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                message="Component is healthy"
            )
            
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component=self.component_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"Health check timed out after {self.timeout_seconds}s"
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component=self.component_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"Health check failed: {str(e)}"
            )
    
    async def _perform_check(self):
        """Override this method to implement specific health check logic"""
        raise NotImplementedError("Subclasses must implement _perform_check")


class MCPHealthCheck(BaseHealthCheck):
    """Health check for MCP client and servers"""
    
    def __init__(self, mcp_client, timeout_seconds: float = 3.0):
        super().__init__("mcp_client", timeout_seconds)
        self.mcp_client = mcp_client
    
    async def _perform_check(self):
        """Check MCP client health and server availability"""
        if not self.mcp_client:
            raise Exception("MCP client not initialized")
        
        # Try to perform a simple health check call
        try:
            # This would be a simple health check call to MCP servers
            # For now, just check if client is initialized
            if not hasattr(self.mcp_client, '_client'):
                raise Exception("MCP client not properly initialized")
            
        except Exception as e:
            raise Exception(f"MCP client unhealthy: {str(e)}")


class ConfigurationHealthCheck(BaseHealthCheck):
    """Health check for configuration system"""
    
    def __init__(self, config_service, timeout_seconds: float = 2.0):
        super().__init__("configuration", timeout_seconds)
        self.config_service = config_service
    
    async def _perform_check(self):
        """Check configuration loading and validation"""
        try:
            # Load configuration
            config = self.config_service.load_configuration()
            
            # Check for validation errors
            errors = self.config_service.get_validation_errors()
            if errors:
                raise Exception(f"Configuration validation errors: {len(errors)} issues")
            
            # Check essential components
            if not config.models:
                raise Exception("No models configured")
            
            current_model = config.get_current_model_config()
            if not current_model:
                raise Exception("No current model available")
                
        except Exception as e:
            raise Exception(f"Configuration system unhealthy: {str(e)}")


class CacheHealthCheck(BaseHealthCheck):
    """Health check for cache system"""
    
    def __init__(self, cache_service, timeout_seconds: float = 1.0):
        super().__init__("cache_system", timeout_seconds)
        self.cache_service = cache_service
    
    async def _perform_check(self):
        """Check cache system responsiveness"""
        try:
            # Get cache statistics
            stats = self.cache_service.get_comprehensive_statistics()
            
            # Check if cache is responding
            if not stats:
                raise Exception("Cache service not responding")
            
            # Check cache configuration
            config = stats.get("configuration", {})
            if not config.get("enabled"):
                logger.info("Cache is disabled - reporting as degraded")
                # This is not an error, just degraded performance
                
        except Exception as e:
            raise Exception(f"Cache system unhealthy: {str(e)}")


class FileSystemHealthCheck(BaseHealthCheck):
    """Health check for file system access"""
    
    def __init__(self, config_paths: List[str] = None, timeout_seconds: float = 1.0):
        super().__init__("file_system", timeout_seconds)
        self.config_paths = config_paths or ["config/"]
    
    async def _perform_check(self):
        """Check file system access for configuration directories"""
        import os
        from pathlib import Path
        
        try:
            for path_str in self.config_paths:
                path = Path(path_str)
                
                # Check if path exists
                if not path.exists():
                    raise Exception(f"Required path does not exist: {path_str}")
                
                # Check read access
                if not os.access(path, os.R_OK):
                    raise Exception(f"No read access to: {path_str}")
                
                # Check write access for directories
                if path.is_dir() and not os.access(path, os.W_OK):
                    raise Exception(f"No write access to directory: {path_str}")
                    
        except Exception as e:
            raise Exception(f"File system access issues: {str(e)}")


class SystemHealthChecker:
    """
    Centralized system health checker that orchestrates multiple health checks.
    """
    
    def __init__(self):
        self.health_checks: Dict[str, BaseHealthCheck] = {}
        self.last_check_results: Dict[str, HealthCheckResult] = {}
        self.check_interval_seconds = 30.0
        self._running = False
        self._background_task = None
        
    def register_health_check(self, health_check: BaseHealthCheck):
        """Register a health check component"""
        self.health_checks[health_check.component_name] = health_check
        logger.info(f"Registered health check for component: {health_check.component_name}")
    
    def unregister_health_check(self, component_name: str):
        """Unregister a health check component"""
        if component_name in self.health_checks:
            del self.health_checks[component_name]
            if component_name in self.last_check_results:
                del self.last_check_results[component_name]
            logger.info(f"Unregistered health check for component: {component_name}")
    
    async def check_component(self, component_name: str) -> Optional[HealthCheckResult]:
        """Check health of a specific component"""
        health_check = self.health_checks.get(component_name)
        if not health_check:
            return None
        
        try:
            result = await health_check.check()
            self.last_check_results[component_name] = result
            return result
        except Exception as e:
            logger.error(f"Health check failed for {component_name}: {e}")
            error_result = HealthCheckResult(
                component=component_name,
                status=HealthStatus.UNKNOWN,
                response_time_ms=0.0,
                message=f"Health check error: {str(e)}"
            )
            self.last_check_results[component_name] = error_result
            return error_result
    
    async def check_all_components(self) -> Dict[str, HealthCheckResult]:
        """Check health of all registered components"""
        results = {}
        
        # Run all health checks concurrently
        tasks = {
            name: self.check_component(name)
            for name in self.health_checks.keys()
        }
        
        if tasks:
            completed = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            for (name, task_result) in zip(tasks.keys(), completed):
                if isinstance(task_result, HealthCheckResult):
                    results[name] = task_result
                elif isinstance(task_result, Exception):
                    logger.error(f"Health check task failed for {name}: {task_result}")
                    results[name] = HealthCheckResult(
                        component=name,
                        status=HealthStatus.UNKNOWN,
                        response_time_ms=0.0,
                        message=f"Task failed: {str(task_result)}"
                    )
        
        return results
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get overall system health summary"""
        if not self.last_check_results:
            return {
                "overall_status": HealthStatus.UNKNOWN.value,
                "message": "No health checks performed yet",
                "component_count": len(self.health_checks),
                "healthy_components": 0,
                "degraded_components": 0,
                "unhealthy_components": 0,
                "components": {}
            }
        
        healthy_count = 0
        degraded_count = 0
        unhealthy_count = 0
        
        component_details = {}
        
        for component, result in self.last_check_results.items():
            component_details[component] = result.to_dict()
            
            if result.status == HealthStatus.HEALTHY:
                healthy_count += 1
            elif result.status == HealthStatus.DEGRADED:
                degraded_count += 1
            else:
                unhealthy_count += 1
        
        # Determine overall status
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
            message = f"{unhealthy_count} components unhealthy"
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
            message = f"{degraded_count} components degraded"
        else:
            overall_status = HealthStatus.HEALTHY
            message = "All components healthy"
        
        return {
            "overall_status": overall_status.value,
            "message": message,
            "component_count": len(self.last_check_results),
            "healthy_components": healthy_count,
            "degraded_components": degraded_count,
            "unhealthy_components": unhealthy_count,
            "components": component_details,
            "last_check_timestamp": max(
                (result.timestamp for result in self.last_check_results.values()),
                default=time.time()
            )
        }
    
    async def start_background_checking(self, interval_seconds: float = None):
        """Start background health checking"""
        if interval_seconds:
            self.check_interval_seconds = interval_seconds
        
        self._running = True
        self._background_task = asyncio.create_task(self._background_check_loop())
        logger.info(f"Started background health checking (interval: {self.check_interval_seconds}s)")
    
    async def stop_background_checking(self):
        """Stop background health checking"""
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped background health checking")
    
    async def _background_check_loop(self):
        """Background loop for periodic health checks"""
        while self._running:
            try:
                await self.check_all_components()
            except Exception as e:
                logger.error(f"Background health check error: {e}")
            
            try:
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                break


# Global health checker instance
system_health_checker = SystemHealthChecker()


def get_system_health_checker() -> SystemHealthChecker:
    """Get the global system health checker instance"""
    return system_health_checker