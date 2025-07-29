#!/usr/bin/env python3
"""
Direct test of screenshot functionality without MCP wrapper
Tests each screenshot method individually
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the services directory to Python path
sys.path.append(str(Path(__file__).parent / "services" / "screen_capture"))

async def test_screenshot_methods():
    """Test each screenshot method individually"""
    
    print("🔬 Direct Screenshot Method Testing")
    print("=" * 40)
    
    # Import the MCP server to get the functions
    import mcp_server
    
    # Get the actual screenshot function
    screenshot_func = None
    screen_info_func = None
    
    # Access the functions directly from the module
    # The functions are decorated with @mcp.tool() so they're available in the module
    if hasattr(mcp_server, 'screen_capture_take_screenshot'):
        screenshot_func = mcp_server.screen_capture_take_screenshot
    
    if hasattr(mcp_server, 'get_screen_info'):
        screen_info_func = mcp_server.get_screen_info
    
    print(f"📋 Found functions: screenshot={screenshot_func is not None}, screen_info={screen_info_func is not None}")
    
    # Test screen info
    if screen_info_func:
        try:
            print("📏 Testing screen info...")
            result = await screen_info_func()
            print(f"✅ Screen info: {result}")
        except Exception as e:
            print(f"❌ Screen info failed: {e}")
    
    # Test screenshot
    if screenshot_func:
        try:
            print("\n📸 Testing screenshot capture...")
            result = await screenshot_func()
            
            print(f"📊 Result type: {type(result)}")
            print(f"📊 Result: {result}")
            
            if isinstance(result, dict):
                if result.get('success'):
                    data = result.get('data', {})
                    method = data.get('method', 'unknown')
                    path = data.get('screenshot_path', '')
                    errors = data.get('errors', [])
                    
                    print(f"✅ Success! Method: {method}")
                    print(f"📁 Path: {path}")
                    
                    if errors:
                        print(f"⚠️  Errors encountered:")
                        for error in errors:
                            print(f"   - {error}")
                    
                    # Check file
                    if path:
                        full_path = Path("web_app/static") / path.lstrip('/')
                        if full_path.exists():
                            size = full_path.stat().st_size
                            print(f"📁 File created: {full_path} ({size} bytes)")
                            
                            # Analyze image
                            try:
                                from PIL import Image
                                with Image.open(full_path) as img:
                                    print(f"🖼️  Image: {img.size} {img.mode}")
                                    
                                    # Check if it looks like a real screenshot
                                    if 'simulated' in method.lower():
                                        print("🎭 This is a simulated/mock screenshot")
                                    else:
                                        print("📸 This appears to be a real screenshot attempt")
                            except Exception as e:
                                print(f"⚠️  Image analysis error: {e}")
                        else:
                            print(f"❌ File not found: {full_path}")
                else:
                    error = result.get('error', 'Unknown error')
                    print(f"❌ Screenshot failed: {error}")
            else:
                print(f"❌ Unexpected result format: {result}")
                
        except Exception as e:
            print(f"❌ Screenshot test failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ Screenshot function not found in MCP tools")

def analyze_wsl_environment():
    """Analyze WSL environment for screenshot capabilities"""
    
    print("\n🔍 WSL Environment Analysis")
    print("=" * 30)
    
    # Check WSL version
    try:
        with open('/proc/version', 'r') as f:
            version = f.read().strip()
            print(f"🐧 Kernel: {version}")
    except:
        pass
    
    # Check if WSL can access Windows
    windows_paths = [
        Path("/mnt/c/Windows"),
        Path("/mnt/c/Users"),
        Path("/mnt/c/Program Files")
    ]
    
    for path in windows_paths:
        if path.exists():
            print(f"✅ Windows access: {path}")
        else:
            print(f"❌ No access: {path}")
    
    # Check for Windows executables
    windows_exes = ["powershell.exe", "cmd.exe", "python.exe"]
    
    for exe in windows_exes:
        try:
            import subprocess
            result = subprocess.run(["which", exe], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Found: {exe} at {result.stdout.strip()}")
            else:
                print(f"❌ Not found: {exe}")
        except:
            print(f"❓ Could not check: {exe}")
    
    # Test PowerShell access
    try:
        import subprocess
        result = subprocess.run(["powershell.exe", "-Command", "Get-Host"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ PowerShell accessible from WSL")
        else:
            print(f"❌ PowerShell failed: {result.stderr}")
    except Exception as e:
        print(f"❌ PowerShell test failed: {e}")

async def main():
    """Main test function"""
    
    print("🎯 Direct Screenshot Testing")
    print("=" * 40)
    
    analyze_wsl_environment()
    await test_screenshot_methods()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()