#!/usr/bin/env python3
"""
Text-to-Speech MCP Server
Provides text-to-speech conversion using pyttsx3
"""
import asyncio
import logging
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
import pyttsx3

from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Text-to-Speech Server")

# TTS Configuration
TTS_CONFIG = {
    "default_rate": 200,  # Words per minute
    "default_volume": 0.8,  # 0.0 to 1.0
    "default_voice_index": 0,  # Use first available voice
    "supported_formats": [".wav", ".mp3"],
    "max_text_length": 5000,  # Character limit for single TTS request
    "temp_dir": None  # Will be set during initialization
}


class TTSProcessor:
    """Handles text-to-speech processing with voice configuration"""
    
    def __init__(self):
        self.engine = None
        self.available_voices = []
        self.current_voice = None
        self.is_initialized = False
        self._engine_lock = threading.Lock()
        self._setup_temp_dir()
        self._initialize_engine()
    
    def _setup_temp_dir(self):
        """Setup temporary directory for audio files"""
        temp_base = Path(tempfile.gettempdir()) / "kiosk_tts"
        temp_base.mkdir(exist_ok=True)
        TTS_CONFIG["temp_dir"] = temp_base
        logger.info(f"TTS temp directory: {temp_base}")
    
    def _initialize_engine(self):
        """Initialize TTS engine and discover available voices"""
        try:
            with self._engine_lock:
                self.engine = pyttsx3.init()
                
                # Get available voices
                voices = self.engine.getProperty('voices')
                self.available_voices = []
                
                for i, voice in enumerate(voices):
                    voice_info = {
                        "index": i,
                        "id": voice.id,
                        "name": getattr(voice, 'name', f"Voice {i}"),
                        "language": getattr(voice, 'languages', ['unknown']),
                        "gender": getattr(voice, 'gender', 'unknown'),
                        "age": getattr(voice, 'age', 'unknown')
                    }
                    self.available_voices.append(voice_info)
                
                # Set default voice
                if self.available_voices:
                    self.current_voice = self.available_voices[TTS_CONFIG["default_voice_index"]]
                    self.engine.setProperty('voice', self.current_voice["id"])
                
                # Set default properties
                self.engine.setProperty('rate', TTS_CONFIG["default_rate"])
                self.engine.setProperty('volume', TTS_CONFIG["default_volume"])
                
                self.is_initialized = True
                logger.info(f"TTS engine initialized with {len(self.available_voices)} voices")
                
        except Exception as e:
            logger.error(f"Failed to initialize TTS engine: {e}")
            self.is_initialized = False
    
    def get_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voices"""
        return self.available_voices.copy()
    
    def set_voice(self, voice_index: int) -> bool:
        """Set voice by index"""
        try:
            if not self.is_initialized:
                return False
                
            if 0 <= voice_index < len(self.available_voices):
                with self._engine_lock:
                    voice = self.available_voices[voice_index]
                    self.engine.setProperty('voice', voice["id"])
                    self.current_voice = voice
                    logger.info(f"Voice set to: {voice['name']}")
                    return True
            else:
                logger.error(f"Invalid voice index: {voice_index}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to set voice: {e}")
            return False
    
    def set_speech_rate(self, rate: int) -> bool:
        """Set speech rate (words per minute)"""
        try:
            if not self.is_initialized:
                return False
                
            if 50 <= rate <= 400:  # Reasonable bounds for speech rate
                with self._engine_lock:
                    self.engine.setProperty('rate', rate)
                    logger.info(f"Speech rate set to: {rate} WPM")
                    return True
            else:
                logger.error(f"Invalid speech rate: {rate} (must be 50-400)")
                return False
                
        except Exception as e:
            logger.error(f"Failed to set speech rate: {e}")
            return False
    
    def set_volume(self, volume: float) -> bool:
        """Set volume level (0.0 to 1.0)"""
        try:
            if not self.is_initialized:
                return False
                
            if 0.0 <= volume <= 1.0:
                with self._engine_lock:
                    self.engine.setProperty('volume', volume)
                    logger.info(f"Volume set to: {volume}")
                    return True
            else:
                logger.error(f"Invalid volume: {volume} (must be 0.0-1.0)")
                return False
                
        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            return False
    
    def text_to_speech_file(self, 
                           text: str, 
                           output_path: Optional[Path] = None,
                           voice_index: Optional[int] = None,
                           rate: Optional[int] = None,
                           volume: Optional[float] = None) -> Dict[str, Any]:
        """
        Convert text to speech and save as audio file
        
        Args:
            text: Text to convert to speech
            output_path: Output file path (auto-generated if None)
            voice_index: Voice to use (None for current)
            rate: Speech rate in WPM (None for current)
            volume: Volume level 0.0-1.0 (None for current)
            
        Returns:
            Dictionary with result information
        """
        try:
            if not self.is_initialized:
                return {
                    "success": False,
                    "error": "TTS engine not initialized",
                    "audio_path": None
                }
            
            # Validate text length
            if len(text) > TTS_CONFIG["max_text_length"]:
                return {
                    "success": False,
                    "error": f"Text too long ({len(text)} chars, max {TTS_CONFIG['max_text_length']})",
                    "audio_path": None
                }
            
            if not text.strip():
                return {
                    "success": False,
                    "error": "Empty text provided",
                    "audio_path": None
                }
            
            # Generate output path if not provided
            if output_path is None:
                audio_id = uuid.uuid4().hex[:8]
                output_path = TTS_CONFIG["temp_dir"] / f"tts_{audio_id}.wav"
            else:
                output_path = Path(output_path)
            
            # Create directory if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with self._engine_lock:
                # Temporarily set voice properties if provided
                original_settings = {}
                try:
                    if voice_index is not None:
                        original_settings["voice"] = self.engine.getProperty('voice')
                        if 0 <= voice_index < len(self.available_voices):
                            self.engine.setProperty('voice', self.available_voices[voice_index]["id"])
                    
                    if rate is not None:
                        original_settings["rate"] = self.engine.getProperty('rate')
                        self.engine.setProperty('rate', rate)
                    
                    if volume is not None:
                        original_settings["volume"] = self.engine.getProperty('volume')
                        self.engine.setProperty('volume', volume)
                    
                    # Convert text to speech and save to file
                    self.engine.save_to_file(text, str(output_path))
                    self.engine.runAndWait()
                    
                finally:
                    # Restore original settings
                    for prop, value in original_settings.items():
                        self.engine.setProperty(prop, value)
            
            # Verify file was created
            if not output_path.exists():
                return {
                    "success": False,
                    "error": "Audio file was not created",
                    "audio_path": None
                }
            
            # Get file info
            file_size = output_path.stat().st_size
            
            result = {
                "success": True,
                "audio_path": str(output_path),
                "file_size_bytes": file_size,
                "text_length": len(text),
                "word_count": len(text.split()),
                "settings": {
                    "voice": self.current_voice["name"] if voice_index is None else self.available_voices[voice_index]["name"],
                    "rate": rate or self.engine.getProperty('rate'),
                    "volume": volume or self.engine.getProperty('volume')
                },
                "duration_estimate": self._estimate_duration(text, rate or self.engine.getProperty('rate'))
            }
            
            logger.info(f"TTS conversion completed: {len(text)} characters -> {output_path}")
            return result
            
        except Exception as e:
            logger.error(f"TTS conversion failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "audio_path": None
            }
    
    def _estimate_duration(self, text: str, rate: int) -> float:
        """Estimate audio duration based on text length and speech rate"""
        word_count = len(text.split())
        # Add some padding for punctuation and natural pauses
        duration_seconds = (word_count / rate) * 60 * 1.2
        return round(duration_seconds, 1)
    
    def cleanup_temp_files(self, older_than_minutes: int = 60) -> int:
        """Clean up temporary audio files older than specified minutes"""
        if not TTS_CONFIG["temp_dir"]:
            return 0
        
        cleanup_count = 0
        cutoff_time = time.time() - (older_than_minutes * 60)
        
        try:
            for audio_file in TTS_CONFIG["temp_dir"].glob("tts_*.wav"):
                if audio_file.stat().st_mtime < cutoff_time:
                    audio_file.unlink()
                    cleanup_count += 1
                    
            if cleanup_count > 0:
                logger.info(f"Cleaned up {cleanup_count} temporary TTS files")
                
        except Exception as e:
            logger.error(f"Error during TTS cleanup: {e}")
        
        return cleanup_count


# Global TTS processor instance
tts_processor = TTSProcessor()


@mcp.tool()
async def text_to_speech(
    text: str,
    voice_index: Optional[int] = None,
    rate: Optional[int] = None,
    volume: Optional[float] = None,
    output_filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convert text to speech and save as audio file
    
    Args:
        text: Text to convert to speech
        voice_index: Index of voice to use (None for default)
        rate: Speech rate in words per minute (50-400)
        volume: Volume level (0.0-1.0)
        output_filename: Custom filename (auto-generated if None)
        
    Returns:
        Dictionary with audio file path and metadata
    """
    try:
        # Prepare output path
        output_path = None
        if output_filename:
            output_path = TTS_CONFIG["temp_dir"] / output_filename
            if not output_path.suffix:
                output_path = output_path.with_suffix('.wav')
        
        # Convert text to speech
        result = tts_processor.text_to_speech_file(
            text=text,
            output_path=output_path,
            voice_index=voice_index,
            rate=rate,
            volume=volume
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Text-to-speech tool failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "audio_path": None
        }


