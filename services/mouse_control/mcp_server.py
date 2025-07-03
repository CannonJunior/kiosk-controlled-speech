#!/usr/bin/env python3
import asyncio
import sys
import time
from typing import Any, Dict, List, Optional
import platform

from mcp.types import Tool
from src.mcp.base_server import BaseMCPServer, MCPToolError, create_tool_response


class MouseControlServer(BaseMCPServer):
    def __init__(self):
        super().__init__("mouse_control", "Control Windows mouse input from WSL")
        
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
                # WSL or Linux - use pynput with Windows interop
                import pynput.mouse
                self.mouse = pynput.mouse.Controller()
                self.use_win32 = False
                
        except ImportError as e:
            raise MCPToolError(f"Failed to import mouse control libraries: {e}")
    
    async def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="click",
                description="Perform mouse click at specified coordinates",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "number",
                            "description": "X coordinate for click"
                        },
                        "y": {
                            "type": "number", 
                            "description": "Y coordinate for click"
                        },
                        "button": {
                            "type": "string",
                            "enum": ["left", "right", "middle"],
                            "default": "left",
                            "description": "Mouse button to click"
                        },
                        "click_type": {
                            "type": "string",
                            "enum": ["single", "double"],
                            "default": "single",
                            "description": "Type of click"
                        },
                        "element_id": {
                            "type": "string",
                            "description": "Optional element ID for validation"
                        }
                    },
                    "required": ["x", "y"]
                }
            ),
            Tool(
                name="move_to",
                description="Move mouse to specified coordinates",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "number", "description": "X coordinate"},
                        "y": {"type": "number", "description": "Y coordinate"},
                        "duration": {
                            "type": "number",
                            "default": 0,
                            "description": "Movement duration in seconds"
                        }
                    },
                    "required": ["x", "y"]
                }
            ),
            Tool(
                name="get_position",
                description="Get current mouse cursor position",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="drag",
                description="Drag from one position to another",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "start_x": {"type": "number"},
                        "start_y": {"type": "number"},
                        "end_x": {"type": "number"},
                        "end_y": {"type": "number"},
                        "button": {
                            "type": "string",
                            "enum": ["left", "right", "middle"],
                            "default": "left"
                        },
                        "duration": {
                            "type": "number",
                            "default": 1.0,
                            "description": "Drag duration in seconds"
                        }
                    },
                    "required": ["start_x", "start_y", "end_x", "end_y"]
                }
            ),
            Tool(
                name="scroll",
                description="Scroll at specified position",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "number", "description": "X coordinate"},
                        "y": {"type": "number", "description": "Y coordinate"},
                        "direction": {
                            "type": "string",
                            "enum": ["up", "down", "left", "right"],
                            "description": "Scroll direction"
                        },
                        "clicks": {
                            "type": "number",
                            "default": 3,
                            "description": "Number of scroll clicks"
                        }
                    },
                    "required": ["x", "y", "direction"]
                }
            ),
            Tool(
                name="configure",
                description="Configure mouse control settings",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "validation_enabled": {"type": "boolean"},
                        "coordinate_offset_x": {"type": "number"},
                        "coordinate_offset_y": {"type": "number"},
                        "max_retries": {"type": "number"},
                        "retry_delay": {"type": "number"}
                    }
                }
            )
        ]
    
    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        try:
            if name == "click":
                return await self._click(arguments)
            elif name == "move_to":
                return await self._move_to(arguments)
            elif name == "get_position":
                return await self._get_position()
            elif name == "drag":
                return await self._drag(arguments)
            elif name == "scroll":
                return await self._scroll(arguments)
            elif name == "configure":
                return await self._configure(arguments)
            else:
                raise MCPToolError(f"Unknown tool: {name}")
                
        except Exception as e:
            return create_tool_response(False, error=str(e))
    
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
                    else:
                        self.mouse.position = (move_x, move_y)
                    
                    await asyncio.sleep(duration / steps)
            else:
                # Instant movement
                if self.use_win32:
                    self.win32api.SetCursorPos((x, y))
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
        else:
            return self.mouse.position
    
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


async def main():
    """Main function to run the mouse control MCP server"""
    server = MouseControlServer()
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())