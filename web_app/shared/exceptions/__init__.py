"""
Shared Exceptions

Common exception classes used across multiple domains and services.
"""

from .domain_exceptions import (
    DomainException, ConfigurationError, ValidationError, ServiceUnavailableError,
    CacheError, OptimizationError, ModelError
)

__all__ = [
    'DomainException',
    'ConfigurationError', 
    'ValidationError',
    'ServiceUnavailableError',
    'CacheError',
    'OptimizationError',
    'ModelError'
]