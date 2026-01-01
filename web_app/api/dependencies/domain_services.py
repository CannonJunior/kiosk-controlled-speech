"""
API Layer - Domain Service Dependencies

FastAPI dependency injection for domain services and infrastructure.
"""
from typing import Annotated
from fastapi import Depends

from web_app.domains.speech.services.audio_processor import AudioProcessor
from web_app.domains.speech.services.chat_processor import ChatProcessor
from web_app.domains.speech.services.text_reading_service import TextReadingService
from web_app.domains.communication.services.communication_service import CommunicationService
from web_app.domains.configuration.services.config_service import ConfigurationService
from web_app.domains.configuration.services.optimization_service import OptimizationService
from web_app.domains.configuration.services.cache_service import CacheService
from web_app.domains.annotation.services.screenshot_service import ScreenshotService
from web_app.domains.annotation.services.vignette_service import VignetteService
from web_app.infrastructure.mcp.mcp_client import EnhancedMCPClient
from web_app.infrastructure.monitoring.metrics import metrics_collector


# Infrastructure dependencies
def get_mcp_client() -> EnhancedMCPClient:
    """Get enhanced MCP client instance"""
    # This would be initialized at startup in main.py
    return _mcp_client_instance


def get_metrics_collector():
    """Get metrics collector instance"""
    return metrics_collector


# Domain service dependencies
def get_speech_audio_processor(
    mcp_client: Annotated[EnhancedMCPClient, Depends(get_mcp_client)],
    metrics: Annotated[object, Depends(get_metrics_collector)]
) -> AudioProcessor:
    """Get Speech Domain audio processor"""
    return AudioProcessor(mcp_client, metrics)


def get_speech_chat_processor(
    mcp_client: Annotated[EnhancedMCPClient, Depends(get_mcp_client)]
) -> ChatProcessor:
    """Get Speech Domain chat processor"""
    return ChatProcessor(mcp_client)


def get_speech_text_reading_service(
    mcp_client: Annotated[EnhancedMCPClient, Depends(get_mcp_client)]
) -> TextReadingService:
    """Get Speech Domain text reading service"""
    return TextReadingService(mcp_client)


def get_communication_service(
    metrics: Annotated[object, Depends(get_metrics_collector)]
) -> CommunicationService:
    """Get Communication Domain service"""
    return CommunicationService(metrics)


def get_configuration_service() -> ConfigurationService:
    """Get Configuration Domain service"""
    return ConfigurationService()


def get_optimization_service(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)]
) -> OptimizationService:
    """Get Configuration Domain optimization service"""
    app_config = config_service.load_configuration()
    return OptimizationService(app_config)


def get_cache_service(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)]
) -> CacheService:
    """Get Configuration Domain cache service"""
    app_config = config_service.load_configuration()
    return CacheService(app_config.cache_config)


def get_screenshot_service(
    mcp_client: Annotated[EnhancedMCPClient, Depends(get_mcp_client)],
    metrics: Annotated[object, Depends(get_metrics_collector)]
) -> ScreenshotService:
    """Get Annotation Domain screenshot service"""
    return ScreenshotService(mcp_client, metrics)


def get_vignette_service(
    metrics: Annotated[object, Depends(get_metrics_collector)]
) -> VignetteService:
    """Get Annotation Domain vignette service"""
    return VignetteService(metrics)


# Global instances (initialized at startup)
_mcp_client_instance: EnhancedMCPClient = None


def initialize_dependencies(mcp_client: EnhancedMCPClient):
    """Initialize global dependency instances at application startup"""
    global _mcp_client_instance
    _mcp_client_instance = mcp_client