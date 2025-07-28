#!/usr/bin/env python3
import asyncio
import json
import threading
import queue
from typing import Any, Dict, List, Optional
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from pathlib import Path

from mcp.types import Tool, TextContent
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.mcp.base_server import BaseMCPServer, MCPToolError, create_tool_response


class SpeechToTextServer(BaseMCPServer):
    def __init__(self):
        super().__init__("speech_to_text", "Convert speech input to text commands")
        
        # Audio configuration
        self.sample_rate = 16000
        self.chunk_duration = 1.0  # seconds
        self.chunk_size = int(self.sample_rate * self.chunk_duration)
        
        # Whisper model
        self.model = None
        self.model_name = "base"
        self.language = "en"
        
        # Audio processing
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.audio_thread = None
        
        # Voice activity detection
        self.vad_threshold = 0.01
        self.silence_timeout = 2.0  # seconds
        
    async def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="start_listening",
                description="Start continuous speech recognition",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "audio_device": {
                            "type": "string",
                            "description": "Audio device index or name",
                            "default": "default"
                        },
                        "language": {
                            "type": "string", 
                            "description": "Speech language code",
                            "default": "en"
                        },
                        "model": {
                            "type": "string",
                            "description": "Whisper model size",
                            "enum": ["tiny", "base", "small", "medium", "large"],
                            "default": "base"
                        }
                    }
                }
            ),
            Tool(
                name="stop_listening",
                description="Stop speech recognition",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="transcribe_audio",
                description="Transcribe audio data to text",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "audio_data": {
                            "type": "string",
                            "description": "Base64 encoded audio data"
                        },
                        "language": {
                            "type": "string",
                            "description": "Speech language code", 
                            "default": "en"
                        }
                    },
                    "required": ["audio_data"]
                }
            ),
            Tool(
                name="transcribe_file",
                description="Transcribe audio file to text",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to audio file (WAV, MP3, etc.)"
                        },
                        "language": {
                            "type": "string",
                            "description": "Speech language code", 
                            "default": "en"
                        }
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="get_audio_devices",
                description="List available audio input devices",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="get_status",
                description="Get current speech recognition status",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="record_and_transcribe",
                description="Record audio from microphone and transcribe it to text",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "description": "Recording duration in seconds",
                            "default": 5
                        },
                        "output_file": {
                            "type": "string",
                            "description": "Output audio file path (optional, auto-generated if not provided)"
                        },
                        "language": {
                            "type": "string",
                            "description": "Speech language code",
                            "default": "en"
                        }
                    }
                }
            )
        ]
    
    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        try:
            if name == "start_listening":
                return await self._start_listening(arguments)
            elif name == "stop_listening":
                return await self._stop_listening()
            elif name == "transcribe_audio":
                return await self._transcribe_audio(arguments)
            elif name == "transcribe_file":
                return await self._transcribe_file(arguments)
            elif name == "get_audio_devices":
                return await self._get_audio_devices()
            elif name == "get_status":
                return await self._get_status()
            elif name == "record_and_transcribe":
                return await self._record_and_transcribe(arguments)
            else:
                raise MCPToolError(f"Unknown tool: {name}")
                
        except Exception as e:
            return create_tool_response(False, error=str(e))
    
    async def _start_listening(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Start continuous speech recognition"""
        if self.is_recording:
            return create_tool_response(False, error="Already listening")
        
        # Load model if not already loaded
        model_name = arguments.get("model", self.model_name)
        if self.model is None or model_name != self.model_name:
            self.model_name = model_name
            self.model = WhisperModel(model_name)
        
        # Set language
        self.language = arguments.get("language", "en")
        
        # Start audio capture thread
        self.is_recording = True
        self.audio_thread = threading.Thread(target=self._audio_capture_loop)
        self.audio_thread.daemon = True
        self.audio_thread.start()
        
        return create_tool_response(True, {
            "status": "listening",
            "model": self.model_name,
            "language": self.language,
            "sample_rate": self.sample_rate
        })
    
    async def _stop_listening(self) -> Dict[str, Any]:
        """Stop speech recognition"""
        if not self.is_recording:
            return create_tool_response(False, error="Not currently listening")
        
        self.is_recording = False
        if self.audio_thread:
            self.audio_thread.join(timeout=2.0)
        
        return create_tool_response(True, {"status": "stopped"})
    
    async def _transcribe_audio(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Transcribe provided audio data"""
        import base64
        
        try:
            # Decode audio data
            audio_data = base64.b64decode(arguments["audio_data"])
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            
            # Load model if needed
            if self.model is None:
                self.model = WhisperModel(self.model_name)
            
            # Transcribe
            language = arguments.get("language", self.language)
            segments, info = self.model.transcribe(audio_array, language=language)
            
            # Combine all segments into text
            text = " ".join(segment.text for segment in segments)
            
            return create_tool_response(True, {
                "text": text.strip(),
                "language": info.language,
                "confidence": info.language_probability
            })
            
        except Exception as e:
            return create_tool_response(False, error=f"Transcription failed: {e}")
    
    async def _record_and_transcribe(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Record audio from microphone and transcribe it"""
        import wave
        import tempfile
        import os
        from datetime import datetime
        
        duration = arguments.get("duration", 5)  # Default 5 seconds
        output_file = arguments.get("output_file", None)
        
        try:
            # Create temporary file if no output file specified
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"recorded_audio_{timestamp}.wav"
            
            print(f"Recording audio for {duration} seconds...")
            
            # Try different approaches for device detection
            input_device = None
            
            try:
                devices = sd.query_devices()
                for i, device in enumerate(devices):
                    if device['max_input_channels'] > 0:
                        input_device = i
                        break
            except Exception as e:
                print(f"Device query failed: {e}")
            
            # If no devices found, try various fallback options
            if input_device is None:
                # Try common device indices
                for test_device in [0, 1, 2, None]:
                    try:
                        # Test recording with this device
                        test_audio = sd.rec(
                            int(0.1 * self.sample_rate),  # 0.1 second test
                            samplerate=self.sample_rate,
                            channels=1,
                            dtype=np.float32,
                            device=test_device
                        )
                        sd.wait()
                        input_device = test_device
                        print(f"Using device {input_device}")
                        break
                    except Exception as e:
                        print(f"Device {test_device} failed: {e}")
                        continue
            
            if input_device is None:
                raise Exception("No working audio input device found")
            
            # Record audio with working device
            recorded_audio = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                device=input_device
            )
            sd.wait()  # Wait for recording to complete
            
            # Save to WAV file
            with wave.open(output_file, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                
                # Convert float32 to int16
                audio_int16 = (recorded_audio * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())
            
            print(f"Audio saved to: {output_file}")
            
            # Load model if needed
            if self.model is None:
                self.model = WhisperModel(self.model_name)
            
            # Transcribe the recorded audio
            language = arguments.get("language", self.language)
            segments, info = self.model.transcribe(recorded_audio.flatten(), language=language)
            
            # Combine all segments into text
            text = " ".join(segment.text for segment in segments)
            
            return create_tool_response(True, {
                "text": text.strip(),
                "language": info.language,
                "confidence": info.language_probability,
                "audio_file": output_file,
                "duration": duration
            })
            
        except Exception as e:
            return create_tool_response(False, error=f"Recording and transcription failed: {e}")
    
    async def _transcribe_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Transcribe audio file to text"""
        import os
        
        file_path = arguments.get("file_path")
        language = arguments.get("language", self.language)
        
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                return create_tool_response(False, error=f"Audio file not found: {file_path}")
            
            # Load model if needed
            if self.model is None:
                self.model = WhisperModel(self.model_name)
            
            # Transcribe the audio file
            segments, info = self.model.transcribe(file_path, language=language)
            
            # Combine all segments into text
            text = " ".join(segment.text for segment in segments)
            
            return create_tool_response(True, {
                "text": text.strip(),
                "language": info.language,
                "confidence": info.language_probability,
                "file_path": file_path
            })
            
        except Exception as e:
            return create_tool_response(False, error=f"File transcription failed: {e}")
    
    async def _get_audio_devices(self) -> Dict[str, Any]:
        """Get list of available audio input devices"""
        try:
            devices = sd.query_devices()
            input_devices = []
            
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append({
                        "index": i,
                        "name": device['name'],
                        "channels": device['max_input_channels'],
                        "sample_rate": device['default_samplerate']
                    })
            
            return create_tool_response(True, {"devices": input_devices})
            
        except Exception as e:
            return create_tool_response(False, error=f"Failed to query devices: {e}")
    
    async def _get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return create_tool_response(True, {
            "is_recording": self.is_recording,
            "model_loaded": self.model is not None,
            "model_name": self.model_name,
            "language": self.language,
            "sample_rate": self.sample_rate
        })
    
    def _audio_capture_loop(self):
        """Audio capture loop running in separate thread"""
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Audio callback status: {status}")
            
            # Convert to float32 and add to queue
            audio_data = indata[:, 0].astype(np.float32)
            
            # Simple voice activity detection
            if np.max(np.abs(audio_data)) > self.vad_threshold:
                print(f"🎤 Microphone input detected - Audio level: {np.max(np.abs(audio_data)):.3f}")
                self.audio_queue.put(audio_data.copy())
        
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                blocksize=self.chunk_size,
                callback=audio_callback
            ):
                # Process audio chunks
                silence_start = None
                audio_buffer = []
                
                while self.is_recording:
                    try:
                        # Get audio chunk with timeout
                        chunk = self.audio_queue.get(timeout=0.1)
                        audio_buffer.append(chunk)
                        silence_start = None
                        
                        # Process when we have enough audio
                        if len(audio_buffer) >= 3:  # ~3 seconds
                            print(f"🔊 Processing audio chunk ({len(audio_buffer)} chunks, ~{len(audio_buffer)}s)")
                            audio_array = np.concatenate(audio_buffer)
                            self._process_audio_chunk(audio_array)
                            audio_buffer.clear()
                            
                    except queue.Empty:
                        # Handle silence timeout
                        if silence_start is None:
                            silence_start = asyncio.get_event_loop().time()
                        elif asyncio.get_event_loop().time() - silence_start > self.silence_timeout:
                            if audio_buffer:
                                print(f"🔊 Processing audio on silence timeout ({len(audio_buffer)} chunks)")
                                audio_array = np.concatenate(audio_buffer)
                                self._process_audio_chunk(audio_array)
                                audio_buffer.clear()
                            silence_start = None
                        
        except Exception as e:
            print(f"Audio capture error: {e}")
    
    def _process_audio_chunk(self, audio_data: np.ndarray):
        """Process audio chunk and emit transcription"""
        try:
            if self.model is None:
                return
            
            # Transcribe audio
            segments, info = self.model.transcribe(audio_data, language=self.language)
            text = " ".join(segment.text for segment in segments).strip()
            
            if text:
                # Emit transcription event (in real implementation, this would
                # be sent to the orchestrator or event system)
                print(f"✅ Speech transcribed: '{text}'")
                
        except Exception as e:
            print(f"Transcription error: {e}")


async def main():
    """Main function to run the speech-to-text MCP server"""
    server = SpeechToTextServer()
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())