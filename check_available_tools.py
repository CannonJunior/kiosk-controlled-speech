#!/usr/bin/env python3
"""
Check available MCP tools in the web app
"""

import requests
import json

def check_tools():
    """Check what tools are available"""
    
    print("🔧 Checking Available MCP Tools")
    print("=" * 35)
    
    # Try to get tools list if endpoint exists
    try:
        response = requests.get("http://localhost:8000/api/tools", timeout=10)
        if response.status_code == 200:
            tools = response.json()
            print(f"✅ Tools endpoint available: {len(tools)} tools")
            for tool in tools:
                print(f"   - {tool}")
        else:
            print(f"⚠️  Tools endpoint returned: {response.status_code}")
    except Exception as e:
        print(f"❌ No tools endpoint: {e}")
    
    # Try some common tool names
    test_tools = [
        "screen_capture_take_screenshot",
        "take_screenshot", 
        "screenshot",
        "screen_capture",
        "capture_screen"
    ]
    
    print("\n🧪 Testing Tool Names:")
    for tool_name in test_tools:
        try:
            payload = {"tool": tool_name, "parameters": {}}
            response = requests.post("http://localhost:8000/api/mcp-tool", json=payload, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ {tool_name} - WORKS")
            elif response.status_code == 500 and "Unknown tool" in response.text:
                print(f"❌ {tool_name} - Unknown tool")
            else:
                print(f"⚠️  {tool_name} - Status {response.status_code}")
                
        except Exception as e:
            print(f"❌ {tool_name} - Error: {e}")

if __name__ == "__main__":
    check_tools()