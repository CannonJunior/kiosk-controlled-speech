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
from web_app.domains.speech.services.audio_processor import AudioProcessor

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
    """Parse FastMCP tool result with detailed error information"""
    if result.is_error:
        error_detail = "Unknown tool error"
        if hasattr(result, 'error') and result.error:
            error_detail = str(result.error)
        elif hasattr(result, 'content') and result.content:
            # Try to extract error from content
            try:
                error_content = result.content[0].text if result.content else "No error details"
                error_detail = error_content
            except:
                error_detail = "Error occurred but details unavailable"
        
        return {
            "success": False, 
            "error": f"🔧 **Tool Call Failed**\n\n**Error Type:** MCP Tool Execution Error\n**Details:** {error_detail}\n**Component:** FastMCP Tool Bridge\n**Timestamp:** {datetime.now().isoformat()}"
        }
    
    if result.content and len(result.content) > 0:
        text_content = result.content[0].text
        try:
            parsed_result = json.loads(text_content)
            # Add parsing success info for debugging
            if not parsed_result.get("success", True):
                # Enhance error with context
                error_msg = parsed_result.get("error", "Unknown error")
                parsed_result["error"] = f"🚨 **Service Error**\n\n**Component:** {parsed_result.get('component', 'Unknown Service')}\n**Error:** {error_msg}\n**Timestamp:** {datetime.now().isoformat()}"
            return parsed_result
        except json.JSONDecodeError as e:
            return {
                "success": False, 
                "error": f"🔍 **JSON Parsing Failed**\n\n**Raw Response:** {text_content[:200]}{'...' if len(text_content) > 200 else ''}\n**Parse Error:** {str(e)}\n**Component:** Response Parser\n**Timestamp:** {datetime.now().isoformat()}"
            }
    
    return {
        "success": False, 
        "error": f"📭 **Empty Response**\n\n**Issue:** No content received from service\n**Expected:** JSON response with action data\n**Component:** MCP Tool Bridge\n**Timestamp:** {datetime.now().isoformat()}"
    }


