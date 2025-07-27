#!/usr/bin/env python3
"""
WSL Audio Setup and Testing Script
Attempts various methods to enable audio in WSL environment.
"""
import subprocess
import sys
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"wsl_audio_setup_{timestamp}.log"

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

def run_command(cmd, description, ignore_errors=False):
    """Run a shell command and log results"""
    log_and_print(f"🔧 {description}")
    log_and_print(f"   Command: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 or ignore_errors:
            if result.stdout.strip():
                log_and_print(f"   ✅ Output: {result.stdout.strip()}")
            else:
                log_and_print(f"   ✅ Command completed")
            if result.stderr.strip() and not ignore_errors:
                log_and_print(f"   ⚠️ Warnings: {result.stderr.strip()}")
        else:
            log_and_print(f"   ❌ Error: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        log_and_print(f"   ⏰ Command timed out")
        return False
    except Exception as e:
        log_and_print(f"   ❌ Exception: {e}")
        return False
    log_and_print("")
    return True

def setup_pulseaudio():
    """Try to setup PulseAudio in WSL"""
    log_and_print("=" * 60)
    log_and_print("🔊 SETTING UP PULSEAUDIO")
    log_and_print("=" * 60)
    
    # Kill existing PulseAudio processes
    run_command("pkill -f pulseaudio", "Killing existing PulseAudio processes", ignore_errors=True)
    
    # Try to start PulseAudio
    log_and_print("🔧 Attempting to start PulseAudio...")
    run_command("pulseaudio --start --log-target=stderr", "Starting PulseAudio daemon", ignore_errors=True)
    
    # Check if PulseAudio is running
    run_command("pulseaudio --check -v", "Checking PulseAudio status")
    
    # Try with different configurations
    run_command("pulseaudio --start --load='module-native-protocol-tcp auth-ip-acl=127.0.0.1'", "Starting PulseAudio with TCP", ignore_errors=True)

def setup_alsa():
    """Try to setup ALSA"""
    log_and_print("=" * 60)
    log_and_print("🔊 SETTING UP ALSA")
    log_and_print("=" * 60)
    
    # Check ALSA configuration
    run_command("cat /etc/asound.conf", "Checking global ALSA config", ignore_errors=True)
    run_command("cat ~/.asoundrc", "Checking user ALSA config", ignore_errors=True)
    
    # Try to create a basic ALSA config
    asound_conf = """
pcm.!default {
    type pulse
}
ctl.!default {
    type pulse
}
"""
    
    try:
        with open("/tmp/asoundrc_test", "w") as f:
            f.write(asound_conf)
        log_and_print("✅ Created test ALSA configuration")
        run_command("cp /tmp/asoundrc_test ~/.asoundrc", "Installing ALSA config", ignore_errors=True)
    except Exception as e:
        log_and_print(f"❌ Failed to create ALSA config: {e}")

def test_windows_audio_bridge():
    """Test Windows audio bridging methods"""
    log_and_print("=" * 60)
    log_and_print("🔊 TESTING WINDOWS AUDIO BRIDGE")
    log_and_print("=" * 60)
    
    # Check if we can access Windows audio via WSL
    run_command("ls /mnt/c/Windows/System32/", "Checking Windows system access", ignore_errors=True)
    
    # Try to use Windows audio tools
    run_command("cmd.exe /c 'echo Testing Windows command access'", "Testing Windows command access", ignore_errors=True)
    
    # Check for Windows audio devices via PowerShell
    run_command("powershell.exe 'Get-WmiObject -Class Win32_SoundDevice'", "Querying Windows audio devices", ignore_errors=True)

def install_audio_packages():
    """Install additional audio packages"""
    log_and_print("=" * 60)
    log_and_print("📦 INSTALLING AUDIO PACKAGES")
    log_and_print("=" * 60)
    
    packages = [
        "alsa-utils",
        "pulseaudio",
        "pulseaudio-utils", 
        "libasound2-dev",
        "portaudio19-dev",
        "sox",
        "ffmpeg"
    ]
    
    for package in packages:
        run_command(f"sudo apt-get install -y {package}", f"Installing {package}", ignore_errors=True)

def test_alternative_methods():
    """Test alternative audio access methods"""
    log_and_print("=" * 60)
    log_and_print("🔊 TESTING ALTERNATIVE METHODS")
    log_and_print("=" * 60)
    
    # Test with updated libraries
    try:
        import speech_recognition as sr
        log_and_print("✅ SpeechRecognition library imported")
        
        r = sr.Recognizer()
        mics = sr.Microphone.list_microphone_names()
        log_and_print(f"   Microphones found: {len(mics)}")
        for i, mic in enumerate(mics):
            log_and_print(f"   • Mic {i}: {mic}")
            
    except Exception as e:
        log_and_print(f"❌ SpeechRecognition error: {e}")
    
    # Test PyAudio if available
    try:
        import pyaudio
        log_and_print("✅ PyAudio library imported")
        
        pa = pyaudio.PyAudio()
        device_count = pa.get_device_count()
        log_and_print(f"   PyAudio devices found: {device_count}")
        
        for i in range(device_count):
            device_info = pa.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                log_and_print(f"   • Input Device {i}: {device_info['name']}")
        
        pa.terminate()
        
    except ImportError:
        log_and_print("❌ PyAudio not available")
    except Exception as e:
        log_and_print(f"❌ PyAudio error: {e}")

def provide_solutions():
    """Provide potential solutions for WSL audio"""
    log_and_print("=" * 60)
    log_and_print("💡 POTENTIAL SOLUTIONS")
    log_and_print("=" * 60)
    
    solutions = [
        "1. Enable WSL audio in Windows:",
        "   • Install WSL with GUI support (WSLg)",
        "   • Ensure Windows audio service is running",
        "   • Check Windows microphone permissions",
        "",
        "2. Use Windows host for audio processing:",
        "   • Run speech recognition on Windows host",
        "   • Use named pipes or TCP to communicate with WSL",
        "   • Process audio in Windows, send text to WSL",
        "",
        "3. Install additional WSL audio drivers:",
        "   • sudo apt update && sudo apt install pulseaudio",
        "   • Configure /etc/pulse/default.pa",
        "   • Set PULSE_RUNTIME_PATH environment variable",
        "",
        "4. Use USB audio device:",
        "   • USB audio devices sometimes work better in WSL",
        "   • May need USB/IP forwarding configuration",
        "",
        "5. Alternative: Use web-based audio:",
        "   • Browser-based speech recognition",
        "   • WebRTC audio capture",
        "   • Send results to WSL via websocket/HTTP"
    ]
    
    for solution in solutions:
        log_and_print(solution)

def main():
    """Run WSL audio setup"""
    log_and_print("=" * 80)
    log_and_print("🔧 WSL AUDIO SETUP AND CONFIGURATION")
    log_and_print("=" * 80)
    log_and_print(f"📝 Log file: {Path(log_file).absolute()}")
    log_and_print("")
    
    # Run setup steps
    install_audio_packages()
    setup_alsa()
    setup_pulseaudio()
    test_windows_audio_bridge()
    test_alternative_methods()
    provide_solutions()
    
    log_and_print("=" * 80)
    log_and_print("✅ WSL AUDIO SETUP COMPLETED")
    log_and_print("=" * 80)
    log_and_print("Next steps:")
    log_and_print("• Review the solutions above")
    log_and_print("• Consider using Windows host for audio processing")
    log_and_print("• Test with a USB audio device if available")
    log_and_print(f"📝 Full log saved to: {Path(log_file).absolute()}")

if __name__ == "__main__":
    main()