"""
API v1 - MCP Tool Routes

Direct MCP tool invocation endpoints for frontend compatibility.
This provides a simple HTTP interface to MCP tools while the frontend 
migrates to domain-specific REST endpoints.
"""
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from web_app.api.dependencies.domain_services import get_mcp_client, get_vignette_service, get_screenshot_service

router = APIRouter(tags=["mcp"])


class MCPToolRequest(BaseModel):
    """Request model for MCP tool invocation"""
    tool: str
    parameters: Dict[str, Any] = {}


class MCPToolResponse(BaseModel):
    """Response model for MCP tool invocation"""
    success: bool
    data: Dict[str, Any] = None
    error: str = None


@router.post("/api/mcp-tool", response_model=MCPToolResponse)
async def call_mcp_tool(
    request: MCPToolRequest,
    mcp_client = Depends(get_mcp_client)
):
    """
    Direct MCP tool invocation endpoint.
    
    Provides backward compatibility with the existing frontend that expects
    a simple /api/mcp-tool endpoint for calling MCP tools.
    
    Args:
        request: MCP tool name and parameters
        mcp_client: MCP client service
        
    Returns:
        MCP tool result with success/error status
    """
    try:
        # Call the MCP tool
        result = await mcp_client.call_tool(request.tool, request.parameters)
        
        # Debug logging
        import logging
        logging.info(f"MCP tool '{request.tool}' returned: {type(result)}")
        
        # Force flattening for screenshot tools - override approach
        if isinstance(result, dict) and request.tool == 'screen_capture_take_screenshot':
            # Extract the screenshot data from the nested structure
            if result.get('success') and 'data' in result:
                inner_data = result['data']
                if isinstance(inner_data, dict) and inner_data.get('success') and 'data' in inner_data:
                    # Double nested - extract the actual screenshot data
                    screenshot_data = inner_data['data']
                    logging.info(f"Screenshot: Flattening nested response, extracted data keys: {list(screenshot_data.keys()) if isinstance(screenshot_data, dict) else 'not dict'}")
                    return MCPToolResponse(
                        success=True,
                        data=screenshot_data
                    )
                else:
                    # Single nested
                    logging.info(f"Screenshot: Single nested response")
                    return MCPToolResponse(
                        success=True,
                        data=inner_data
                    )
        
        # Handle other MCP response formats
        if isinstance(result, dict):
            # General handling for other tools
            if result.get('success'):
                return MCPToolResponse(
                    success=True,
                    data=result.get('data', result)
                )
            else:
                return MCPToolResponse(
                    success=False,
                    error=result.get('error', 'MCP tool call failed')
                )
        elif hasattr(result, 'success'):
            # Object with success attribute
            if result.success:
                return MCPToolResponse(
                    success=True,
                    data=result.data if hasattr(result, 'data') else result.content
                )
            else:
                return MCPToolResponse(
                    success=False,
                    error=result.error if hasattr(result, 'error') else str(result)
                )
        else:
            # Assume success if no explicit format
            return MCPToolResponse(
                success=True,
                data=result if isinstance(result, dict) else {"result": str(result)}
            )
            
    except Exception as e:
        # Log the error for debugging
        import logging
        logging.error(f"MCP tool call failed: {request.tool} - {str(e)}")
        
        return MCPToolResponse(
            success=False,
            error=f"Failed to call MCP tool '{request.tool}': {str(e)}"
        )


