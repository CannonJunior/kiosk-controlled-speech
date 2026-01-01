"""
API Middleware - Enhanced Global Error Handler

Centralized error handling for all API endpoints with proper HTTP status codes,
structured logging, and comprehensive error categorization.
"""
import logging
import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import domain-specific exceptions
from web_app.shared.exceptions import (
    DomainException, ConfigurationError, ValidationError, ServiceUnavailableError
)

logger = logging.getLogger(__name__)


def generate_error_id() -> str:
    """Generate unique error ID for tracking"""
    return str(uuid.uuid4())[:8]


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def domain_exception_handler(request: Request, exc: DomainException) -> Response:
    """
    Handler for domain-specific exceptions.
    
    Args:
        request: FastAPI request object
        exc: DomainException that was raised
        
    Returns:
        JSON error response with domain context
    """
    error_id = generate_error_id()
    
    # Map domain exceptions to HTTP status codes
    status_code_map = {
        ConfigurationError: 500,
        ValidationError: 400,
        ServiceUnavailableError: 503,
        CacheError: 500,
        OptimizationError: 500,
        ModelError: 500
    }
    
    status_code = status_code_map.get(type(exc), 500)
    
    # Enhanced logging with structured data
    logger.error(
        f"Domain exception [{error_id}]: {type(exc).__name__}: {exc.message}",
        extra={
            "error_id": error_id,
            "exception_type": type(exc).__name__,
            "error_code": exc.error_code,
            "url": str(request.url),
            "method": request.method,
            "client_ip": get_client_ip(request),
            "context": exc.context,
            "user_agent": request.headers.get("user-agent"),
            "status_code": status_code
        },
        exc_info=exc.cause if exc.cause else None
    )
    
    # Create structured error response
    error_response = {
        "success": False,
        "error": exc.message,
        "error_type": type(exc).__name__,
        "error_code": exc.error_code,
        "error_id": error_id,
        "context": exc.context,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


async def global_exception_handler(request: Request, exc: Exception) -> Response:
    """
    Enhanced global exception handler for all unhandled exceptions.
    
    Args:
        request: FastAPI request object
        exc: Exception that was raised
        
    Returns:
        JSON error response with tracking information
    """
    error_id = generate_error_id()
    
    # Log the exception with full traceback and context
    logger.error(
        f"Unhandled exception [{error_id}]: {type(exc).__name__}: {str(exc)}",
        extra={
            "error_id": error_id,
            "exception_type": type(exc).__name__,
            "url": str(request.url),
            "method": request.method,
            "client_ip": get_client_ip(request),
            "user_agent": request.headers.get("user-agent"),
            "traceback": traceback.format_exc()
        }
    )
    
    # Create error response (don't expose internal details in production)
    error_response = {
        "success": False,
        "error": "An unexpected error occurred. Please contact support if this persists.",
        "error_type": "InternalServerError",
        "error_id": error_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    return JSONResponse(
        status_code=500,
        content=error_response
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """
    Handler for HTTPException (includes FastAPI HTTPException).
    
    Args:
        request: FastAPI request object
        exc: HTTPException that was raised
        
    Returns:
        JSON error response with exception status code
    """
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}",
                   extra={"url": str(request.url), "method": request.method})
    
    error_response = {
        "success": False,
        "error": exc.detail,
        "status_code": exc.status_code,
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> Response:
    """
    Handler for request validation errors.
    
    Args:
        request: FastAPI request object
        exc: RequestValidationError that was raised
        
    Returns:
        JSON error response with validation details
    """
    logger.warning(f"Validation error: {exc.errors()}",
                   extra={"url": str(request.url), "method": request.method})
    
    error_response = {
        "success": False,
        "error": "Request validation failed",
        "validation_errors": exc.errors(),
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    return JSONResponse(
        status_code=422,
        content=error_response
    )


async def starlette_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """
    Handler for Starlette HTTP exceptions.
    
    Args:
        request: FastAPI request object
        exc: StarletteHTTPException that was raised
        
    Returns:
        JSON error response
    """
    logger.warning(f"Starlette HTTP exception: {exc.status_code} - {exc.detail}",
                   extra={"url": str(request.url), "method": request.method})
    
    error_response = {
        "success": False,
        "error": exc.detail or "HTTP error",
        "status_code": exc.status_code,
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )


def create_error_response(
    error_message: str, 
    status_code: int = 500,
    error_type: str = "error",
    additional_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create standardized error response dictionary.
    
    Args:
        error_message: Human-readable error message
        status_code: HTTP status code
        error_type: Type of error for categorization
        additional_data: Additional error context data
        
    Returns:
        Standardized error response dictionary
    """
    response = {
        "success": False,
        "error": error_message,
        "error_type": error_type,
        "status_code": status_code,
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    if additional_data:
        response.update(additional_data)
    
    return response


def setup_exception_handlers(app):
    """
    Set up all exception handlers for the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    # Order matters - more specific handlers first
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)  # Catch-all last
    
    logger.info("Enhanced exception handlers configured with domain-specific handling")