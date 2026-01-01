"""
Infrastructure Layer - Metrics and Performance Monitoring

Centralized metrics collection and performance monitoring for all domains.
"""
import time
import statistics
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class DomainMetrics:
    """Metrics for a specific domain"""
    domain_name: str
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    response_times: List[float] = field(default_factory=list)
    last_request_time: Optional[datetime] = None
    avg_response_time: float = 0.0
    
    def add_request(self, success: bool, response_time: float):
        """Add a request to the metrics"""
        self.request_count += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        self.response_times.append(response_time)
        self.last_request_time = datetime.now()
        
        # Keep only last 1000 response times
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]
        
        # Update average
        self.avg_response_time = statistics.mean(self.response_times)
    
    def get_success_rate(self) -> float:
        """Get success rate as percentage"""
        if self.request_count == 0:
            return 0.0
        return (self.success_count / self.request_count) * 100
    
    def get_response_time_stats(self) -> Dict[str, float]:
        """Get response time statistics"""
        if not self.response_times:
            return {"avg": 0.0, "min": 0.0, "max": 0.0, "median": 0.0}
        
        return {
            "avg": statistics.mean(self.response_times),
            "min": min(self.response_times),
            "max": max(self.response_times),
            "median": statistics.median(self.response_times)
        }


class MetricsCollector:
    """
    Centralized metrics collection for application monitoring.
    
    Responsibilities:
    - Collect metrics from all domains
    - Provide real-time performance statistics
    - Monitor system health and performance trends
    - Generate alerts for performance degradation
    """
    
    def __init__(self):
        self.domain_metrics: Dict[str, DomainMetrics] = {}
        self.start_time = time.time()
        self.system_metrics = {
            "total_requests": 0,
            "total_errors": 0,
            "uptime_seconds": 0
        }
        
        # Performance thresholds
        self.response_time_threshold = 2.0  # 2 seconds
        self.error_rate_threshold = 5.0     # 5% error rate
        self.alert_callbacks = []
    
    def record_domain_request(self, domain: str, success: bool, response_time: float, context: Optional[Dict[str, Any]] = None):
        """
        Record a request for a specific domain.
        
        Args:
            domain: Domain name (e.g., 'speech', 'communication')
            success: Whether the request was successful
            response_time: Response time in seconds
            context: Additional context information
        """
        if domain not in self.domain_metrics:
            self.domain_metrics[domain] = DomainMetrics(domain_name=domain)
        
        self.domain_metrics[domain].add_request(success, response_time)
        self.system_metrics["total_requests"] += 1
        
        if not success:
            self.system_metrics["total_errors"] += 1
        
        # Check for performance issues
        self._check_performance_alerts(domain, response_time, success)
    
    def get_domain_metrics(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific domain"""
        if domain not in self.domain_metrics:
            return None
        
        metrics = self.domain_metrics[domain]
        return {
            "domain": domain,
            "request_count": metrics.request_count,
            "success_count": metrics.success_count,
            "error_count": metrics.error_count,
            "success_rate": f"{metrics.get_success_rate():.1f}%",
            "response_times": metrics.get_response_time_stats(),
            "last_request": metrics.last_request_time.isoformat() if metrics.last_request_time else None
        }
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system metrics"""
        uptime = time.time() - self.start_time
        self.system_metrics["uptime_seconds"] = uptime
        
        # Calculate overall success rate
        overall_success_rate = 0.0
        if self.system_metrics["total_requests"] > 0:
            success_count = self.system_metrics["total_requests"] - self.system_metrics["total_errors"]
            overall_success_rate = (success_count / self.system_metrics["total_requests"]) * 100
        
        return {
            "uptime_hours": uptime / 3600,
            "total_requests": self.system_metrics["total_requests"],
            "total_errors": self.system_metrics["total_errors"],
            "overall_success_rate": f"{overall_success_rate:.1f}%",
            "active_domains": len(self.domain_metrics),
            "performance_status": self._get_performance_status()
        }
    
    def get_all_domain_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all domains"""
        return {
            domain: self.get_domain_metrics(domain)
            for domain in self.domain_metrics.keys()
        }
    
    def get_health_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive health dashboard data"""
        system_metrics = self.get_system_metrics()
        domain_metrics = self.get_all_domain_metrics()
        
        # Calculate domain health status
        domain_health = {}
        for domain, metrics in domain_metrics.items():
            if metrics:
                response_stats = metrics["response_times"]
                success_rate = float(metrics["success_rate"].rstrip('%'))
                avg_response = response_stats["avg"]
                
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
                    "success_rate": success_rate,
                    "avg_response_time": f"{avg_response:.3f}s",
                    "request_count": metrics["request_count"]
                }
        
        return {
            "system": system_metrics,
            "domains": domain_health,
            "alerts": self._get_active_alerts(),
            "timestamp": datetime.now().isoformat()
        }
    
    def add_alert_callback(self, callback):
        """Add a callback function for performance alerts"""
        self.alert_callbacks.append(callback)
    
    def _check_performance_alerts(self, domain: str, response_time: float, success: bool):
        """Check if performance thresholds are exceeded and trigger alerts"""
        alerts = []
        
        # Check response time threshold
        if response_time > self.response_time_threshold:
            alerts.append({
                "type": "slow_response",
                "domain": domain,
                "response_time": response_time,
                "threshold": self.response_time_threshold,
                "timestamp": datetime.now().isoformat()
            })
        
        # Check error rate for domain
        if domain in self.domain_metrics:
            metrics = self.domain_metrics[domain]
            if metrics.request_count >= 10:  # Only check after enough requests
                error_rate = (metrics.error_count / metrics.request_count) * 100
                if error_rate > self.error_rate_threshold:
                    alerts.append({
                        "type": "high_error_rate",
                        "domain": domain,
                        "error_rate": error_rate,
                        "threshold": self.error_rate_threshold,
                        "timestamp": datetime.now().isoformat()
                    })
        
        # Trigger alert callbacks
        for alert in alerts:
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    print(f"Alert callback error: {e}")
    
    def _get_performance_status(self) -> str:
        """Get overall performance status"""
        if not self.domain_metrics:
            return "unknown"
        
        poor_domains = 0
        total_domains = len(self.domain_metrics)
        
        for domain_metrics in self.domain_metrics.values():
            if domain_metrics.request_count == 0:
                continue
                
            error_rate = (domain_metrics.error_count / domain_metrics.request_count) * 100
            avg_response = domain_metrics.avg_response_time
            
            if error_rate > self.error_rate_threshold or avg_response > self.response_time_threshold:
                poor_domains += 1
        
        if poor_domains == 0:
            return "excellent"
        elif poor_domains <= total_domains * 0.2:  # 20% or less performing poorly
            return "good"
        elif poor_domains <= total_domains * 0.5:  # 50% or less performing poorly
            return "acceptable"
        else:
            return "poor"
    
    def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get currently active performance alerts"""
        alerts = []
        
        for domain, metrics in self.domain_metrics.items():
            if metrics.request_count == 0:
                continue
            
            # Check for high error rate
            error_rate = (metrics.error_count / metrics.request_count) * 100
            if error_rate > self.error_rate_threshold:
                alerts.append({
                    "type": "high_error_rate",
                    "domain": domain,
                    "current_value": f"{error_rate:.1f}%",
                    "threshold": f"{self.error_rate_threshold:.1f}%",
                    "severity": "high" if error_rate > self.error_rate_threshold * 2 else "medium"
                })
            
            # Check for slow response times
            if metrics.avg_response_time > self.response_time_threshold:
                alerts.append({
                    "type": "slow_response",
                    "domain": domain,
                    "current_value": f"{metrics.avg_response_time:.3f}s",
                    "threshold": f"{self.response_time_threshold:.1f}s",
                    "severity": "high" if metrics.avg_response_time > self.response_time_threshold * 2 else "medium"
                })
        
        return alerts
    
    def record_mcp_tool_call(self, tool_name: str, success: bool, duration_ms: float):
        """Record MCP tool call metrics"""
        domain = "mcp"
        if domain not in self.domain_metrics:
            self.domain_metrics[domain] = DomainMetrics(domain_name=domain)
        
        duration_seconds = duration_ms / 1000.0
        self.record_domain_request(domain, success, duration_seconds, context={
            "operation": "tool_call",
            "tool_name": tool_name
        })
    
    def reset_metrics(self, domain: Optional[str] = None):
        """Reset metrics for a domain or all domains"""
        if domain:
            if domain in self.domain_metrics:
                self.domain_metrics[domain] = DomainMetrics(domain_name=domain)
        else:
            self.domain_metrics.clear()
            self.system_metrics = {
                "total_requests": 0,
                "total_errors": 0,
                "uptime_seconds": 0
            }
            self.start_time = time.time()


# Global metrics collector instance
metrics_collector = MetricsCollector()