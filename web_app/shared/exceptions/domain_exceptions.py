"""
Domain Exception Classes

Exception hierarchy for domain-specific errors across all application domains.
"""
from typing import Dict, Any, Optional


class DomainException(Exception):
    """
    Base exception for all domain-related errors.
    
    Provides structured error information with context and metadata.
    """
    
    def __init__(
        self, 
        message: str, 
        error_code: str = None,
        context: Dict[str, Any] = None,
        cause: Exception = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        result = {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context
        }
        
        if self.cause:
            result["caused_by"] = str(self.cause)
        
        return result


class ConfigurationError(DomainException):
    """
    Exception for configuration-related errors.
    
    Used when configuration loading, validation, or access fails.
    """
    
    def __init__(self, message: str, config_file: str = None, validation_errors: list = None, **kwargs):
        super().__init__(message, **kwargs)
        if config_file:
            self.context["config_file"] = config_file
        if validation_errors:
            self.context["validation_errors"] = validation_errors


class ValidationError(DomainException):
    """
    Exception for data validation errors.
    
    Used when input data doesn't meet domain requirements.
    """
    
    def __init__(self, message: str, field: str = None, value: Any = None, **kwargs):
        super().__init__(message, **kwargs)
        if field:
            self.context["field"] = field
        if value is not None:
            self.context["value"] = str(value)


class ServiceUnavailableError(DomainException):
    """
    Exception for service availability issues.
    
    Used when external services (MCP servers, databases, etc.) are unavailable.
    """
    
    def __init__(self, message: str, service_name: str = None, retry_after: int = None, **kwargs):
        super().__init__(message, **kwargs)
        if service_name:
            self.context["service_name"] = service_name
        if retry_after:
            self.context["retry_after_seconds"] = retry_after


class CacheError(DomainException):
    """
    Exception for cache-related errors.
    
    Used when cache operations fail or cache consistency is compromised.
    """
    
    def __init__(self, message: str, cache_type: str = None, operation: str = None, **kwargs):
        super().__init__(message, **kwargs)
        if cache_type:
            self.context["cache_type"] = cache_type
        if operation:
            self.context["operation"] = operation


class OptimizationError(DomainException):
    """
    Exception for optimization and performance-related errors.
    
    Used when model selection, query analysis, or optimization operations fail.
    """
    
    def __init__(self, message: str, model_name: str = None, complexity_score: int = None, **kwargs):
        super().__init__(message, **kwargs)
        if model_name:
            self.context["model_name"] = model_name
        if complexity_score is not None:
            self.context["complexity_score"] = complexity_score


class ModelError(DomainException):
    """
    Exception for LLM model-related errors.
    
    Used when model configuration, loading, or inference fails.
    """
    
    def __init__(self, message: str, model_name: str = None, model_type: str = None, **kwargs):
        super().__init__(message, **kwargs)
        if model_name:
            self.context["model_name"] = model_name
        if model_type:
            self.context["model_type"] = model_type


# Convenience exception classes for common HTTP status codes
class BadRequestError(ValidationError):
    """400 Bad Request - Client error in request format or content"""
    pass


class UnauthorizedError(DomainException):
    """401 Unauthorized - Authentication required"""
    pass


class ForbiddenError(DomainException):
    """403 Forbidden - Access denied"""
    pass


class NotFoundError(DomainException):
    """404 Not Found - Requested resource doesn't exist"""
    
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None, **kwargs):
        super().__init__(message, **kwargs)
        if resource_type:
            self.context["resource_type"] = resource_type
        if resource_id:
            self.context["resource_id"] = resource_id


class ConflictError(DomainException):
    """409 Conflict - Request conflicts with current resource state"""
    pass


class TooManyRequestsError(DomainException):
    """429 Too Many Requests - Rate limit exceeded"""
    
    def __init__(self, message: str, retry_after: int = None, **kwargs):
        super().__init__(message, **kwargs)
        if retry_after:
            self.context["retry_after_seconds"] = retry_after