#!/usr/bin/env python3
"""
Test script for FastMCP services
Run this to verify all services are working correctly.
"""

import asyncio
import sys
import json
from fastmcp import Client

def parse_tool_result(result):
    """Parse FastMCP tool result"""
    if result.is_error:
        return {"error": "Tool call failed"}
    
    if result.content and len(result.content) > 0:
        text_content = result.content[0].text
        try:
            return json.loads(text_content)
        except json.JSONDecodeError:
            return {"raw_text": text_content}
    
    return {"no_content": True}

async def test_mouse_control():
    """Test mouse control service"""
    print("🖱️  Testing Mouse Control Service...")
    try:
        config = {
            'mcpServers': {
                'mouse_control': {
                    'command': 'python', 
                    'args': ['services/mouse_control/mcp_server.py']
                }
            }
        }
        
        async with Client(config) as client:
            # List tools
            tools = await client.list_tools()
            mouse_tools = [t.name for t in tools]
            print(f"   ✅ Found {len(mouse_tools)} mouse tools: {mouse_tools}")
            
            # Test click (mock implementation)
            result_raw = await client.call_tool('click', {'x': 100, 'y': 200})
            result = parse_tool_result(result_raw)
            if result.get('x') == 100 and result.get('mock'):
                print("   ✅ Click test successful (mock mode)")
            else:
                print("   ❌ Click test failed")
                
            # Test get position
            pos_result_raw = await client.call_tool('get_position')
            pos_result = parse_tool_result(pos_result_raw)
            if pos_result.get('x') is not None:
                print("   ✅ Get position test successful")
            else:
                print("   ❌ Get position test failed")
                
    except Exception as e:
        print(f"   ❌ Mouse control test failed: {e}")

async def test_screen_detector():
    """Test screen detector service"""
    print("🔍 Testing Screen Detector Service...")
    try:
        config = {
            'mcpServers': {
                'screen_detector': {
                    'command': 'python', 
                    'args': ['services/screen_detector/mcp_server.py']
                }
            }
        }
        
        async with Client(config) as client:
            # List tools
            tools = await client.list_tools()
            detector_tools = [t.name for t in tools]
            print(f"   ✅ Found {len(detector_tools)} detector tools: {detector_tools}")
            
            # Test screen detection
            result_raw = await client.call_tool('detect_current_screen', {
                'screenshot_data': 'mock_base64_data',
                'screen_definitions': {'home': {'name': 'Home Screen'}}
            })
            result = parse_tool_result(result_raw)
            
            if result.get('detected_screen'):
                print(f"   ✅ Screen detection test successful: {result['detected_screen']}")
            else:
                print("   ❌ Screen detection test failed")
                
    except Exception as e:
        print(f"   ❌ Screen detector test failed: {e}")

async def test_screen_capture():
    """Test screen capture service"""
    print("📸 Testing Screen Capture Service...")
    try:
        config = {
            'mcpServers': {
                'screen_capture': {
                    'command': 'python', 
                    'args': ['services/screen_capture/mcp_server.py']
                }
            }
        }
        
        async with Client(config) as client:
            # List tools
            tools = await client.list_tools()
            capture_tools = [t.name for t in tools]
            print(f"   ✅ Found {len(capture_tools)} capture tools: {capture_tools}")
            
            # Test screenshot
            result_raw = await client.call_tool('take_screenshot')
            result = parse_tool_result(result_raw)
            if result.get('success') and result.get('data', {}).get('format'):
                print(f"   ✅ Screenshot test successful: {result['data']['format']}")
            else:
                print("   ❌ Screenshot test failed")
                
    except Exception as e:
        print(f"   ❌ Screen capture test failed: {e}")

async def test_speech_to_text():
    """Test speech-to-text service"""
    print("🎤 Testing Speech-to-Text Service...")
    try:
        config = {
            'mcpServers': {
                'speech_to_text': {
                    'command': 'python', 
                    'args': ['services/speech_to_text/mcp_server_fastmcp.py']
                }
            }
        }
        
        async with Client(config) as client:
            # List tools
            tools = await client.list_tools()
            speech_tools = [t.name for t in tools]
            print(f"   ✅ Found {len(speech_tools)} speech tools: {speech_tools}")
            
            # Test start listening
            result_raw = await client.call_tool('start_listening')
            result = parse_tool_result(result_raw)
            if result.get('success'):
                print("   ✅ Start listening test successful")
                
                # Test status
                status_raw = await client.call_tool('get_status')
                status = parse_tool_result(status_raw)
                if status.get('is_listening'):
                    print("   ✅ Status check successful - listening active")
                else:
                    print("   ❌ Status check failed")
                    
                # Test stop listening
                stop_result_raw = await client.call_tool('stop_listening')
                stop_result = parse_tool_result(stop_result_raw)
                if stop_result.get('success'):
                    print("   ✅ Stop listening test successful")
                else:
                    print("   ❌ Stop listening test failed")
            else:
                print("   ❌ Start listening test failed")
                
    except Exception as e:
        print(f"   ❌ Speech-to-text test failed: {e}")

async def test_all_services():
    """Test all FastMCP services"""
    print("🚀 FastMCP Services Test Suite")
    print("=" * 50)
    
    try:
        await test_mouse_control()
        print()
        
        await test_screen_detector()
        print()
        
        await test_screen_capture()
        print()
        
        await test_speech_to_text()
        print()
        
        print("✅ All service tests completed!")
        print("\nTo test the full system integration, run:")
        print("   python -m src.orchestrator.main test-command 'help'")
        
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Check if we're in the virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: Virtual environment not detected.")
        print("   Please run: source venv/bin/activate")
        print()
    
    print("FastMCP Services Test")
    print("Make sure you've installed FastMCP: pip install fastmcp")
    print()
    
    asyncio.run(test_all_services())