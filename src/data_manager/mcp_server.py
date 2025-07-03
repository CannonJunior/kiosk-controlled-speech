#!/usr/bin/env python3
import asyncio
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from mcp.types import Tool, Resource
from src.mcp.base_server import BaseMCPServer, MCPToolError, create_tool_response
from .kiosk_data import KioskDataManager, KioskScreen, KioskElement


class KioskDataMCPServer(BaseMCPServer):
    def __init__(self, data_file_path: str = "config/kiosk_data.json"):
        super().__init__("kiosk_data_manager", "Manage kiosk screen and element data")
        self.data_manager = KioskDataManager(data_file_path)
        self.data_file_path = Path(data_file_path)
    
    async def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="load_data",
                description="Load kiosk data from file",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="save_data",
                description="Save kiosk data to file",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="get_screen",
                description="Get screen data by ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screen_id": {
                            "type": "string",
                            "description": "Screen identifier"
                        }
                    },
                    "required": ["screen_id"]
                }
            ),
            Tool(
                name="get_all_screens",
                description="Get all screen data",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="find_elements_by_voice",
                description="Find elements that match voice command",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Voice command to search for"
                        },
                        "current_screen": {
                            "type": "string",
                            "description": "Current screen ID for prioritized search"
                        }
                    },
                    "required": ["command"]
                }
            ),
            Tool(
                name="find_global_command",
                description="Find global command that matches voice input",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Voice command to search for"
                        }
                    },
                    "required": ["command"]
                }
            ),
            Tool(
                name="get_screen_detection_criteria",
                description="Get detection criteria for screen identification",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screen_id": {
                            "type": "string",
                            "description": "Specific screen ID (optional)"
                        }
                    }
                }
            ),
            Tool(
                name="update_element_coordinates",
                description="Update element coordinates",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screen_id": {"type": "string"},
                        "element_id": {"type": "string"},
                        "x": {"type": "number"},
                        "y": {"type": "number"}
                    },
                    "required": ["screen_id", "element_id", "x", "y"]
                }
            ),
            Tool(
                name="add_voice_command",
                description="Add voice command to element",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screen_id": {"type": "string"},
                        "element_id": {"type": "string"},
                        "voice_command": {"type": "string"}
                    },
                    "required": ["screen_id", "element_id", "voice_command"]
                }
            ),
            Tool(
                name="add_screen",
                description="Add or update a screen",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screen_data": {
                            "type": "object",
                            "description": "Complete screen data object"
                        }
                    },
                    "required": ["screen_data"]
                }
            ),
            Tool(
                name="remove_screen",
                description="Remove a screen",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screen_id": {
                            "type": "string",
                            "description": "Screen ID to remove"
                        }
                    },
                    "required": ["screen_id"]
                }
            ),
            Tool(
                name="get_statistics",
                description="Get data statistics and summary",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="validate_data",
                description="Validate kiosk data integrity",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    
    async def get_resources(self) -> List[Resource]:
        return [
            Resource(
                uri=f"file://{self.data_file_path.absolute()}",
                name="kiosk_data",
                description="Kiosk screen and element data"
            )
        ]
    
    async def read_resource_content(self, uri: str) -> str:
        """Read kiosk data file content"""
        if self.data_file_path.exists():
            with open(self.data_file_path, 'r') as f:
                return f.read()
        else:
            return json.dumps({
                "version": "1.0",
                "screens": {},
                "global_commands": {},
                "settings": {}
            }, indent=2)
    
    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        try:
            if name == "load_data":
                return await self._load_data()
            elif name == "save_data":
                return await self._save_data()
            elif name == "get_screen":
                return await self._get_screen(arguments)
            elif name == "get_all_screens":
                return await self._get_all_screens()
            elif name == "find_elements_by_voice":
                return await self._find_elements_by_voice(arguments)
            elif name == "find_global_command":
                return await self._find_global_command(arguments)
            elif name == "get_screen_detection_criteria":
                return await self._get_screen_detection_criteria(arguments)
            elif name == "update_element_coordinates":
                return await self._update_element_coordinates(arguments)
            elif name == "add_voice_command":
                return await self._add_voice_command(arguments)
            elif name == "add_screen":
                return await self._add_screen(arguments)
            elif name == "remove_screen":
                return await self._remove_screen(arguments)
            elif name == "get_statistics":
                return await self._get_statistics()
            elif name == "validate_data":
                return await self._validate_data()
            else:
                raise MCPToolError(f"Unknown tool: {name}")
                
        except Exception as e:
            return create_tool_response(False, error=str(e))
    
    async def _load_data(self) -> Dict[str, Any]:
        """Load kiosk data from file"""
        success = await self.data_manager.load_data()
        if success:
            return create_tool_response(True, {
                "message": "Data loaded successfully",
                "statistics": self.data_manager.get_statistics()
            })
        else:
            return create_tool_response(False, error="Failed to load data")
    
    async def _save_data(self) -> Dict[str, Any]:
        """Save kiosk data to file"""
        success = await self.data_manager.save_data()
        if success:
            return create_tool_response(True, {"message": "Data saved successfully"})
        else:
            return create_tool_response(False, error="Failed to save data")
    
    async def _get_screen(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get screen by ID"""
        screen_id = arguments["screen_id"]
        screen = self.data_manager.get_screen(screen_id)
        
        if screen:
            return create_tool_response(True, {
                "screen": screen.to_dict(),
                "screen_id": screen_id
            })
        else:
            return create_tool_response(False, error=f"Screen {screen_id} not found")
    
    async def _get_all_screens(self) -> Dict[str, Any]:
        """Get all screens"""
        screens = self.data_manager.get_all_screens()
        screen_data = {
            screen_id: screen.to_dict() 
            for screen_id, screen in screens.items()
        }
        
        return create_tool_response(True, {
            "screens": screen_data,
            "count": len(screens)
        })
    
    async def _find_elements_by_voice(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Find elements by voice command"""
        command = arguments["command"]
        current_screen = arguments.get("current_screen")
        
        results = self.data_manager.find_elements_by_voice_command(command, current_screen)
        
        element_matches = []
        for screen_id, element in results:
            element_matches.append({
                "screen_id": screen_id,
                "element": element.to_dict(),
                "match_confidence": self._calculate_voice_match_confidence(command, element)
            })
        
        # Sort by confidence (highest first)
        element_matches.sort(key=lambda x: x["match_confidence"], reverse=True)
        
        return create_tool_response(True, {
            "matches": element_matches,
            "count": len(element_matches),
            "command": command
        })
    
    async def _find_global_command(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Find global command"""
        command = arguments["command"]
        global_cmd = self.data_manager.find_global_command(command)
        
        if global_cmd:
            return create_tool_response(True, {
                "command": {
                    "voice_commands": global_cmd.voice_commands,
                    "action": global_cmd.action,
                    "description": global_cmd.description
                }
            })
        else:
            return create_tool_response(False, error=f"No global command found for: {command}")
    
    async def _get_screen_detection_criteria(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get screen detection criteria"""
        screen_id = arguments.get("screen_id")
        
        if screen_id:
            screen = self.data_manager.get_screen(screen_id)
            if screen:
                return create_tool_response(True, {
                    "screen_id": screen_id,
                    "criteria": screen.detection_criteria.__dict__
                })
            else:
                return create_tool_response(False, error=f"Screen {screen_id} not found")
        else:
            criteria = self.data_manager.get_screen_detection_criteria()
            criteria_dict = {
                screen_id: criteria_obj.__dict__ 
                for screen_id, criteria_obj in criteria.items()
            }
            return create_tool_response(True, {"all_criteria": criteria_dict})
    
    async def _update_element_coordinates(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Update element coordinates"""
        screen_id = arguments["screen_id"]
        element_id = arguments["element_id"]
        x = int(arguments["x"])
        y = int(arguments["y"])
        
        success = self.data_manager.update_element_coordinates(screen_id, element_id, x, y)
        
        if success:
            return create_tool_response(True, {
                "screen_id": screen_id,
                "element_id": element_id,
                "new_coordinates": {"x": x, "y": y}
            })
        else:
            return create_tool_response(False, error="Failed to update coordinates")
    
    async def _add_voice_command(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Add voice command to element"""
        screen_id = arguments["screen_id"]
        element_id = arguments["element_id"]
        voice_command = arguments["voice_command"]
        
        success = self.data_manager.add_voice_command_to_element(
            screen_id, element_id, voice_command
        )
        
        if success:
            return create_tool_response(True, {
                "screen_id": screen_id,
                "element_id": element_id,
                "added_command": voice_command
            })
        else:
            return create_tool_response(False, error="Failed to add voice command")
    
    async def _add_screen(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update screen"""
        try:
            screen_data = arguments["screen_data"]
            screen = KioskScreen.from_dict(screen_data["id"], screen_data)
            
            success = self.data_manager.add_screen(screen)
            
            if success:
                return create_tool_response(True, {
                    "screen_id": screen.id,
                    "action": "added"
                })
            else:
                return create_tool_response(False, error="Failed to add screen")
                
        except Exception as e:
            return create_tool_response(False, error=f"Invalid screen data: {e}")
    
    async def _remove_screen(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Remove screen"""
        screen_id = arguments["screen_id"]
        success = self.data_manager.remove_screen(screen_id)
        
        if success:
            return create_tool_response(True, {
                "screen_id": screen_id,
                "action": "removed"
            })
        else:
            return create_tool_response(False, error=f"Screen {screen_id} not found")
    
    async def _get_statistics(self) -> Dict[str, Any]:
        """Get data statistics"""
        stats = self.data_manager.get_statistics()
        return create_tool_response(True, {"statistics": stats})
    
    async def _validate_data(self) -> Dict[str, Any]:
        """Validate data integrity"""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check for orphaned screen references
        all_screens = self.data_manager.get_all_screens()
        for screen_id, screen in all_screens.items():
            for element in screen.elements:
                if element.next_screen and element.next_screen not in all_screens:
                    validation_results["warnings"].append(
                        f"Element {element.id} in screen {screen_id} references non-existent screen: {element.next_screen}"
                    )
        
        # Check for duplicate element IDs within screens
        for screen_id, screen in all_screens.items():
            element_ids = [elem.id for elem in screen.elements]
            if len(element_ids) != len(set(element_ids)):
                validation_results["errors"].append(f"Duplicate element IDs in screen {screen_id}")
                validation_results["valid"] = False
        
        # Check for empty voice commands
        for screen_id, screen in all_screens.items():
            for element in screen.elements:
                if not element.voice_commands:
                    validation_results["warnings"].append(
                        f"Element {element.id} in screen {screen_id} has no voice commands"
                    )
        
        return create_tool_response(True, {"validation": validation_results})
    
    def _calculate_voice_match_confidence(self, command: str, element: KioskElement) -> float:
        """Calculate confidence score for voice command match"""
        command_lower = command.lower()
        best_score = 0.0
        
        for voice_cmd in element.voice_commands:
            voice_cmd_lower = voice_cmd.lower()
            
            # Exact match
            if command_lower == voice_cmd_lower:
                return 1.0
            
            # Substring match
            if command_lower in voice_cmd_lower:
                score = len(command_lower) / len(voice_cmd_lower)
                best_score = max(best_score, score)
            elif voice_cmd_lower in command_lower:
                score = len(voice_cmd_lower) / len(command_lower)
                best_score = max(best_score, score)
        
        return best_score


async def main():
    """Main function to run the kiosk data MCP server"""
    server = KioskDataMCPServer()
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())