"""
Annotation Domain - Vignette Data Models

Data models for vignette collections, annotations, and metadata management.
"""
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path

from web_app.domains.annotation.models.screenshot_models import ScreenshotMetadata


@dataclass
class AnnotationData:
    """Individual annotation within a vignette"""
    id: str
    type: str  # "text", "arrow", "highlight", "shape"
    content: str
    position: Dict[str, float]  # x, y coordinates
    style: Dict[str, Any] = field(default_factory=dict)
    screenshot_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "position": self.position,
            "style": self.style,
            "screenshot_id": self.screenshot_id,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnnotationData':
        """Create annotation from dictionary"""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()
        
        return cls(
            id=data["id"],
            type=data["type"],
            content=data["content"],
            position=data["position"],
            style=data.get("style", {}),
            screenshot_id=data.get("screenshot_id"),
            created_at=created_at
        )


@dataclass
class VignetteScreenshot:
    """Screenshot reference within a vignette"""
    id: str
    filename: str
    original_path: str
    vignette_path: str
    web_path: str
    size_bytes: int = 0
    timestamp: str = ""
    copied_successfully: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "filename": self.filename,
            "original_path": self.original_path,
            "vignette_path": self.vignette_path,
            "web_path": self.web_path,
            "size": self.size_bytes,
            "timestamp": self.timestamp,
            "copied_successfully": self.copied_successfully
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VignetteScreenshot':
        """Create vignette screenshot from dictionary"""
        return cls(
            id=data["id"],
            filename=data["filename"],
            original_path=data["original_path"],
            vignette_path=data["vignette_path"],
            web_path=data.get("web_path", data.get("original_path", "")),
            size_bytes=data.get("size", 0),
            timestamp=data.get("timestamp", ""),
            copied_successfully=data.get("copied_successfully", True)
        )


@dataclass
class VignetteMetadata:
    """Complete vignette metadata and content"""
    name: str
    safe_name: str
    screenshots: List[VignetteScreenshot] = field(default_factory=list)
    annotations: Dict[str, AnnotationData] = field(default_factory=dict)
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    screenshot_count: int = 0
    annotation_count: int = 0
    directory: Optional[str] = None
    
    def __post_init__(self):
        """Initialize computed fields"""
        if self.created is None:
            self.created = datetime.now()
        if self.modified is None:
            self.modified = datetime.now()
        
        # Update counts
        self.screenshot_count = len(self.screenshots)
        self.annotation_count = len(self.annotations)
    
    def add_screenshot(self, screenshot: VignetteScreenshot):
        """Add screenshot to vignette"""
        self.screenshots.append(screenshot)
        self.screenshot_count = len(self.screenshots)
        self.modified = datetime.now()
    
    def add_annotation(self, annotation: AnnotationData):
        """Add annotation to vignette"""
        self.annotations[annotation.id] = annotation
        self.annotation_count = len(self.annotations)
        self.modified = datetime.now()
    
    def remove_screenshot(self, screenshot_id: str) -> bool:
        """Remove screenshot from vignette"""
        initial_count = len(self.screenshots)
        self.screenshots = [s for s in self.screenshots if s.id != screenshot_id]
        
        if len(self.screenshots) < initial_count:
            self.screenshot_count = len(self.screenshots)
            self.modified = datetime.now()
            return True
        return False
    
    def remove_annotation(self, annotation_id: str) -> bool:
        """Remove annotation from vignette"""
        if annotation_id in self.annotations:
            del self.annotations[annotation_id]
            self.annotation_count = len(self.annotations)
            self.modified = datetime.now()
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "safe_name": self.safe_name,
            "screenshots": [screenshot.to_dict() for screenshot in self.screenshots],
            "annotations": {aid: ann.to_dict() for aid, ann in self.annotations.items()},
            "created": self.created.isoformat() if self.created else None,
            "modified": self.modified.isoformat() if self.modified else None,
            "screenshot_count": self.screenshot_count,
            "annotation_count": self.annotation_count,
            "directory": self.directory,
            "copied_screenshots": [screenshot.to_dict() for screenshot in self.screenshots]  # Legacy compatibility
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VignetteMetadata':
        """Create vignette metadata from dictionary"""
        # Parse datetime fields
        created = data.get("created")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        
        modified = data.get("modified")
        if isinstance(modified, str):
            modified = datetime.fromisoformat(modified)
        
        # Parse screenshots
        screenshots = []
        for screenshot_data in data.get("screenshots", []):
            screenshots.append(VignetteScreenshot.from_dict(screenshot_data))
        
        # Parse annotations
        annotations = {}
        for ann_id, ann_data in data.get("annotations", {}).items():
            annotations[ann_id] = AnnotationData.from_dict(ann_data)
        
        return cls(
            name=data["name"],
            safe_name=data["safe_name"],
            screenshots=screenshots,
            annotations=annotations,
            created=created,
            modified=modified,
            directory=data.get("directory")
        )


@dataclass
class VignetteIndexEntry:
    """Entry in the vignettes index file"""
    name: str
    safe_name: str
    created: datetime
    modified: datetime
    screenshot_count: int = 0
    annotation_count: int = 0
    directory: str = ""
    has_metadata: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "name": self.name,
            "safe_name": self.safe_name,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "screenshot_count": self.screenshot_count,
            "annotation_count": self.annotation_count,
            "directory": self.directory,
            "has_metadata": self.has_metadata
        }
    
    @classmethod
    def from_metadata(cls, metadata: VignetteMetadata) -> 'VignetteIndexEntry':
        """Create index entry from vignette metadata"""
        return cls(
            name=metadata.name,
            safe_name=metadata.safe_name,
            created=metadata.created or datetime.now(),
            modified=metadata.modified or datetime.now(),
            screenshot_count=metadata.screenshot_count,
            annotation_count=metadata.annotation_count,
            directory=metadata.directory or f"config/vignettes/{metadata.safe_name}",
            has_metadata=True
        )