@mcp.tool()
async def get_available_voices() -> Dict[str, Any]:
    """
    Get list of available TTS voices
    
    Returns:
        Dictionary with voice information
    """
    try:
        if not tts_processor.is_initialized:
            return {
                "success": False,
                "error": "TTS engine not initialized",
                "voices": []
            }
        
        voices = tts_processor.get_voices()
        
        return {
            "success": True,
            "voices": voices,
            "current_voice": tts_processor.current_voice,
            "voice_count": len(voices)
        }
        
    except Exception as e:
        logger.error(f"Failed to get available voices: {e}")
        return {
            "success": False,
            "error": str(e),
            "voices": []
        }


@mcp.tool()
async def set_tts_voice(voice_index: int) -> Dict[str, Any]:
    """
    Set the TTS voice to use
    
    Args:
        voice_index: Index of voice to use
        
    Returns:
        Dictionary with success status
    """
    try:
        success = tts_processor.set_voice(voice_index)
        
        if success:
            return {
                "success": True,
                "voice": tts_processor.current_voice,
                "message": f"Voice set to: {tts_processor.current_voice['name']}"
            }
        else:
            return {
                "success": False,
                "error": f"Failed to set voice index: {voice_index}",
                "available_voices": len(tts_processor.available_voices)
            }
            
    except Exception as e:
        logger.error(f"Failed to set TTS voice: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def set_speech_settings(
    rate: Optional[int] = None,
    volume: Optional[float] = None
) -> Dict[str, Any]:
    """
    Set speech rate and volume settings
    
    Args:
        rate: Speech rate in words per minute (50-400)
        volume: Volume level (0.0-1.0)
        
    Returns:
        Dictionary with success status
    """
    try:
        results = {"success": True, "settings_updated": []}
        
        if rate is not None:
            if tts_processor.set_speech_rate(rate):
                results["settings_updated"].append(f"rate: {rate} WPM")
            else:
                results["success"] = False
                results["error"] = f"Failed to set rate: {rate}"
        
        if volume is not None:
            if tts_processor.set_volume(volume):
                results["settings_updated"].append(f"volume: {volume}")
            else:
                results["success"] = False
                results["error"] = results.get("error", "") + f" Failed to set volume: {volume}"
        
        if results["settings_updated"]:
            results["message"] = "Updated: " + ", ".join(results["settings_updated"])
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to set speech settings: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def get_tts_capabilities() -> Dict[str, Any]:
    """
    Get TTS service capabilities and configuration
    
    Returns:
        Dictionary with TTS service information
    """
    try:
        return {
            "success": True,
            "engine_initialized": tts_processor.is_initialized,
            "available_voices": len(tts_processor.available_voices),
            "current_voice": tts_processor.current_voice,
            "supported_formats": TTS_CONFIG["supported_formats"],
            "max_text_length": TTS_CONFIG["max_text_length"],
            "rate_range": {"min": 50, "max": 400, "default": TTS_CONFIG["default_rate"]},
            "volume_range": {"min": 0.0, "max": 1.0, "default": TTS_CONFIG["default_volume"]},
            "temp_directory": str(TTS_CONFIG["temp_dir"]),
            "capabilities": {
                "voice_selection": True,
                "rate_control": True,
                "volume_control": True,
                "file_output": True,
                "multiple_formats": len(TTS_CONFIG["supported_formats"]) > 1,
                "batch_processing": False  # Future enhancement
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get TTS capabilities: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def cleanup_tts_files(older_than_minutes: int = 60) -> Dict[str, Any]:
    """
    Clean up temporary TTS audio files
    
    Args:
        older_than_minutes: Remove files older than this many minutes
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        cleanup_count = tts_processor.cleanup_temp_files(older_than_minutes)
        
        return {
            "success": True,
            "files_cleaned": cleanup_count,
            "message": f"Cleaned up {cleanup_count} temporary TTS files older than {older_than_minutes} minutes"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup TTS files: {e}")
        return {
            "success": False,
            "error": str(e),
            "files_cleaned": 0
        }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()