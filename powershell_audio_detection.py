import subprocess
import json
import re

def detect_audio_devices():
    """
    Detect audio devices by querying Windows directly
    """
    # PowerShell script to get audio devices
    ps_script = '''
    # Get recording devices (microphones)
    $recording = Get-WmiObject -Query "SELECT * FROM Win32_SoundDevice WHERE DeviceID LIKE '%MICROPHONE%' OR Name LIKE '%microphone%' OR Name LIKE '%mic%'"
    
    # Get all audio devices and filter for input devices
    $allAudio = Get-CimInstance -ClassName Win32_PnPEntity | Where-Object {
        $_.PNPClass -eq "AudioEndpoint" -or 
        $_.Service -eq "AudioEndpoint" -or
        $_.Name -match "microphone|mic|audio input|recording"
    }
    
    # Combine and format results
    $devices = @()
    foreach ($device in $allAudio) {
        $devices += @{
            Name = $device.Name
            DeviceID = $device.DeviceID
            Status = $device.Status
            Present = $device.Present
        }
    }
    
    $devices | ConvertTo-Json
    '''
    
    try:
        result = subprocess.run(
            ['powershell.exe', '-Command', ps_script],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Parse JSON output
            devices_json = result.stdout.strip()
            if devices_json and devices_json != "null":
                devices = json.loads(devices_json)
                return devices if isinstance(devices, list) else [devices]
        
        print("No devices found or JSON parsing failed")
        return []
        
    except subprocess.TimeoutExpired:
        print("PowerShell query timed out")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Raw output: {result.stdout}")
        return []
    except Exception as e:
        print(f"Error querying Windows audio: {e}")
        return []

def monitor_microphone_connection():
    """
    Monitor for microphone connection changes
    """
    print("Checking for audio devices...")
    devices = detect_audio_devices()
    
    microphones = []
    for device in devices:
        name = device.get('Name', '').lower()
        if any(term in name for term in ['microphone', 'mic', 'audio input', 'recording']):
            microphones.append(device)
    
    print(f"\nFound {len(microphones)} potential microphone(s):")
    for i, mic in enumerate(microphones, 1):
        status = mic.get('Status', 'Unknown')
        present = mic.get('Present', 'Unknown')
        print(f"{i}. {mic.get('Name', 'Unknown Device')}")
        print(f"   Status: {status}, Present: {present}")
        print(f"   Device ID: {mic.get('DeviceID', 'N/A')[:50]}...")
    
    return microphones

# Test the detection
if __name__ == "__main__":
    monitor_microphone_connection()
