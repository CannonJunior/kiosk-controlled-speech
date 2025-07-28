#!/usr/bin/env python3
import asyncio
import json
from typing import Any, Dict, List, Optional
import httpx
from dataclasses import dataclass

from fastmcp import FastMCP
from mcp.types import Tool
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.mcp.base_server import MCPToolError, create_tool_response

mcp = FastMCP("Ollama Agent Server")


@dataclass
class OllamaConfig:
    host: str = "localhost"
    port: int = 11434
    model: str = "qwen2.5:1.5b"
    timeout: int = 30
    temperature: float = 0.1
    max_tokens: int = 512


class OllamaAgentServer:
    def __init__(self, config: OllamaConfig = None):
        
        self.config = config or OllamaConfig()
        self.base_url = f"http://{self.config.host}:{self.config.port}"
        self.client = httpx.AsyncClient(timeout=self.config.timeout)
        
        # System prompt for kiosk voice commands
        self.system_prompt = """You are a voice assistant for a Kiosk demonstration system. Your role is to convert natural language voice commands into specific mouse actions based on the current screen state and available elements.

You have access to:
- Current screen screenshot analysis
- List of clickable elements with coordinates and IDs
- Element names and voice command mappings
- Screen transition rules

CRITICAL INSTRUCTIONS:
1. ALWAYS respond with a valid JSON object containing an "action" field
2. Available actions: "click", "navigate", "help", "error", "clarify"
3. For click actions, ALWAYS include "element_id" and "coordinates" if available
4. Be precise and direct - users expect immediate responses
5. If unclear, ask for clarification but suggest the most likely option

Response format:
{
  "action": "click|navigate|help|error|clarify",
  "element_id": "string (required for click)",
  "coordinates": {"x": number, "y": number},
  "screen_transition": "target_screen_id",
  "confidence": 0.0-1.0,
  "message": "Brief explanation for user",
  "alternatives": ["alternative interpretations if any"]
}

Examples:
- "click start" → {"action": "click", "element_id": "start_button", "coordinates": {"x": 400, "y": 300}, "confidence": 0.95, "message": "Clicking Start button"}
- "go back" → {"action": "click", "element_id": "back_button", "coordinates": {"x": 50, "y": 50}, "confidence": 0.9, "message": "Going back"}
- "what can I do" → {"action": "help", "message": "Available commands: start, menu, back, help"}"""
    
    async def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="process_voice_command",
                description="Process natural language voice command and return action",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "voice_text": {
                            "type": "string",
                            "description": "Transcribed voice command text"
                        },
                        "current_screen": {
                            "type": "object",
                            "description": "Current screen data with available elements"
                        },
                        "context": {
                            "type": "object",
                            "description": "Additional context (previous actions, screen history, etc.)",
                            "properties": {
                                "previous_screen": {"type": "string"},
                                "last_action": {"type": "string"},
                                "session_history": {"type": "array"}
                            }
                        }
                    },
                    "required": ["voice_text", "current_screen"]
                }
            ),
            Tool(
                name="generate_help_response",
                description="Generate contextual help based on current screen",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "current_screen": {
                            "type": "object",
                            "description": "Current screen data with available elements"
                        },
                        "user_level": {
                            "type": "string",
                            "enum": ["beginner", "intermediate", "advanced"],
                            "default": "beginner"
                        }
                    },
                    "required": ["current_screen"]
                }
            ),
            Tool(
                name="analyze_intent",
                description="Analyze user intent from voice command",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "voice_text": {
                            "type": "string",
                            "description": "Voice command text"
                        },
                        "available_actions": {
                            "type": "array",
                            "description": "List of available actions on current screen"
                        }
                    },
                    "required": ["voice_text"]
                }
            ),
            Tool(
                name="suggest_alternatives",
                description="Suggest alternative commands when intent is unclear",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "unclear_command": {
                            "type": "string",
                            "description": "The unclear voice command"
                        },
                        "available_elements": {
                            "type": "array",
                            "description": "Available elements on current screen"
                        }
                    },
                    "required": ["unclear_command", "available_elements"]
                }
            ),
            Tool(
                name="validate_action",
                description="Validate if proposed action is possible on current screen",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "proposed_action": {
                            "type": "object",
                            "description": "Proposed action object"
                        },
                        "current_screen": {
                            "type": "object",
                            "description": "Current screen state"
                        }
                    },
                    "required": ["proposed_action", "current_screen"]
                }
            ),
            Tool(
                name="configure_model",
                description="Configure Ollama model parameters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "temperature": {"type": "number"},
                        "max_tokens": {"type": "number"}
                    }
                }
            ),
            Tool(
                name="health_check",
                description="Check Ollama server connectivity and model availability",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    
    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        try:
            if name == "process_voice_command":
                return await self._process_voice_command(arguments)
            elif name == "generate_help_response":
                return await self._generate_help_response(arguments)
            elif name == "analyze_intent":
                return await self._analyze_intent(arguments)
            elif name == "suggest_alternatives":
                return await self._suggest_alternatives(arguments)
            elif name == "validate_action":
                return await self._validate_action(arguments)
            elif name == "configure_model":
                return await self._configure_model(arguments)
            elif name == "health_check":
                return await self._health_check()
            else:
                raise MCPToolError(f"Unknown tool: {name}")
                
        except Exception as e:
            return create_tool_response(False, error=str(e))
    
    async def _process_voice_command(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Process voice command and return structured action"""
        voice_text = arguments["voice_text"]
        current_screen = arguments["current_screen"]
        context = arguments.get("context", {})
        
        # Build context-aware prompt
        prompt = self._build_command_prompt(voice_text, current_screen, context)
        
        try:
            # Call Ollama
            response = await self._call_ollama(prompt)
            
            # Parse response as JSON
            try:
                action_data = json.loads(response)
                
                # Validate response structure
                if not isinstance(action_data, dict) or "action" not in action_data:
                    raise ValueError("Invalid response format")
                
                # Add metadata
                action_data["original_text"] = voice_text
                action_data["processing_time"] = "< 1s"  # Placeholder
                
                return create_tool_response(True, action_data)
                
            except json.JSONDecodeError:
                # Fallback parsing if response isn't valid JSON
                return await self._fallback_command_parsing(voice_text, current_screen)
                
        except Exception as e:
            return create_tool_response(False, error=f"Failed to process command: {e}")
    
    def _build_command_prompt(self, voice_text: str, current_screen: Dict[str, Any], 
                            context: Dict[str, Any]) -> str:
        """Build context-aware prompt for command processing"""
        # Extract screen information
        screen_name = current_screen.get("name", "Unknown Screen")
        elements = current_screen.get("elements", [])
        
        # Build elements list
        elements_text = ""
        for element in elements:
            elem_id = element.get("id", "")
            elem_name = element.get("name", "")
            coords = element.get("coordinates", {})
            voice_cmds = element.get("voice_commands", [])
            
            elements_text += f"- {elem_name} (ID: {elem_id})\n"
            elements_text += f"  Coordinates: ({coords.get('x', 0)}, {coords.get('y', 0)})\n"
            elements_text += f"  Voice commands: {', '.join(voice_cmds)}\n"
        
        # Build context
        context_text = ""
        if context.get("previous_screen"):
            context_text += f"Previous screen: {context['previous_screen']}\n"
        if context.get("last_action"):
            context_text += f"Last action: {context['last_action']}\n"
        
        prompt = f"""Current Screen: {screen_name}

Available Elements:
{elements_text}

Context:
{context_text}

User Voice Command: "{voice_text}"

Convert this voice command to a specific action. Respond with ONLY a valid JSON object following the required format."""

        return prompt
    
    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API with the given prompt"""
        try:
            # Prepare request
            request_data = {
                "model": self.config.model,
                "prompt": f"{self.system_prompt}\n\n{prompt}",
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens
                }
            }
            
            # Make API call
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=request_data
            )
            
            if response.status_code != 200:
                raise httpx.HTTPError(f"Ollama API error: {response.status_code}")
            
            result = response.json()
            return result.get("response", "").strip()
            
        except httpx.TimeoutException:
            raise Exception("Ollama request timed out")
        except httpx.HTTPError as e:
            raise Exception(f"Ollama API error: {e}")
        except Exception as e:
            raise Exception(f"Failed to call Ollama: {e}")
    
    async def _fallback_command_parsing(self, voice_text: str, 
                                      current_screen: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback command parsing when Ollama fails"""
        voice_lower = voice_text.lower()
        elements = current_screen.get("elements", [])
        
        # Simple keyword matching
        for element in elements:
            voice_commands = element.get("voice_commands", [])
            for cmd in voice_commands:
                if cmd.lower() in voice_lower or voice_lower in cmd.lower():
                    action_data = {
                        "action": "click",
                        "element_id": element["id"],
                        "coordinates": element.get("coordinates", {}),
                        "confidence": 0.7,
                        "message": f"Matched '{cmd}' (fallback parsing)",
                        "fallback": True
                    }
                    return create_tool_response(True, action_data)
        
        # Global commands
        if any(word in voice_lower for word in ["help", "commands", "what can"]):
            action_data = {
                "action": "help",
                "confidence": 0.8,
                "message": "Showing available commands",
                "fallback": True
            }
            return create_tool_response(True, action_data)
        
        # Default: request clarification
        action_data = {
            "action": "clarify",
            "confidence": 0.3,
            "message": f"I didn't understand '{voice_text}'. Please try again.",
            "fallback": True
        }
        return create_tool_response(True, action_data)
    
    async def _generate_help_response(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Generate contextual help"""
        current_screen = arguments["current_screen"]
        user_level = arguments.get("user_level", "beginner")
        
        elements = current_screen.get("elements", [])
        
        help_text = f"Available commands on {current_screen.get('name', 'this screen')}:\n"
        
        for element in elements:
            name = element.get("name", "Unknown")
            voice_commands = element.get("voice_commands", [])
            if voice_commands:
                help_text += f"• Say '{voice_commands[0]}' to use {name}\n"
        
        help_text += "\nGlobal commands:\n• Say 'help' for this message\n• Say 'go back' to return"
        
        return create_tool_response(True, {
            "help_text": help_text,
            "user_level": user_level,
            "total_options": len(elements)
        })
    
    async def _analyze_intent(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user intent"""
        voice_text = arguments["voice_text"]
        available_actions = arguments.get("available_actions", [])
        
        voice_lower = voice_text.lower()
        
        # Intent classification
        intent = "unknown"
        confidence = 0.0
        
        if any(word in voice_lower for word in ["click", "press", "tap", "select"]):
            intent = "click"
            confidence = 0.8
        elif any(word in voice_lower for word in ["go", "navigate", "open"]):
            intent = "navigate"
            confidence = 0.8
        elif any(word in voice_lower for word in ["help", "commands", "what"]):
            intent = "help"
            confidence = 0.9
        elif any(word in voice_lower for word in ["back", "return", "previous"]):
            intent = "back"
            confidence = 0.9
        
        return create_tool_response(True, {
            "intent": intent,
            "confidence": confidence,
            "original_text": voice_text,
            "available_actions": available_actions
        })
    
    async def _suggest_alternatives(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest alternatives for unclear commands"""
        unclear_command = arguments["unclear_command"]
        available_elements = arguments["available_elements"]
        
        suggestions = []
        
        # Extract keywords from unclear command
        words = unclear_command.lower().split()
        
        for element in available_elements:
            element_name = element.get("name", "").lower()
            voice_commands = element.get("voice_commands", [])
            
            # Check for partial matches
            for word in words:
                if word in element_name or any(word in cmd.lower() for cmd in voice_commands):
                    if voice_commands:
                        suggestions.append(f"Did you mean '{voice_commands[0]}'?")
                    break
        
        # Add generic suggestions
        if not suggestions:
            suggestions = [
                "Try saying 'help' to see available commands",
                "Be more specific about what you want to do",
                "Say the name of the button you want to click"
            ]
        
        return create_tool_response(True, {
            "original_command": unclear_command,
            "suggestions": suggestions[:3],  # Limit to 3 suggestions
            "total_elements": len(available_elements)
        })
    
    async def _validate_action(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validate proposed action"""
        proposed_action = arguments["proposed_action"]
        current_screen = arguments["current_screen"]
        
        action_type = proposed_action.get("action")
        element_id = proposed_action.get("element_id")
        
        validation_result = {
            "is_valid": False,
            "reason": "Unknown",
            "action": proposed_action
        }
        
        if action_type == "click" and element_id:
            # Check if element exists
            elements = current_screen.get("elements", [])
            element_exists = any(elem.get("id") == element_id for elem in elements)
            
            if element_exists:
                validation_result["is_valid"] = True
                validation_result["reason"] = "Element found and clickable"
            else:
                validation_result["reason"] = f"Element {element_id} not found on current screen"
        
        elif action_type in ["help", "clarify"]:
            validation_result["is_valid"] = True
            validation_result["reason"] = "Global action, always valid"
        
        else:
            validation_result["reason"] = f"Unknown action type: {action_type}"
        
        return create_tool_response(True, validation_result)
    
    async def _configure_model(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Configure model parameters"""
        updates = {}
        
        if "model" in arguments:
            self.config.model = arguments["model"]
            updates["model"] = arguments["model"]
        
        if "temperature" in arguments:
            self.config.temperature = float(arguments["temperature"])
            updates["temperature"] = arguments["temperature"]
        
        if "max_tokens" in arguments:
            self.config.max_tokens = int(arguments["max_tokens"])
            updates["max_tokens"] = arguments["max_tokens"]
        
        return create_tool_response(True, {
            "updated_config": updates,
            "current_config": {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "host": self.config.host,
                "port": self.config.port
            }
        })
    
    async def _health_check(self) -> Dict[str, Any]:
        """Check Ollama health"""
        try:
            # Test connection
            response = await self.client.get(f"{self.base_url}/api/tags")
            
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name") for model in models]
                
                # Check if configured model is available
                model_available = self.config.model in model_names
                
                return create_tool_response(True, {
                    "status": "healthy",
                    "available_models": model_names,
                    "configured_model": self.config.model,
                    "model_available": model_available,
                    "url": self.base_url
                })
            else:
                return create_tool_response(False, error=f"Ollama API returned {response.status_code}")
                
        except Exception as e:
            return create_tool_response(False, error=f"Health check failed: {e}")


if __name__ == "__main__":
    mcp.run()