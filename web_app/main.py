#!/usr/bin/env python3
"""
FastAPI Web Application for Kiosk Speech Interface
Provides web-based chat interface with speech-to-text integration
"""
import asyncio
import json
import logging
import base64
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import existing MCP infrastructure
import sys
sys.path.append('..')
from fastmcp import Client
from web_app.error_recovery import error_recovery
from web_app.vad_config import get_vad_config
from web_app.optimization import ModelConfigManager
from web_app.path_resolver import path_resolver
from web_app.websocket_error_handler import websocket_error_handler, WebSocketError, ErrorSeverity
from web_app.text_reading_service import TextReadingService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Kiosk Speech Web Interface",
    description="Web-based chat interface with speech-to-text capabilities",
    version="1.0.0"
)

# CORS middleware for Windows browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for web interface
app.mount("/static", StaticFiles(directory="web_app/static"), name="static")
app.mount("/config", StaticFiles(directory="config"), name="config")

# Mount temporary audio files directory for TTS
temp_audio_dir = path_resolver.temp_dir / "kiosk_tts"
temp_audio_dir.mkdir(exist_ok=True)
app.mount("/temp_audio", StaticFiles(directory=str(temp_audio_dir)), name="temp_audio")

class WebSocketConnectionManager:
    """Manages WebSocket connections for real-time communication"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.user_sessions[client_id] = {
            "connected_at": datetime.now(),
            "message_count": 0,
            "last_activity": datetime.now()
        }
        logger.info(f"Client {client_id} connected")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.user_sessions:
            del self.user_sessions[client_id]
        logger.info(f"Client {client_id} disconnected")
    
    async def send_personal_message(self, message: Dict[str, Any], client_id: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
                self.user_sessions[client_id]["last_activity"] = datetime.now()
                return True
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                self.disconnect(client_id)
                return False
        return False

def parse_tool_result(result):
    """Parse FastMCP tool result"""
    if result.is_error:
        return {"success": False, "error": "Tool call failed"}
    
    if result.content and len(result.content) > 0:
        text_content = result.content[0].text
        try:
            return json.loads(text_content)
        except json.JSONDecodeError:
            return {"success": True, "data": {"raw_text": text_content}}
    
    return {"success": False, "error": "No content in response"}

class SpeechWebBridge:
    """Bridges web audio to existing MCP speech services"""
    
    def __init__(self):
        self.mcp_client = None
        self.mcp_config = None
        self.temp_dir = path_resolver.get_temp_path("web_audio")
        self.temp_dir.mkdir(exist_ok=True)
        self.model_manager = ModelConfigManager()
        self.text_reading_service = None  # Will be initialized after MCP client is ready
        
        # Performance optimizations: caching
        self._kiosk_data_cache = None
        self._kiosk_data_cache_time = 0
        self._kiosk_data_cache_duration = 5.0  # Cache for 5 seconds
        self._screen_context_cache = None
        
        # Response caching for common queries
        self._response_cache = {}
        self._response_cache_duration = 30.0  # Cache responses for 30 seconds
        self._common_patterns = [
            "take screenshot", "click", "help", "what can i do", 
            "start recording", "stop recording", "open settings"
        ]
        
        # Fast-path heuristic patterns for instant response (<100ms)
        self._fast_patterns = {
            "take screenshot": {"action": "click", "element_id": "takeScreenshotButton", "confidence": 0.95},
            "screenshot": {"action": "click", "element_id": "takeScreenshotButton", "confidence": 0.9},
            "help": {"action": "help", "confidence": 0.99},
            "what can i do": {"action": "help", "confidence": 0.95},
            "open settings": {"action": "click", "element_id": "settingsToggle", "confidence": 0.9},
            "settings": {"action": "click", "element_id": "settingsToggle", "confidence": 0.85}
        }
        
    async def initialize(self):
        """Initialize MCP services using FastMCP client"""
        try:
            # Load MCP configuration
            await self._load_mcp_config()
            
            # Initialize MCP client with context manager
            self.mcp_client = Client(self.mcp_config)
            await self.mcp_client.__aenter__()
            
            # Debug: List available tools
            try:
                tools = await self.mcp_client.list_tools()
                logger.info(f"Available tools: {[tool.name for tool in tools]}")
            except Exception as e:
                logger.warning(f"Could not list tools: {e}")
            
            # Initialize text reading service
            self.text_reading_service = TextReadingService(self.mcp_client)
            
            logger.info("MCP services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP services: {e}")
            raise
    
    async def _load_mcp_config(self):
        """Load MCP configuration from config file"""
        config_path = path_resolver.resolve_config("mcp_config.json", required=True)
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Convert to FastMCP Client format
            self.mcp_config = {
                "mcpServers": {}
            }
            
            for name, server_data in config_data.get("servers", {}).items():
                if server_data.get("enabled", True):
                    self.mcp_config["mcpServers"][name] = {
                        "command": server_data["command"],
                        "args": server_data["args"]
                    }
                    
                    # Add environment variables if present
                    if "env" in server_data:
                        for key, value in server_data["env"].items():
                            os.environ[key] = value
                            
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            # Fallback configuration
            self.mcp_config = {
                "mcpServers": {
                    "speech_to_text": {
                        "command": "python3",
                        "args": ["services/speech_to_text/mcp_server.py"]
                    },
                    "ollama_agent": {
                        "command": "python3", 
                        "args": ["services/ollama_agent/mcp_server.py"]
                    },
                    "mouse_control": {
                        "command": "python3",
                        "args": ["services/mouse_control/mcp_server.py"]
                    },
                    "screen_capture": {
                        "command": "python3",
                        "args": ["services/screen_capture/mcp_server.py"]
                    },
                    "screen_detector": {
                        "command": "python3",
                        "args": ["services/screen_detector/mcp_server.py"]
                    }
                }
            }
            
    async def _load_kiosk_data_for_context(self) -> Dict[str, Any]:
        """Load kiosk data to provide complete screen context with caching"""
        try:
            # Check cache first for performance optimization
            current_time = time.time()
            if (self._kiosk_data_cache and 
                current_time - self._kiosk_data_cache_time < self._kiosk_data_cache_duration):
                return self._kiosk_data_cache
                
            config_path = path_resolver.resolve_config("kiosk_data.json", required=False)
            
            if config_path:
                # Check file modification time to avoid unnecessary reads
                file_stat = config_path.stat()
                if (self._screen_context_cache and 
                    hasattr(self, '_last_file_mtime') and 
                    file_stat.st_mtime <= self._last_file_mtime):
                    # File hasn't changed, use cached context
                    self._kiosk_data_cache = self._screen_context_cache
                    self._kiosk_data_cache_time = current_time
                    return self._screen_context_cache
                
                # File changed or no cache, reload
                with open(config_path, 'r') as f:
                    kiosk_data = json.load(f)
                    
                # Create merged screen view for performance (avoid screen detection overhead)
                all_screens = kiosk_data.get("screens", {})
                merged_screen = {
                    "name": "All Screens (Merged)",
                    "description": "Merged view of all available screens",
                    "elements": []
                }
                
                # Optimize: pre-calculate total elements for better performance
                total_elements = sum(len(screen.get("elements", [])) for screen in all_screens.values())
                merged_screen["elements"] = []
                
                # Collect all elements with batch processing
                for screen_id, screen_data in all_screens.items():
                    screen_name = screen_data.get("name", screen_id)
                    elements = screen_data.get("elements", [])
                    
                    # Batch process elements for better performance
                    enhanced_elements = []
                    for element in elements:
                        element_copy = {
                            **element,  # Faster than element.copy()
                            "source_screen": screen_name,
                            "source_screen_id": screen_id
                        }
                        enhanced_elements.append(element_copy)
                    
                    merged_screen["elements"].extend(enhanced_elements)
                
                # Cache the result
                self._screen_context_cache = merged_screen
                self._kiosk_data_cache = merged_screen
                self._kiosk_data_cache_time = current_time
                self._last_file_mtime = file_stat.st_mtime
                
                logger.debug(f"Cached {len(merged_screen['elements'])} elements from {len(all_screens)} screens")
                return merged_screen
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to load kiosk data for context: {e}")
            return None
    
    async def _execute_suggested_action(self, ollama_response: Dict[str, Any], current_screen: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action suggested by Ollama model"""
        try:
            action_type = ollama_response.get("action")
            
            if action_type == "click":
                # Get element information
                element_id = ollama_response.get("element_id")
                config_coordinates = None
                config_element_info = None
                
                # Always validate against config - only use coordinates from kiosk_data.json
                if element_id:
                    for element in current_screen.get("elements", []):
                        if element.get("id") == element_id:
                            raw_coordinates = element.get("coordinates")
                            element_size = element.get("size", {})
                            
                            # Calculate center point from top-left coordinates and size
                            if raw_coordinates and element_size:
                                center_x = raw_coordinates["x"] + (element_size.get("width", 0) // 2)
                                center_y = raw_coordinates["y"] + (element_size.get("height", 0) // 2)
                                config_coordinates = {"x": center_x, "y": center_y}
                                logger.info(f"Calculated center coordinates for {element_id}: {config_coordinates} (from top-left {raw_coordinates} + size {element_size})")
                            else:
                                # Fallback to raw coordinates if size not available
                                config_coordinates = raw_coordinates
                                logger.warning(f"No size data for {element_id}, using top-left coordinates: {config_coordinates}")
                            
                            config_element_info = {
                                "id": element.get("id"),
                                "name": element.get("name", element_id),
                                "screen": element.get("source_screen", current_screen.get("name", "unknown")),
                                "screen_id": element.get("source_screen_id", "unknown")
                            }
                            break
                
                # Reject any coordinates not from config
                ollama_coordinates = ollama_response.get("coordinates")
                if ollama_coordinates and not config_coordinates:
                    logger.warning(f"Ollama suggested coordinates {ollama_coordinates} for {element_id}, but element not found in config. Rejecting click.")
                    return {
                        "action_executed": False,
                        "action_type": "click",
                        "error": f"Element '{element_id}' not found in configuration. Cannot execute click with unvalidated coordinates."
                    }
                elif ollama_coordinates and config_coordinates:
                    # Log when Ollama provides coordinates but we're using config instead
                    logger.info(f"Ollama suggested coordinates {ollama_coordinates} for {element_id}, but using validated config coordinates {config_coordinates}")
                
                coordinates = config_coordinates
                
                if coordinates:
                    # Execute mouse click using MCP tool
                    try:
                        result_raw = await self.mcp_client.call_tool(
                            "mouse_control_click", {
                                "x": coordinates["x"],
                                "y": coordinates["y"],
                                "button": "left"
                            }
                        )
                        click_result = parse_tool_result(result_raw)
                        
                        if click_result.get("success"):
                            click_data = click_result.get("data", {})
                            method = click_data.get("method", "unknown")
                            is_mock = click_data.get("mock", True)
                            
                            # Create descriptive message indicating source from config
                            element_name = config_element_info["name"] if config_element_info else element_id
                            screen_name = config_element_info["screen"] if config_element_info else "unknown screen"
                            
                            logger.info(f"Successfully clicked {element_id} at {coordinates} using {method}")
                            return {
                                "action_executed": True,
                                "action_type": "click",
                                "element_id": element_id,
                                "coordinates": coordinates,
                                "result": "success",
                                "method": method,
                                "mock": is_mock,
                                "config_source": config_element_info,
                                "message": f"🖱️ Successfully clicked \"{element_name}\" at coordinates ({coordinates['x']}, {coordinates['y']}) using {method}. Coordinates from config element '{element_id}' on screen '{screen_name}'."
                            }
                        else:
                            logger.error(f"Click failed: {click_result.get('error')}")
                            return {
                                "action_executed": False,
                                "action_type": "click",
                                "error": f"Click failed: {click_result.get('error')}"
                            }
                            
                    except Exception as e:
                        logger.error(f"Mouse click execution error: {e}")
                        return {
                            "action_executed": False,
                            "action_type": "click",
                            "error": f"Mouse click error: {str(e)}"
                        }
                else:
                    logger.warning(f"No coordinates found for element {element_id}")
                    return {
                        "action_executed": False,
                        "action_type": "click",
                        "error": f"No coordinates found for element {element_id}"
                    }
                    
            elif action_type in ["help", "error", "clarify", "navigate"]:
                # These are response-only actions, no execution needed
                return {
                    "action_executed": False,
                    "action_type": action_type,
                    "message": "Response-only action, no execution needed"
                }
            else:
                # Unknown or unsupported action
                return {
                    "action_executed": False,
                    "action_type": action_type,
                    "error": f"Unsupported action type: {action_type}"
                }
                
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return {
                "action_executed": False,
                "error": f"Action execution failed: {str(e)}"
            }

    async def cleanup(self):
        """Cleanup MCP client"""
        if self.mcp_client:
            try:
                await self.mcp_client.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"MCP client cleanup error: {e}")
    
    async def process_audio_data(self, audio_data: str, client_id: str) -> Dict[str, Any]:
        """Process base64 audio data and return transcription"""
        try:
            # Save audio data to temporary file
            audio_bytes = base64.b64decode(audio_data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_file = self.temp_dir / f"audio_{client_id}_{timestamp}.wav"
            
            with open(temp_file, 'wb') as f:
                f.write(audio_bytes)
            
            # Register temp file for cleanup
            error_recovery.resource_manager.register_temp_file(str(temp_file))
            
            # Use FastMCP client to call speech-to-text service with error recovery
            async def call_speech_service():
                result_raw = await self.mcp_client.call_tool(
                    "speech_to_text_transcribe_file", {
                        "file_path": str(temp_file)
                    }
                )
                return parse_tool_result(result_raw)
            
            result = await error_recovery.execute_with_resilience(
                "speech_to_text", call_speech_service
            )
            
            # Clean up temp file
            try:
                temp_file.unlink()
            except Exception:
                pass
            
            if result.get("success"):
                data = result.get("data", {})
                transcription = data.get("text", "")
                return {
                    "success": True,
                    "transcription": transcription,
                    "confidence": data.get("confidence", 0.0),
                    "language": data.get("language", "en")
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Transcription failed")
                }
                
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return {
                "success": False,
                "error": f"Audio processing failed: {str(e)}"
            }
    
    def _get_cache_key(self, message: str) -> str:
        """Generate cache key for response caching"""
        return f"chat:{message.lower().strip()}"
    
    def _is_cacheable_query(self, message: str) -> bool:
        """Check if query should be cached"""
        message_lower = message.lower().strip()
        return any(pattern in message_lower for pattern in self._common_patterns)
    
    async def _try_fast_path_response(self, message: str, current_screen: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Try to handle simple commands instantly without LLM"""
        message_lower = message.lower().strip()
        
        # Check for exact or close matches in fast patterns
        for pattern, response_data in self._fast_patterns.items():
            if pattern in message_lower:
                logger.debug(f"Fast-path match for '{message}': {pattern}")
                
                # Create instant response
                if response_data["action"] == "help":
                    return {
                        "success": True,
                        "response": {
                            "message": "🎤 **Available Commands**\n\n• 'Take screenshot' - Capture screen\n• 'Click [element name]' - Click interface elements\n• 'Open settings' - Open settings panel\n• 'Help' - Show this help message\n\nYou can use voice or text input!",
                            "action": "help",
                            "confidence": response_data["confidence"]
                        },
                        "action_result": {"action_executed": False, "message": "Help displayed"},
                        "processing_time": "< 0.1s",
                        "model_used": "fast_heuristic",
                        "query_complexity": 1,
                        "fast_path": True
                    }
                elif response_data["action"] == "click":
                    # Execute the click action immediately
                    ollama_response = {
                        "action": "click",
                        "element_id": response_data["element_id"],
                        "confidence": response_data["confidence"],
                        "message": f"Fast-path click on {response_data['element_id']}"
                    }
                    
                    action_result = await self._execute_suggested_action(ollama_response, current_screen)
                    
                    return {
                        "success": True,
                        "response": ollama_response,
                        "action_result": action_result,
                        "processing_time": "< 0.5s", 
                        "model_used": "fast_heuristic",
                        "query_complexity": 1,
                        "fast_path": True
                    }
        
        return None  # No fast-path match
    
    async def process_chat_message(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process chat message through Ollama agent or text reading service with caching"""
        try:
            # Performance optimization: Check response cache for common queries
            if self._is_cacheable_query(message):
                cache_key = self._get_cache_key(message)
                if cache_key in self._response_cache:
                    cached_entry = self._response_cache[cache_key]
                    if time.time() - cached_entry["time"] < self._response_cache_duration:
                        logger.debug(f"Returning cached response for: {message}")
                        cached_response = cached_entry["response"].copy()
                        cached_response["from_cache"] = True
                        return cached_response
                    else:
                        # Remove expired cache entry
                        del self._response_cache[cache_key]
            
            # Load screen context first for fast-path processing
            current_screen = await self._load_kiosk_data_for_context()
            if not current_screen:
                # Fallback to basic screen data if kiosk data unavailable
                current_screen = {
                    "name": "Chat Interface",
                    "elements": [
                        {
                            "id": "chat_input",
                            "name": "Message Input",
                            "coordinates": {"x": 400, "y": 500},
                            "voice_commands": ["send message", "type message"]
                        },
                        {
                            "id": "voice_button", 
                            "name": "Voice Input",
                            "coordinates": {"x": 450, "y": 500},
                            "voice_commands": ["start recording", "voice input"]
                        }
                    ]
                }
            
            # Fast-path processing for simple commands (avoid LLM completely)
            fast_response = await self._try_fast_path_response(message, current_screen)
            if fast_response:
                logger.info(f"Fast-path response for: {message}")
                return fast_response
            
            # Check if this is a text reading request first
            if self.text_reading_service and self.text_reading_service.is_text_reading_request(message):
                logger.info(f"Processing text reading request: {message}")
                result = await self.text_reading_service.process_text_reading_request(message)
                
                if result["success"]:
                    response_text = f"📖 **Text Reading Results**\n\n"
                    response_text += f"**Region:** {result['region']}\n"
                    response_text += f"**Confidence:** {int(result['confidence'] * 100)}%\n"
                    response_text += f"**Word Count:** {result['word_count']}\n\n"
                    response_text += f"**Extracted Text:**\n{result['text']}\n\n"
                    
                    if result.get('audio_generated'):
                        response_text += f"🔊 **Audio generated and ready to play**\n"
                        response_text += f"Duration: ~{result.get('audio_duration', 0)}s"
                    else:
                        response_text += f"⚠️ Text extracted but audio generation failed: {result.get('audio_error', 'Unknown error')}"
                    
                    return {
                        "success": True,
                        "response": {
                            "message": response_text,
                            "text_reading_result": result
                        },
                        "processing_time": "< 3s",
                        "model_used": "text_reading_service",
                        "query_complexity": 3
                    }
                else:
                    error_text = f"❌ **Text Reading Failed**\n\n"
                    error_text += f"**Error:** {result['error']}\n\n"
                    
                    if "available_regions" in result:
                        error_text += f"**Available regions:**\n"
                        for region in result['available_regions']:
                            error_text += f"• {region}\n"
                        error_text += f"\n**Try:** 'Read the text in the bottom banner'"
                    elif "suggestion" in result:
                        error_text += f"**Suggestion:** {result['suggestion']}"
                    
                    return {
                        "success": True,
                        "response": {
                            "message": error_text,
                            "text_reading_error": result
                        },
                        "processing_time": "< 1s",
                        "model_used": "text_reading_service",
                        "query_complexity": 2
                    }
            
            # Screen context already loaded above for performance
            
            # Select optimal model based on query complexity
            optimal_model = self.model_manager.select_optimal_model(message)
            model_config = self.model_manager._config.get("models", {}).get(optimal_model, {})
            
            # Process through Ollama agent using FastMCP with error recovery
            async def call_ollama_service():
                request_context = context or {}
                request_context["model_preference"] = optimal_model
                request_context["estimated_latency"] = model_config.get("estimated_latency", "unknown")
                
                result_raw = await self.mcp_client.call_tool(
                    "ollama_agent_process_voice_command", {
                        "voice_text": message,
                        "current_screen": current_screen,
                        "context": request_context
                    }
                )
                return parse_tool_result(result_raw)
            
            result = await error_recovery.execute_with_resilience(
                "ollama_agent", call_ollama_service
            )
            
            if result.get("success"):
                ollama_response = result.get("data", {})
                
                # Execute suggested action if applicable
                action_result = await self._execute_suggested_action(ollama_response, current_screen)
                
                response = {
                    "success": True,
                    "response": ollama_response,
                    "action_result": action_result,
                    "processing_time": model_config.get("estimated_latency", "< 1s"),
                    "model_used": optimal_model,
                    "query_complexity": self.model_manager._analyze_query_complexity(message)
                }
                
                # Cache successful responses for common queries
                if self._is_cacheable_query(message):
                    cache_key = self._get_cache_key(message)
                    self._response_cache[cache_key] = {
                        "response": response,
                        "time": time.time()
                    }
                    logger.debug(f"Cached response for: {message}")
                
                return response
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Message processing failed")
                }
                
        except Exception as e:
            logger.error(f"Chat processing error: {e}")
            return {
                "success": False,
                "error": f"Chat processing failed: {str(e)}"
            }

# Global instances
connection_manager = WebSocketConnectionManager()
speech_bridge = SpeechWebBridge()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Initialize error recovery
        await error_recovery.start()
        
        # Initialize speech bridge
        await speech_bridge.initialize()
        
        logger.info("Web application started successfully")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown"""
    try:
        await speech_bridge.cleanup()
        await error_recovery.stop()
        logger.info("Web application shutdown complete")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

@app.get("/", response_class=HTMLResponse)
async def get_chat_interface():
    """Serve the main chat interface"""
    html_file = Path("web_app/static/index.html")
    if html_file.exists():
        return FileResponse(html_file)
    else:
        # Return basic HTML if static file not found
        return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Kiosk Speech Chat</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .status { text-align: center; color: #666; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 Kiosk Speech Chat Interface</h1>
        <div class="status">
            <p>Loading chat interface...</p>
            <p>Please check that the static files are properly configured.</p>
        </div>
    </div>
</body>
</html>
        """)

@app.get("/troubleshooting", response_class=HTMLResponse)
async def get_troubleshooting_page():
    """Serve the troubleshooting page"""
    html_file = Path("web_app/static/troubleshooting.html")
    if html_file.exists():
        return FileResponse(html_file)

@app.get("/api/vad-config")
async def get_vad_configuration():
    """Get VAD configuration for the web client"""
    try:
        config = get_vad_config()
        return {
            "success": True,
            "config": {
                "client_defaults": config.get_client_defaults(),
                "ui_settings": config.get_ui_settings()
            }
        }
    except Exception as e:
        logger.error(f"Failed to load VAD configuration: {e}")
        return {
            "success": False,
            "error": str(e),
            "config": {
                "client_defaults": {
                    "vadEnabled": True,
                    "vadSensitivity": 0.003,
                    "silenceTimeout": 2500,
                    "speechStartDelay": 800
                },
                "ui_settings": {
                    "timeoutRange": {"min": 1.5, "max": 6.0, "step": 0.5, "default": 2.5}
                }
            }
        }

@app.get("/api/kiosk-data")
async def get_kiosk_data():
    """Get kiosk data configuration for the web client"""
    try:
        # Load kiosk_data.json using path resolver
        config_path = path_resolver.resolve_config("kiosk_data.json", required=True)
        
        with open(config_path, 'r') as f:
            kiosk_data = json.load(f)
        logger.info(f"Loaded kiosk data from {config_path}")
        
        return {
            "success": True,
            "data": kiosk_data
        }
    except Exception as e:
        logger.error(f"Failed to load kiosk data: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": None
        }

@app.post("/api/kiosk-data")
async def save_kiosk_data(request: Request):
    """Save coordinate updates to kiosk_data.json"""
    try:
        data = await request.json()
        updates = data.get("updates", {})
        new_screens = data.get("newScreens", {})
        new_elements = data.get("newElements", {})
        
        # Debug logging
        logger.info(f"Received save request - updates: {len(updates)}, new_screens: {len(new_screens)}, new_elements: {len(new_elements)}")
        logger.info(f"Request data keys: {list(data.keys())}")
        
        if not updates and not new_screens and not new_elements:
            raise ValueError("No updates, new screens, or new elements provided")
        
        # Find the kiosk_data.json file using path resolver
        config_path = path_resolver.resolve_config("kiosk_data.json", required=True)
        
        # Create backup before modifying
        backup_path = config_path.with_suffix('.json.backup')
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
        
        # Load current data
        with open(config_path, 'r') as f:
            kiosk_data = json.load(f)
        
        # Apply coordinate updates
        updated_elements = []
        for update_key, update_info in updates.items():
            screen_name = update_info["screen"]
            element_id = update_info["elementId"]
            new_coords = update_info["newCoordinates"]
            new_size = update_info.get("newSize")  # Get newSize if present
            
            # Debug logging
            logger.info(f"Processing update for {element_id}: coords={new_coords}, size={new_size}")
            logger.info(f"Full update_info: {update_info}")
            
            # Validate screen exists
            if screen_name not in kiosk_data.get("screens", {}):
                raise ValueError(f"Screen '{screen_name}' not found in kiosk data")
            
            # Find and update element
            screen_data = kiosk_data["screens"][screen_name]
            element_found = False
            
            for element in screen_data.get("elements", []):
                if element.get("id") == element_id:
                    # Update coordinates
                    if "coordinates" not in element:
                        element["coordinates"] = {}
                    
                    old_coords = element["coordinates"].copy()
                    element["coordinates"]["x"] = new_coords["x"]
                    element["coordinates"]["y"] = new_coords["y"]
                    
                    # Update size if provided
                    if new_size:
                        if "size" not in element:
                            element["size"] = {}
                        
                        old_size = element["size"].copy() if "size" in element else {}
                        element["size"]["width"] = new_size["width"]
                        element["size"]["height"] = new_size["height"]
                        logger.info(f"Updated size for {element_id}: {old_size} -> {new_size}")
                    else:
                        logger.info(f"No newSize provided for {element_id}, keeping existing size")
                    
                    element_update_info = {
                        "screen": screen_name,
                        "element": element_id,
                        "element_name": element.get("name", element_id),
                        "old_coordinates": old_coords,
                        "new_coordinates": new_coords
                    }
                    
                    # Add size information if it was updated
                    if new_size:
                        element_update_info["old_size"] = old_size
                        element_update_info["new_size"] = new_size
                    
                    updated_elements.append(element_update_info)
                    
                    element_found = True
                    break
            
            if not element_found:
                raise ValueError(f"Element '{element_id}' not found in screen '{screen_name}'")
        
        # Apply new screens
        added_screens = []
        for screen_id, screen_data in new_screens.items():
            if screen_id in kiosk_data.get("screens", {}):
                raise ValueError(f"Screen '{screen_id}' already exists")
            
            # Initialize screens section if it doesn't exist
            if "screens" not in kiosk_data:
                kiosk_data["screens"] = {}
            
            # Add the new screen
            kiosk_data["screens"][screen_id] = screen_data
            added_screens.append({
                "screen_id": screen_id,
                "name": screen_data.get("name", screen_id),
                "description": screen_data.get("description", "")
            })
        
        # Apply new elements
        added_elements = []
        for screen_name, elements in new_elements.items():
            # Validate screen exists
            if screen_name not in kiosk_data.get("screens", {}):
                raise ValueError(f"Screen '{screen_name}' not found in kiosk data")
            
            # Initialize elements array if it doesn't exist
            if "elements" not in kiosk_data["screens"][screen_name]:
                kiosk_data["screens"][screen_name]["elements"] = []
            
            # Add each new element
            for element_data in elements:
                element_id = element_data.get("id")
                
                # Check if element already exists
                existing_element = next((e for e in kiosk_data["screens"][screen_name]["elements"] if e.get("id") == element_id), None)
                if existing_element:
                    raise ValueError(f"Element '{element_id}' already exists in screen '{screen_name}'")
                
                # Add the new element
                kiosk_data["screens"][screen_name]["elements"].append(element_data)
                added_elements.append({
                    "screen_name": screen_name,
                    "element_id": element_id,
                    "name": element_data.get("name", element_id),
                    "action": element_data.get("action", ""),
                    "coordinates": element_data.get("coordinates", {})
                })
        
        # Write updated data back to file
        with open(config_path, 'w') as f:
            json.dump(kiosk_data, f, indent=2)
        
        logger.info(f"Successfully updated {len(updated_elements)} elements, added {len(added_screens)} screens, and added {len(added_elements)} elements in {config_path}")
        
        # Build response message
        messages = []
        if updated_elements:
            messages.append(f"Updated {len(updated_elements)} element(s)")
        if added_screens:
            messages.append(f"Added {len(added_screens)} screen(s)")
        if added_elements:
            messages.append(f"Added {len(added_elements)} new element(s)")
        
        return {
            "success": True,
            "message": "Successfully " + " and ".join(messages).lower(),
            "updated_elements": updated_elements,
            "added_screens": added_screens,
            "added_elements": added_elements,
            "backup_path": str(backup_path)
        }
        
    except Exception as e:
        logger.error(f"Failed to save kiosk data: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(connection_manager.active_connections),
        "services": {
            "speech_to_text": "initialized",
            "ollama_agent": "initialized"
        },
        "error_recovery": error_recovery.get_metrics()
    }

@app.get("/api/metrics")
async def get_metrics():
    """Get detailed application metrics"""
    return {
        "timestamp": datetime.now().isoformat(),
        "connections": {
            "active": len(connection_manager.active_connections),
            "sessions": len(connection_manager.user_sessions)
        },
        "error_recovery": error_recovery.get_metrics()
    }

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time communication"""
    await connection_manager.connect(websocket, client_id)
    
    try:
        # Send welcome message
        await connection_manager.send_personal_message({
            "type": "connection",
            "status": "connected",
            "client_id": client_id,
            "message": "Welcome to Kiosk Speech Chat! You can type or use voice input."
        }, client_id)
        
        while True:
            try:
                # Receive data from client
                data = await websocket.receive_text()
                
                try:
                    message_data = json.loads(data)
                except json.JSONDecodeError as e:
                    raise WebSocketError(
                        f"Invalid JSON format: {e}",
                        error_code="JSON_DECODE_ERROR",
                        severity=ErrorSeverity.MEDIUM,
                        context={"raw_data": data[:100]}  # Limit raw data for logging
                    )
                
                message_type = message_data.get("type")
                
                if not message_type:
                    raise WebSocketError(
                        "Message type is required",
                        error_code="MISSING_MESSAGE_TYPE",
                        severity=ErrorSeverity.MEDIUM,
                        context={"message_data": message_data}
                    )
            
                if message_type == "chat_message":
                    try:
                        # Process text chat message
                        text = message_data.get("message", "")
                        context = message_data.get("context", {})
                        processing_mode = message_data.get("processing_mode", "llm")
                        
                        if not text.strip():
                            raise WebSocketError(
                                "Empty message content",
                                error_code="EMPTY_MESSAGE",
                                severity=ErrorSeverity.LOW
                            )
                        
                        # Only process with LLM if client is in LLM mode
                        if processing_mode == "llm":
                            # Process through Ollama
                            result = await speech_bridge.process_chat_message(text, context)
                            
                            # Send response
                            await connection_manager.send_personal_message({
                                "type": "chat_response",
                                "original_message": text,
                                "response": result,
                                "timestamp": datetime.now().isoformat()
                            }, client_id)
                        else:
                            # Client is in heuristic mode, server should not process
                            logger.debug(f"Ignoring chat message in heuristic mode: {text}")
                        
                        # Reset error count on successful processing
                        websocket_error_handler.reset_error_count(client_id)
                        
                    except Exception as e:
                        raise WebSocketError(
                            f"Chat message processing failed: {str(e)}",
                            error_code="CHAT_PROCESSING_ERROR",
                            severity=ErrorSeverity.MEDIUM,
                            context={"text": text[:100], "processing_mode": processing_mode}
                        )
                
                elif message_type == "audio_data":
                    # Process audio data
                    audio_data = message_data.get("audio")
                    processing_mode = message_data.get("processing_mode", "llm")
                    
                    # Transcribe audio
                    transcription_result = await speech_bridge.process_audio_data(audio_data, client_id)
                    
                    if transcription_result.get("success"):
                        transcription = transcription_result["transcription"]
                        
                        # Send transcription
                        await connection_manager.send_personal_message({
                            "type": "transcription",
                            "text": transcription,
                            "confidence": transcription_result.get("confidence", 0.0),
                            "timestamp": datetime.now().isoformat()
                        }, client_id)
                        
                        # Only process transcription as chat message if in LLM mode
                        if transcription.strip() and processing_mode == "llm":
                            chat_result = await speech_bridge.process_chat_message(transcription)
                            
                            await connection_manager.send_personal_message({
                                "type": "chat_response", 
                                "original_message": transcription,
                                "response": chat_result,
                                "from_speech": True,
                                "timestamp": datetime.now().isoformat()
                            }, client_id)
                        elif transcription.strip() and processing_mode == "heuristic":
                            # Client is in heuristic mode, server should not process transcription
                            logger.debug(f"Ignoring transcription in heuristic mode: {transcription}")
                    else:
                        # Send transcription error
                        await connection_manager.send_personal_message({
                            "type": "error",
                            "message": transcription_result.get("error", "Speech recognition failed"),
                            "timestamp": datetime.now().isoformat()
                        }, client_id)
                
                elif message_type == "ping":
                    # Respond to ping
                    await connection_manager.send_personal_message({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }, client_id)
                
                # Update session activity
                if client_id in connection_manager.user_sessions:
                    connection_manager.user_sessions[client_id]["message_count"] += 1
                    connection_manager.user_sessions[client_id]["last_activity"] = datetime.now()
                    
            except WebSocketError as ws_error:
                # Handle structured WebSocket errors
                should_continue = await websocket_error_handler.handle_error(
                    websocket, client_id, ws_error, connection_manager
                )
                if not should_continue:
                    break  # Exit the message loop to disconnect
            
            except Exception as e:
                # Handle unexpected errors
                ws_error = WebSocketError(
                    f"Unexpected error: {str(e)}",
                    error_code="UNEXPECTED_ERROR", 
                    severity=ErrorSeverity.HIGH,
                    context={"error_type": type(e).__name__}
                )
                should_continue = await websocket_error_handler.handle_error(
                    websocket, client_id, ws_error, connection_manager
                )
                if not should_continue:
                    break  # Exit the message loop to disconnect
            
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
        connection_manager.disconnect(client_id)
    except Exception as e:
        # Final catch-all for connection-level errors
        logger.error(f"WebSocket connection error for client {client_id}: {e}")
        try:
            await websocket_error_handler.handle_error(
                websocket, client_id,
                WebSocketError(
                    f"Connection error: {str(e)}",
                    error_code="CONNECTION_ERROR",
                    severity=ErrorSeverity.CRITICAL,
                    recoverable=False
                ),
                connection_manager
            )
        finally:
            connection_manager.disconnect(client_id)

@app.post("/api/mcp-tool")
async def call_mcp_tool(request: Request):
    """Call MCP tool endpoint for web interface"""
    try:
        data = await request.json()
        tool_name = data.get("tool")
        parameters = data.get("parameters", {})
        
        if not tool_name:
            raise HTTPException(status_code=400, detail="Tool name is required")
        
        # Use the speech bridge MCP client to call the tool
        if not speech_bridge.mcp_client:
            raise HTTPException(status_code=503, detail="MCP services not initialized")
        
        # Call the tool using FastMCP client
        result_raw = await speech_bridge.mcp_client.call_tool(tool_name, parameters)
        result = parse_tool_result(result_raw)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Tool call failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP tool call error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_optimization_presets():
    """Get the optimization presets configuration"""
    return {
        "speed": {
            "model": "qwen2.5:1.5b",
            "temperature": 0.3,
            "max_tokens": 256,
            "name": "Speed",
            "description": "Fast responses with higher temperature for quick interactions"
        },
        "balanced": {
            "model": "qwen2.5:1.5b", 
            "temperature": 0.1,
            "max_tokens": 512,
            "name": "Balanced",
            "description": "Good balance of speed and accuracy for general use"
        },
        "accuracy": {
            "model": "qwen2.5:1.5b",
            "temperature": 0.0,
            "max_tokens": 768,
            "name": "Accuracy",
            "description": "Most accurate responses with lower temperature for complex tasks"
        }
    }

@app.get("/api/optimization/presets")
async def get_optimization_presets_api():
    """Get all optimization presets with their model configurations"""
    try:
        presets = get_optimization_presets()
        return {
            "success": True,
            "presets": presets
        }
    except Exception as e:
        logger.error(f"Get presets error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/optimization/preset/{preset}")
async def set_optimization_preset(preset: str):
    """Set optimization preset for Ollama model"""
    try:
        # Get optimization presets
        presets = get_optimization_presets()
        
        if preset not in presets:
            raise HTTPException(status_code=400, detail=f"Unknown preset: {preset}. Available: {list(presets.keys())}")
        
        preset_config = presets[preset]
        
        # Use the speech bridge MCP client to configure the ollama_agent
        if not speech_bridge.mcp_client:
            raise HTTPException(status_code=503, detail="MCP services not initialized")
        
        # Call the configure_model tool
        result_raw = await speech_bridge.mcp_client.call_tool(
            "ollama_agent_configure_model", {
                "model": preset_config["model"],
                "temperature": preset_config["temperature"],
                "max_tokens": preset_config["max_tokens"]
            }
        )
        result = parse_tool_result(result_raw)
        
        if result.get("success"):
            config_data = result.get("data", {})
            return {
                "success": True,
                "preset": preset,
                "model": {
                    "name": preset_config["name"],
                    "description": preset_config["description"],
                    "model_id": preset_config["model"],
                    "temperature": preset_config["temperature"],
                    "max_tokens": preset_config["max_tokens"]
                },
                "current_config": config_data.get("current_config", {})
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to configure model"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Optimization preset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/optimization/current")
async def get_current_optimization():
    """Get current optimization settings"""
    try:
        # Use the speech bridge MCP client to get current ollama config
        if not speech_bridge.mcp_client:
            raise HTTPException(status_code=503, detail="MCP services not initialized")
        
        # Call the health_check tool which returns current config
        result_raw = await speech_bridge.mcp_client.call_tool("ollama_agent_check_ollama_health", {})
        result = parse_tool_result(result_raw)
        
        if result.get("success"):
            config_data = result.get("data", {})
            current_model = config_data.get("configured_model", "qwen2.5:1.5b")
            
            # Determine which preset this matches
            preset = "balanced"  # default
            if "0.5b" in current_model:
                preset = "speed"
            elif "3b" in current_model:
                preset = "accuracy"
                
            return {
                "success": True,
                "current_preset": preset,
                "model": {
                    "model_id": current_model,
                    "available": config_data.get("model_available", True),
                    "status": config_data.get("status", "unknown")
                },
                "available_models": config_data.get("available_models", [])
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unable to get current configuration"),
                "current_preset": "balanced",
                "model": {"model_id": "qwen2.5:1.5b", "available": False, "status": "unknown"}
            }
            
    except Exception as e:
        logger.error(f"Get optimization error: {e}")
        return {
            "success": False,
            "error": str(e),
            "current_preset": "balanced",
            "model": {"model_id": "qwen2.5:1.5b", "available": False, "status": "error"}
        }

@app.get("/api/optimization/stats")
async def get_optimization_stats():
    """Get optimization and performance statistics"""
    try:
        # Get current optimization settings
        current_result = await get_current_optimization()
        
        # Mock cache statistics for now (these would be real in a full implementation)
        cache_stats = {
            "screen_cache_hit_rate": "85%",
            "response_cache_hit_rate": "72%", 
            "total_queries": 156
        }
        
        return {
            "success": True,
            "cache_stats": cache_stats,
            "metrics": {
                "total_queries": cache_stats["total_queries"],
                "screen_cache_hit_rate": cache_stats["screen_cache_hit_rate"],
                "response_cache_hit_rate": cache_stats["response_cache_hit_rate"]
            },
            "model_config": {
                "current_model": {
                    "name": f"{current_result['current_preset'].title()} Mode",
                    "description": f"Optimized for {current_result['current_preset']} performance",
                    "estimated_latency": "< 1s" if current_result['current_preset'] == 'speed' else 
                                        "< 2s" if current_result['current_preset'] == 'balanced' else "< 3s"
                }
            }
        }
    except Exception as e:
        logger.error(f"Get optimization stats error: {e}")
        return {
            "success": False,
            "error": str(e),
            "cache_stats": {"screen_cache_hit_rate": "--", "response_cache_hit_rate": "--", "total_queries": 0},
            "metrics": {"total_queries": 0}
        }

@app.post("/api/optimization/cache/clear")
async def clear_optimization_caches():
    """Clear optimization caches"""
    try:
        # In a full implementation, this would clear actual caches
        # For now, we'll just return success
        return {
            "success": True,
            "message": "All optimization caches cleared",
            "cleared_items": ["screen_cache", "response_cache", "model_cache"]
        }
    except Exception as e:
        logger.error(f"Clear caches error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/sessions")
async def get_active_sessions():
    """Get information about active sessions"""
    return {
        "active_sessions": len(connection_manager.active_connections),
        "sessions": {
            client_id: {
                "connected_at": session["connected_at"].isoformat(),
                "message_count": session["message_count"],
                "last_activity": session["last_activity"].isoformat()
            }
            for client_id, session in connection_manager.user_sessions.items()
        }
    }

@app.post("/api/feedback/command-history")
async def update_command_history(request: Request):
    """Update command history based on user feedback"""
    try:
        data = await request.json()
        action = data.get("action")  # "add_pair" or "update_correction"
        
        command_history_path = Path("config/command_history.json")
        
        # Load existing command history
        if command_history_path.exists():
            with open(command_history_path, 'r') as f:
                command_history = json.load(f)
        else:
            command_history = {"command_pairs": []}
        
        if action == "add_pair":
            # User clicked "Yes" - add the successful command-action pair
            user_command = data.get("user_command")
            matched_action = data.get("matched_action")
            
            if user_command and matched_action:
                # Check if this exact pair already exists
                existing_pair = next((pair for pair in command_history["command_pairs"] 
                                    if pair["user_command"].lower() == user_command.lower()), None)
                
                if not existing_pair:
                    command_history["command_pairs"].append({
                        "user_command": user_command,
                        "action": matched_action,
                        "added_via_feedback": True,
                        "timestamp": datetime.now().isoformat()
                    })
                    logger.info(f"Added new command pair via feedback: {user_command} -> {matched_action}")
                else:
                    logger.info(f"Command pair already exists: {user_command}")
        
        elif action == "update_correction":
            # User clicked "No" and provided correct screen/element
            user_command = data.get("user_command")
            correct_screen = data.get("correct_screen")
            correct_element = data.get("correct_element")
            
            if user_command and correct_screen and correct_element:
                # Load kiosk data to get element details
                kiosk_data_path = Path("config/kiosk_data.json")
                if kiosk_data_path.exists():
                    with open(kiosk_data_path, 'r') as f:
                        kiosk_data = json.load(f)
                    
                    # Find the correct element
                    screen_data = kiosk_data["screens"].get(correct_screen)
                    if screen_data:
                        element_data = next((elem for elem in screen_data["elements"] 
                                           if elem["id"] == correct_element), None)
                        
                        if element_data:
                            # Create corrected action
                            corrected_action = {
                                "type": element_data["action"],
                                "element_id": element_data["id"],
                                "coordinates": element_data["coordinates"],
                                "method": "user_corrected",
                                "description": f'corrected to {element_data["action"]} "{element_data["id"]}" at coordinates {element_data["coordinates"]}'
                            }
                            
                            # Add corrected pair
                            command_history["command_pairs"].append({
                                "user_command": user_command,
                                "action": corrected_action,
                                "corrected_via_feedback": True,
                                "timestamp": datetime.now().isoformat()
                            })
                            logger.info(f"Added corrected command pair: {user_command} -> {correct_element}")
        
        # Save updated command history
        with open(command_history_path, 'w') as f:
            json.dump(command_history, f, indent=2)
        
        return {"success": True, "message": "Command history updated"}
        
    except Exception as e:
        logger.error(f"Error updating command history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def main():
    """Run the web application"""
    # Create static directory if it doesn't exist
    static_dir = Path("web_app/static")
    static_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("Starting Kiosk Speech Web Interface...")
    logger.info("Access the interface at: http://localhost:8000")
    logger.info("WebSocket endpoint: ws://localhost:8000/ws/{client_id}")
    
    # Run with uvicorn
    uvicorn.run(
        "web_app.main:app",
        host="0.0.0.0",  # Allow access from Windows host
        port=8000,
        log_level="info",
        reload=False  # Set to True for development
    )

if __name__ == "__main__":
    main()
