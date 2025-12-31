"""
API Middleware - Global Error Handler

Centralized error handling for all API endpoints with proper HTTP status codes.
"""
import logging
from typing import Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception) -> Response:
    """
    Global exception handler for all unhandled exceptions.
    
    Args:
        request: FastAPI request object
        exc: Exception that was raised
        
    Returns:
        JSON error response with appropriate status code
    """
    # Log the exception details
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}", 
                 extra={"url": str(request.url), "method": request.method})
    
    # Create error response
    error_response = {
        "success": False,
        "error": "Internal server error",
        "error_type": type(exc).__name__,
        "timestamp": "2024-01-01T00:00:00Z"
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
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_exception_handler)
    
    logger.info("Global exception handlers configured")