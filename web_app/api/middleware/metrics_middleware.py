"""
API Middleware - Performance Metrics Collection

Middleware for collecting request metrics, performance data, and domain-specific statistics.
"""
import time
import logging
from typing import Callable, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and aggregates performance metrics for API requests.
    """
    
    def __init__(self):
        self._request_count = 0
        self._total_duration = 0.0
        self._endpoint_metrics: Dict[str, Dict[str, Any]] = {}
        self._domain_metrics: Dict[str, Dict[str, Any]] = {}
        
    def record_request(self, endpoint: str, method: str, duration: float, 
                      status_code: int, domain: str = None):
        """Record request metrics"""
        self._request_count += 1
        self._total_duration += duration
        
        # Endpoint-specific metrics
        endpoint_key = f"{method} {endpoint}"
        if endpoint_key not in self._endpoint_metrics:
            self._endpoint_metrics[endpoint_key] = {
                "count": 0,
                "total_duration": 0.0,
                "error_count": 0,
                "status_codes": {}
            }
        
        endpoint_data = self._endpoint_metrics[endpoint_key]
        endpoint_data["count"] += 1
        endpoint_data["total_duration"] += duration
        
        if status_code >= 400:
            endpoint_data["error_count"] += 1
        
        status_key = str(status_code)
        endpoint_data["status_codes"][status_key] = endpoint_data["status_codes"].get(status_key, 0) + 1
        
        # Domain-specific metrics  
        if domain:
            if domain not in self._domain_metrics:
                self._domain_metrics[domain] = {
                    "count": 0,
                    "total_duration": 0.0,
                    "error_count": 0
                }
            
            domain_data = self._domain_metrics[domain]
            domain_data["count"] += 1
            domain_data["total_duration"] += duration
            
            if status_code >= 400:
                domain_data["error_count"] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        avg_duration = self._total_duration / max(1, self._request_count)
        
        # Calculate endpoint averages
        endpoint_summaries = {}
        for endpoint, data in self._endpoint_metrics.items():
            endpoint_summaries[endpoint] = {
                "count": data["count"],
                "avg_duration_ms": (data["total_duration"] / max(1, data["count"])) * 1000,
                "error_rate": (data["error_count"] / max(1, data["count"])) * 100,
                "status_codes": data["status_codes"]
            }
        
        # Calculate domain averages
        domain_summaries = {}
        for domain, data in self._domain_metrics.items():
            domain_summaries[domain] = {
                "count": data["count"],
                "avg_duration_ms": (data["total_duration"] / max(1, data["count"])) * 1000,
                "error_rate": (data["error_count"] / max(1, data["count"])) * 100
            }
        
        return {
            "overall": {
                "total_requests": self._request_count,
                "avg_duration_ms": avg_duration * 1000,
                "total_duration_seconds": self._total_duration
            },
            "endpoints": endpoint_summaries,
            "domains": domain_summaries
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect performance metrics for all API requests.
    """
    
    def __init__(self, app):
        super().__init__(app)
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics"""
        start_time = time.time()
        
        # Extract endpoint and domain info
        path = request.url.path
        method = request.method
        domain = self._extract_domain_from_path(path)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            metrics_collector.record_request(
                endpoint=path,
                method=method,
                duration=duration,
                status_code=response.status_code,
                domain=domain
            )
            
            # Add timing header
            response.headers["X-Response-Time-Ms"] = f"{duration * 1000:.2f}"
            
            # Log slow requests
            if duration > 1.0:  # Log requests over 1 second
                logger.warning(
                    f"Slow request: {method} {path} took {duration:.2f}s "
                    f"(status: {response.status_code})"
                )
            
            return response
            
        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time
            metrics_collector.record_request(
                endpoint=path,
                method=method,
                duration=duration,
                status_code=500,
                domain=domain
            )
            
            logger.error(f"Request error: {method} {path} - {str(e)}")
            raise
    
    def _extract_domain_from_path(self, path: str) -> str:
        """Extract domain from API path"""
        if "/config" in path or "/optimization" in path:
            return "configuration"
        elif "/speech" in path or "/audio" in path:
            return "speech"
        elif "/ws" in path or "/websocket" in path:
            return "communication"
        elif "/annotation" in path or "/screenshot" in path or "/vignette" in path:
            return "annotation"
        elif "/health" in path or "/metrics" in path:
            return "infrastructure"
        else:
            return "unknown"


class ConfigurationMetricsCollector:
    """
    Specialized metrics collector for Configuration Domain operations.
    """
    
    def __init__(self):
        self._config_loads = 0
        self._config_load_errors = 0
        self._model_switches = 0
        self._cache_operations = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }
        self._query_complexities = []
        
    def record_config_load(self, success: bool = True):
        """Record configuration load attempt"""
        self._config_loads += 1
        if not success:
            self._config_load_errors += 1
    
    def record_model_switch(self, from_model: str, to_model: str):
        """Record model switch operation"""
        self._model_switches += 1
        logger.info(f"Model switch recorded: {from_model} -> {to_model}")
    
    def record_cache_operation(self, operation: str):
        """Record cache operation (hit, miss, eviction)"""
        if operation in self._cache_operations:
            self._cache_operations[operation] += 1
    
    def record_query_complexity(self, complexity: int):
        """Record query complexity score"""
        self._query_complexities.append(complexity)
        # Keep only last 1000 entries
        if len(self._query_complexities) > 1000:
            self._query_complexities = self._query_complexities[-1000:]
    
    def get_configuration_metrics(self) -> Dict[str, Any]:
        """Get Configuration Domain specific metrics"""
        cache_total = sum(self._cache_operations.values())
        cache_hit_rate = (self._cache_operations["hits"] / max(1, cache_total)) * 100
        
        avg_complexity = 0.0
        if self._query_complexities:
            avg_complexity = sum(self._query_complexities) / len(self._query_complexities)
        
        return {
            "configuration_loads": {
                "total": self._config_loads,
                "errors": self._config_load_errors,
                "success_rate": ((self._config_loads - self._config_load_errors) / max(1, self._config_loads)) * 100
            },
            "model_optimization": {
                "model_switches": self._model_switches
            },
            "cache_performance": {
                **self._cache_operations,
                "hit_rate_percent": cache_hit_rate,
                "total_operations": cache_total
            },
            "query_analysis": {
                "total_analyzed": len(self._query_complexities),
                "average_complexity": avg_complexity,
                "complexity_distribution": {
                    f"level_{i}": self._query_complexities.count(i) 
                    for i in range(1, 7)
                } if self._query_complexities else {}
            }
        }


# Global configuration metrics collector
config_metrics_collector = ConfigurationMetricsCollector()


def get_all_metrics() -> Dict[str, Any]:
    """Get comprehensive metrics from all collectors"""
    return {
        "api_metrics": metrics_collector.get_summary(),
        "configuration_metrics": config_metrics_collector.get_configuration_metrics(),
        "timestamp": time.time()
    }