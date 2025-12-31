"""
Annotation Domain - Vignette Management Service

Manages vignette creation, persistence, and screenshot collection workflows.
"""
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from web_app.domains.annotation.models.vignette_models import (
    VignetteMetadata, VignetteScreenshot, VignetteIndexEntry, AnnotationData
)
from web_app.infrastructure.monitoring.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class VignetteService:
    """
    Service for vignette creation, management, and persistence.
    
    Responsibilities:
    - Create and manage vignette collections
    - Handle screenshot copying and organization
    - Manage vignette metadata and indexing
    - Provide vignette listing and retrieval functions
    """
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.config_dir = Path("config")
        self.vignettes_dir = self.config_dir / "vignettes"
        self.vignettes_index_file = self.vignettes_dir / "index.json"
        self.source_screenshots_dir = Path("web_app/static/screenshots")
        
        # Ensure directories exist
        self.vignettes_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_vignette(self, vignette_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new vignette with screenshots and metadata.
        
        Args:
            vignette_data: Vignette creation data including name, screenshots, annotations
            
        Returns:
            Creation result with vignette metadata
        """
        start_time = time.time()
        
        try:
            vignette_name = vignette_data.get("name", "").strip()
            if not vignette_name:
                return {
                    "success": False,
                    "error": "Vignette name is required",
                    "status_code": 400
                }
            
            # Sanitize vignette name for filesystem
            safe_name = self._sanitize_filename(vignette_name)
            if not safe_name:
                return {
                    "success": False,
                    "error": "Invalid vignette name",
                    "status_code": 400
                }
            
            # Create vignette directory structure
            vignette_dir = self.vignettes_dir / safe_name
            screenshots_dir = vignette_dir / "screenshots"
            
            vignette_dir.mkdir(exist_ok=True)
            screenshots_dir.mkdir(exist_ok=True)
            
            logger.info(f"Creating vignette directory: {vignette_dir}")
            
            # Copy screenshots to vignette directory
            screenshots_data = vignette_data.get("screenshotData", [])
            copied_screenshots = await self._copy_screenshots(screenshots_data, screenshots_dir, safe_name)
            
            # Create vignette metadata
            vignette_metadata = VignetteMetadata(
                name=vignette_name,
                safe_name=safe_name,
                screenshots=copied_screenshots,
                created=datetime.fromisoformat(vignette_data.get("created", datetime.now().isoformat())),
                modified=datetime.fromisoformat(vignette_data.get("modified", datetime.now().isoformat())),
                directory=f"config/vignettes/{safe_name}"
            )
            
            # Add annotations if provided
            annotations_data = vignette_data.get("annotations", {})
            for ann_id, ann_data in annotations_data.items():
                if isinstance(ann_data, dict):
                    annotation = AnnotationData.from_dict(ann_data)
                    vignette_metadata.add_annotation(annotation)
            
            # Save vignette metadata
            metadata_file = vignette_dir / "vignette.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(vignette_metadata.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved vignette metadata: {metadata_file}")
            
            # Update vignettes index
            await self._update_vignettes_index(vignette_metadata)
            
            processing_time = time.time() - start_time
            
            # Record creation metric
            self.metrics.record_domain_request(
                "annotation", True, processing_time,
                context={
                    "operation": "vignette_create",
                    "vignette_name": safe_name,
                    "screenshot_count": len(copied_screenshots),
                    "annotation_count": vignette_metadata.annotation_count
                }
            )
            
            return {
                "success": True,
                "message": f"Vignette '{vignette_name}' saved successfully",
                "vignette_directory": str(vignette_dir),
                "screenshots_copied": len(copied_screenshots),
                "metadata_file": str(metadata_file)
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error creating vignette: {e}")
            
            # Record error metric
            self.metrics.record_domain_request(
                "annotation", False, processing_time,
                context={"operation": "vignette_create_error", "error": str(e)}
            )
            
            return {
                "success": False,
                "error": f"Failed to create vignette: {str(e)}",
                "status_code": 500
            }
    
    async def get_vignettes_list(self) -> Dict[str, Any]:
        """Get list of all saved vignettes with metadata"""
        start_time = time.time()
        
        try:
            if not self.vignettes_index_file.exists():
                return {"success": True, "vignettes": []}
            
            with open(self.vignettes_index_file, 'r', encoding='utf-8') as f:
                vignettes_index = json.load(f)
            
            vignettes = vignettes_index.get("vignettes", [])
            
            # Enhance each vignette with current metadata
            for vignette in vignettes:
                vignette_dir = Path(vignette["directory"])
                metadata_file = vignette_dir / "vignette.json"
                
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        vignette["has_metadata"] = True
                        vignette["screenshots"] = metadata.get("screenshots", [])
                        vignette["annotations"] = metadata.get("annotations", {})
                    except Exception as e:
                        logger.warning(f"Could not read metadata for vignette {vignette['name']}: {e}")
                        vignette["has_metadata"] = False
                else:
                    vignette["has_metadata"] = False
            
            processing_time = time.time() - start_time
            
            # Record listing metric
            self.metrics.record_domain_request(
                "annotation", True, processing_time,
                context={
                    "operation": "vignettes_list",
                    "vignette_count": len(vignettes)
                }
            )
            
            return {"success": True, "vignettes": vignettes}
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error listing vignettes: {e}")
            
            # Record error metric
            self.metrics.record_domain_request(
                "annotation", False, processing_time,
                context={"operation": "vignettes_list_error", "error": str(e)}
            )
            
            return {"success": False, "error": str(e), "vignettes": []}
    
    async def get_vignette(self, vignette_name: str) -> Dict[str, Any]:
        """Get specific vignette data and metadata"""
        start_time = time.time()
        
        try:
            safe_name = self._sanitize_filename(vignette_name)
            vignette_dir = self.vignettes_dir / safe_name
            metadata_file = vignette_dir / "vignette.json"
            
            if not metadata_file.exists():
                return {
                    "success": False,
                    "error": f"Vignette '{vignette_name}' not found",
                    "status_code": 404
                }
            
            with open(metadata_file, 'r', encoding='utf-8') as f:
                vignette_data = json.load(f)
            
            # Convert screenshot paths to web-accessible URLs
            for screenshot in vignette_data.get("copied_screenshots", []):
                screenshot["web_path"] = screenshot.get("original_path", "")
            
            processing_time = time.time() - start_time
            
            # Record retrieval metric
            self.metrics.record_domain_request(
                "annotation", True, processing_time,
                context={
                    "operation": "vignette_get",
                    "vignette_name": safe_name
                }
            )
            
            return {"success": True, "vignette": vignette_data}
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error getting vignette {vignette_name}: {e}")
            
            # Record error metric
            self.metrics.record_domain_request(
                "annotation", False, processing_time,
                context={"operation": "vignette_get_error", "error": str(e)}
            )
            
            return {
                "success": False,
                "error": f"Failed to get vignette: {str(e)}",
                "status_code": 500
            }
    
    async def load_vignette_to_gallery(self, vignette_name: str) -> Dict[str, Any]:
        """Copy vignette screenshots back to main gallery"""
        start_time = time.time()
        
        try:
            safe_name = self._sanitize_filename(vignette_name)
            vignette_dir = self.vignettes_dir / safe_name
            metadata_file = vignette_dir / "vignette.json"
            
            if not metadata_file.exists():
                return {
                    "success": False,
                    "error": f"Vignette '{vignette_name}' not found",
                    "status_code": 404
                }
            
            # Load vignette metadata
            with open(metadata_file, 'r', encoding='utf-8') as f:
                vignette_data = json.load(f)
            
            # Ensure main screenshots directory exists
            self.source_screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            copied_count = 0
            copied_screenshots = []
            
            # Copy each screenshot from vignette to main gallery
            for screenshot_info in vignette_data.get("copied_screenshots", []):
                screenshot_id = screenshot_info["id"]
                filename = screenshot_info["filename"]
                vignette_path = Path(screenshot_info["vignette_path"])
                main_path = self.source_screenshots_dir / filename
                
                if vignette_path.exists():
                    if not main_path.exists():
                        shutil.copy2(vignette_path, main_path)
                        copied_count += 1
                        logger.info(f"Copied screenshot {filename} to main gallery")
                    else:
                        logger.info(f"Screenshot {filename} already exists in main gallery")
                    
                    copied_screenshots.append({
                        "id": screenshot_id,
                        "filename": filename,
                        "path": f"/static/screenshots/{filename}",
                        "size": main_path.stat().st_size if main_path.exists() else 0,
                        "timestamp": screenshot_info.get("timestamp", "")
                    })
                else:
                    logger.warning(f"Vignette screenshot {vignette_path} not found")
            
            processing_time = time.time() - start_time
            
            # Record loading metric
            self.metrics.record_domain_request(
                "annotation", True, processing_time,
                context={
                    "operation": "vignette_load_to_gallery",
                    "vignette_name": safe_name,
                    "copied_count": copied_count
                }
            )
            
            return {
                "success": True,
                "data": {
                    "vignette_name": vignette_name,
                    "copied_count": copied_count,
                    "total_screenshots": len(vignette_data.get("copied_screenshots", [])),
                    "screenshots": copied_screenshots
                }
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error loading vignette {vignette_name} to gallery: {e}")
            
            # Record error metric
            self.metrics.record_domain_request(
                "annotation", False, processing_time,
                context={"operation": "vignette_load_error", "error": str(e)}
            )
            
            return {
                "success": False,
                "error": f"Failed to load vignette to gallery: {str(e)}",
                "status_code": 500
            }
    
    async def _copy_screenshots(self, screenshots_data: List[Dict[str, Any]], 
                              screenshots_dir: Path, safe_name: str) -> List[VignetteScreenshot]:
        """Copy screenshots from gallery to vignette directory"""
        copied_screenshots = []
        
        for screenshot in screenshots_data:
            source_file = self.source_screenshots_dir / screenshot["filename"]
            dest_file = screenshots_dir / screenshot["filename"]
            
            if source_file.exists():
                shutil.copy2(str(source_file), str(dest_file))
                
                vignette_screenshot = VignetteScreenshot(
                    id=screenshot["id"],
                    filename=screenshot["filename"],
                    original_path=screenshot["path"],
                    vignette_path=f"config/vignettes/{safe_name}/screenshots/{screenshot['filename']}",
                    web_path=screenshot["path"],
                    size_bytes=screenshot.get("size", 0),
                    timestamp=screenshot.get("timestamp", ""),
                    copied_successfully=True
                )
                
                copied_screenshots.append(vignette_screenshot)
                logger.info(f"Copied screenshot: {source_file} -> {dest_file}")
            else:
                logger.warning(f"Screenshot file not found: {source_file}")
        
        return copied_screenshots
    
    async def _update_vignettes_index(self, metadata: VignetteMetadata):
        """Update the vignettes index file with new or updated vignette"""
        if self.vignettes_index_file.exists():
            with open(self.vignettes_index_file, 'r', encoding='utf-8') as f:
                vignettes_index = json.load(f)
        else:
            vignettes_index = {"vignettes": []}
        
        # Create index entry
        index_entry = VignetteIndexEntry.from_metadata(metadata)
        
        # Update or add vignette in index
        existing_index = next(
            (i for i, v in enumerate(vignettes_index["vignettes"]) 
             if v["safe_name"] == metadata.safe_name), 
            None
        )
        
        if existing_index is not None:
            vignettes_index["vignettes"][existing_index] = index_entry.to_dict()
        else:
            vignettes_index["vignettes"].append(index_entry.to_dict())
        
        # Save updated index
        with open(self.vignettes_index_file, 'w', encoding='utf-8') as f:
            json.dump(vignettes_index, f, indent=2, ensure_ascii=False)
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize name for filesystem safety"""
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        return safe_name.replace(' ', '_')