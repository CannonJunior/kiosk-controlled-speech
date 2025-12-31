"""
Configuration Domain - Optimization and Performance Models

Data models for optimization settings and performance tracking.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import time
import threading


@dataclass
class CacheEntry:
    """Generic cache entry with metadata"""
    data: Any
    created_at: float
    last_accessed: float
    access_count: int = 1
    context_hash: Optional[str] = None
    
    def update_access(self):
        """Update access timestamp and count"""
        self.last_accessed = time.time()
        self.access_count += 1
    
    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if entry has expired"""
        return (time.time() - self.created_at) > ttl_seconds
    
    def get_age_seconds(self) -> float:
        """Get age of entry in seconds"""
        return time.time() - self.created_at
    
    def get_idle_seconds(self) -> float:
        """Get time since last access in seconds"""
        return time.time() - self.last_accessed


@dataclass
class QueryComplexityAnalysis:
    """Analysis result for query complexity"""
    query: str
    complexity_score: int  # 1-6 scale
    word_count: int
    has_simple_patterns: bool
    has_complex_keywords: bool
    has_questions: bool
    has_multiple_requirements: bool
    recommended_model: str
    analysis_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "query": self.query,
            "complexity_score": self.complexity_score,
            "word_count": self.word_count,
            "patterns": {
                "simple_patterns": self.has_simple_patterns,
                "complex_keywords": self.has_complex_keywords,
                "questions": self.has_questions,
                "multiple_requirements": self.has_multiple_requirements
            },
            "recommended_model": self.recommended_model,
            "analysis_timestamp": datetime.fromtimestamp(self.analysis_time).isoformat()
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for optimization tracking"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    model_switches: int = 0
    query_complexities: List[int] = field(default_factory=list)
    response_times: List[float] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    def record_cache_hit(self):
        """Record cache hit"""
        self.cache_hits += 1
    
    def record_cache_miss(self):
        """Record cache miss"""
        self.cache_misses += 1
    
    def record_request(self, response_time: float, complexity_score: Optional[int] = None):
        """Record request with performance data"""
        self.total_requests += 1
        self.response_times.append(response_time)
        
        if complexity_score is not None:
            self.query_complexities.append(complexity_score)
        
        # Keep only last 1000 entries to prevent memory growth
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]
        if len(self.query_complexities) > 1000:
            self.query_complexities = self.query_complexities[-1000:]
    
    def record_model_switch(self):
        """Record model switch event"""
        self.model_switches += 1
    
    def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate percentage"""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / max(1, total)) * 100
    
    def get_average_response_time(self) -> float:
        """Calculate average response time"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def get_average_complexity(self) -> float:
        """Calculate average query complexity"""
        if not self.query_complexities:
            return 0.0
        return sum(self.query_complexities) / len(self.query_complexities)
    
    def get_uptime_seconds(self) -> float:
        """Get uptime in seconds"""
        return time.time() - self.start_time
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        uptime = self.get_uptime_seconds()
        
        # Response time statistics
        response_stats = {}
        if self.response_times:
            response_stats = {
                "count": len(self.response_times),
                "average": self.get_average_response_time(),
                "min": min(self.response_times),
                "max": max(self.response_times),
                "median": sorted(self.response_times)[len(self.response_times) // 2]
            }
        
        # Complexity distribution
        complexity_distribution = {}
        if self.query_complexities:
            for score in range(1, 7):
                complexity_distribution[f"level_{score}"] = self.query_complexities.count(score)
        
        return {
            "requests": {
                "total": self.total_requests,
                "requests_per_second": self.total_requests / max(1, uptime),
                "uptime_hours": uptime / 3600
            },
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate_percent": self.get_cache_hit_rate(),
                "total_cache_operations": self.cache_hits + self.cache_misses
            },
            "response_times": response_stats,
            "complexity": {
                "average_complexity": self.get_average_complexity(),
                "distribution": complexity_distribution,
                "total_analyzed": len(self.query_complexities)
            },
            "model_optimization": {
                "model_switches": self.model_switches,
                "switches_per_hour": self.model_switches / max(1, uptime / 3600)
            }
        }


@dataclass 
class CacheStatistics:
    """Statistics for cache performance"""
    name: str
    total_entries: int = 0
    max_size: int = 100
    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0
    last_cleanup: float = field(default_factory=time.time)
    
    def record_hit(self):
        """Record cache hit"""
        self.hit_count += 1
    
    def record_miss(self):
        """Record cache miss"""
        self.miss_count += 1
    
    def record_eviction(self):
        """Record cache eviction"""
        self.eviction_count += 1
    
    def get_hit_rate(self) -> float:
        """Calculate hit rate percentage"""
        total = self.hit_count + self.miss_count
        return (self.hit_count / max(1, total)) * 100
    
    def get_utilization(self) -> float:
        """Calculate cache utilization percentage"""
        return (self.total_entries / max(1, self.max_size)) * 100
    
    def get_summary(self) -> Dict[str, Any]:
        """Get cache statistics summary"""
        return {
            "name": self.name,
            "entries": self.total_entries,
            "max_size": self.max_size,
            "utilization_percent": self.get_utilization(),
            "hit_rate_percent": self.get_hit_rate(),
            "hits": self.hit_count,
            "misses": self.miss_count,
            "evictions": self.eviction_count,
            "last_cleanup": datetime.fromtimestamp(self.last_cleanup).isoformat()
        }


@dataclass
class OptimizationState:
    """Current optimization state and settings"""
    current_preset: str = "balanced"
    current_model: str = "default"
    cache_enabled: bool = True
    auto_optimization: bool = True
    performance_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    cache_stats: Dict[str, CacheStatistics] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)
    
    def update_timestamp(self):
        """Update last modified timestamp"""
        self.last_updated = time.time()
    
    def get_cache_stats(self, cache_name: str) -> CacheStatistics:
        """Get or create cache statistics"""
        if cache_name not in self.cache_stats:
            self.cache_stats[cache_name] = CacheStatistics(name=cache_name)
        return self.cache_stats[cache_name]
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive optimization status"""
        return {
            "current_preset": self.current_preset,
            "current_model": self.current_model,
            "cache_enabled": self.cache_enabled,
            "auto_optimization": self.auto_optimization,
            "performance": self.performance_metrics.get_statistics(),
            "cache_statistics": {
                name: stats.get_summary() 
                for name, stats in self.cache_stats.items()
            },
            "last_updated": datetime.fromtimestamp(self.last_updated).isoformat()
        }