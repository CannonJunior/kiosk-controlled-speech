#!/usr/bin/env python3
"""
Test script for MCP screenshot tool from WSL
Tests the screen capture functionality directly using MCP client
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add the services directory to Python path
sys.path.append(str(Path(__file__).parent / "services" / "screen_capture"))

try:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
except ImportError:
    print("MCP client not available. Installing...")
    os.system("pip install mcp")
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

async def test_mcp_screenshot():
    """Test the MCP screenshot tool using subprocess"""
    
    print("🧪 Testing MCP Screenshot Tool via Subprocess")
    print("=" * 50)
    
    # Path to the MCP server script
    server_script = Path(__file__).parent / "services" / "screen_capture" / "mcp_server.py"
    
    if not server_script.exists():
        print(f"❌ MCP server script not found at: {server_script}")
        return False
    
    print(f"📁 Using MCP server: {server_script}")
    
    try:
        import subprocess
        
        # Run the MCP server directly as a test
        print("🚀 Running MCP server directly...")
        
        result = subprocess.run([
            "python3", str(server_script)
        ], capture_output=True, text=True, timeout=10, input="")
        
        print(f"📤 Return code: {result.returncode}")
        print(f"📝 stdout: {result.stdout}")
        if result.stderr:
            print(f"⚠️  stderr: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("⏰ MCP server timed out (expected for server)")
    except Exception as e:
        print(f"❌ MCP subprocess failed: {e}")
        return False
    
    print("\n🎯 Subprocess test completed")
    return True

async def test_direct_function_calls():
    """Test calling the screenshot functions directly"""
    
    print("\n🔬 Testing Direct Function Calls")
    print("=" * 30)
    
    try:
        # Change to the correct directory and import
        original_path = sys.path[:]
        sys.path.insert(0, str(Path(__file__).parent / "services" / "screen_capture"))
        
        # Import the server module 
        import mcp_server
        
        print("✅ MCP server module imported successfully")
        
        # Get the actual functions from the FastMCP app
        app = mcp_server.mcp
        
        # Find the registered tools
        tools = []
        if hasattr(app, '_tools'):
            tools = list(app._tools.values())
            print(f"🛠️  Found {len(tools)} registered tools")
            for tool in tools:
                print(f"   - {tool.__name__}")
        
        # Test screen info function directly
        try:
            print("\n📏 Testing get_screen_info...")
            screen_info_func = None
            for tool in tools:
                if tool.__name__ == 'get_screen_info':
                    screen_info_func = tool
                    break
            
            if screen_info_func:
                screen_info = await screen_info_func()
                print(f"✅ Screen info: {screen_info}")
            else:
                print("❌ get_screen_info function not found")
                
        except Exception as e:
            print(f"⚠️  Screen info failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test screenshot function directly
        try:
            print("\n📸 Testing screen_capture_take_screenshot...")
            screenshot_func = None
            for tool in tools:
                if tool.__name__ == 'screen_capture_take_screenshot':
                    screenshot_func = tool
                    break
            
            if screenshot_func:
                print("🚀 Calling screenshot function...")
                screenshot_result = await screenshot_func()
                print(f"📸 Screenshot result type: {type(screenshot_result)}")
                print(f"📸 Screenshot result: {screenshot_result}")
                
                if isinstance(screenshot_result, dict):
                    if screenshot_result.get('success'):
                        screenshot_path = screenshot_result.get('data', {}).get('screenshot_path')
                        method = screenshot_result.get('data', {}).get('method', 'unknown')
                        print(f"✅ Screenshot created using: {method}")
                        
                        if screenshot_path:
                            full_path = Path("web_app/static") / screenshot_path.lstrip('/')
                            if full_path.exists():
                                file_size = full_path.stat().st_size
                                print(f"✅ Screenshot file: {full_path}")
                                print(f"📁 Size: {file_size} bytes")
                                
                                # Analyze the image
                                try:
                                    from PIL import Image
                                    with Image.open(full_path) as img:
                                        print(f"🖼️  Dimensions: {img.size}")
                                        print(f"🎨 Mode: {img.mode}")
                                        
                                        # Check if it's a real screenshot or mock
                                        if img.size == (1920, 1080) and 'simulated' in method:
                                            print("🎭 This appears to be a simulated screenshot")
                                        else:
                                            print("📸 This appears to be a real screenshot")
                                            
                                except Exception as img_error:
                                    print(f"⚠️  Image analysis failed: {img_error}")
                            else:
                                print(f"❌ File not found: {full_path}")
                    else:
                        error_msg = screenshot_result.get('error', 'Unknown error')
                        print(f"❌ Screenshot failed: {error_msg}")
                else:
                    print(f"❌ Unexpected result type: {type(screenshot_result)}")
            else:
                print("❌ screen_capture_take_screenshot function not found")
                
        except Exception as e:
            print(f"❌ Direct screenshot failed: {e}")
            import traceback
            traceback.print_exc()
            
        # Restore path
        sys.path[:] = original_path
            
    except ImportError as e:
        print(f"❌ Cannot import MCP server: {e}")
        return False
    
    return True

def check_environment():
    """Check the WSL environment and dependencies"""
    
    print("🔍 Environment Check")
    print("=" * 20)
    
    # Check OS
    import platform
    print(f"🖥️  Platform: {platform.platform()}")
    print(f"🐧 System: {platform.system()}")
    print(f"🏗️  Architecture: {platform.machine()}")
    
    # Check if we're in WSL
    try:
        with open('/proc/version', 'r') as f:
            version_info = f.read()
            if 'microsoft' in version_info.lower():
                print("✅ Running in WSL")
            else:
                print("ℹ️  Not running in WSL")
    except:
        print("❓ Cannot determine if WSL")
    
    # Check Python packages
    packages_to_check = ['PIL', 'fastmcp']
    
    for package in packages_to_check:
        try:
            __import__(package)
            print(f"✅ {package} available")
        except ImportError:
            print(f"❌ {package} not available")
    
    # Check pyautogui with DISPLAY handling
    try:
        # Temporarily unset DISPLAY to avoid X11 errors
        old_display = os.environ.get('DISPLAY')
        if 'DISPLAY' in os.environ:
            del os.environ['DISPLAY']
        
        import pyautogui
        print(f"✅ pyautogui available (without X11)")
        
        # Restore DISPLAY
        if old_display:
            os.environ['DISPLAY'] = old_display
            
    except ImportError:
        print(f"❌ pyautogui not available")
    except Exception as e:
        print(f"⚠️  pyautogui available but X11 issue: {e}")
        # Restore DISPLAY
        if old_display:
            os.environ['DISPLAY'] = old_display
    
    # Check display
    display = os.environ.get('DISPLAY')
    print(f"🖥️  DISPLAY: {display or 'Not set'}")
    
    # Check if screenshots directory exists
    screenshots_dir = Path("web_app/static/screenshots")
    if screenshots_dir.exists():
        print(f"✅ Screenshots directory exists: {screenshots_dir}")
        existing_files = list(screenshots_dir.glob("*.png"))
        print(f"📁 Existing screenshots: {len(existing_files)}")
    else:
        print(f"❌ Screenshots directory missing: {screenshots_dir}")

async def main():
    """Main test function"""
    
    print("🎬 MCP Screenshot Tool Test")
    print("=" * 40)
    
    # Environment check
    check_environment()
    
    # Test direct function calls
    await test_direct_function_calls()
    
    # Test via subprocess
    await test_mcp_screenshot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()