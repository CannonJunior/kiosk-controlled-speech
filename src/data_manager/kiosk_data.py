from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import aiofiles
from enum import Enum


class ElementCondition(Enum):
    ALWAYS_VISIBLE = "always_visible"
    CONDITIONAL = "conditional"
    CONTEXT_DEPENDENT = "context_dependent"


@dataclass
class ElementCoordinates:
    x: int
    y: int


@dataclass
class ElementSize:
    width: int
    height: int


@dataclass
class KioskElement:
    id: str
    name: str
    coordinates: ElementCoordinates
    size: ElementSize
    voice_commands: List[str]
    conditions: List[str]
    action: str = "click"
    next_screen: Optional[str] = None
    element_type: str = "button"
    confidence_threshold: float = 0.8
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KioskElement':
        coords = ElementCoordinates(**data["coordinates"])
        size = ElementSize(**data["size"])
        return cls(
            id=data["id"],
            name=data["name"],
            coordinates=coords,
            size=size,
            voice_commands=data["voice_commands"],
            conditions=data["conditions"],
            action=data.get("action", "click"),
            next_screen=data.get("next_screen"),
            element_type=data.get("element_type", "button"),
            confidence_threshold=data.get("confidence_threshold", 0.8)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "coordinates": asdict(self.coordinates),
            "size": asdict(self.size),
            "voice_commands": self.voice_commands,
            "conditions": self.conditions,
            "action": self.action,
            "next_screen": self.next_screen,
            "element_type": self.element_type,
            "confidence_threshold": self.confidence_threshold
        }


@dataclass
class ScreenDetectionCriteria:
    title_text: Optional[str] = None
    elements: List[str] = None
    unique_features: List[str] = None
    color_signature: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScreenDetectionCriteria':
        return cls(
            title_text=data.get("title_text"),
            elements=data.get("elements", []),
            unique_features=data.get("unique_features", []),
            color_signature=data.get("color_signature")
        )


@dataclass
class KioskScreen:
    id: str
    name: str
    description: str
    detection_criteria: ScreenDetectionCriteria
    elements: List[KioskElement]
    
    @classmethod
    def from_dict(cls, screen_id: str, data: Dict[str, Any]) -> 'KioskScreen':
        detection = ScreenDetectionCriteria.from_dict(data.get("detection_criteria", {}))
        elements = [KioskElement.from_dict(elem) for elem in data.get("elements", [])]
        
        return cls(
            id=screen_id,
            name=data["name"],
            description=data["description"],
            detection_criteria=detection,
            elements=elements
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "detection_criteria": asdict(self.detection_criteria),
            "elements": [elem.to_dict() for elem in self.elements]
        }
    
    def get_element_by_id(self, element_id: str) -> Optional[KioskElement]:
        """Get element by ID"""
        for element in self.elements:
            if element.id == element_id:
                return element
        return None
    
    def get_elements_by_voice_command(self, command: str) -> List[KioskElement]:
        """Get elements that match a voice command"""
        matching_elements = []
        command_lower = command.lower()
        
        for element in self.elements:
            for voice_cmd in element.voice_commands:
                if voice_cmd.lower() in command_lower or command_lower in voice_cmd.lower():
                    matching_elements.append(element)
                    break
        
        return matching_elements


@dataclass
class GlobalCommand:
    voice_commands: List[str]
    action: str
    description: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GlobalCommand':
        return cls(
            voice_commands=data["voice_commands"],
            action=data["action"],
            description=data["description"]
        )


@dataclass
class KioskSettings:
    voice_confidence_threshold: float = 0.8
    screen_detection_confidence: float = 0.85
    click_validation_enabled: bool = True
    fallback_mode: str = "manual_selection"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KioskSettings':
        return cls(
            voice_confidence_threshold=data.get("voice_confidence_threshold", 0.8),
            screen_detection_confidence=data.get("screen_detection_confidence", 0.85),
            click_validation_enabled=data.get("click_validation_enabled", True),
            fallback_mode=data.get("fallback_mode", "manual_selection")
        )


