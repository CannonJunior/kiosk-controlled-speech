"""
Configuration Domain - Optimization and Performance Service

Service for managing performance optimization, model selection, and query analysis.
"""
import logging
import re
import time
from typing import Dict, Any, Optional, List
from difflib import SequenceMatcher

from web_app.domains.configuration.models.config_models import (
    OptimizationPreset, ModelConfiguration, ApplicationConfiguration
)
from web_app.domains.configuration.models.optimization_models import (
    QueryComplexityAnalysis, PerformanceMetrics, OptimizationState
)

logger = logging.getLogger(__name__)


class QueryComplexityAnalyzer:
    """
    Analyzes query complexity for optimal model selection.
    """
    
    # Simple command patterns that indicate low complexity
    SIMPLE_PATTERNS = [
        r'^(click|tap|press|select)\s+\w+$',
        r'^(open|close|start|stop)\s+\w+$',
        r'^(go\s+to|navigate\s+to)\s+\w+$',
        r'^(help|show|display)\s*$'
    ]
    
    # Keywords that indicate complex operations
    COMPLEX_KEYWORDS = [
        'analyze', 'compare', 'calculate', 'generate', 'create', 'explain',
        'troubleshoot', 'configure', 'customize', 'optimize', 'research'
    ]
    
    # Question indicators
    QUESTION_WORDS = ['why', 'how', 'what if', 'explain']
    
    # Multi-requirement indicators
    MULTI_REQ_WORDS = [' and ', ' or ', ' also ', ' then ', ' after ']
    
    @classmethod
    def analyze_query(cls, query: str, available_models: Dict[str, ModelConfiguration]) -> QueryComplexityAnalysis:
        """
        Analyze query complexity and recommend optimal model.
        
        Args:
            query: Query text to analyze
            available_models: Available model configurations
            
        Returns:
            Query complexity analysis with model recommendation
        """
        if not query.strip():
            return QueryComplexityAnalysis(
                query=query,
                complexity_score=1,
                word_count=0,
                has_simple_patterns=False,
                has_complex_keywords=False,
                has_questions=False,
                has_multiple_requirements=False,
                recommended_model="default"
            )
        
        query_lower = query.lower().strip()
        complexity_score = 1
        word_count = len(query_lower.split())
        
        # Analyze patterns
        has_simple_patterns = any(re.match(pattern, query_lower) for pattern in cls.SIMPLE_PATTERNS)
        has_complex_keywords = any(keyword in query_lower for keyword in cls.COMPLEX_KEYWORDS)
        has_questions = any(word in query_lower for word in cls.QUESTION_WORDS)
        has_multiple_requirements = any(word in query_lower for word in cls.MULTI_REQ_WORDS)
        
        # Calculate complexity score
        # Base score from word count
        if word_count > 10:
            complexity_score += 2
        elif word_count > 5:
            complexity_score += 1
        
        # Adjust for patterns
        if has_simple_patterns:
            complexity_score = max(1, complexity_score - 1)
        
        if has_complex_keywords:
            complexity_score += 1
        
        if has_questions:
            complexity_score += 1
        
        if has_multiple_requirements:
            complexity_score += 1
        
        # Cap at 6
        complexity_score = min(6, complexity_score)
        
        # Recommend model based on complexity
        recommended_model = cls._recommend_model(complexity_score, available_models)
        
        return QueryComplexityAnalysis(
            query=query,
            complexity_score=complexity_score,
            word_count=word_count,
            has_simple_patterns=has_simple_patterns,
            has_complex_keywords=has_complex_keywords,
            has_questions=has_questions,
            has_multiple_requirements=has_multiple_requirements,
            recommended_model=recommended_model
        )
    
    @classmethod
    def _recommend_model(cls, complexity_score: int, available_models: Dict[str, ModelConfiguration]) -> str:
        """Recommend model based on complexity score"""
        if complexity_score <= 2:
            # Simple commands - use fastest model
            if "phi" in available_models:
                return "phi"
            return "default"
        elif complexity_score <= 4:
            # Medium complexity - use default balanced model
            return "default"
        else:
            # Complex queries - use accurate model
            if "accurate" in available_models:
                return "accurate"
            elif "balanced" in available_models:
                return "balanced"
            return "default"