@router.get("/api/kiosk-data")
async def get_kiosk_data_legacy(mcp_client = Depends(get_mcp_client)):
    """
    Legacy compatibility endpoint for kiosk data.
    
    Provides backward compatibility for the frontend that expects 
    the kiosk data endpoint at /api/kiosk-data.
    
    Returns:
        Kiosk data with success/error status
    """
    try:
        # Return basic kiosk data for annotation system compatibility
        # This is a simplified response to make the annotation dropdowns work
        kiosk_data = {
            "screens": {
                "claude_code": {
                    "name": "Claude Code",
                    "description": "Claude Code interface",
                    "elements": [
                        {
                            "id": "example_button",
                            "name": "Example Button", 
                            "action": "click",
                            "coordinates": {"x": 100, "y": 100},
                            "size": {"width": 80, "height": 30}
                        }
                    ]
                },
                "browser": {
                    "name": "Web Browser",
                    "description": "Browser window",
                    "elements": [
                        {
                            "id": "address_bar",
                            "name": "Address Bar",
                            "action": "click", 
                            "coordinates": {"x": 400, "y": 50},
                            "size": {"width": 400, "height": 25}
                        }
                    ]
                }
            }
        }
        
        return {
            "success": True,
            "data": kiosk_data
        }
            
    except Exception as e:
        # Log the error for debugging
        import logging
        logging.error(f"Legacy kiosk data call failed: {str(e)}")
        
        return {
            "success": False,
            "error": f"Failed to retrieve kiosk data: {str(e)}"
        }


# Vignette API compatibility routes  
@router.post("/api/vignettes/save")
async def save_vignette_legacy(
    request: Request,
    vignette_service = Depends(get_vignette_service)
):
    """Legacy compatibility endpoint for saving vignettes"""
    try:
        data = await request.json()
        result = await vignette_service.create_vignette(data)
        
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Failed to save vignette")
            }
        
        return result
            
    except Exception as e:
        import logging
        logging.error(f"Legacy vignette save failed: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to save vignette: {str(e)}"
        }


@router.get("/api/vignettes/list")
async def list_vignettes_legacy(
    vignette_service = Depends(get_vignette_service)
):
    """Legacy compatibility endpoint for listing vignettes"""
    try:
        result = await vignette_service.get_vignettes_list()
        return result
            
    except Exception as e:
        import logging
        logging.error(f"Legacy vignette list failed: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to list vignettes: {str(e)}"
        }


@router.get("/api/vignettes/{vignette_name}")
async def get_vignette_legacy(
    vignette_name: str,
    vignette_service = Depends(get_vignette_service)
):
    """Legacy compatibility endpoint for getting vignette data"""
    try:
        result = await vignette_service.get_vignette(vignette_name)
        
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Failed to get vignette")
            }
        
        return result
            
    except Exception as e:
        import logging
        logging.error(f"Legacy vignette get failed: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to get vignette: {str(e)}"
        }


@router.post("/api/vignettes/{vignette_name}/load-to-gallery")
async def load_vignette_to_gallery_legacy(
    vignette_name: str,
    vignette_service = Depends(get_vignette_service)
):
    """Legacy compatibility endpoint for loading vignette to gallery"""
    try:
        result = await vignette_service.load_vignette_to_gallery(vignette_name)
        
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Failed to load vignette to gallery")
            }
        
        return result
            
    except Exception as e:
        import logging
        logging.error(f"Legacy vignette load to gallery failed: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to load vignette to gallery: {str(e)}"
        }


# Screenshot API compatibility routes
@router.get("/api/screenshots")
async def get_screenshots_legacy(
    screenshot_service = Depends(get_screenshot_service)
):
    """Legacy compatibility endpoint for getting screenshots list"""
    try:
        gallery = await screenshot_service.get_gallery_listing("newest_first")
        return gallery.to_dict()
            
    except Exception as e:
        import logging
        logging.error(f"Legacy screenshot list failed: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to get screenshots: {str(e)}"
        }


@router.delete("/api/screenshots/{screenshot_id}")
async def delete_screenshot_legacy(
    screenshot_id: str,
    screenshot_service = Depends(get_screenshot_service)
):
    """Legacy compatibility endpoint for deleting a single screenshot"""
    try:
        result = await screenshot_service.delete_screenshot(screenshot_id)
        
        if not result["success"]:
            status_code = result.get("status_code", 500)
            raise HTTPException(status_code=status_code, detail=result["error"])
        
        return result
            
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Legacy screenshot delete failed: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to delete screenshot: {str(e)}"
        }