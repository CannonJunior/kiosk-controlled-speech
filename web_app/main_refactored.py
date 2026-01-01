#!/usr/bin/env python3
"""
FastAPI Web Application - Minimal Entry Point

Clean, focused FastAPI application with all business logic extracted to services
and routes. Contains only app setup, middleware configuration, and route registration.
Target: 150 lines maximum.
"""
import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add parent directory to path for MCP imports
sys.path.append('..')

from web_app.path_resolver import path_resolver
from web_app.api.dependencies.domain_services import initialize_dependencies
from web_app.infrastructure.mcp.mcp_client import EnhancedMCPClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    # Create FastAPI app
    app = FastAPI(
        title="Kiosk Speech Web Interface",
        description="Modular web-based chat interface with speech-to-text capabilities",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register API routes
    register_routes(app)
    
    # Configure static file serving
    configure_static_files(app)
    
    # Setup application lifecycle events
    setup_lifecycle_events(app)
    
    logger.info("FastAPI application created and configured")
    return app

def register_routes(app: FastAPI):
    """
    Register all API route modules.
    
    Args:
        app: FastAPI application instance
    """
    from web_app.api.v1.core_routes import router as core_router
    from web_app.api.v1.speech_routes import router as speech_router
    from web_app.api.v1.configuration_routes import router as config_router
    from web_app.api.v1.annotation_routes import router as annotation_router
    from web_app.api.v1.websocket_routes import router as websocket_router
    from web_app.api.v1.health_routes import router as health_router
    
    # Core application routes (root, health, performance)
    app.include_router(core_router)
    
    # Domain-specific API routes
    app.include_router(speech_router)
    app.include_router(config_router)
    app.include_router(annotation_router)
    app.include_router(websocket_router)
    app.include_router(health_router)
    
    logger.info("All API routes registered")

def configure_static_files(app: FastAPI):
    """
    Configure static file serving for web assets.
    
    Args:
        app: FastAPI application instance
    """
    # Static web files (HTML, CSS, JS)
    app.mount("/static", StaticFiles(directory="web_app/static"), name="static")
    
    # Configuration files
    if Path("config").exists():
        app.mount("/config", StaticFiles(directory="config"), name="config")
    
    # Temporary audio files for TTS
    temp_audio_dir = path_resolver.temp_dir / "kiosk_tts"
    temp_audio_dir.mkdir(exist_ok=True)
    app.mount("/temp_audio", StaticFiles(directory=str(temp_audio_dir)), name="temp_audio")
    
    logger.info("Static file serving configured")

def setup_lifecycle_events(app: FastAPI):
    """
    Setup application startup and shutdown events.
    
    Args:
        app: FastAPI application instance
    """
    @app.on_event("startup")
    async def startup_event():
        """Initialize application on startup"""
        logger.info("🚀 Kiosk Speech Interface starting up...")
        
        try:
            # Initialize MCP client and dependencies
            mcp_client = EnhancedMCPClient()
            await mcp_client.initialize()
            
            # Initialize domain services and dependencies
            initialize_dependencies(mcp_client)
            logger.info("✅ Dependencies initialized successfully")
            
            # Log startup completion
            logger.info("🎉 Application startup complete - ready to serve requests")
            
        except Exception as e:
            logger.error(f"❌ Startup failed: {e}")
            raise
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Clean up resources on shutdown"""
        logger.info("🛑 Kiosk Speech Interface shutting down...")
        
        try:
            # Cleanup domain services if needed
            # (Services should handle their own cleanup)
            logger.info("✅ Clean shutdown completed")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")

# Create the FastAPI application instance
app = create_app()

def main():
    """
    Main entry point for running the application.
    """
    try:
        logger.info("Starting Kiosk Speech Interface server...")
        
        # Run the application
        uvicorn.run(
            "web_app.main_refactored:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info",
            access_log=True
        )
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()