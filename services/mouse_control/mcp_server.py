#!/usr/bin/env python3
import asyncio
import sys
import time
from typing import Any, Dict, List, Optional
import platform

from fastmcp import FastMCP

mcp = FastMCP("Mouse Control Server")

class MouseControlServer:
    def __init__(self):
        # Platform-specific imports and setup
        self.platform = platform.system()
        self._setup_mouse_control()
        
        # Click validation settings
        self.validation_enabled = True
        self.coordinate_offset_x = 0
        self.coordinate_offset_y = 0
        
        # Error recovery
        self.max_retries = 3
        self.retry_delay = 0.1

    def _setup_mouse_control(self):
        """Setup platform-specific mouse control"""
        try:
            if self.platform == "Windows":
                import win32api
                import win32con
                self.win32api = win32api
                self.win32con = win32con
                self.use_win32 = True
            else:
                # Check if we're in WSL environment
                self.is_wsl = self._is_wsl()
                if self.is_wsl:
                    # WSL environment - use PowerShell interop for mouse control
                    import subprocess
                    self.subprocess = subprocess
                    self.use_win32 = False
                    self.use_wsl_interop = True
                else:
                    # Linux with X server - use pynput
                    try:
                        import pynput.mouse
                        self.mouse = pynput.mouse.Controller()
                        self.use_win32 = False
                        self.use_wsl_interop = False
                    except ImportError:
                        # Fallback to mock implementation
                        self.use_win32 = False
                        self.use_wsl_interop = False
                        self.mock_mode = True
                
        except ImportError:
            # Fallback to mock implementation for testing
            self.use_win32 = False
            self.use_wsl_interop = False
            self.mock_mode = True

    def _is_wsl(self) -> bool:
        """Check if running in WSL environment."""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False

    async def _click(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Perform mouse click"""
        x = int(arguments["x"] + self.coordinate_offset_x)
        y = int(arguments["y"] + self.coordinate_offset_y)
        button = arguments.get("button", "left")
        click_type = arguments.get("click_type", "single")
        element_id = arguments.get("element_id")
        
        # Mock implementation for testing
        return {
            "success": True,
            "data": {
                "x": x,
                "y": y,
                "button": button,
                "click_type": click_type,
                "element_id": element_id,
                "timestamp": time.time(),
                "mock": True
            }
        }

    async def _move_to(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Move mouse to specified coordinates"""
        x = int(arguments["x"] + self.coordinate_offset_x)
        y = int(arguments["y"] + self.coordinate_offset_y)
        duration = arguments.get("duration", 0)
        
        return {
            "success": True,
            "data": {"x": x, "y": y, "duration": duration, "mock": True}
        }

    async def _get_position(self) -> Dict[str, Any]:
        """Get current mouse position"""
        return {
            "success": True,
            "data": {"x": 100, "y": 100, "mock": True}
        }

    async def _drag(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Perform drag operation"""
        return {
            "success": True,
            "data": {
                "start_x": arguments["start_x"], 
                "start_y": arguments["start_y"],
                "end_x": arguments["end_x"], 
                "end_y": arguments["end_y"],
                "mock": True
            }
        }

    async def _scroll(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Perform scroll operation"""
        return {
            "success": True,
            "data": {
                "x": arguments["x"], 
                "y": arguments["y"], 
                "direction": arguments["direction"],
                "mock": True
            }
        }

    async def _configure(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Configure mouse control settings"""
        for key, value in arguments.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        return {
            "success": True,
            "data": {
                "validation_enabled": self.validation_enabled,
                "coordinate_offset_x": self.coordinate_offset_x,
                "coordinate_offset_y": self.coordinate_offset_y,
                "max_retries": self.max_retries,
                "retry_delay": self.retry_delay
            }
        }

# Global instance
mouse_server = MouseControlServer()

@mcp.tool()
async def click(x: float, y: float, button: str = "left", click_type: str = "single", element_id: str = None):
    """Perform mouse click at specified coordinates"""
    result = await mouse_server._click({
        "x": x, "y": y, "button": button, 
        "click_type": click_type, "element_id": element_id
    })
    return result["data"] if result.get("success") else {"error": result.get("error")}

@mcp.tool()
async def move_to(x: float, y: float, duration: float = 0):
    """Move mouse to specified coordinates"""
    result = await mouse_server._move_to({"x": x, "y": y, "duration": duration})
    return result["data"] if result.get("success") else {"error": result.get("error")}

@mcp.tool()
async def get_position():
    """Get current mouse cursor position"""
    result = await mouse_server._get_position()
    return result["data"] if result.get("success") else {"error": result.get("error")}

@mcp.tool()
async def drag(start_x: float, start_y: float, end_x: float, end_y: float, button: str = "left", duration: float = 1.0):
    """Drag from one position to another"""
    result = await mouse_server._drag({
        "start_x": start_x, "start_y": start_y, "end_x": end_x, "end_y": end_y,
        "button": button, "duration": duration
    })
    return result["data"] if result.get("success") else {"error": result.get("error")}

@mcp.tool()
async def scroll(x: float, y: float, direction: str, clicks: int = 3):
    """Scroll at specified position"""
    result = await mouse_server._scroll({
        "x": x, "y": y, "direction": direction, "clicks": clicks
    })
    return result["data"] if result.get("success") else {"error": result.get("error")}

@mcp.tool()
async def configure(validation_enabled: bool = None, coordinate_offset_x: float = None, 
                   coordinate_offset_y: float = None, max_retries: int = None, retry_delay: float = None):
    """Configure mouse control settings"""
    args = {k: v for k, v in locals().items() if v is not None}
    result = await mouse_server._configure(args)
    return result["data"] if result.get("success") else {"error": result.get("error")}

if __name__ == "__main__":
    mcp.run()