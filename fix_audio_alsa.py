#!/usr/bin/env python3
"""
ALSA Audio Fix for WSL
Creates a dummy ALSA device for testing
"""
import subprocess
import os
import tempfile

def create_alsa_config():
    """Create ALSA configuration for dummy device"""
    config = """
pcm.dummy {
    type hw
    card 0
    device 0
}

ctl.dummy {
    type hw
    card 0
}

pcm.!default {
    type plug
    slave.pcm "dummy"
}

ctl.!default {
    type hw
    card 0
}
"""
    
    # Write to home directory
    alsa_config_path = os.path.expanduser("~/.asoundrc")
    with open(alsa_config_path, 'w') as f:
        f.write(config)
    
    print(f"✓ Created ALSA config at {alsa_config_path}")
    return alsa_config_path

def test_alsa_devices():
    """Test ALSA device detection"""
    try:
        # List ALSA cards
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
        print("ALSA cards:")
        print(result.stdout)
        
        # List ALSA devices
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        print("ALSA recording devices:")
        print(result.stdout)
        
        return True
        
    except Exception as e:
        print(f"ALSA test failed: {e}")
        return False

def test_sounddevice_with_alsa():
    """Test sounddevice with ALSA backend"""
    try:
        # Set ALSA as audio backend
        os.environ['SDL_AUDIODRIVER'] = 'alsa'
        
        import sounddevice as sd
        
        # Force ALSA
        sd.default.hostapi = 0  # Usually ALSA is 0
        
        devices = sd.query_devices()
        print(f"SoundDevice with ALSA found {len(devices)} devices:")
        
        for i, device in enumerate(devices):
            print(f"  {i}: {device['name']} (in: {device['max_input_channels']}, out: {device['max_output_channels']})")
            
        return len(devices) > 0
        
    except Exception as e:
        print(f"SoundDevice ALSA test failed: {e}")
        return False

if __name__ == "__main__":
    print("ALSA Audio Fix for WSL")
    print("=" * 30)
    
    # Create ALSA config
    create_alsa_config()
    
    # Test ALSA
    print("\nTesting ALSA devices...")
    test_alsa_devices()
    
    # Test with sounddevice
    print("\nTesting sounddevice with ALSA...")
    if test_sounddevice_with_alsa():
        print("✓ Audio devices working with ALSA")
    else:
        print("✗ ALSA setup failed")
        print("Note: WSL may not have direct audio hardware access")