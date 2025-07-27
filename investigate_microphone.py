#!/usr/bin/env python3
"""
Comprehensive microphone detection script using multiple methods.
Tests various audio libraries and approaches to find microphones.
"""
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"microphone_investigation_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def log_and_print(message):
    """Log and print with immediate flush"""
    print(message)
    sys.stdout.flush()
    logger.info(message)

def run_command(cmd, description):
    """Run a shell command and log results"""
    log_and_print(f"🔍 {description}")
    log_and_print(f"   Command: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            if result.stdout.strip():
                log_and_print(f"   ✅ Output: {result.stdout.strip()}")
            else:
                log_and_print(f"   ✅ Command succeeded (no output)")
        else:
            log_and_print(f"   ❌ Error: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        log_and_print(f"   ⏰ Command timed out")
    except Exception as e:
        log_and_print(f"   ❌ Exception: {e}")
    log_and_print("")

def test_sounddevice():
    """Test sounddevice library detection"""
    log_and_print("=" * 60)
    log_and_print("🎤 TESTING SOUNDDEVICE LIBRARY")
    log_and_print("=" * 60)
    
    try:
        import sounddevice as sd
        log_and_print("✅ sounddevice library imported successfully")
        
        # Query devices
        log_and_print("🔍 Querying all devices...")
        devices = sd.query_devices()
        log_and_print(f"   Total devices found: {len(devices)}")
        
        input_devices = []
        for i, device in enumerate(devices):
            log_and_print(f"   Device {i}: {device}")
            if device['max_input_channels'] > 0:
                input_devices.append(device)
        
        log_and_print(f"✅ Input devices found: {len(input_devices)}")
        for device in input_devices:
            log_and_print(f"   • {device['name']} - {device['max_input_channels']} channels")
        
        # Test default device
        try:
            log_and_print("🔍 Testing default input device...")
            default_device = sd.query_devices(kind='input')
            log_and_print(f"   Default input: {default_device}")
        except Exception as e:
            log_and_print(f"   ❌ No default input device: {e}")
        
    except ImportError:
        log_and_print("❌ sounddevice library not available")
    except Exception as e:
        log_and_print(f"❌ sounddevice error: {e}")
    log_and_print("")

def test_pyaudio():
    """Test PyAudio library detection"""
    log_and_print("=" * 60)
    log_and_print("🎤 TESTING PYAUDIO LIBRARY")
    log_and_print("=" * 60)
    
    try:
        import pyaudio
        log_and_print("✅ PyAudio library imported successfully")
        
        # Initialize PyAudio
        pa = pyaudio.PyAudio()
        device_count = pa.get_device_count()
        log_and_print(f"   Total devices found: {device_count}")
        
        input_devices = []
        for i in range(device_count):
            device_info = pa.get_device_info_by_index(i)
            log_and_print(f"   Device {i}: {device_info}")
            if device_info['maxInputChannels'] > 0:
                input_devices.append(device_info)
        
        log_and_print(f"✅ Input devices found: {len(input_devices)}")
        for device in input_devices:
            log_and_print(f"   • {device['name']} - {device['maxInputChannels']} channels")
        
        # Test default device
        try:
            default_input = pa.get_default_input_device_info()
            log_and_print(f"   Default input: {default_input}")
        except Exception as e:
            log_and_print(f"   ❌ No default input device: {e}")
        
        pa.terminate()
        
    except ImportError:
        log_and_print("❌ PyAudio library not available")
        log_and_print("   Install with: pip install pyaudio")
    except Exception as e:
        log_and_print(f"❌ PyAudio error: {e}")
    log_and_print("")

def test_wave_recording():
    """Test if we can record audio using wave module"""
    log_and_print("=" * 60)
    log_and_print("🎤 TESTING WAVE RECORDING")
    log_and_print("=" * 60)
    
    try:
        import wave
        import struct
        log_and_print("✅ Wave module available")
        log_and_print("   Note: Wave module requires a working audio input source")
    except ImportError:
        log_and_print("❌ Wave module not available")
    log_and_print("")

def test_system_commands():
    """Test system-level audio commands"""
    log_and_print("=" * 60)
    log_and_print("🎤 TESTING SYSTEM AUDIO COMMANDS")
    log_and_print("=" * 60)
    
    commands = [
        ("arecord -l", "List ALSA recording devices"),
        ("arecord -L", "List ALSA recording device names"),
        ("pactl list sources", "List PulseAudio sources"),
        ("pactl list source-outputs", "List PulseAudio source outputs"),
        ("pulseaudio --check", "Check PulseAudio daemon"),
        ("cat /proc/asound/cards", "Check ALSA sound cards"),
        ("cat /proc/asound/devices", "Check ALSA devices"),
        ("ls -la /dev/snd/", "List sound device nodes"),
        ("lsmod | grep snd", "List sound kernel modules"),
        ("dmesg | grep -i audio", "Check kernel audio messages"),
        ("which arecord", "Check if arecord is available"),
        ("which pactl", "Check if pactl is available"),
    ]
    
    for cmd, desc in commands:
        run_command(cmd, desc)

def test_wsl_specific():
    """Test WSL-specific audio configurations"""
    log_and_print("=" * 60)
    log_and_print("🎤 TESTING WSL-SPECIFIC AUDIO")
    log_and_print("=" * 60)
    
    # Check if we're in WSL
    try:
        with open('/proc/version', 'r') as f:
            version = f.read()
            if 'microsoft' in version.lower() or 'wsl' in version.lower():
                log_and_print("✅ Running in WSL environment")
                log_and_print(f"   Version: {version.strip()}")
            else:
                log_and_print("❌ Not running in WSL")
                log_and_print(f"   Version: {version.strip()}")
    except Exception as e:
        log_and_print(f"❌ Could not determine environment: {e}")
    
    # Check WSL-specific configurations
    wsl_commands = [
        ("wsl.exe --version", "WSL version"),
        ("cat /etc/wsl.conf", "WSL configuration"),
        ("env | grep WSL", "WSL environment variables"),
        ("mount | grep drvfs", "Windows drive mounts"),
    ]
    
    for cmd, desc in wsl_commands:
        run_command(cmd, desc)
    
    log_and_print("")

def test_alternative_libraries():
    """Test alternative audio libraries"""
    log_and_print("=" * 60)
    log_and_print("🎤 TESTING ALTERNATIVE AUDIO LIBRARIES")
    log_and_print("=" * 60)
    
    # Test pydub
    try:
        from pydub import AudioSegment
        from pydub.utils import which
        log_and_print("✅ pydub library available")
        
        # Check for ffmpeg
        ffmpeg_path = which("ffmpeg")
        if ffmpeg_path:
            log_and_print(f"   ✅ ffmpeg found at: {ffmpeg_path}")
        else:
            log_and_print("   ❌ ffmpeg not found")
    except ImportError:
        log_and_print("❌ pydub library not available")
    
    # Test speech_recognition
    try:
        import speech_recognition as sr
        log_and_print("✅ speech_recognition library available")
        
        r = sr.Recognizer()
        mics = sr.Microphone.list_microphone_names()
        log_and_print(f"   Microphones found: {len(mics)}")
        for i, mic in enumerate(mics):
            log_and_print(f"   • Mic {i}: {mic}")
    except ImportError:
        log_and_print("❌ speech_recognition library not available")
    except Exception as e:
        log_and_print(f"❌ speech_recognition error: {e}")
    
    log_and_print("")

def main():
    """Run all microphone detection tests"""
    log_and_print("=" * 80)
    log_and_print("🔍 COMPREHENSIVE MICROPHONE DETECTION INVESTIGATION")
    log_and_print("=" * 80)
    log_and_print(f"📝 Log file: {Path(log_file).absolute()}")
    log_and_print("")
    
    # Run all tests
    test_system_commands()
    test_wsl_specific()
    test_sounddevice()
    test_pyaudio()
    test_wave_recording()
    test_alternative_libraries()
    
    log_and_print("=" * 80)
    log_and_print("✅ INVESTIGATION COMPLETED")
    log_and_print("=" * 80)
    log_and_print("Summary:")
    log_and_print("• Check the log file for detailed results")
    log_and_print("• If no devices found, audio may not be properly configured in WSL")
    log_and_print("• Consider using Windows host audio tools or configuring WSL audio")
    log_and_print(f"📝 Full log saved to: {Path(log_file).absolute()}")

if __name__ == "__main__":
    main()