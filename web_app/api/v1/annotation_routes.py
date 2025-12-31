"""
API v1 - Annotation Domain Routes

REST endpoints for screenshot capture, gallery management, and vignette workflows.
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request

from web_app.api.dependencies.domain_services import get_screenshot_service, get_vignette_service
from web_app.domains.annotation.services.screenshot_service import ScreenshotService
from web_app.domains.annotation.services.vignette_service import VignetteService
from web_app.domains.annotation.models.screenshot_models import ScreenshotCaptureRequest

router = APIRouter(prefix="/api/v1/annotation", tags=["annotation"])


@router.get("/screenshots")
async def get_screenshots(
    sort_order: str = "newest_first",
    screenshot_service: Annotated[ScreenshotService, Depends(get_screenshot_service)] = None
):
    """Get list of screenshots from the gallery with metadata"""
    gallery = await screenshot_service.get_gallery_listing(sort_order)
    return gallery.to_dict()


@router.post("/screenshots/capture")
async def capture_screenshot(
    screenshot_service: Annotated[ScreenshotService, Depends(get_screenshot_service)] = None
):
    """Capture new screenshot via MCP integration"""
    request = ScreenshotCaptureRequest()
    result = await screenshot_service.capture_screenshot(request)
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    
    return result.to_dict()


@router.delete("/screenshots/{screenshot_id}")
async def delete_screenshot(
    screenshot_id: str,
    screenshot_service: Annotated[ScreenshotService, Depends(get_screenshot_service)] = None
):
    """Delete a single screenshot from the file system"""
    result = await screenshot_service.delete_screenshot(screenshot_id)
    
    if not result["success"]:
        status_code = result.get("status_code", 500)
        raise HTTPException(status_code=status_code, detail=result["error"])
    
    return result


@router.get("/screenshots/stats")
async def get_screenshot_stats(
    screenshot_service: Annotated[ScreenshotService, Depends(get_screenshot_service)] = None
):
    """Get screenshot capture performance statistics"""
    return screenshot_service.get_capture_statistics()


@router.post("/vignettes/save")
async def save_vignette(
    request: Request,
    vignette_service: Annotated[VignetteService, Depends(get_vignette_service)] = None
):
    """Save a vignette with screenshots to the config folder"""
    data = await request.json()
    result = await vignette_service.create_vignette(data)
    
    if not result["success"]:
        status_code = result.get("status_code", 500)
        raise HTTPException(status_code=status_code, detail=result["error"])
    
    return result


@router.get("/vignettes/list")
async def list_vignettes(
    vignette_service: Annotated[VignetteService, Depends(get_vignette_service)] = None
):
    """Get list of saved vignettes"""
    return await vignette_service.get_vignettes_list()


@router.get("/vignettes/{vignette_name}")
async def get_vignette(
    vignette_name: str,
    vignette_service: Annotated[VignetteService, Depends(get_vignette_service)] = None
):
    """Get a specific vignette's data"""
    result = await vignette_service.get_vignette(vignette_name)
    
    if not result["success"]:
        status_code = result.get("status_code", 500)
        raise HTTPException(status_code=status_code, detail=result["error"])
    
    return result


@router.post("/vignettes/{vignette_name}/load-to-gallery")
async def load_vignette_to_gallery(
    vignette_name: str,
    vignette_service: Annotated[VignetteService, Depends(get_vignette_service)] = None
):
    """Copy vignette screenshots to main gallery"""
    result = await vignette_service.load_vignette_to_gallery(vignette_name)
    
    if not result["success"]:
        status_code = result.get("status_code", 500)
        raise HTTPException(status_code=status_code, detail=result["error"])
    
    return result