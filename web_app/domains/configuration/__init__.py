"""
Configuration Domain

Domain-driven design module for centralized configuration management,
optimization settings, and performance tracking.

This domain provides:
- Configuration loading and validation
- Model selection and optimization
- Multi-tier caching services
- Performance metrics tracking
"""

from .services.config_service import ConfigurationService
from .services.optimization_service import OptimizationService
from .services.cache_service import CacheService
from .repositories.config_repository import ConfigurationFileRepository
from .models.config_models import (
    ApplicationConfiguration, VADConfiguration, ModelConfiguration,
    CacheConfiguration, OptimizationPreset
)
from .models.optimization_models import (
    QueryComplexityAnalysis, PerformanceMetrics, OptimizationState,
    CacheEntry, CacheStatistics
)

__all__ = [
    # Services
    'ConfigurationService',
    'OptimizationService', 
    'CacheService',
    
    # Repository
    'ConfigurationFileRepository',
    
    # Models - Configuration
    'ApplicationConfiguration',
    'VADConfiguration',
    'ModelConfiguration',
    'CacheConfiguration',
    'OptimizationPreset',
    
    # Models - Optimization
    'QueryComplexityAnalysis',
    'PerformanceMetrics',
    'OptimizationState',
    'CacheEntry',
    'CacheStatistics'
]


def create_configuration_domain():
    """
    Factory function to create and initialize the configuration domain.
    
    Returns:
        Tuple of (config_service, optimization_service, cache_service)
    """
    # Initialize repository
    config_repository = ConfigurationFileRepository()
    
    # Initialize configuration service
    config_service = ConfigurationService()
    
    # Load application configuration
    app_config = config_service.load_configuration()
    
    # Initialize optimization service
    optimization_service = OptimizationService(app_config)
    
    # Initialize cache service
    cache_service = CacheService(app_config.cache_config)
    
    return config_service, optimization_service, cache_service