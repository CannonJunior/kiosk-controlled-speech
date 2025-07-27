#!/usr/bin/env python3
"""
Windows Audio Capture via WSL
Uses Windows PowerShell to record audio and transfer to WSL
"""
import subprocess
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

class WindowsAudioCapture:
    def __init__(self):
        self.temp_dir = Path("/tmp/audio_capture")
        self.temp_dir.mkdir(exist_ok=True)
        
    def record_audio(self, duration=5, sample_rate=16000, output_file=None):
        """Record audio using Windows PowerShell script"""
        try:
            # Generate output filename if not provided
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"recorded_audio_{timestamp}.wav"
            
            # Windows temp path (accessible from WSL)
            windows_temp_file = f"C:\\temp\\{Path(output_file).name}"
            wsl_output_path = self.temp_dir / Path(output_file).name
            
            print(f"Recording audio for {duration} seconds using Windows...")
            print(f"Windows temp file: {windows_temp_file}")
            print(f"WSL output file: {wsl_output_path}")
            
            # Create Windows temp directory
            subprocess.run([
                "powershell.exe", "-Command", 
                "New-Item -ItemType Directory -Force -Path C:\\temp"
            ], check=True, capture_output=True)
            
            # Get the PowerShell script path in Windows format
            script_path = Path(__file__).parent / "windows_audio_recorder.ps1"
            windows_script_path = subprocess.run([
                "wslpath", "-w", str(script_path)
            ], capture_output=True, text=True, check=True).stdout.strip()
            
            # Run PowerShell audio recording script
            ps_command = f"""
                & '{windows_script_path}' -Duration {duration} -OutputFile '{windows_temp_file}' -SampleRate {sample_rate}
            """
            
            result = subprocess.run([
                "powershell.exe", "-ExecutionPolicy", "Bypass", "-Command", ps_command
            ], capture_output=True, text=True, timeout=duration + 30)
            
            if result.returncode != 0:
                raise Exception(f"PowerShell recording failed: {result.stderr}")
            
            print("Windows recording completed, transferring to WSL...")
            print(f"PowerShell output: {result.stdout}")
            
            # Convert Windows path to WSL path and copy file
            wsl_temp_path = subprocess.run([
                "wslpath", windows_temp_file
            ], capture_output=True, text=True, check=True).stdout.strip()
            
            if os.path.exists(wsl_temp_path):
                shutil.copy2(wsl_temp_path, wsl_output_path)
                print(f"Audio file transferred to: {wsl_output_path}")
                
                # Clean up Windows temp file
                subprocess.run([
                    "powershell.exe", "-Command", f"Remove-Item '{windows_temp_file}' -ErrorAction SilentlyContinue"
                ], capture_output=True)
                
                return str(wsl_output_path)
            else:
                raise Exception(f"Windows recording file not found: {wsl_temp_path}")
                
        except subprocess.TimeoutExpired:
            raise Exception(f"Recording timeout after {duration + 30} seconds")
        except subprocess.CalledProcessError as e:
            raise Exception(f"Windows command failed: {e}")
        except Exception as e:
            raise Exception(f"Windows audio capture failed: {e}")
    
    def test_windows_audio(self):
        """Test Windows audio capture functionality"""
        try:
            print("Testing Windows audio capture...")
            
            # Test PowerShell availability
            result = subprocess.run([
                "powershell.exe", "-Command", "Get-Host | Select-Object Version"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print("✓ PowerShell available")
                print(f"PowerShell version info: {result.stdout.strip()}")
            else:
                print("✗ PowerShell not available")
                return False
            
            # Test audio devices via PowerShell
            ps_audio_test = """
                Add-Type -AssemblyName System.Speech
                try {
                    $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
                    $recognizer.SetInputToDefaultAudioDevice()
                    Write-Host "Audio device available"
                    $recognizer.Dispose()
                } catch {
                    Write-Host "No audio device: $($_.Exception.Message)"
                }
            """
            
            result = subprocess.run([
                "powershell.exe", "-Command", ps_audio_test
            ], capture_output=True, text=True, timeout=15)
            
            print(f"Audio device test: {result.stdout.strip()}")
            
            return "Audio device available" in result.stdout
            
        except Exception as e:
            print(f"Windows audio test failed: {e}")
            return False

def main():
    """Test Windows audio capture"""
    capture = WindowsAudioCapture()
    
    # Test Windows audio availability
    if not capture.test_windows_audio():
        print("Windows audio capture not available")
        return False
    
    try:
        # Record a short test
        audio_file = capture.record_audio(duration=3)
        print(f"✓ Test recording successful: {audio_file}")
        
        # Check file exists and has content
        if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
            print(f"✓ Audio file created successfully ({os.path.getsize(audio_file)} bytes)")
            return True
        else:
            print("✗ Audio file empty or missing")
            return False
            
    except Exception as e:
        print(f"✗ Test recording failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)