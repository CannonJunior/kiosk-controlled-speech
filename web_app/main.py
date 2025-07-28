#!/usr/bin/env python3
"""
FastAPI Web Application for Kiosk Speech Interface
Provides web-based chat interface with speech-to-text integration
"""
import asyncio
import json
import logging
import base64
import tempfile
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import uuid

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
        self.temp_dir = Path("/tmp/web_audio")
        self.temp_dir.mkdir(exist_ok=True)
        
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
            
            logger.info("MCP services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP services: {e}")
            raise
    
    async def _load_mcp_config(self):
        """Load MCP configuration from config file"""
        config_path = Path("../config/mcp_config.json")
        if not config_path.exists():
            config_path = Path("config/mcp_config.json")
        
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
                        "command": "python",
                        "args": ["../services/speech_to_text/mcp_server.py"]
                    },
                    "ollama_agent": {
                        "command": "python", 
                        "args": ["../services/ollama_agent/mcp_server.py"]
                    }
                }
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
    
    async def process_chat_message(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process chat message through Ollama agent"""
        try:
            # Create mock screen data for chat context
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
            
            # Process through Ollama agent using FastMCP with error recovery
            async def call_ollama_service():
                result_raw = await self.mcp_client.call_tool(
                    "ollama_agent_process_voice_command", {
                        "voice_text": message,
                        "current_screen": current_screen,
                        "context": context or {}
                    }
                )
                return parse_tool_result(result_raw)
            
            result = await error_recovery.execute_with_resilience(
                "ollama_agent", call_ollama_service
            )
            
            if result.get("success"):
                return {
                    "success": True,
                    "response": result.get("data", {}),
                    "processing_time": "< 1s"
                }
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
    else:
        return HTMLResponse("<h1>Troubleshooting page not found</h1>")

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
            # Receive data from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            message_type = message_data.get("type")
            
            if message_type == "chat_message":
                # Process text chat message
                text = message_data.get("message", "")
                context = message_data.get("context", {})
                
                # Process through Ollama
                result = await speech_bridge.process_chat_message(text, context)
                
                # Send response
                await connection_manager.send_personal_message({
                    "type": "chat_response",
                    "original_message": text,
                    "response": result,
                    "timestamp": datetime.now().isoformat()
                }, client_id)
                
            elif message_type == "audio_data":
                # Process audio data
                audio_data = message_data.get("audio")
                
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
                    
                    # Process transcription as chat message
                    if transcription.strip():
                        chat_result = await speech_bridge.process_chat_message(transcription)
                        
                        await connection_manager.send_personal_message({
                            "type": "chat_response", 
                            "original_message": transcription,
                            "response": chat_result,
                            "from_speech": True,
                            "timestamp": datetime.now().isoformat()
                        }, client_id)
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
            
    except WebSocketDisconnect:
        connection_manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        connection_manager.disconnect(client_id)

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