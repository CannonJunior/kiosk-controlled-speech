#!/usr/bin/env python3
import asyncio
from typing import Any, Dict

from fastmcp import FastMCP

mcp = FastMCP("Speech to Text Server")

class SpeechToTextState:
    def __init__(self):
        self.is_listening = False
        self.last_command = None

# Global state
speech_state = SpeechToTextState()

@mcp.tool()
async def start_listening():
    """Start speech recognition"""
    try:
        speech_state.is_listening = True
        print("🎤 Speech recognition started - listening for microphone input")
        return {
            "success": True,
            "status": "listening",
            "message": "Speech recognition started"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def stop_listening():
    """Stop speech recognition"""
    try:
        speech_state.is_listening = False
        print("🔇 Speech recognition stopped - no longer listening for microphone input")
        return {
            "success": True, 
            "status": "stopped",
            "message": "Speech recognition stopped"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_status():
    """Get current speech recognition status"""
    return {
        "is_listening": speech_state.is_listening,
        "last_command": speech_state.last_command
    }

@mcp.tool()
async def process_audio_data(audio_data: str):
    """Process audio data and return transcribed text"""
    # Placeholder implementation - would integrate with speech recognition service
    print("🎤 Processing microphone audio data for transcription")
    result = {
        "success": True,
        "transcribed_text": "mock transcribed text",
        "confidence": 0.85
    }
    print(f"✅ Audio transcribed: '{result['transcribed_text']}'")
    return result

if __name__ == "__main__":
    mcp.run()