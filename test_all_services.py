#!/usr/bin/env python3
"""Test script to verify all services work in WSL environment"""

import asyncio
import sys
import subprocess
import time
from pathlib import Path

def test_service(service_path: str, name: str, timeout: int = 3):
    """Test if a service can start without errors"""
    print(f"Testing {name}...")
    try:
        # Run service for a short time to check for import/startup errors
        result = subprocess.run([
            sys.executable, service_path
        ], timeout=timeout, capture_output=True, text=True)
        
        if result.returncode is None:  # Process was terminated by timeout (expected)
            print(f"✓ {name}: Started successfully")
            return True
        else:
            print(f"✗ {name}: Exited with code {result.returncode}")
            if result.stderr:
                print(f"  Error: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"✓ {name}: Started successfully (timeout expected)")
        return True
    except Exception as e:
        print(f"✗ {name}: Exception - {e}")
        return False

def test_dependencies():
    """Test critical dependencies"""
    print("Testing Dependencies...")
    
    tests = [
        ("Python Audio", "import sounddevice; print('Audio OK')"),
        ("Whisper", "from faster_whisper import WhisperModel; print('Whisper OK')"),
        ("OpenCV", "import cv2; print('OpenCV OK')"),
        ("PIL", "from PIL import Image; print('PIL OK')"),  
        ("Mouse Control", "import pynput.mouse; print('Mouse OK')"),
        ("MCP Framework", "from mcp.server import Server; print('MCP OK')"),
        ("PowerShell Access", "import subprocess; subprocess.run(['powershell.exe', '-Command', 'Write-Output OK'], check=True)")
    ]
    
    for name, test_code in tests:
        try:
            subprocess.run([sys.executable, "-c", test_code], 
                         check=True, capture_output=True, text=True)
            print(f"✓ {name}")
        except Exception as e:
            print(f"✗ {name}: {e}")

async def main():
    print("Kiosk Voice Control System - Service Test")
    print("=" * 50)
    
    # Test dependencies first
    test_dependencies()
    print()
    
    # Test all services
    services = [
        ("services/speech_to_text/mcp_server.py", "Speech-to-Text Service"),
        ("services/screen_capture/mcp_screenshot_server.py", "Screen Capture Service"),
        ("services/mouse_control/mcp_server.py", "Mouse Control Service"),
        ("services/screen_detector/mcp_server.py", "Screen Detector Service"),
        ("services/ollama_agent/mcp_server.py", "Ollama Agent Service"),
        ("src/data_manager/mcp_server.py", "Data Manager Service")
    ]
    
    passed = 0
    total = len(services)
    
    for service_path, name in services:
        if Path(service_path).exists():
            if test_service(service_path, name):
                passed += 1
        else:
            print(f"✗ {name}: File not found - {service_path}")
    
    print()
    print(f"Results: {passed}/{total} services working")
    
    if passed == total:
        print("🎉 All services are working correctly!")
        print("\nNext steps:")
        print("1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh")
        print("2. Run orchestrator: python src/orchestrator/main.py")
        print("3. Test end-to-end workflow")
    else:
        print("⚠️  Some services need attention before full deployment")

if __name__ == "__main__":
    asyncio.run(main())