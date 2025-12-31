"""
Annotation Domain - Screenshot Capture Service

Manages screenshot capture via MCP integration and file system operations.
"""
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from web_app.domains.annotation.models.screenshot_models import (
    ScreenshotMetadata, ScreenshotCaptureRequest, ScreenshotCaptureResult, GalleryListing
)
from web_app.infrastructure.mcp.mcp_client import EnhancedMCPClient
from web_app.infrastructure.monitoring.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class ScreenshotService:
    """
    Service for screenshot capture and management.
    
    Responsibilities:
    - Coordinate screenshot capture via MCP services
    - Manage screenshot file operations and metadata
    - Provide gallery listing and management functions
    - Track screenshot capture performance metrics
    """
    
    def __init__(self, mcp_client: EnhancedMCPClient, metrics_collector: MetricsCollector):
        self.mcp_client = mcp_client
        self.metrics = metrics_collector
        self.screenshots_dir = Path("web_app/static/screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance metrics
        self.capture_stats = {
            "total_captures": 0,
            "successful_captures": 0,
            "failed_captures": 0,
            "average_capture_time": 0.0
        }
    
    async def capture_screenshot(self, request: ScreenshotCaptureRequest = None) -> ScreenshotCaptureResult:
        """
        Capture screenshot using MCP screen capture service.
        
        Args:
            request: Screenshot capture request parameters
            
        Returns:
            Screenshot capture result with metadata
        """
        start_time = time.time()
        request = request or ScreenshotCaptureRequest()
        
        try:
            self.capture_stats["total_captures"] += 1
            
            # Call MCP screenshot tool
            logger.info("Initiating screenshot capture via MCP")
            mcp_result = await self.mcp_client.call_tool(
                "screen_capture_take_screenshot", 
                request.to_mcp_params()
            )
            
            processing_time = time.time() - start_time
            
            if not mcp_result.get("success"):
                self.capture_stats["failed_captures"] += 1
                error_msg = mcp_result.get("error", "MCP screenshot capture failed")
                
                # Record failed capture metric
                self.metrics.record_domain_request(
                    "annotation", False, processing_time,
                    context={"operation": "screenshot_capture", "error": error_msg}
                )
                
                return ScreenshotCaptureResult(
                    success=False,
                    error=error_msg,
                    processing_time=processing_time
                )
            
            # Extract screenshot data from MCP result
            mcp_data = mcp_result.get("data", {})
            screenshot_path = mcp_data.get("screenshot_path")
            
            if not screenshot_path:
                self.capture_stats["failed_captures"] += 1
                return ScreenshotCaptureResult(
                    success=False,
                    error="No screenshot path returned from MCP",
                    processing_time=processing_time
                )
            
            # Create screenshot metadata
            screenshot_file = Path(screenshot_path)
            web_path = f"/static/screenshots/{screenshot_file.name}"
            
            screenshot_metadata = ScreenshotMetadata(
                id=screenshot_file.stem,
                filename=screenshot_file.name,
                file_path=str(screenshot_file),
                web_path=web_path,
                timestamp=datetime.now(),
                size_bytes=mcp_data.get("size", 0),
                dimensions={
                    "width": mcp_data.get("width", 0),
                    "height": mcp_data.get("height", 0)
                },
                method=mcp_data.get("method", "mcp_capture")
            )
            
            self.capture_stats["successful_captures"] += 1
            
            # Update average capture time
            total_successful = self.capture_stats["successful_captures"]
            current_avg = self.capture_stats["average_capture_time"]
            self.capture_stats["average_capture_time"] = (
                (current_avg * (total_successful - 1) + processing_time) / total_successful
            )
            
            # Record successful capture metric
            self.metrics.record_domain_request(
                "annotation", True, processing_time,
                context={
                    "operation": "screenshot_capture",
                    "filename": screenshot_metadata.filename,
                    "method": screenshot_metadata.method
                }
            )
            
            logger.info(f"Screenshot captured successfully: {screenshot_metadata.filename}")
            
            return ScreenshotCaptureResult(
                success=True,
                screenshot=screenshot_metadata,
                mcp_data=mcp_data,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.capture_stats["failed_captures"] += 1
            
            logger.error(f"Screenshot capture error: {e}")
            
            # Record error metric
            self.metrics.record_domain_request(
                "annotation", False, processing_time,
                context={"operation": "screenshot_capture_error", "error": str(e)}
            )
            
            return ScreenshotCaptureResult(
                success=False,
                error=str(e),
                processing_time=processing_time
            )
    
    async def get_gallery_listing(self, sort_order: str = "newest_first") -> GalleryListing:
        """
        Get screenshot gallery listing with metadata.
        
        Args:
            sort_order: "newest_first", "oldest_first", or "filename"
            
        Returns:
            Gallery listing with all screenshots
        """
        start_time = time.time()
        
        try:
            if not self.screenshots_dir.exists():
                return GalleryListing()
            
            gallery = GalleryListing()
            
            # Get all PNG files in screenshots directory
            screenshot_files = list(self.screenshots_dir.glob("*.png"))
            
            for file_path in screenshot_files:
                try:
                    web_path = f"/static/screenshots/{file_path.name}"
                    screenshot = ScreenshotMetadata.from_file(file_path, web_path)
                    gallery.add_screenshot(screenshot)
                except Exception as e:
                    logger.warning(f"Failed to process screenshot {file_path}: {e}")
            
            # Sort gallery based on requested order
            if sort_order == "newest_first":
                gallery.sort_by_timestamp(reverse=True)
            elif sort_order == "oldest_first":
                gallery.sort_by_timestamp(reverse=False)
            elif sort_order == "filename":
                gallery.screenshots.sort(key=lambda x: x.filename)
            
            processing_time = time.time() - start_time
            
            # Record gallery listing metric
            self.metrics.record_domain_request(
                "annotation", True, processing_time,
                context={
                    "operation": "gallery_listing",
                    "screenshot_count": gallery.total_count,
                    "sort_order": sort_order
                }
            )
            
            logger.info(f"Gallery listing completed: {gallery.total_count} screenshots")
            return gallery
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Gallery listing error: {e}")
            
            # Record error metric
            self.metrics.record_domain_request(
                "annotation", False, processing_time,
                context={"operation": "gallery_listing_error", "error": str(e)}
            )
            
            return GalleryListing()
    
    async def delete_screenshot(self, screenshot_id: str) -> Dict[str, Any]:
        """
        Delete screenshot from file system.
        
        Args:
            screenshot_id: Screenshot ID or filename to delete
            
        Returns:
            Delete operation result
        """
        start_time = time.time()
        
        try:
            # Handle both filename-based IDs and full filenames
            if screenshot_id.endswith('.png'):
                filename = screenshot_id
            else:
                filename = f"{screenshot_id}.png"
            
            file_path = self.screenshots_dir / filename
            
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"Screenshot not found: {filename}",
                    "status_code": 404
                }
            
            # Delete the file
            file_path.unlink()
            
            processing_time = time.time() - start_time
            
            # Record deletion metric
            self.metrics.record_domain_request(
                "annotation", True, processing_time,
                context={
                    "operation": "screenshot_delete",
                    "filename": filename
                }
            )
            
            logger.info(f"Deleted screenshot: {filename}")
            
            return {
                "success": True,
                "message": f"Screenshot {filename} deleted successfully"
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            logger.error(f"Error deleting screenshot {screenshot_id}: {e}")
            
            # Record error metric
            self.metrics.record_domain_request(
                "annotation", False, processing_time,
                context={"operation": "screenshot_delete_error", "error": str(e)}
            )
            
            return {
                "success": False,
                "error": f"Failed to delete screenshot: {str(e)}",
                "status_code": 500
            }
    
    def get_capture_statistics(self) -> Dict[str, Any]:
        """Get screenshot capture performance statistics"""
        success_rate = 0.0
        if self.capture_stats["total_captures"] > 0:
            success_rate = (
                self.capture_stats["successful_captures"] / 
                self.capture_stats["total_captures"] * 100
            )
        
        return {
            "total_captures": self.capture_stats["total_captures"],
            "successful_captures": self.capture_stats["successful_captures"],
            "failed_captures": self.capture_stats["failed_captures"],
            "success_rate": f"{success_rate:.1f}%",
            "average_capture_time": f"{self.capture_stats['average_capture_time']:.3f}s",
            "gallery_size": len(list(self.screenshots_dir.glob("*.png"))) if self.screenshots_dir.exists() else 0
        }