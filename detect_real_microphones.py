import subprocess
import json
import time

def detect_real_microphones():
    """
    Detect actual microphone devices, filtering out system devices
    """
    # More targeted PowerShell script for audio input devices
    ps_script = '''
    # Get actual audio recording devices from Windows Audio system
    Add-Type -AssemblyName System.Speech
    
    # Method 1: Get MMDevice API audio endpoints
    $devices = Get-CimInstance -ClassName Win32_PnPEntity | Where-Object {
        ($_.Name -match "microphone|mic" -and $_.Name -notmatch "microsoft|hyper-v|virtual|proxy|synth|management") -or
        ($_.Service -eq "ks" -and $_.Name -match "realtek.*audio") -or
        ($_.DeviceID -match "SWD\\MMDEVAPI" -and $_.Name -match "mic|microphone")
    }
    
    # Method 2: Also check for audio devices by class
    $audioDevices = Get-CimInstance -ClassName Win32_SoundDevice | Where-Object {
        $_.Name -notmatch "microsoft|hyper-v|virtual|proxy|synth|loopback" -and
        $_.Name -match "realtek|audio|mic|microphone"
    }
    
    # Combine results
    $allDevices = @()
    
    foreach ($device in $devices) {
        $allDevices += @{
            Name = $device.Name
            DeviceID = $device.DeviceID
            Status = $device.Status
            Present = $device.Present
            Type = "PnP"
        }
    }
    
    foreach ($device in $audioDevices) {
        $allDevices += @{
            Name = $device.Name
            DeviceID = $device.DeviceID
            Status = $device.Status
            Present = $device.Present
            Type = "SoundDevice"
        }
    }
    
    $allDevices | ConvertTo-Json
    '''
    
    try:
        result = subprocess.run(
            ['powershell.exe', '-Command', ps_script],
            capture_output=True, text=True, timeout=15
        )
        
        if result.returncode == 0 and result.stdout.strip():
            devices_json = result.stdout.strip()
            if devices_json and devices_json != "null":
                devices = json.loads(devices_json)
                return devices if isinstance(devices, list) else [devices]
        
        return []
        
    except Exception as e:
        print(f"Error querying microphones: {e}")
        return []

def is_jack_microphone(device_name, device_id):
    """
    Determine if this is likely a 3.5mm jack microphone
    """
    name_lower = device_name.lower()
    id_lower = device_id.lower()
    
    # Look for jack/line-in indicators
    jack_indicators = [
        'jack mic', 'line in', 'mic in', 'audio input',
        'front mic', 'rear mic', 'line-in'
    ]
    
    # Check if it's a Realtek device (common for 3.5mm jacks)
    is_realtek = 'realtek' in name_lower
    
    # Check for jack-specific terms
    has_jack_term = any(term in name_lower for term in jack_indicators)
    
    return is_realtek and (has_jack_term or 'jack' in name_lower)

def monitor_microphone_changes():
    """
    Monitor for microphone connection/disconnection
    """
    print("Refined Microphone Detection")
    print("=" * 40)
    
    devices = detect_real_microphones()
    
    if not devices:
        print("No microphones detected.")
        return
    
    print(f"Found {len(devices)} audio device(s):\n")
    
    jack_mics = []
    built_in_mics = []
    other_mics = []
    
    for i, device in enumerate(devices, 1):
        name = device.get('Name', 'Unknown')
        status = device.get('Status', 'Unknown')
        device_id = device.get('DeviceID', '')
        
        print(f"{i}. {name}")
        print(f"   Status: {status}")
        print(f"   Type: {device.get('Type', 'Unknown')}")
        
        # Categorize the device
        if is_jack_microphone(name, device_id):
            jack_mics.append(device)
            print("   🎤 -> 3.5mm Jack Microphone")
        elif 'array' in name.lower() or 'built-in' in name.lower():
            built_in_mics.append(device)
            print("   🔊 -> Built-in Microphone Array")
        else:
            other_mics.append(device)
            print("   ❓ -> Other Audio Device")
        
        print()
    
    # Summary
    print("Summary:")
    print(f"• 3.5mm Jack Microphones: {len(jack_mics)}")
    print(f"• Built-in Microphones: {len(built_in_mics)}")
    print(f"• Other Audio Devices: {len(other_mics)}")
    
    if jack_mics:
        print(f"\n✅ 3.5mm jack microphone detected: {jack_mics[0]['Name']}")
    else:
        print(f"\n❌ No 3.5mm jack microphone detected")
    
    return {
        'jack_mics': jack_mics,
        'built_in_mics': built_in_mics,
        'other_mics': other_mics
    }

def continuous_monitoring(interval=3):
    """
    Continuously monitor for microphone changes
    """
    print("Starting continuous microphone monitoring...")
    print("Plug/unplug your 3.5mm microphone to test detection.")
    print("Press Ctrl+C to stop.\n")
    
    last_jack_count = 0
    
    try:
        while True:
            devices = detect_real_microphones()
            
            # Count jack microphones
            current_jack_count = sum(1 for device in devices 
                                   if is_jack_microphone(device.get('Name', ''), 
                                                       device.get('DeviceID', '')))
            
            # Check for changes
            if current_jack_count != last_jack_count:
                timestamp = time.strftime('%H:%M:%S')
                if current_jack_count > last_jack_count:
                    print(f"[{timestamp}] 🎤 3.5mm microphone CONNECTED")
                else:
                    print(f"[{timestamp}] 🎤 3.5mm microphone DISCONNECTED")
                
                last_jack_count = current_jack_count
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")

if __name__ == "__main__":
    # Run initial detection
    result = monitor_microphone_changes()
    
    # Ask if user wants continuous monitoring
    print("\nWould you like to start continuous monitoring? (y/n): ", end="")
    try:
        choice = input().lower().strip()
        if choice in ['y', 'yes']:
            continuous_monitoring()
    except:
        print("\nExiting...")
