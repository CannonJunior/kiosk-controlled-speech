"""
Annotation Domain - Screenshot Data Models

Data models for screenshot capture, metadata, and file management.
"""
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScreenshotMetadata:
    """Screenshot metadata and file information"""
    id: str
    filename: str
    file_path: str
    web_path: str
    timestamp: datetime
    size_bytes: int
    dimensions: Optional[Dict[str, int]] = None
    method: str = "mcp_capture"
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "filename": self.filename,
            "path": self.web_path,
            "timestamp": self.timestamp.isoformat(),
            "created": self.created_at.isoformat(),
            "size": self.size_bytes,
            "dimensions": f"{self.dimensions.get('width', 0)}x{self.dimensions.get('height', 0)}" if self.dimensions else "unknown",
            "method": self.method
        }
    
    @classmethod
    def from_file(cls, file_path: Path, web_path: str) -> 'ScreenshotMetadata':
        """Create screenshot metadata from file"""
        stat_info = file_path.stat()
        
        return cls(
            id=file_path.stem,
            filename=file_path.name,
            file_path=str(file_path),
            web_path=web_path,
            timestamp=datetime.fromtimestamp(stat_info.st_mtime),
            size_bytes=stat_info.st_size,
            created_at=datetime.fromtimestamp(stat_info.st_ctime)
        )


@dataclass
class ScreenshotCaptureRequest:
    """Screenshot capture request parameters"""
    capture_method: str = "default"
    include_metadata: bool = True
    save_to_gallery: bool = True
    custom_filename: Optional[str] = None
    
    def to_mcp_params(self) -> Dict[str, Any]:
        """Convert to MCP tool parameters"""
        params = {}
        if self.custom_filename:
            params["filename"] = self.custom_filename
        return params


@dataclass
class ScreenshotCaptureResult:
    """Result from screenshot capture operation"""
    success: bool
    screenshot: Optional[ScreenshotMetadata] = None
    error: Optional[str] = None
    mcp_data: Dict[str, Any] = field(default_factory=dict)
    processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        result = {
            "success": self.success,
            "processing_time": f"{self.processing_time:.2f}s"
        }
        
        if self.screenshot:
            result.update({
                "action_executed": True,
                "action_type": "screenshot",
                "screenshot_path": self.screenshot.file_path,
                "filename": self.screenshot.filename,
                "size": self.screenshot.size_bytes,
                "dimensions": self.screenshot.dimensions,
                "method": self.screenshot.method,
                "message": f"📸 Screenshot captured successfully! File: {self.screenshot.filename}"
            })
        else:
            result.update({
                "action_executed": False,
                "action_type": "screenshot",
                "error": self.error or "Unknown error",
                "message": f"❌ Screenshot failed: {self.error or 'Unknown error'}"
            })
        
        return result


@dataclass 
class GalleryListing:
    """Screenshot gallery listing with metadata"""
    screenshots: List[ScreenshotMetadata] = field(default_factory=list)
    total_count: int = 0
    total_size_bytes: int = 0
    oldest_screenshot: Optional[datetime] = None
    newest_screenshot: Optional[datetime] = None
    
    def add_screenshot(self, screenshot: ScreenshotMetadata):
        """Add screenshot to gallery listing"""
        self.screenshots.append(screenshot)
        self.total_count += 1
        self.total_size_bytes += screenshot.size_bytes
        
        if not self.oldest_screenshot or screenshot.timestamp < self.oldest_screenshot:
            self.oldest_screenshot = screenshot.timestamp
        
        if not self.newest_screenshot or screenshot.timestamp > self.newest_screenshot:
            self.newest_screenshot = screenshot.timestamp
    
    def sort_by_timestamp(self, reverse: bool = False):
        """Sort screenshots by timestamp"""
        self.screenshots.sort(key=lambda x: x.timestamp, reverse=reverse)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "success": True,
            "screenshots": [screenshot.to_dict() for screenshot in self.screenshots],
            "total": self.total_count,
            "total_size_mb": round(self.total_size_bytes / (1024 * 1024), 2),
            "date_range": {
                "oldest": self.oldest_screenshot.isoformat() if self.oldest_screenshot else None,
                "newest": self.newest_screenshot.isoformat() if self.newest_screenshot else None
            }
        }