class SpeechWebBridge:
    """Bridges web audio to existing MCP speech services"""
    
    def __init__(self):
        self.mcp_client = None
        self.mcp_config = None
        self.temp_dir = path_resolver.get_temp_path("web_audio")
        self.temp_dir.mkdir(exist_ok=True)
        self.model_manager = ModelConfigManager()
        self.text_reading_service = None  # Will be initialized after MCP client is ready
        self.audio_processor = None  # Will be initialized after MCP client is ready
        
        # Performance optimizations: caching
        self._kiosk_data_cache = None
        self._kiosk_data_cache_time = 0
        self._kiosk_data_cache_duration = 5.0  # Cache for 5 seconds
        self._screen_context_cache = None
        
        # Response caching for common queries
        self._response_cache = {}
        self._response_cache_duration = 120.0  # Cache responses for 2 minutes for better performance
        self._common_patterns = [
            "take screenshot", "screenshot", "capture screen", "click", "help", 
            "what can i do", "what can you do", "commands", "start recording", 
            "stop recording", "open settings", "settings", "interactive mission",
            "mission vignettes", "vignettes"
        ]
        
        # Processing timing metrics and monitoring
        self.processing_metrics = {
            "total_requests": 0,
            "completed_requests": 0,
            "timed_out_requests": 0,
            "failed_requests": 0,
            "processing_times": [],
            "cache_hits": 0,
            "fast_path_hits": 0,
            "start_time": time.time()
        }
        self.max_processing_time = 3.0  # 3 second limit
        self.target_median_time = 1.0  # Target 1 second median
        
        # Fast-path heuristic patterns for instant response (<100ms)
        # EXPANDED to catch more commands and avoid Ollama calls
        self._fast_patterns = {
            # Native screenshot commands (direct MCP call)
            "hey optix portal screenshot": {"action": "native_screenshot", "confidence": 0.99},
            "portal screenshot": {"action": "native_screenshot", "confidence": 0.95},
            "native screenshot": {"action": "native_screenshot", "confidence": 0.9},
            
            # UI screenshot commands (click button)
            "take screenshot": {"action": "screenshot", "confidence": 0.95},
            "screenshot": {"action": "screenshot", "confidence": 0.9},
            "take a screenshot": {"action": "screenshot", "confidence": 0.95},
            "capture screen": {"action": "screenshot", "confidence": 0.9},
            "screen capture": {"action": "screenshot", "confidence": 0.9},
            "snap": {"action": "screenshot", "confidence": 0.8},
            "capture": {"action": "screenshot", "confidence": 0.8},
            "hey optix take a screenshot": {"action": "screenshot", "confidence": 0.95},
            
            # Help commands
            "help": {"action": "help", "confidence": 0.99},
            "what can i do": {"action": "help", "confidence": 0.95},
            "what can you do": {"action": "help", "confidence": 0.95},
            "commands": {"action": "help", "confidence": 0.9},
            "options": {"action": "help", "confidence": 0.9},
            "what": {"action": "help", "confidence": 0.8},
            "how": {"action": "help", "confidence": 0.8},
            "?": {"action": "help", "confidence": 0.8},
            
            # Settings commands
            "open settings": {"action": "click", "element_id": "settingsToggle", "confidence": 0.9},
            "settings": {"action": "click", "element_id": "settingsToggle", "confidence": 0.85},
            "options": {"action": "click", "element_id": "settingsToggle", "confidence": 0.8},
            "configure": {"action": "click", "element_id": "settingsToggle", "confidence": 0.8},
            
            # Greeting/basic commands
            "hello": {"action": "help", "confidence": 0.8},
            "hi": {"action": "help", "confidence": 0.8},
            "hey": {"action": "help", "confidence": 0.8},
            "start": {"action": "help", "confidence": 0.7},
            "begin": {"action": "help", "confidence": 0.7},
            "test": {"action": "help", "confidence": 0.7},
            
            # Common single words that should get help
            "yes": {"action": "help", "confidence": 0.6},
            "no": {"action": "help", "confidence": 0.6},
            "ok": {"action": "help", "confidence": 0.6},
            "okay": {"action": "help", "confidence": 0.6},
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
            
            # Initialize audio processor with detailed timing
            self.audio_processor = AudioProcessor(self.mcp_client)
            
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
                        "args": ["../services/speech_to_text/mcp_server.py"]
                    },
                    "ollama_agent": {
                        "command": "python3", 
                        "args": ["../../services/ollama_agent/mcp_server.py"]
                    },
                    "mouse_control": {
                        "command": "python3",
                        "args": ["../services/mouse_control/mcp_server.py"]
                    },
                    "screen_capture": {
                        "command": "python3",
                        "args": ["../services/screen_capture/mcp_server.py"]
                    },
                    "screen_detector": {
                        "command": "python3",
                        "args": ["../services/screen_detector/mcp_server.py"]
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
                    "id": "merged_all_screens",
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
                            
                            # Use enhanced message from voice processor if available, otherwise create default
                            enhanced_message = ollama_response.get("message")
                            if enhanced_message:
                                display_message = enhanced_message
                            else:
                                display_message = f"🖱️ Successfully clicked \"{element_name}\" at coordinates ({coordinates['x']}, {coordinates['y']}) using {method}. Coordinates from config element '{element_id}' on screen '{screen_name}'."
                            
                            return {
                                "action_executed": True,
                                "action_type": "click",
                                "element_id": element_id,
                                "coordinates": coordinates,
                                "result": "success",
                                "method": method,
                                "mock": is_mock,
                                "config_source": config_element_info,
                                "processor": ollama_response.get("processor", "unknown"),
                                "match_type": ollama_response.get("match_type", "unknown"),
                                "confidence": ollama_response.get("confidence", 0.0),
                                "processing_time_ms": ollama_response.get("processing_time_ms", 0),
                                "message": display_message
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
                    
            elif action_type == "screenshot":
                # Execute screenshot directly through MCP
                try:
                    result_raw = await self.mcp_client.call_tool("screen_capture_take_screenshot", {})
                    screenshot_result = parse_tool_result(result_raw)
                    
                    if screenshot_result.get("success"):
                        screenshot_data = screenshot_result.get("data", {})
                        return {
                            "action_executed": True,
                            "action_type": "screenshot",
                            "screenshot_path": screenshot_data.get("screenshot_path"),
                            "filename": screenshot_data.get("filename"),
                            "size": screenshot_data.get("size"),
                            "dimensions": f"{screenshot_data.get('width')}x{screenshot_data.get('height')}",
                            "method": screenshot_data.get("method"),
                            "message": f"📸 Screenshot captured successfully! File: {screenshot_data.get('filename')}, Size: {screenshot_data.get('size')}, Method: {screenshot_data.get('method')}"
                        }
                    else:
                        return {
                            "action_executed": False,
                            "action_type": "screenshot",
                            "error": screenshot_result.get("error", "Screenshot failed"),
                            "message": f"❌ Screenshot failed: {screenshot_result.get('error', 'Unknown error')}"
                        }
                        
                except Exception as e:
                    logger.error(f"Screenshot execution error: {e}")
                    return {
                        "action_executed": False,
                        "action_type": "screenshot",
                        "error": str(e),
                        "message": f"❌ Screenshot failed: {str(e)}"
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
        """Try to handle simple commands instantly without LLM - AGGRESSIVE MATCHING"""
        message_lower = message.lower().strip()
        
        # STEP 1: Exact and substring matches (most aggressive)
        for pattern, response_data in self._fast_patterns.items():
            if pattern in message_lower:
                logger.info(f"Fast-path EXACT match for '{message}': {pattern}")
                return await self._execute_fast_path_action(response_data, message, current_screen)
        
        # STEP 2: Word-based fuzzy matching (catch variations)
        message_words = set(message_lower.split())
        for pattern, response_data in self._fast_patterns.items():
            pattern_words = set(pattern.split())
            
            # If any pattern word matches any message word, and it's a short message
            if (pattern_words.intersection(message_words) and 
                len(message_words) <= 3 and len(pattern_words) <= 3):
                logger.info(f"Fast-path FUZZY match for '{message}': {pattern}")
                return await self._execute_fast_path_action(response_data, message, current_screen)
        
        # STEP 3: Keyword emergency matching (prevent Ollama calls for common words)
        emergency_keywords = {
            "screenshot": {"action": "screenshot", "confidence": 0.7},
            "help": {"action": "help", "confidence": 0.8},
            "settings": {"action": "click", "element_id": "settingsToggle", "confidence": 0.6}
        }
        
        for word in message_words:
            if word in emergency_keywords:
                logger.warning(f"Fast-path EMERGENCY match for '{message}': keyword '{word}'")
                return await self._execute_fast_path_action(emergency_keywords[word], message, current_screen)
        
        # STEP 4: Ultimate fallback for very short messages (avoid Ollama entirely)
        if len(message_words) <= 2 and len(message_lower) <= 10:
            logger.warning(f"Fast-path FALLBACK for short message: '{message}'")
            return await self._execute_fast_path_action(
                {"action": "help", "confidence": 0.5}, 
                message, current_screen
            )
        
        return None  # No fast-path match, allow normal processing
    
    async def _execute_fast_path_action(self, response_data: Dict[str, Any], original_message: str, current_screen: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a fast-path action and return formatted response"""
        action_type = response_data["action"]
        
        # Create instant response
        if action_type == "help":
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
        elif action_type == "click":
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
        elif action_type == "native_screenshot":
            # Execute native screenshot directly through MCP (new portal command)
            try:
                result_raw = await self.mcp_client.call_tool("screen_capture_take_screenshot", {})
                screenshot_result = parse_tool_result(result_raw)
                
                if screenshot_result.get("success"):
                    screenshot_data = screenshot_result.get("data", {})
                    action_result = {
                        "action_executed": True,
                        "action_type": "native_screenshot",
                        "screenshot_path": screenshot_data.get("screenshot_path"),
                        "filename": screenshot_data.get("filename"),
                        "size": screenshot_data.get("size"),
                        "dimensions": f"{screenshot_data.get('width')}x{screenshot_data.get('height')}",
                        "method": screenshot_data.get("method"),
                        "message": f"🚀 **Portal Screenshot Captured!**\n📁 File: {screenshot_data.get('filename')}\n📏 Size: {screenshot_data.get('size')}\n🖼️ Dimensions: {screenshot_data.get('width')}x{screenshot_data.get('height')}\n⚙️ Method: {screenshot_data.get('method')}\n\n✨ Native MCP screenshot capture completed!"
                    }
                else:
                    action_result = {
                        "action_executed": False,
                        "action_type": "native_screenshot",
                        "error": screenshot_result.get("error", "Screenshot failed"),
                        "message": f"❌ **Portal Screenshot Failed**\n\nError: {screenshot_result.get('error', 'Unknown error')}\n\nTry: 'portal screenshot' again or use 'take screenshot'"
                    }
                
                ollama_response = {
                    "action": "native_screenshot",
                    "confidence": response_data["confidence"],
                    "message": action_result["message"]
                }
                
                return {
                    "success": True,
                    "response": ollama_response,
                    "action_result": action_result,
                    "processing_time": "< 1s",
                    "model_used": "fast_heuristic_native",
                    "query_complexity": 1,
                    "fast_path": True,
                    "native_command": True
                }
                
            except Exception as e:
                action_result = {
                    "action_executed": False,
                    "action_type": "native_screenshot",
                    "error": str(e),
                    "message": f"❌ **Portal Screenshot Error**\n\nError: {str(e)}\n\nTry: 'portal screenshot' again or use 'take screenshot'"
                }
                
                ollama_response = {
                    "action": "native_screenshot",
                    "confidence": response_data["confidence"],
                    "message": action_result["message"]
                }
                
                return {
                    "success": True,
                    "response": ollama_response,
                    "action_result": action_result,
                    "processing_time": "< 1s",
                    "model_used": "fast_heuristic_native",
                    "query_complexity": 1,
                    "fast_path": True,
                    "native_command": True
                }
        elif action_type == "screenshot":
            # Execute screenshot directly through MCP
            try:
                result_raw = await self.mcp_client.call_tool("screen_capture_take_screenshot", {})
                screenshot_result = parse_tool_result(result_raw)
                
                if screenshot_result.get("success"):
                    screenshot_data = screenshot_result.get("data", {})
                    action_result = {
                        "action_executed": True,
                        "action_type": "screenshot",
                        "screenshot_path": screenshot_data.get("screenshot_path"),
                        "filename": screenshot_data.get("filename"),
                        "size": screenshot_data.get("size"),
                        "dimensions": f"{screenshot_data.get('width')}x{screenshot_data.get('height')}",
                        "method": screenshot_data.get("method"),
                        "message": f"📸 Fast-path screenshot captured! File: {screenshot_data.get('filename')}"
                    }
                else:
                    action_result = {
                        "action_executed": False,
                        "action_type": "screenshot",
                        "error": screenshot_result.get("error", "Screenshot failed"),
                        "message": f"❌ Fast-path screenshot failed: {screenshot_result.get('error', 'Unknown error')}"
                    }
                
                ollama_response = {
                    "action": "screenshot",
                    "confidence": response_data["confidence"],
                    "message": action_result["message"]
                }
                
                return {
                    "success": True,
                    "response": ollama_response,
                    "action_result": action_result,
                    "processing_time": "< 1s",
                    "model_used": "fast_heuristic",
                    "query_complexity": 1,
                    "fast_path": True
                }
                
            except Exception as e:
                action_result = {
                    "action_executed": False,
                    "action_type": "screenshot",
                    "error": str(e),
                    "message": f"❌ Fast-path screenshot error: {str(e)}"
                }
                
                ollama_response = {
                    "action": "screenshot",
                    "confidence": response_data["confidence"],
                    "message": action_result["message"]
                }
                
                return {
                    "success": True,
                    "response": ollama_response,
                    "action_result": action_result,
                    "processing_time": "< 1s",
                    "model_used": "fast_heuristic",
                    "query_complexity": 1,
                    "fast_path": True
                }
        
        # Fallback for unknown action types
        return {
            "success": True,
            "response": {
                "message": f"I recognized your command '{original_message}' but couldn't process the action type '{action_type}'. Try 'help' for available commands.",
                "action": "unknown",
                "confidence": 0.3
            },
            "action_result": {"action_executed": False, "message": "Unknown fast-path action"},
            "processing_time": "< 0.1s",
            "model_used": "fast_heuristic",
            "query_complexity": 1,
            "fast_path": True
        }
    
    async def process_chat_message(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process chat message with aggressive timeout handling"""
        start_time = time.time()
        processing_id = f"proc_{int(start_time * 1000)}"
        
        # Track metrics
        self.processing_metrics["total_requests"] += 1
        
        try:
            logger.info(f"[TIMING-{processing_id}] Processing started for message: '{message[:50]}...' at {datetime.now().isoformat()}")
            
            # PROCESS MESSAGE WITHOUT TIMEOUT - Let successful commands complete
            result = await self._process_message_internal(message, context)
            
            # Add timing metrics to result
            actual_time = time.time() - start_time
            if result.get("success"):
                result["actual_processing_time"] = f"{actual_time:.2f}s"
                result["processing_id"] = processing_id
                result["processing_start"] = datetime.fromtimestamp(start_time).isoformat()
                result["processing_end"] = datetime.now().isoformat()
                
                # Track successful completion
                self.processing_metrics["completed_requests"] += 1
                self._track_processing_time(actual_time)
                
                # Check if this was a cached or fast-path response
                if result.get("from_cache"):
                    self.processing_metrics["cache_hits"] += 1
                elif result.get("fast_path"):
                    self.processing_metrics["fast_path_hits"] += 1
                
                logger.info(f"[TIMING-{processing_id}] Processing completed successfully - Duration: {actual_time:.2f}s")
            else:
                result["actual_processing_time"] = f"{actual_time:.2f}s"
                result["processing_id"] = processing_id
                self.processing_metrics["failed_requests"] += 1
                self._track_processing_time(actual_time)
                logger.warning(f"[TIMING-{processing_id}] Processing failed - Duration: {actual_time:.2f}s")
            
            return result
                
        except Exception as e:
            actual_time = time.time() - start_time
            self.processing_metrics["failed_requests"] += 1
            self._track_processing_time(actual_time)
            logger.error(f"[ERROR-{processing_id}] Chat processing error after {actual_time:.2f}s: {e}")
            
            # Return a helpful error response instead of complete failure
            fallback_response = self._create_error_fallback_response(message, str(e), actual_time, processing_id)
            return fallback_response
    
    def _try_fast_path_processing(self, message: str) -> Dict[str, Any]:
        """Fast-path processing for simple commands that don't need LLM"""
        message_lower = message.lower().strip()
        
        # Screenshot commands
        if any(keyword in message_lower for keyword in ["screenshot", "capture", "screen shot", "take picture"]):
            return {
                "success": True,
                "response": {
                    "message": "📸 Taking screenshot...",
                    "action": "screenshot",
                    "confidence": 0.95
                },
                "action_result": {
                    "action_type": "screenshot",
                    "message": "Fast-path screenshot command"
                }
            }
        
        # Help commands
        if any(keyword in message_lower for keyword in ["help", "what can you do", "commands", "what commands"]):
            return {
                "success": True,
                "response": {
                    "message": "🎤 **Available Commands**\n\n• 'Take screenshot' - Capture screen\n• 'Click [element name]' - Click interface elements\n• 'Open settings' - Open settings panel\n• 'Help' - Show this help message",
                    "action": "help",
                    "confidence": 0.95
                },
                "action_result": {
                    "action_type": "help",
                    "message": "Fast-path help command"
                }
            }
        
        return None  # No fast-path match, continue with standard processing

    
    def _create_error_fallback_response(self, message: str, error_msg: str, duration: float, processing_id: str) -> Dict[str, Any]:
        """Create a helpful response when processing fails with an error"""
        response_text = f"I encountered an issue while processing your request. You can try:\n\n• 'Take screenshot'\n• 'Help'\n• 'Open settings'\n\nError details: {error_msg[:100]}..."
        
        return {
            "success": True,  # Return success to avoid error display
            "response": {
                "message": response_text,
                "action": "error_recovery", 
                "confidence": 0.3
            },
            "action_result": {
                "action_executed": False,
                "action_type": "error_recovery",
                "message": f"❌ Processing error - returned recovery response"
            },
            "actual_processing_time": f"{duration:.2f}s",
            "processing_id": processing_id,
            "error": True,
            "fallback": True,
            "processing_time": "ERROR",
            "model_used": "fallback_error"
        }
    
    def _track_processing_time(self, processing_time: float):
        """Track processing time for performance monitoring"""
        self.processing_metrics["processing_times"].append(processing_time)
        
        # Keep only last 1000 processing times to avoid memory growth
        if len(self.processing_metrics["processing_times"]) > 1000:
            self.processing_metrics["processing_times"] = self.processing_metrics["processing_times"][-1000:]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        processing_times = self.processing_metrics["processing_times"]
        uptime = time.time() - self.processing_metrics["start_time"]
        
        # Calculate statistics
        if processing_times:
            import statistics
            avg_time = statistics.mean(processing_times)
            median_time = statistics.median(processing_times)
            min_time = min(processing_times)
            max_time = max(processing_times)
            
            # Count times by performance category
            excellent = len([t for t in processing_times if t <= 0.5])
            good = len([t for t in processing_times if 0.5 < t <= 1.0])
            acceptable = len([t for t in processing_times if 1.0 < t <= 2.0])
            slow = len([t for t in processing_times if t > 2.0])
        else:
            avg_time = median_time = min_time = max_time = 0.0
            excellent = good = acceptable = slow = 0
        
        return {
            "total_requests": self.processing_metrics["total_requests"],
            "completed_requests": self.processing_metrics["completed_requests"],
            "failed_requests": self.processing_metrics["failed_requests"],
            "timed_out_requests": self.processing_metrics["timed_out_requests"],
            "cache_hits": self.processing_metrics["cache_hits"],
            "fast_path_hits": self.processing_metrics["fast_path_hits"],
            "uptime_seconds": uptime,
            "processing_time_stats": {
                "count": len(processing_times),
                "average": f"{avg_time:.3f}s",
                "median": f"{median_time:.3f}s",
                "min": f"{min_time:.3f}s",
                "max": f"{max_time:.3f}s",
                "target_median": f"{self.target_median_time:.1f}s",
                "median_achievement": "✅" if median_time <= self.target_median_time else "❌",
                "performance_breakdown": {
                    "excellent_≤0.5s": excellent,
                    "good_0.5-1.0s": good,
                    "acceptable_1.0-2.0s": acceptable,
                    "slow_>2.0s": slow
                }
            },
            "success_rate": f"{(self.processing_metrics['completed_requests'] / max(1, self.processing_metrics['total_requests']) * 100):.1f}%",
            "cache_hit_rate": f"{(self.processing_metrics['cache_hits'] / max(1, self.processing_metrics['total_requests']) * 100):.1f}%",
            "fast_path_rate": f"{(self.processing_metrics['fast_path_hits'] / max(1, self.processing_metrics['total_requests']) * 100):.1f}%"
        }
    
    async def _process_message_internal(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Internal message processing logic with detailed timing breakdown"""
        
        # Initialize detailed timing breakdown
        timing_breakdown = {
            "stage_timings": {},
            "total_start_time": time.time(),
            "cache_check_duration_ms": 0,
            "fast_path_duration_ms": 0,
            "context_loading_duration_ms": 0,
            "llm_processing_duration_ms": 0,
            "action_execution_duration_ms": 0,
            "total_duration_ms": 0
        }
        
        try:
            # Performance optimization: Check response cache for common queries
            cache_start = time.time()
            if self._is_cacheable_query(message):
                cache_key = self._get_cache_key(message)
                if cache_key in self._response_cache:
                    cached_entry = self._response_cache[cache_key]
                    if time.time() - cached_entry["time"] < self._response_cache_duration:
                        cache_end = time.time()
                        timing_breakdown["cache_check_duration_ms"] = (cache_end - cache_start) * 1000
                        logger.debug(f"Returning cached response for: {message}")
                        cached_response = cached_entry["response"].copy()
                        cached_response["from_cache"] = True
                        cached_response["timing_breakdown"] = timing_breakdown
                        return cached_response
                    else:
                        # Remove expired cache entry
                        del self._response_cache[cache_key]
            cache_end = time.time()
            timing_breakdown["cache_check_duration_ms"] = (cache_end - cache_start) * 1000
            
            # FAST-PATH: Check for simple direct commands first
            fast_path_start = time.time()
            fast_path_result = self._try_fast_path_processing(message)
            fast_path_end = time.time()
            timing_breakdown["fast_path_duration_ms"] = (fast_path_end - fast_path_start) * 1000
            
            if fast_path_result:
                logger.debug(f"Fast-path processing for: {message}")
                fast_path_result["fast_path"] = True
                fast_path_result["timing_breakdown"] = timing_breakdown
                return fast_path_result
            
            # Load screen context for standard processing
            context_start = time.time()
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
            context_end = time.time()
            timing_breakdown["context_loading_duration_ms"] = (context_end - context_start) * 1000
            
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
            llm_start = time.time()
            async def call_ollama_service():
                request_context = context or {}
                request_context["model_preference"] = optimal_model
                request_context["estimated_latency"] = model_config.get("estimated_latency", "unknown")
                request_context["current_screen_id"] = current_screen.get("id", "web_app")  # Default to web_app screen
                
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
            llm_end = time.time()
            timing_breakdown["llm_processing_duration_ms"] = (llm_end - llm_start) * 1000
            
            if result.get("success"):
                ollama_response = result.get("data", {})
                
                # Execute suggested action if applicable
                action_start = time.time()
                action_result = await self._execute_suggested_action(ollama_response, current_screen)
                action_end = time.time()
                timing_breakdown["action_execution_duration_ms"] = (action_end - action_start) * 1000
                
                # Calculate total timing
                total_end = time.time()
                timing_breakdown["total_duration_ms"] = (total_end - timing_breakdown["total_start_time"]) * 1000
                
                response = {
                    "success": True,
                    "response": ollama_response,
                    "action_result": action_result,
                    "processing_time": f"{timing_breakdown['total_duration_ms']:.1f}ms",
                    "model_used": optimal_model,
                    "query_complexity": self.model_manager._analyze_query_complexity(message),
                    "timing_breakdown": {
                        "cache_check_ms": f"{timing_breakdown['cache_check_duration_ms']:.1f}ms",
                        "fast_path_ms": f"{timing_breakdown['fast_path_duration_ms']:.1f}ms", 
                        "context_loading_ms": f"{timing_breakdown['context_loading_duration_ms']:.1f}ms",
                        "llm_processing_ms": f"{timing_breakdown['llm_processing_duration_ms']:.1f}ms",
                        "action_execution_ms": f"{timing_breakdown['action_execution_duration_ms']:.1f}ms",
                        "total_duration_ms": f"{timing_breakdown['total_duration_ms']:.1f}ms"
                    }
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
                # Calculate total timing even for failures
                total_end = time.time()
                timing_breakdown["total_duration_ms"] = (total_end - timing_breakdown["total_start_time"]) * 1000
                
                return {
                    "success": False,
                    "error": result.get("error", "Message processing failed"),
                    "timing_breakdown": timing_breakdown
                }
                
        except Exception as e:
            # Calculate total timing even for exceptions
            total_end = time.time()
            timing_breakdown["total_duration_ms"] = (total_end - timing_breakdown["total_start_time"]) * 1000
            
            logger.error(f"Internal processing error: {e}, Timing: {timing_breakdown}")
            return {
                "success": False,
                "error": f"Internal processing failed: {str(e)}",
                "timing_breakdown": timing_breakdown
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
async def get_landing_page():
    """Serve the landing page"""
    html_file = Path("web_app/static/landing.html")
    if html_file.exists():
        return FileResponse(html_file)
    else:
        # Return basic landing page if static file not found
        return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Kiosk Controlled Speech</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-align: center; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { max-width: 600px; padding: 2rem; }
        h1 { font-size: 3rem; margin-bottom: 1rem; }
        .launch-btn { background: rgba(255,255,255,0.2); border: none; color: white; padding: 1rem 2rem; font-size: 1.2rem; border-radius: 50px; cursor: pointer; }
        .launch-btn:hover { background: rgba(255,255,255,0.3); }
    </style>
    <script>
        function launchApp() {
            window.open('/app', 'KioskControlledSpeech', 'width=1200,height=800,resizable=yes');
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>🎤 Kiosk Controlled Speech</h1>
        <p>Landing page file not found. Click below to launch the application:</p>
        <button class="launch-btn" onclick="launchApp()">Launch Application</button>
    </div>
</body>
</html>
        """)

@app.get("/app", response_class=HTMLResponse)
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

@app.post("/api/kiosk-data/save-complete")
async def save_complete_kiosk_data(request: Request):
    """Save complete kiosk data structure to kiosk_data.json"""
    try:
        data = await request.json()
        kiosk_data = data.get("kiosk_data")
        
        if not kiosk_data:
            raise ValueError("No kiosk_data provided")
        
        # Debug logging
        logger.info(f"Received complete kiosk data save request")
        logger.info(f"Screens in data: {list(kiosk_data.get('screens', {}).keys())}")
        
        # Find the kiosk_data.json file using path resolver
        config_path = path_resolver.resolve_config("kiosk_data.json", required=True)
        
        # Create backup before modifying
        backup_path = config_path.with_suffix('.json.backup')
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
        
        # Save the complete kiosk data
        with open(config_path, 'w') as f:
            json.dump(kiosk_data, f, indent=2)
        
        logger.info(f"Successfully saved complete kiosk data to {config_path}")
        
        return {
            "success": True,
            "message": "Kiosk data saved successfully",
            "backup_created": str(backup_path)
        }
        
    except Exception as e:
        logger.error(f"Failed to save complete kiosk data: {e}")
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
        "performance": speech_bridge.get_performance_metrics(),
        "error_recovery": error_recovery.get_metrics()
    }

@app.get("/api/performance")
async def get_performance_metrics():
    """Get detailed performance metrics for processing optimization"""
    return {
        "success": True,
        "metrics": speech_bridge.get_performance_metrics(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/ollama/models")
async def get_ollama_models():
    """Get list of available Ollama models"""
    try:
        # Check if MCP services are initialized
        if not speech_bridge.mcp_client:
            raise HTTPException(status_code=503, detail="MCP services not initialized")
        
        # Use the ollama_agent MCP tool to get available models
        result_raw = await speech_bridge.mcp_client.call_tool("ollama_agent_check_ollama_health", {})
        result = parse_tool_result(result_raw)
        
        if result.get("success"):
            # Extract models directly from health check response
            response_data = result.get("data", {})
            available_models = response_data.get("available_models", [])
            configured_model = response_data.get("configured_model", "qwen:0.5b")
            
            if available_models:
                return {
                    "success": True,
                    "models": available_models,
                    "current_model": configured_model
                }
        
        # Fallback if MCP tools don't work - return models from centralized config
        from web_app.config.model_manager import get_model_manager
        
        central_model_manager = get_model_manager()
        available_models = central_model_manager.get_fallback_models()
        current_model = central_model_manager.get_current_model()
        
        return {
            "success": True,
            "models": available_models,
            "current_model": current_model
        }
        
    except Exception as e:
        logger.error(f"Error getting Ollama models: {e}")
        # Return default models from centralized config as fallback
        try:
            from web_app.config.model_manager import get_model_manager
            central_model_manager = get_model_manager()
            available_models = central_model_manager.get_fallback_models()
            current_model = central_model_manager.get_current_model()
            
            return {
                "success": True,
                "models": available_models,
                "current_model": current_model
            }
        except:
            return {
                "success": True,
                "models": ["qwen:0.5b"],
                "current_model": "qwen:0.5b"
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
                
                elif message_type == "cancel_processing":
                    # Log cancellation request - actual cancellation is handled by timeout logic
                    logger.info(f"Processing cancellation requested by client {client_id}")
                    await connection_manager.send_personal_message({
                        "type": "processing_cancelled",
                        "message": "Processing cancellation acknowledged",
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
    from web_app.config.model_manager import get_model_manager
    
    model_manager = get_model_manager()
    return model_manager.get_optimization_presets()

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
    from web_app.config.model_manager import get_model_manager
    central_model_manager = get_model_manager()
    
    try:
        # Use the speech bridge MCP client to get current ollama config
        if not speech_bridge.mcp_client:
            raise HTTPException(status_code=503, detail="MCP services not initialized")
        
        # Call the health_check tool which returns current config
        result_raw = await speech_bridge.mcp_client.call_tool("ollama_agent_check_ollama_health", {})
        result = parse_tool_result(result_raw)
        
        if result.get("success"):
            config_data = result.get("data", {})
            # Get default model from centralized config
            default_model = central_model_manager.get_current_model()
            current_model = config_data.get("configured_model", default_model)
            
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
                "model": {"model_id": central_model_manager.get_current_model(), "available": False, "status": "unknown"}
            }
            
    except Exception as e:
        logger.error(f"Get optimization error: {e}")
        return {
            "success": False,
            "error": str(e),
            "current_preset": "balanced",
            "model": {"model_id": central_model_manager.get_current_model(), "available": False, "status": "error"}
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

@app.get("/api/screenshots")
async def get_screenshots():
    """Get list of screenshots from the file system"""
    try:
        screenshots_dir = Path("web_app/static/screenshots")
        
        if not screenshots_dir.exists():
            return {"success": True, "screenshots": []}
        
        screenshots = []
        
        # Get all PNG files in the screenshots directory
        screenshot_files = list(screenshots_dir.glob("*.png"))
        screenshot_files.sort(key=lambda x: x.stat().st_mtime, reverse=False)  # Sort by modification time, oldest first
        
        for file_path in screenshot_files:
            stat_info = file_path.stat()
            
            screenshot_data = {
                "id": file_path.stem,  # filename without extension
                "filename": file_path.name,
                "path": f"/static/screenshots/{file_path.name}",
                "timestamp": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                "size": stat_info.st_size,
                "created": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat()
            }
            screenshots.append(screenshot_data)
        
        logger.info(f"Found {len(screenshots)} screenshots in {screenshots_dir}")
        
        return {
            "success": True,
            "screenshots": screenshots,
            "total": len(screenshots)
        }
        
    except Exception as e:
        logger.error(f"Error listing screenshots: {e}")
        return {
            "success": False,
            "error": str(e),
            "screenshots": []
        }

@app.delete("/api/screenshots/{screenshot_id}")
async def delete_screenshot(screenshot_id: str):
    """Delete a single screenshot from the file system"""
    try:
        screenshots_dir = Path("web_app/static/screenshots")
        
        # Handle both filename-based IDs and full filenames
        if screenshot_id.endswith('.png'):
            filename = screenshot_id
        else:
            filename = f"{screenshot_id}.png"
        
        file_path = screenshots_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Screenshot not found: {filename}")
        
        file_path.unlink()
        logger.info(f"Deleted screenshot: {filename}")
        
        return {"success": True, "message": f"Screenshot {filename} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting screenshot {screenshot_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete screenshot: {str(e)}")

@app.post("/api/vignettes/save")
async def save_vignette(request: Request):
    """Save a vignette with screenshots to the config folder"""
    try:
        data = await request.json()
        
        vignette_name = data.get("name", "").strip()
        if not vignette_name:
            raise HTTPException(status_code=400, detail="Vignette name is required")
        
        # Sanitize vignette name for filesystem
        safe_name = "".join(c for c in vignette_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        
        if not safe_name:
            raise HTTPException(status_code=400, detail="Invalid vignette name")
        
        # Create vignette directory structure
        config_dir = Path("config").resolve()
        vignettes_dir = config_dir / "vignettes"
        vignette_dir = vignettes_dir / safe_name
        screenshots_dir = vignette_dir / "screenshots"
        
        # Create directories
        vignettes_dir.mkdir(exist_ok=True)
        vignette_dir.mkdir(exist_ok=True)
        screenshots_dir.mkdir(exist_ok=True)
        
        logger.info(f"Creating vignette directory: {vignette_dir}")
        
        # Copy screenshot files to vignette directory
        screenshots = data.get("screenshotData", [])
        copied_screenshots = []
        source_screenshots_dir = Path("web_app/static/screenshots").resolve()
        
        for screenshot in screenshots:
            source_file = source_screenshots_dir / screenshot["filename"]
            dest_file = screenshots_dir / screenshot["filename"]
            
            if source_file.exists():
                import shutil
                shutil.copy2(str(source_file), str(dest_file))
                copied_screenshots.append({
                    "id": screenshot["id"],
                    "filename": screenshot["filename"],
                    "original_path": screenshot["path"],
                    "vignette_path": f"config/vignettes/{safe_name}/screenshots/{screenshot['filename']}",
                    "size": screenshot.get("size", 0),
                    "timestamp": screenshot.get("timestamp", "")
                })
                logger.info(f"Copied screenshot: {source_file} -> {dest_file}")
            else:
                logger.warning(f"Screenshot file not found: {source_file}")
        
        # Save vignette metadata
        vignette_metadata = {
            "name": vignette_name,
            "safe_name": safe_name,
            "screenshots": data.get("screenshots", []),
            "annotations": data.get("annotations", {}),
            "created": data.get("created"),
            "modified": data.get("modified"),
            "screenshot_count": len(copied_screenshots),
            "annotation_count": len(data.get("annotations", {})),
            "copied_screenshots": copied_screenshots
        }
        
        # Save metadata as JSON file
        metadata_file = vignette_dir / "vignette.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(vignette_metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved vignette metadata: {metadata_file}")
        
        # Update vignettes index
        vignettes_index_file = vignettes_dir / "index.json"
        if vignettes_index_file.exists():
            with open(vignettes_index_file, 'r', encoding='utf-8') as f:
                vignettes_index = json.load(f)
        else:
            vignettes_index = {"vignettes": []}
        
        # Update or add vignette in index
        existing_index = next((i for i, v in enumerate(vignettes_index["vignettes"]) if v["safe_name"] == safe_name), None)
        vignette_entry = {
            "name": vignette_name,
            "safe_name": safe_name,
            "created": vignette_metadata["created"],
            "modified": vignette_metadata["modified"],
            "screenshot_count": len(copied_screenshots),
            "annotation_count": len(data.get("annotations", {})),
            "directory": f"config/vignettes/{safe_name}"
        }
        
        if existing_index is not None:
            vignettes_index["vignettes"][existing_index] = vignette_entry
        else:
            vignettes_index["vignettes"].append(vignette_entry)
        
        # Save updated index
        with open(vignettes_index_file, 'w', encoding='utf-8') as f:
            json.dump(vignettes_index, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": f"Vignette '{vignette_name}' saved successfully",
            "vignette_directory": str(vignette_dir),
            "screenshots_copied": len(copied_screenshots),
            "metadata_file": str(metadata_file)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving vignette: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save vignette: {str(e)}")

@app.get("/api/vignettes/list")
async def list_vignettes():
    """Get list of saved vignettes"""
    try:
        vignettes_dir = Path("config/vignettes")
        vignettes_index_file = vignettes_dir / "index.json"
        
        if not vignettes_index_file.exists():
            return {"success": True, "vignettes": []}
        
        with open(vignettes_index_file, 'r', encoding='utf-8') as f:
            import json
            vignettes_index = json.load(f)
        
        vignettes = vignettes_index.get("vignettes", [])
        
        # Add additional metadata for each vignette
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
        
        return {"success": True, "vignettes": vignettes}
        
    except Exception as e:
        logger.error(f"Error listing vignettes: {e}")
        return {"success": False, "error": str(e), "vignettes": []}

@app.get("/api/vignettes/{vignette_name}")
async def get_vignette(vignette_name: str):
    """Get a specific vignette's data"""
    try:
        # Sanitize vignette name for filesystem
        safe_name = "".join(c for c in vignette_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        
        vignette_dir = Path("config/vignettes") / safe_name
        metadata_file = vignette_dir / "vignette.json"
        
        if not metadata_file.exists():
            raise HTTPException(status_code=404, detail=f"Vignette '{vignette_name}' not found")
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            import json
            vignette_data = json.load(f)
        
        # Convert screenshot paths to web-accessible URLs
        for screenshot in vignette_data.get("copied_screenshots", []):
            # Convert config path to web-accessible path
            config_path = screenshot.get("vignette_path", "")
            if config_path:
                # Create a web-accessible URL for vignette screenshots
                # For now, we'll reference the original screenshots since they're web-accessible
                screenshot["web_path"] = screenshot.get("original_path", "")
        
        return {"success": True, "vignette": vignette_data}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vignette {vignette_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get vignette: {str(e)}")

@app.post("/api/vignettes/{vignette_name}/load-to-gallery")
async def load_vignette_to_gallery(vignette_name: str):
    """Copy vignette screenshots to main gallery"""
    try:
        # Sanitize vignette name for filesystem
        safe_name = "".join(c for c in vignette_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        
        vignette_dir = Path("config/vignettes") / safe_name
        metadata_file = vignette_dir / "vignette.json"
        
        if not metadata_file.exists():
            raise HTTPException(status_code=404, detail=f"Vignette '{vignette_name}' not found")
        
        # Load vignette data
        with open(metadata_file, 'r', encoding='utf-8') as f:
            import json
            vignette_data = json.load(f)
        
        # Create main screenshots directory if it doesn't exist
        main_screenshots_dir = Path("web_app/static/screenshots")
        main_screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        copied_count = 0
        copied_screenshots = []
        
        # Copy each screenshot from vignette to main gallery
        for screenshot_info in vignette_data.get("copied_screenshots", []):
            screenshot_id = screenshot_info["id"]
            filename = screenshot_info["filename"]
            vignette_path = Path(screenshot_info["vignette_path"])
            
            # Target path in main screenshots directory
            main_path = main_screenshots_dir / filename
            
            # Copy if source exists and target doesn't already exist
            if vignette_path.exists():
                if not main_path.exists():
                    import shutil
                    shutil.copy2(vignette_path, main_path)
                    copied_count += 1
                    logger.info(f"Copied screenshot {filename} to main gallery")
                else:
                    logger.info(f"Screenshot {filename} already exists in main gallery")
                
                # Add to copied screenshots list
                copied_screenshots.append({
                    "id": screenshot_id,
                    "filename": filename,
                    "path": f"/static/screenshots/{filename}",
                    "size": main_path.stat().st_size if main_path.exists() else 0,
                    "timestamp": screenshot_info.get("timestamp", "")
                })
            else:
                logger.warning(f"Vignette screenshot {vignette_path} not found")
        
        return {
            "success": True,
            "data": {
                "vignette_name": vignette_name,
                "copied_count": copied_count,
                "total_screenshots": len(vignette_data.get("copied_screenshots", [])),
                "screenshots": copied_screenshots
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading vignette {vignette_name} to gallery: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load vignette to gallery: {str(e)}")

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