class KioskDataManager:
    def __init__(self, data_file_path: str):
        self.data_file_path = Path(data_file_path)
        self.version = "1.0"
        self.screens: Dict[str, KioskScreen] = {}
        self.global_commands: Dict[str, GlobalCommand] = {}
        self.settings = KioskSettings()
        self._loaded = False
    
    async def load_data(self) -> bool:
        """Load kiosk data from JSON file"""
        try:
            if not self.data_file_path.exists():
                await self._create_default_data()
                return True
            
            async with aiofiles.open(self.data_file_path, 'r') as f:
                data = json.loads(await f.read())
            
            self.version = data.get("version", "1.0")
            
            # Load screens
            for screen_id, screen_data in data.get("screens", {}).items():
                self.screens[screen_id] = KioskScreen.from_dict(screen_id, screen_data)
            
            # Load global commands
            for cmd_id, cmd_data in data.get("global_commands", {}).items():
                self.global_commands[cmd_id] = GlobalCommand.from_dict(cmd_data)
            
            # Load settings
            if "settings" in data:
                self.settings = KioskSettings.from_dict(data["settings"])
            
            self._loaded = True
            return True
            
        except Exception as e:
            print(f"Failed to load kiosk data: {e}")
            return False
    
    async def save_data(self) -> bool:
        """Save kiosk data to JSON file"""
        try:
            data = {
                "version": self.version,
                "screens": {
                    screen_id: screen.to_dict() 
                    for screen_id, screen in self.screens.items()
                },
                "global_commands": {
                    cmd_id: asdict(cmd) 
                    for cmd_id, cmd in self.global_commands.items()
                },
                "settings": asdict(self.settings)
            }
            
            # Ensure directory exists
            self.data_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(self.data_file_path, 'w') as f:
                await f.write(json.dumps(data, indent=2))
            
            return True
            
        except Exception as e:
            print(f"Failed to save kiosk data: {e}")
            return False
    
    async def _create_default_data(self):
        """Create default kiosk data structure"""
        # Create default screens and elements as defined in config
        home_screen = KioskScreen(
            id="home",
            name="Home Screen",
            description="Main kiosk home screen",
            detection_criteria=ScreenDetectionCriteria(
                title_text="Welcome",
                elements=["start_button", "menu_button"]
            ),
            elements=[
                KioskElement(
                    id="start_button",
                    name="Start Button",
                    coordinates=ElementCoordinates(400, 300),
                    size=ElementSize(200, 60),
                    voice_commands=["start", "begin", "get started"],
                    conditions=["always_visible"],
                    action="click",
                    next_screen="main_menu"
                )
            ]
        )
        
        self.screens["home"] = home_screen
        
        # Add global commands
        self.global_commands["help"] = GlobalCommand(
            voice_commands=["help", "what can I do", "commands"],
            action="show_help",
            description="Show available voice commands"
        )
        
        await self.save_data()
    
    def get_screen(self, screen_id: str) -> Optional[KioskScreen]:
        """Get screen by ID"""
        return self.screens.get(screen_id)
    
    def get_all_screens(self) -> Dict[str, KioskScreen]:
        """Get all screens"""
        return self.screens.copy()
    
    def add_screen(self, screen: KioskScreen) -> bool:
        """Add or update a screen"""
        try:
            self.screens[screen.id] = screen
            return True
        except Exception:
            return False
    
    def remove_screen(self, screen_id: str) -> bool:
        """Remove a screen"""
        if screen_id in self.screens:
            del self.screens[screen_id]
            return True
        return False
    
    def find_elements_by_voice_command(self, command: str, current_screen_id: str = None) -> List[tuple]:
        """Find elements across all screens that match a voice command"""
        results = []
        
        # Check current screen first if specified
        if current_screen_id and current_screen_id in self.screens:
            screen = self.screens[current_screen_id]
            elements = screen.get_elements_by_voice_command(command)
            for element in elements:
                results.append((screen.id, element))
        
        # Check other screens
        for screen_id, screen in self.screens.items():
            if screen_id == current_screen_id:
                continue
            elements = screen.get_elements_by_voice_command(command)
            for element in elements:
                results.append((screen_id, element))
        
        return results
    
    def find_global_command(self, command: str) -> Optional[GlobalCommand]:
        """Find global command that matches voice input"""
        command_lower = command.lower()
        
        for cmd in self.global_commands.values():
            for voice_cmd in cmd.voice_commands:
                if voice_cmd.lower() in command_lower or command_lower in voice_cmd.lower():
                    return cmd
        
        return None
    
    def get_screen_detection_criteria(self) -> Dict[str, ScreenDetectionCriteria]:
        """Get detection criteria for all screens"""
        return {
            screen_id: screen.detection_criteria 
            for screen_id, screen in self.screens.items()
        }
    
    def update_element_coordinates(self, screen_id: str, element_id: str, 
                                 x: int, y: int) -> bool:
        """Update element coordinates"""
        screen = self.get_screen(screen_id)
        if not screen:
            return False
        
        element = screen.get_element_by_id(element_id)
        if not element:
            return False
        
        element.coordinates.x = x
        element.coordinates.y = y
        return True
    
    def add_voice_command_to_element(self, screen_id: str, element_id: str, 
                                   voice_command: str) -> bool:
        """Add voice command to an element"""
        screen = self.get_screen(screen_id)
        if not screen:
            return False
        
        element = screen.get_element_by_id(element_id)
        if not element:
            return False
        
        if voice_command not in element.voice_commands:
            element.voice_commands.append(voice_command)
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get data statistics"""
        total_elements = sum(len(screen.elements) for screen in self.screens.values())
        total_voice_commands = sum(
            len(element.voice_commands) 
            for screen in self.screens.values() 
            for element in screen.elements
        )
        
        return {
            "total_screens": len(self.screens),
            "total_elements": total_elements,
            "total_voice_commands": total_voice_commands,
            "global_commands": len(self.global_commands),
            "version": self.version,
            "loaded": self._loaded
        }