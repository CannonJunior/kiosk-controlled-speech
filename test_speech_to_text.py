#!/usr/bin/env python3
"""
Test script for the speech-to-text MCP service.
This test logs microphone status, speech detection events, and transcribed text.
"""
import asyncio
import json
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from services.speech_to_text.mcp_server import SpeechToTextServer
from detect_real_microphones import detect_real_microphones, is_jack_microphone
from windows_audio_capture import WindowsAudioCapture


class SpeechToTextTester:
    def __init__(self):
        self.server = SpeechToTextServer()
        self.test_duration = 5  # seconds
        self.log_file = None
        self.windows_audio = WindowsAudioCapture()
        self.use_windows_audio = False
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging to both file and console"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"speech_test_{timestamp}.log"
        self.log_file = Path(log_filename)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.log_and_print(f"Log file: {self.log_file.name}")
        self.log_and_print("Starting speech-to-text test")
    
    def log_and_print(self, message):
        """Log message to both file and console with immediate flush"""
        if hasattr(self, 'logger'):
            self.logger.info(message.replace('🎤', 'MIC').replace('✅', 'OK').replace('❌', 'ERR').replace('🔊', 'AUDIO').replace('📊', 'STATUS').replace('🗣️', 'SPEECH').replace('📝', 'LOG').replace('🚀', 'START').replace('🎧', 'LISTEN'))
        
    async def log_microphone_status(self):
        """Check and log microphone device availability including 3.5mm jack detection"""
        self.log_and_print("Checking microphone status...")
        
        # First check for 3.5mm jack microphones using Windows detection
        self.log_and_print("Detecting 3.5mm jack microphones...")
        try:
            real_devices = detect_real_microphones()
            jack_mics = []
            
            for device in real_devices:
                name = device.get('Name', 'Unknown')
                device_id = device.get('DeviceID', '')
                status = device.get('Status', 'Unknown')
                
                if is_jack_microphone(name, device_id):
                    jack_mics.append(device)
                    self.log_and_print(f"3.5mm Jack Mic detected: {name} (Status: {status})")
            
            if jack_mics:
                self.log_and_print(f"Found {len(jack_mics)} 3.5mm jack microphone(s)")
            else:
                self.log_and_print("No 3.5mm jack microphones detected")
                
        except Exception as e:
            self.log_and_print(f"ERROR detecting 3.5mm jack microphones: {e}")
        
        # Then check PyAudio devices
        try:
            devices_result = await asyncio.wait_for(
                self.server.handle_tool_call("get_audio_devices", {}),
                timeout=10.0
            )
            
            if devices_result.get("success", False):
                devices = devices_result["data"]["devices"]
                self.log_and_print(f"Found {len(devices)} PyAudio device(s)")
                for device in devices:
                    self.log_and_print(f"Device {device['index']}: {device['name']}")
                
                if len(devices) > 0:
                    return True
            else:
                self.log_and_print(f"No PyAudio devices: {devices_result.get('error', 'Unknown error')}")
            
            # If no PyAudio devices, try Windows audio forwarding
            self.log_and_print("Checking Windows audio forwarding...")
            if self.windows_audio.test_windows_audio():
                self.log_and_print("Windows audio forwarding available - will use for recording")
                self.use_windows_audio = True
                return True
            else:
                self.log_and_print("Windows audio forwarding not available")
                return False
            
        except asyncio.TimeoutError:
            self.log_and_print("ERROR: Timeout while checking PyAudio devices")
            return False
        except Exception as e:
            self.log_and_print(f"ERROR: Exception while checking PyAudio devices: {e}")
            return False
    
    async def test_speech_recognition(self):
        """Test speech recognition with logging"""
        self.log_and_print("Starting speech recognition...")
        
        try:
            # Start listening with timeout
            start_result = await asyncio.wait_for(
                self.server.handle_tool_call("start_listening", {
                    "model": "base",
                    "language": "en"
                }),
                timeout=30.0
            )
            
            if not start_result.get("success", False):
                self.log_and_print(f"ERROR: Failed to start listening: {start_result.get('error', 'Unknown error')}")
                return
            
            self.log_and_print(f"Speech recognition started - Model: {start_result['data']['model']}, Language: {start_result['data']['language']}, Sample Rate: {start_result['data']['sample_rate']} Hz")
            
            self.log_and_print(f"Listening for {self.test_duration} seconds - speak now...")
            
            # Monitor status during listening period
            await asyncio.sleep(self.test_duration)
            
            # Check final status
            status_result = await asyncio.wait_for(
                self.server.handle_tool_call("get_status", {}),
                timeout=5.0
            )
            if status_result.get("success", False):
                status_data = status_result["data"]
                self.log_and_print(f"Status check - Recording: {status_data.get('is_recording', False)}, Model loaded: {status_data.get('model_loaded', False)}")
            
            self.log_and_print("Listening period completed")
                
        except asyncio.TimeoutError:
            self.log_and_print("ERROR: Timeout during speech recognition")
        except KeyboardInterrupt:
            self.log_and_print("Test interrupted by user")
        except Exception as e:
            self.log_and_print(f"ERROR during listening: {e}")
        finally:
            # Always try to stop listening
            self.log_and_print("Stopping speech recognition...")
            try:
                stop_result = await asyncio.wait_for(
                    self.server.handle_tool_call("stop_listening", {}),
                    timeout=5.0
                )
                
                if stop_result.get("success", False):
                    self.log_and_print("Speech recognition stopped")
                else:
                    self.log_and_print(f"ERROR: Failed to stop listening: {stop_result.get('error', 'Unknown error')}")
            except asyncio.TimeoutError:
                self.log_and_print("ERROR: Timeout while stopping speech recognition")
            except Exception as e:
                self.log_and_print(f"ERROR while stopping: {e}")
    
    async def test_audio_transcription(self):
        """Test direct audio transcription by recording from microphone"""
        self.log_and_print("Starting direct audio transcription test...")
        
        try:
            if self.use_windows_audio:
                # Use Windows audio forwarding
                self.log_and_print(f"Recording audio via Windows for {self.test_duration} seconds - speak now...")
                
                # Record using Windows
                audio_file = self.windows_audio.record_audio(
                    duration=self.test_duration,
                    sample_rate=16000
                )
                
                self.log_and_print(f"Windows recording completed: {audio_file}")
                
                # Transcribe using MCP server file method
                result = await asyncio.wait_for(
                    self.server.handle_tool_call("transcribe_file", {
                        "file_path": audio_file,
                        "language": "en"
                    }),
                    timeout=30.0
                )
                
                if result.get("success", False):
                    data = result["data"]
                    self.log_and_print(f"Transcription completed successfully!")
                    self.log_and_print(f"Audio file: {audio_file}")
                    self.log_and_print(f"Transcribed text: '{data['text']}'")
                    self.log_and_print(f"Detected language: {data['language']} (confidence: {data['confidence']:.2f})")
                    
                    if data['text'].strip():
                        self.log_and_print("SUCCESS: Windows audio was transcribed successfully!")
                    else:
                        self.log_and_print("WARNING: No text was transcribed (silence or unclear audio)")
                else:
                    self.log_and_print(f"ERROR: Transcription failed: {result.get('error', 'Unknown error')}")
                    
            else:
                # Use standard Linux audio recording
                self.log_and_print(f"Recording audio for {self.test_duration} seconds - speak now...")
                
                result = await asyncio.wait_for(
                    self.server.handle_tool_call("record_and_transcribe", {
                        "duration": self.test_duration,
                        "language": "en"
                    }),
                    timeout=self.test_duration + 10.0  # Add extra time for processing
                )
                
                if result.get("success", False):
                    data = result["data"]
                    self.log_and_print(f"Recording completed successfully!")
                    self.log_and_print(f"Audio saved to: {data['audio_file']}")
                    self.log_and_print(f"Transcribed text: '{data['text']}'")
                    self.log_and_print(f"Detected language: {data['language']} (confidence: {data['confidence']:.2f})")
                    
                    if data['text'].strip():
                        self.log_and_print("SUCCESS: Audio was transcribed successfully!")
                    else:
                        self.log_and_print("WARNING: No text was transcribed (silence or unclear audio)")
                else:
                    self.log_and_print(f"ERROR: Recording failed: {result.get('error', 'Unknown error')}")
                
        except asyncio.TimeoutError:
            self.log_and_print("ERROR: Timeout during recording and transcription")
        except Exception as e:
            self.log_and_print(f"ERROR during recording and transcription: {e}")
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        self.log_and_print(f"Speech-to-text test starting (duration: {self.test_duration}s)")
        
        mic_available = await self.log_microphone_status()
        if not mic_available:
            self.log_and_print("ERROR: No microphone available")
            return
        
        await self.test_speech_recognition()
        await self.test_audio_transcription()
        
        self.log_and_print(f"Test completed - log saved to: {self.log_file.name}")


async def main():
    """Main test function"""
    print("Initializing speech-to-text tester...")
    
    try:
        tester = SpeechToTextTester()
        
        # Allow user to customize test duration
        if len(sys.argv) > 1:
            try:
                tester.test_duration = int(sys.argv[1])
                tester.log_and_print(f"Test duration: {tester.test_duration} seconds")
            except ValueError:
                tester.log_and_print(f"Invalid duration '{sys.argv[1]}', using default {tester.test_duration}s")
        
        await tester.run_all_tests()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("Speech-to-Text MCP Service Tester")
    print("Usage: python test_speech_to_text.py [duration_in_seconds]")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Test interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)