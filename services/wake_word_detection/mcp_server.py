#!/usr/bin/env python3
import asyncio
import json
import threading
import queue
import base64
import io
import wave
from typing import Any, Dict, List, Optional
import numpy as np
from pathlib import Path

from mcp.types import Tool, TextContent
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.mcp.base_server import BaseMCPServer, MCPToolError, create_tool_response

try:
    import openwakeword.model
    import openwakeword.utils
    OPENWAKEWORD_AVAILABLE = True
except ImportError as e:
    print(f"Warning: OpenWakeWord not available: {e}")
    OPENWAKEWORD_AVAILABLE = False


class WakeWordDetectionServer(BaseMCPServer):
    def __init__(self):
        super().__init__("wake_word_detection", "On-device wake word detection using OpenWakeWord")
        
        self.model = None
        self.is_listening = False
        self.sample_rate = 16000
        self.frame_size = 1280  # 80ms frames at 16kHz
        
        # Wake word models and configurations
        self.wake_word_models = {}
        self.detection_threshold = 0.5
        self.debounce_frames = 5  # Number of frames to wait before allowing another detection
        self.frames_since_detection = 0
        
        # Audio buffer for processing
        self.audio_buffer = np.array([], dtype=np.float32)
        self.max_buffer_size = 16000 * 10  # 10 seconds max buffer
        
        # Initialize wake word models
        self._initialize_models()

    def _initialize_models(self):
        """Initialize OpenWakeWord models"""
        if not OPENWAKEWORD_AVAILABLE:
            print("OpenWakeWord not available, wake word detection disabled")
            return
            
        try:
            # Initialize the model with default models
            # This will download pre-trained models on first run
            self.model = openwakeword.model.Model(
                inference_framework='onnx',  # Use ONNX for better compatibility
                wakeword_models=[],  # Start with no models, will add dynamically
            )
            
            # Get available pre-trained models
            available_models = openwakeword.utils.list_models()
            print(f"Available wake word models: {available_models}")
            
            # Load some common models that might match "Hey Optix"
            common_models = ['hey_jarvis', 'alexa', 'hey_google']
            for model_name in common_models:
                if model_name in available_models:
                    try:
                        self.wake_word_models[model_name] = True
                        print(f"Loaded wake word model: {model_name}")
                    except Exception as e:
                        print(f"Failed to load model {model_name}: {e}")
            
            print(f"Initialized OpenWakeWord with {len(self.wake_word_models)} models")
            
        except Exception as e:
            print(f"Failed to initialize OpenWakeWord: {e}")
            self.model = None

    def get_tools(self) -> List[Tool]:
        """Return available wake word detection tools"""
        return [
            Tool(
                name="wake_word_detect_audio",
                description="Detect wake words in audio data",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "audio_data": {
                            "type": "string",
                            "description": "Base64 encoded audio data (16kHz, 16-bit PCM)"
                        },
                        "wake_words": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of wake words to detect (optional, uses all loaded models if not specified)",
                            "default": []
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Detection threshold (0.0-1.0)",
                            "default": 0.5
                        }
                    },
                    "required": ["audio_data"]
                }
            ),
            Tool(
                name="wake_word_list_models",
                description="List available wake word models",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="wake_word_configure",
                description="Configure wake word detection parameters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "threshold": {
                            "type": "number",
                            "description": "Detection threshold (0.0-1.0)",
                            "default": 0.5
                        },
                        "debounce_frames": {
                            "type": "integer",
                            "description": "Number of frames to wait before allowing another detection",
                            "default": 5
                        }
                    }
                }
            ),
            Tool(
                name="wake_word_start_listening",
                description="Start continuous wake word listening",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "wake_words": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of wake words to listen for",
                            "default": []
                        }
                    }
                }
            ),
            Tool(
                name="wake_word_stop_listening",
                description="Stop continuous wake word listening",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="wake_word_get_status",
                description="Get current wake word detection status",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]

    async def wake_word_detect_audio(self, audio_data: str, wake_words: List[str] = None, threshold: float = 0.5) -> Dict[str, Any]:
        """Detect wake words in audio data"""
        if not OPENWAKEWORD_AVAILABLE or self.model is None:
            raise MCPToolError("OpenWakeWord not available")
        
        try:
            # Decode base64 audio data
            audio_bytes = base64.b64decode(audio_data)
            
            # Convert to numpy array
            # Assuming 16-bit PCM audio
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Add to buffer
            self.audio_buffer = np.concatenate([self.audio_buffer, audio_np])
            
            # Keep buffer within max size
            if len(self.audio_buffer) > self.max_buffer_size:
                self.audio_buffer = self.audio_buffer[-self.max_buffer_size:]
            
            detections = []
            
            # Process audio in frames
            while len(self.audio_buffer) >= self.frame_size:
                frame = self.audio_buffer[:self.frame_size]
                self.audio_buffer = self.audio_buffer[self.frame_size:]
                
                # Run detection on frame
                prediction = self.model.predict(frame)
                
                # Check for detections
                for wake_word, score in prediction.items():
                    if score >= threshold and self.frames_since_detection >= self.debounce_frames:
                        detections.append({
                            "wake_word": wake_word,
                            "confidence": float(score),
                            "timestamp": asyncio.get_event_loop().time()
                        })
                        self.frames_since_detection = 0
                
                self.frames_since_detection += 1
            
            return {
                "success": True,
                "detections": detections,
                "buffer_size": len(self.audio_buffer),
                "models_active": list(self.wake_word_models.keys())
            }
            
        except Exception as e:
            raise MCPToolError(f"Wake word detection failed: {str(e)}")

    async def wake_word_list_models(self) -> Dict[str, Any]:
        """List available wake word models"""
        try:
            if not OPENWAKEWORD_AVAILABLE:
                return {
                    "success": False,
                    "error": "OpenWakeWord not available",
                    "available_models": [],
                    "loaded_models": []
                }
            
            available_models = openwakeword.utils.list_models() if OPENWAKEWORD_AVAILABLE else []
            
            return {
                "success": True,
                "available_models": available_models,
                "loaded_models": list(self.wake_word_models.keys()),
                "model_status": "initialized" if self.model else "not_initialized"
            }
            
        except Exception as e:
            raise MCPToolError(f"Failed to list models: {str(e)}")

    async def wake_word_configure(self, threshold: float = 0.5, debounce_frames: int = 5) -> Dict[str, Any]:
        """Configure wake word detection parameters"""
        try:
            self.detection_threshold = max(0.0, min(1.0, threshold))
            self.debounce_frames = max(1, debounce_frames)
            
            return {
                "success": True,
                "configuration": {
                    "threshold": self.detection_threshold,
                    "debounce_frames": self.debounce_frames,
                    "sample_rate": self.sample_rate,
                    "frame_size": self.frame_size
                }
            }
            
        except Exception as e:
            raise MCPToolError(f"Configuration failed: {str(e)}")

    async def wake_word_start_listening(self, wake_words: List[str] = None) -> Dict[str, Any]:
        """Start continuous wake word listening"""
        try:
            if not OPENWAKEWORD_AVAILABLE or self.model is None:
                raise MCPToolError("OpenWakeWord not available")
            
            self.is_listening = True
            self.audio_buffer = np.array([], dtype=np.float32)
            self.frames_since_detection = 0
            
            return {
                "success": True,
                "status": "listening",
                "models_active": list(self.wake_word_models.keys()),
                "threshold": self.detection_threshold
            }
            
        except Exception as e:
            raise MCPToolError(f"Failed to start listening: {str(e)}")

    async def wake_word_stop_listening(self) -> Dict[str, Any]:
        """Stop continuous wake word listening"""
        try:
            self.is_listening = False
            self.audio_buffer = np.array([], dtype=np.float32)
            
            return {
                "success": True,
                "status": "stopped"
            }
            
        except Exception as e:
            raise MCPToolError(f"Failed to stop listening: {str(e)}")

    async def wake_word_get_status(self) -> Dict[str, Any]:
        """Get current wake word detection status"""
        try:
            return {
                "success": True,
                "status": {
                    "is_listening": self.is_listening,
                    "openwakeword_available": OPENWAKEWORD_AVAILABLE,
                    "model_initialized": self.model is not None,
                    "loaded_models": list(self.wake_word_models.keys()),
                    "threshold": self.detection_threshold,
                    "debounce_frames": self.debounce_frames,
                    "buffer_size": len(self.audio_buffer),
                    "sample_rate": self.sample_rate,
                    "frame_size": self.frame_size
                }
            }
            
        except Exception as e:
            raise MCPToolError(f"Failed to get status: {str(e)}")

    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Handle tool calls for wake word detection"""
        try:
            if name == "wake_word_detect_audio":
                return await self.wake_word_detect_audio(**arguments)
            elif name == "wake_word_list_models":
                return await self.wake_word_list_models(**arguments)
            elif name == "wake_word_configure":
                return await self.wake_word_configure(**arguments)
            elif name == "wake_word_start_listening":
                return await self.wake_word_start_listening(**arguments)
            elif name == "wake_word_stop_listening":
                return await self.wake_word_stop_listening(**arguments)
            elif name == "wake_word_get_status":
                return await self.wake_word_get_status(**arguments)
            else:
                raise MCPToolError(f"Unknown tool: {name}")
                
        except Exception as e:
            raise MCPToolError(f"Tool call failed: {str(e)}")


async def main():
    """Main entry point for the wake word detection MCP server"""
    server = WakeWordDetectionServer()
    
    # Run the server
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())