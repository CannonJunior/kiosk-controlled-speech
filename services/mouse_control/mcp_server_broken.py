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

# Global instance
mouse_server = MouseControlServer()

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
                    import pynput.mouse
                    self.mouse = pynput.mouse.Controller()
                    self.use_win32 = False
                    self.use_wsl_interop = False
                
        except ImportError as e:
            if self.is_wsl:
                # In WSL, we can fall back to PowerShell interop
                import subprocess
                self.subprocess = subprocess
                self.use_win32 = False
                self.use_wsl_interop = True
            else:
                raise MCPToolError(f"Failed to import mouse control libraries: {e}")
    
    def _is_wsl(self) -> bool:
        """Check if running in WSL environment."""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
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
    
def create_tool_response(success: bool, data: Any = None, error: str = None) -> Dict[str, Any]:
    """Create a standardized tool response"""
    response = {"success": success}
    if data is not None:
        response["data"] = data
    if error is not None:
        response["error"] = error
    return response
    
    async def _click(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Perform mouse click"""
        x = int(arguments["x"] + self.coordinate_offset_x)
        y = int(arguments["y"] + self.coordinate_offset_y)
        button = arguments.get("button", "left")
        click_type = arguments.get("click_type", "single")
        element_id = arguments.get("element_id")
        
        # Validate coordinates
        if not self._validate_coordinates(x, y):
            return create_tool_response(False, error=f"Invalid coordinates: ({x}, {y})")
        
        # Perform click with retry logic
        for attempt in range(self.max_retries):
            try:
                if self.use_win32:
                    await self._win32_click(x, y, button, click_type)
                elif hasattr(self, 'use_wsl_interop') and self.use_wsl_interop:
                    await self._wsl_click(x, y, button, click_type)
                else:
                    await self._pynput_click(x, y, button, click_type)
                
                # Validate click if enabled
                if self.validation_enabled and element_id:
                    validation_result = await self._validate_click(x, y, element_id)
                    if not validation_result:
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        return create_tool_response(False, error="Click validation failed")
                
                return create_tool_response(True, {
                    "x": x,
                    "y": y,
                    "button": button,
                    "click_type": click_type,
                    "element_id": element_id,
                    "timestamp": time.time()
                })
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                raise e
    
    async def _win32_click(self, x: int, y: int, button: str, click_type: str):
        """Perform click using Win32 API"""
        # Move to position
        self.win32api.SetCursorPos((x, y))
        await asyncio.sleep(0.01)
        
        # Map button types
        button_map = {
            "left": (self.win32con.MOUSEEVENTF_LEFTDOWN, self.win32con.MOUSEEVENTF_LEFTUP),
            "right": (self.win32con.MOUSEEVENTF_RIGHTDOWN, self.win32con.MOUSEEVENTF_RIGHTUP),
            "middle": (self.win32con.MOUSEEVENTF_MIDDLEDOWN, self.win32con.MOUSEEVENTF_MIDDLEUP)
        }
        
        if button not in button_map:
            raise MCPToolError(f"Unsupported button: {button}")
        
        down_event, up_event = button_map[button]
        
        # Perform click(s)
        clicks = 2 if click_type == "double" else 1
        for _ in range(clicks):
            self.win32api.mouse_event(down_event, x, y, 0, 0)
            await asyncio.sleep(0.01)
            self.win32api.mouse_event(up_event, x, y, 0, 0)
            if clicks > 1:
                await asyncio.sleep(0.1)
    
    async def _pynput_click(self, x: int, y: int, button: str, click_type: str):
        """Perform click using pynput"""
        import pynput.mouse
        
        # Map button types
        button_map = {
            "left": pynput.mouse.Button.left,
            "right": pynput.mouse.Button.right,
            "middle": pynput.mouse.Button.middle
        }
        
        if button not in button_map:
            raise MCPToolError(f"Unsupported button: {button}")
        
        mouse_button = button_map[button]
        
        # Move to position
        self.mouse.position = (x, y)
        await asyncio.sleep(0.01)
        
        # Perform click(s)
        clicks = 2 if click_type == "double" else 1
        for _ in range(clicks):
            self.mouse.click(mouse_button)
            if clicks > 1:
                await asyncio.sleep(0.1)
    
    async def _wsl_click(self, x: int, y: int, button: str, click_type: str):
        """Perform click using PowerShell from WSL"""
        # PowerShell script to perform mouse click
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Set cursor position
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x}, {y})
Start-Sleep -Milliseconds 10

# Import user32.dll for mouse events
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Win32 {{
    [DllImport("user32.dll", CharSet = CharSet.Auto, CallingConvention = CallingConvention.StdCall)]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint cButtons, uint dwExtraInfo);
    public const int MOUSEEVENTF_LEFTDOWN = 0x02;
    public const int MOUSEEVENTF_LEFTUP = 0x04;
    public const int MOUSEEVENTF_RIGHTDOWN = 0x08;
    public const int MOUSEEVENTF_RIGHTUP = 0x10;
    public const int MOUSEEVENTF_MIDDLEDOWN = 0x20;
    public const int MOUSEEVENTF_MIDDLEUP = 0x40;
}}
"@

"""
        
        # Map button types to PowerShell constants
        button_map = {
            "left": ("MOUSEEVENTF_LEFTDOWN", "MOUSEEVENTF_LEFTUP"),
            "right": ("MOUSEEVENTF_RIGHTDOWN", "MOUSEEVENTF_RIGHTUP"),
            "middle": ("MOUSEEVENTF_MIDDLEDOWN", "MOUSEEVENTF_MIDDLEUP")
        }
        
        if button not in button_map:
            raise MCPToolError(f"Unsupported button: {button}")
        
        down_event, up_event = button_map[button]
        
        # Add click events to script
        clicks = 2 if click_type == "double" else 1
        for i in range(clicks):
            ps_script += f"""
[Win32]::mouse_event([Win32]::{down_event}, {x}, {y}, 0, 0)
Start-Sleep -Milliseconds 10
[Win32]::mouse_event([Win32]::{up_event}, {x}, {y}, 0, 0)
"""
            if i < clicks - 1:  # Add delay between double clicks
                ps_script += "Start-Sleep -Milliseconds 100\n"
        
        try:
            # Execute PowerShell script from WSL
            result = self.subprocess.run([
                'powershell.exe', '-Command', ps_script
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                raise MCPToolError(f"PowerShell mouse click failed: {result.stderr}")
                
        except self.subprocess.TimeoutExpired:
            raise MCPToolError("PowerShell mouse click timed out")
        except Exception as e:
            raise MCPToolError(f"WSL mouse click error: {e}")
    
    async def _wsl_move_to(self, x: int, y: int):
        """Move mouse cursor using PowerShell from WSL"""
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x}, {y})
"""
        try:
            result = self.subprocess.run([
                'powershell.exe', '-Command', ps_script
            ], capture_output=True, text=True, timeout=2)
            
            if result.returncode != 0:
                raise MCPToolError(f"PowerShell mouse move failed: {result.stderr}")
                
        except self.subprocess.TimeoutExpired:
            raise MCPToolError("PowerShell mouse move timed out")
        except Exception as e:
            raise MCPToolError(f"WSL mouse move error: {e}")
    
    async def _move_to(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Move mouse to specified coordinates"""
        x = int(arguments["x"] + self.coordinate_offset_x)
        y = int(arguments["y"] + self.coordinate_offset_y)
        duration = arguments.get("duration", 0)
        
        if not self._validate_coordinates(x, y):
            return create_tool_response(False, error=f"Invalid coordinates: ({x}, {y})")
        
        try:
            if duration > 0:
                # Smooth movement
                current_x, current_y = await self._get_current_position()
                steps = max(int(duration * 60), 1)  # 60 FPS
                
                for i in range(steps + 1):
                    t = i / steps
                    move_x = int(current_x + (x - current_x) * t)
                    move_y = int(current_y + (y - current_y) * t)
                    
                    if self.use_win32:
                        self.win32api.SetCursorPos((move_x, move_y))
                    elif hasattr(self, 'use_wsl_interop') and self.use_wsl_interop:
                        await self._wsl_move_to(move_x, move_y)
                    else:
                        self.mouse.position = (move_x, move_y)
                    
                    await asyncio.sleep(duration / steps)
            else:
                # Instant movement
                if self.use_win32:
                    self.win32api.SetCursorPos((x, y))
                elif hasattr(self, 'use_wsl_interop') and self.use_wsl_interop:
                    await self._wsl_move_to(x, y)
                else:
                    self.mouse.position = (x, y)
            
            return create_tool_response(True, {"x": x, "y": y, "duration": duration})
            
        except Exception as e:
            return create_tool_response(False, error=f"Move failed: {e}")
    
    async def _get_position(self) -> Dict[str, Any]:
        """Get current mouse position"""
        try:
            x, y = await self._get_current_position()
            return create_tool_response(True, {"x": x, "y": y})
        except Exception as e:
            return create_tool_response(False, error=f"Failed to get position: {e}")
    
    async def _get_current_position(self) -> tuple:
        """Get current mouse position"""
        if self.use_win32:
            return self.win32api.GetCursorPos()
        elif hasattr(self, 'use_wsl_interop') and self.use_wsl_interop:
            return await self._wsl_get_position()
        else:
            return self.mouse.position
    
    async def _wsl_get_position(self) -> tuple:
        """Get current mouse position using PowerShell from WSL"""
        ps_script = """
Add-Type -AssemblyName System.Windows.Forms
$pos = [System.Windows.Forms.Cursor]::Position
Write-Output "$($pos.X),$($pos.Y)"
"""
        try:
            result = self.subprocess.run([
                'powershell.exe', '-Command', ps_script
            ], capture_output=True, text=True, timeout=2)
            
            if result.returncode != 0:
                raise MCPToolError(f"PowerShell get position failed: {result.stderr}")
            
            # Parse coordinates
            coords = result.stdout.strip().split(',')
            return (int(coords[0]), int(coords[1]))
                
        except self.subprocess.TimeoutExpired:
            raise MCPToolError("PowerShell get position timed out")
        except Exception as e:
            raise MCPToolError(f"WSL get position error: {e}")
    
    async def _drag(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Perform drag operation"""
        start_x = int(arguments["start_x"] + self.coordinate_offset_x)
        start_y = int(arguments["start_y"] + self.coordinate_offset_y)
        end_x = int(arguments["end_x"] + self.coordinate_offset_x)
        end_y = int(arguments["end_y"] + self.coordinate_offset_y)
        button = arguments.get("button", "left")
        duration = arguments.get("duration", 1.0)
        
        try:
            # Move to start position
            await self._move_to({"x": start_x, "y": start_y})
            
            # Press button down
            if self.use_win32:
                button_down_map = {
                    "left": self.win32con.MOUSEEVENTF_LEFTDOWN,
                    "right": self.win32con.MOUSEEVENTF_RIGHTDOWN,
                    "middle": self.win32con.MOUSEEVENTF_MIDDLEDOWN
                }
                self.win32api.mouse_event(button_down_map[button], start_x, start_y, 0, 0)
            else:
                import pynput.mouse
                button_map = {
                    "left": pynput.mouse.Button.left,
                    "right": pynput.mouse.Button.right,
                    "middle": pynput.mouse.Button.middle
                }
                self.mouse.press(button_map[button])
            
            # Move to end position
            await self._move_to({"x": end_x, "y": end_y, "duration": duration})
            
            # Release button
            if self.use_win32:
                button_up_map = {
                    "left": self.win32con.MOUSEEVENTF_LEFTUP,
                    "right": self.win32con.MOUSEEVENTF_RIGHTUP,
                    "middle": self.win32con.MOUSEEVENTF_MIDDLEUP
                }
                self.win32api.mouse_event(button_up_map[button], end_x, end_y, 0, 0)
            else:
                self.mouse.release(button_map[button])
            
            return create_tool_response(True, {
                "start_x": start_x, "start_y": start_y,
                "end_x": end_x, "end_y": end_y,
                "button": button, "duration": duration
            })
            
        except Exception as e:
            return create_tool_response(False, error=f"Drag failed: {e}")
    
    async def _scroll(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Perform scroll operation"""
        x = int(arguments["x"] + self.coordinate_offset_x)
        y = int(arguments["y"] + self.coordinate_offset_y)
        direction = arguments["direction"]
        clicks = arguments.get("clicks", 3)
        
        try:
            # Move to position
            await self._move_to({"x": x, "y": y})
            
            if self.use_win32:
                wheel_delta = 120 * clicks
                if direction == "down":
                    wheel_delta = -wheel_delta
                elif direction in ["left", "right"]:
                    # Horizontal scrolling
                    wheel_delta = wheel_delta if direction == "right" else -wheel_delta
                    self.win32api.mouse_event(self.win32con.MOUSEEVENTF_HWHEEL, x, y, wheel_delta, 0)
                else:
                    self.win32api.mouse_event(self.win32con.MOUSEEVENTF_WHEEL, x, y, wheel_delta, 0)
            else:
                scroll_value = clicks if direction in ["up", "right"] else -clicks
                if direction in ["up", "down"]:
                    self.mouse.scroll(0, scroll_value)
                else:
                    self.mouse.scroll(scroll_value, 0)
            
            return create_tool_response(True, {
                "x": x, "y": y, "direction": direction, "clicks": clicks
            })
            
        except Exception as e:
            return create_tool_response(False, error=f"Scroll failed: {e}")
    
    async def _configure(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Configure mouse control settings"""
        for key, value in arguments.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        return create_tool_response(True, {
            "validation_enabled": self.validation_enabled,
            "coordinate_offset_x": self.coordinate_offset_x,
            "coordinate_offset_y": self.coordinate_offset_y,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay
        })
    
    def _validate_coordinates(self, x: int, y: int) -> bool:
        """Validate coordinates are within screen bounds"""
        # Basic validation - can be enhanced with actual screen size detection
        return 0 <= x <= 3840 and 0 <= y <= 2160  # Support up to 4K resolution
    
    async def _validate_click(self, x: int, y: int, element_id: str) -> bool:
        """Validate that click was successful (placeholder)"""
        # This would integrate with screen detection service
        # For now, always return True
        return True


if __name__ == "__main__":
    mcp.run()