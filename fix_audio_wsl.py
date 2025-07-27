#!/usr/bin/env python3
"""
WSL Audio Fix Script
Attempts to configure audio devices for WSL environment
"""
import os
import subprocess
import sys

def setup_wsl_audio():
    """Set up WSL audio environment variables and test"""
    print("Setting up WSL audio environment...")
    
    # Set WSL audio environment variables
    env_vars = {
        'PULSE_SERVER': 'unix:/mnt/wslg/PulseServer',
        'XDG_RUNTIME_DIR': '/mnt/wslg/runtime-dir/kiosk_user',
        'WAYLAND_DISPLAY': 'wayland-0',
        'DISPLAY': ':0'
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"Set {key}={value}")
    
    # Test PulseAudio connection
    try:
        result = subprocess.run(['pactl', 'info'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ PulseAudio connection successful")
            return True
        else:
            print(f"✗ PulseAudio connection failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ PulseAudio test failed: {e}")
        return False

def create_dummy_audio_device():
    """Create a dummy audio device for testing"""
    try:
        # Load dummy module
        subprocess.run(['pactl', 'load-module', 'module-null-sink', 
                       'sink_name=dummy_sink'], 
                      capture_output=True, timeout=5)
        subprocess.run(['pactl', 'load-module', 'module-null-source', 
                       'source_name=dummy_source'], 
                      capture_output=True, timeout=5)
        print("✓ Created dummy audio devices")
        return True
    except Exception as e:
        print(f"✗ Failed to create dummy devices: {e}")
        return False

def test_sounddevice():
    """Test sounddevice functionality"""
    try:
        import sounddevice as sd
        
        # Set environment for sounddevice
        setup_wsl_audio()
        
        devices = sd.query_devices()
        print(f"Found {len(devices)} audio devices:")
        
        for i, device in enumerate(devices):
            print(f"  {i}: {device['name']} (in: {device['max_input_channels']}, out: {device['max_output_channels']})")
        
        if len(devices) == 0:
            print("No devices found, trying to use ALSA...")
            # Try ALSA backend
            os.environ['SDL_AUDIODRIVER'] = 'alsa'
            
        return len(devices) > 0
        
    except Exception as e:
        print(f"✗ sounddevice test failed: {e}")
        return False

if __name__ == "__main__":
    print("WSL Audio Configuration Tool")
    print("=" * 40)
    
    # Step 1: Setup environment
    if setup_wsl_audio():
        print("✓ WSL audio environment configured")
    else:
        print("✗ WSL audio environment setup failed")
        create_dummy_audio_device()
    
    # Step 2: Test sounddevice
    if test_sounddevice():
        print("✓ Audio devices detected successfully")
    else:
        print("✗ No audio devices detected")
        print("Recommendation: Use Windows audio pass-through or install PipeWire")
        sys.exit(1)
    
    print("\nAudio setup complete!")