"""
Annotation Domain - Domain Package

Exports main annotation services and models for domain integration.
"""
from .services.screenshot_service import ScreenshotService
from .services.vignette_service import VignetteService
from .models.screenshot_models import (
    ScreenshotMetadata, ScreenshotCaptureRequest, ScreenshotCaptureResult, GalleryListing
)
from .models.vignette_models import (
    VignetteMetadata, VignetteScreenshot, VignetteIndexEntry, AnnotationData
)

__all__ = [
    "ScreenshotService",
    "VignetteService",
    "ScreenshotMetadata",
    "ScreenshotCaptureRequest", 
    "ScreenshotCaptureResult",
    "GalleryListing",
    "VignetteMetadata",
    "VignetteScreenshot",
    "VignetteIndexEntry",
    "AnnotationData"
]