class OptimizationService:
    """
    Service for managing application optimization settings and performance.
    
    Responsibilities:
    - Query complexity analysis and model selection
    - Performance metrics tracking
    - Optimization preset management
    - Cache coordination
    """
    
    def __init__(self, app_config: ApplicationConfiguration):
        self.app_config = app_config
        self.optimization_state = OptimizationState()
        self.complexity_analyzer = QueryComplexityAnalyzer()
        
    def analyze_query_complexity(self, query: str) -> QueryComplexityAnalysis:
        """
        Analyze query complexity and recommend optimal model.
        
        Args:
            query: Query text to analyze
            
        Returns:
            Complexity analysis with model recommendation
        """
        analysis = self.complexity_analyzer.analyze_query(query, self.app_config.models)
        
        # Record metrics
        self.optimization_state.performance_metrics.record_request(
            response_time=0.0,  # Will be updated when actual response time is available
            complexity_score=analysis.complexity_score
        )
        
        return analysis
    
    def select_optimal_model(self, query: str) -> str:
        """
        Select optimal model for query based on complexity analysis.
        
        Args:
            query: Query text to analyze
            
        Returns:
            Recommended model key
        """
        if not self.optimization_state.auto_optimization:
            return self.optimization_state.current_model
        
        analysis = self.analyze_query_complexity(query)
        recommended_model = analysis.recommended_model
        
        # Ensure recommended model exists in configuration
        if recommended_model not in self.app_config.models:
            recommended_model = self.app_config.current_model
        
        # Record model switch if different from current
        if recommended_model != self.optimization_state.current_model:
            self.optimization_state.performance_metrics.record_model_switch()
            logger.info(f"Switching to model '{recommended_model}' for query complexity {analysis.complexity_score}")
        
        return recommended_model
    
    def apply_optimization_preset(self, preset_name: str) -> bool:
        """
        Apply optimization preset settings.
        
        Args:
            preset_name: Name of preset to apply
            
        Returns:
            True if preset applied successfully
        """
        preset = self.app_config.optimization_presets.get(preset_name)
        if not preset:
            logger.error(f"Optimization preset '{preset_name}' not found")
            return False
        
        try:
            # Update optimization state
            self.optimization_state.current_preset = preset_name
            self.optimization_state.current_model = preset_name  # Use preset name as model key
            self.optimization_state.update_timestamp()
            
            logger.info(f"Applied optimization preset: {preset_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply optimization preset '{preset_name}': {e}")
            return False
    
    def get_optimization_presets(self) -> Dict[str, Dict[str, Any]]:
        """Get all optimization presets in API format"""
        return {
            name: preset.to_dict()
            for name, preset in self.app_config.optimization_presets.items()
        }
    
    def get_current_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status and settings"""
        current_model_config = self.app_config.models.get(
            self.optimization_state.current_model,
            self.app_config.get_current_model_config()
        )
        
        return {
            "current_preset": self.optimization_state.current_preset,
            "current_model": {
                "key": self.optimization_state.current_model,
                "name": current_model_config.name if current_model_config else "unknown",
                "description": current_model_config.description if current_model_config else "",
                "estimated_latency": current_model_config.estimated_latency if current_model_config else "unknown"
            },
            "auto_optimization": self.optimization_state.auto_optimization,
            "cache_enabled": self.optimization_state.cache_enabled,
            "available_models": list(self.app_config.models.keys()),
            "last_updated": self.optimization_state.last_updated
        }
    
    def get_performance_statistics(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        return self.optimization_state.get_comprehensive_status()
    
    def record_response_time(self, response_time: float, query: Optional[str] = None):
        """
        Record response time for performance tracking.
        
        Args:
            response_time: Response time in seconds
            query: Optional query for complexity analysis
        """
        complexity_score = None
        if query:
            analysis = self.analyze_query_complexity(query)
            complexity_score = analysis.complexity_score
        
        self.optimization_state.performance_metrics.record_request(
            response_time=response_time,
            complexity_score=complexity_score
        )
    
    def record_cache_hit(self, cache_name: str = "response"):
        """Record cache hit for performance tracking"""
        self.optimization_state.performance_metrics.record_cache_hit()
        cache_stats = self.optimization_state.get_cache_stats(cache_name)
        cache_stats.record_hit()
    
    def record_cache_miss(self, cache_name: str = "response"):
        """Record cache miss for performance tracking"""
        self.optimization_state.performance_metrics.record_cache_miss()
        cache_stats = self.optimization_state.get_cache_stats(cache_name)
        cache_stats.record_miss()
    
    def set_auto_optimization(self, enabled: bool):
        """Enable or disable automatic optimization"""
        self.optimization_state.auto_optimization = enabled
        self.optimization_state.update_timestamp()
        logger.info(f"Auto-optimization {'enabled' if enabled else 'disabled'}")
    
    def set_cache_enabled(self, enabled: bool):
        """Enable or disable caching"""
        self.optimization_state.cache_enabled = enabled
        self.optimization_state.update_timestamp()
        logger.info(f"Caching {'enabled' if enabled else 'disabled'}")
    
    def clear_performance_metrics(self):
        """Reset performance metrics"""
        self.optimization_state.performance_metrics = PerformanceMetrics()
        self.optimization_state.cache_stats.clear()
        logger.info("Performance metrics cleared")
    
    def get_model_recommendations(self, query_history: List[str]) -> Dict[str, Any]:
        """
        Analyze query history and provide model usage recommendations.
        
        Args:
            query_history: Recent queries to analyze
            
        Returns:
            Analysis and recommendations
        """
        if not query_history:
            return {"recommendations": "No query history available"}
        
        # Analyze complexity distribution
        complexity_scores = []
        for query in query_history[-100:]:  # Analyze last 100 queries
            analysis = self.analyze_query_complexity(query)
            complexity_scores.append(analysis.complexity_score)
        
        avg_complexity = sum(complexity_scores) / len(complexity_scores)
        complexity_distribution = {}
        for score in range(1, 7):
            complexity_distribution[f"level_{score}"] = complexity_scores.count(score)
        
        # Generate recommendations
        recommendations = []
        if avg_complexity < 2.5:
            recommendations.append("Consider using 'speed' preset for faster responses")
        elif avg_complexity > 4.0:
            recommendations.append("Consider using 'accuracy' preset for better results")
        else:
            recommendations.append("Current 'balanced' configuration is optimal")
        
        # Cache efficiency recommendations
        cache_hit_rate = self.optimization_state.performance_metrics.get_cache_hit_rate()
        if cache_hit_rate < 50:
            recommendations.append("Cache hit rate is low - consider increasing cache TTL")
        elif cache_hit_rate > 90:
            recommendations.append("Excellent cache performance")
        
        return {
            "average_complexity": avg_complexity,
            "complexity_distribution": complexity_distribution,
            "cache_hit_rate": cache_hit_rate,
            "recommendations": recommendations,
            "analysis_period": f"Last {len(query_history)} queries"
        }