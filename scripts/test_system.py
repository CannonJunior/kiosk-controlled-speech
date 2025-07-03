#!/usr/bin/env python3
"""
Test script for the kiosk voice control system
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_manager.kiosk_data import KioskDataManager
from src.mcp.client import MCPOrchestrator


async def test_data_manager():
    """Test the kiosk data manager"""
    print("🧪 Testing Kiosk Data Manager...")
    
    data_manager = KioskDataManager("config/kiosk_data.json")
    
    # Load data
    success = await data_manager.load_data()
    print(f"  ✅ Data loaded: {success}")
    
    # Get statistics
    stats = data_manager.get_statistics()
    print(f"  📊 Statistics: {stats}")
    
    # Test voice command search
    results = data_manager.find_elements_by_voice_command("start")
    print(f"  🎤 Voice command 'start' found {len(results)} elements")
    
    return True


async def test_mcp_config():
    """Test MCP configuration loading"""
    print("🧪 Testing MCP Configuration...")
    
    orchestrator = MCPOrchestrator("config/mcp_config.json")
    
    try:
        await orchestrator.load_config()
        print("  ✅ MCP config loaded successfully")
        print(f"  🔧 Found {len(orchestrator.server_configs)} server configurations")
        
        for name, config in orchestrator.server_configs.items():
            print(f"    - {name}: {config.command} {' '.join(config.args)}")
        
        return True
    except Exception as e:
        print(f"  ❌ MCP config failed: {e}")
        return False


async def test_screen_capture_import():
    """Test screen capture service import"""
    print("🧪 Testing Screen Capture Service...")
    
    try:
        from services.screen_capture.mcp_screenshot_server import take_screenshot
        print("  ✅ Screen capture service imported successfully")
        return True
    except Exception as e:
        print(f"  ❌ Screen capture import failed: {e}")
        return False


async def test_speech_service_import():
    """Test speech-to-text service import"""
    print("🧪 Testing Speech-to-Text Service...")
    
    try:
        from services.speech_to_text.mcp_server import SpeechToTextServer
        server = SpeechToTextServer()
        tools = await server.get_tools()
        print(f"  ✅ Speech service imported, {len(tools)} tools available")
        return True
    except Exception as e:
        print(f"  ❌ Speech service import failed: {e}")
        return False


async def test_mouse_control_import():
    """Test mouse control service import"""
    print("🧪 Testing Mouse Control Service...")
    
    try:
        from services.mouse_control.mcp_server import MouseControlServer
        server = MouseControlServer()
        tools = await server.get_tools()
        print(f"  ✅ Mouse control service imported, {len(tools)} tools available")
        return True
    except Exception as e:
        print(f"  ❌ Mouse control import failed: {e}")
        return False


async def test_screen_detector_import():
    """Test screen detector service import"""
    print("🧪 Testing Screen Detector Service...")
    
    try:
        from services.screen_detector.mcp_server import ScreenDetectorServer
        server = ScreenDetectorServer()
        tools = await server.get_tools()
        print(f"  ✅ Screen detector service imported, {len(tools)} tools available")
        return True
    except Exception as e:
        print(f"  ❌ Screen detector import failed: {e}")
        return False


async def test_ollama_agent_import():
    """Test Ollama agent service import"""
    print("🧪 Testing Ollama Agent Service...")
    
    try:
        from services.ollama_agent.mcp_server import OllamaAgentServer
        server = OllamaAgentServer()
        tools = await server.get_tools()
        print(f"  ✅ Ollama agent service imported, {len(tools)} tools available")
        return True
    except Exception as e:
        print(f"  ❌ Ollama agent import failed: {e}")
        return False


async def test_orchestrator_import():
    """Test main orchestrator import"""
    print("🧪 Testing Main Orchestrator...")
    
    try:
        from src.orchestrator.main import KioskOrchestrator
        orchestrator = KioskOrchestrator()
        print("  ✅ Main orchestrator imported successfully")
        return True
    except Exception as e:
        print(f"  ❌ Orchestrator import failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("🚀 Starting Kiosk Voice Control System Tests\n")
    
    tests = [
        test_data_manager,
        test_mcp_config,
        test_screen_capture_import,
        test_speech_service_import,
        test_mouse_control_import,
        test_screen_detector_import,
        test_ollama_agent_import,
        test_orchestrator_import
    ]
    
    results = []
    
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ Test {test.__name__} crashed: {e}")
            results.append(False)
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("📋 Test Summary:")
    print(f"  ✅ Passed: {passed}/{total}")
    print(f"  ❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} tests failed. Check dependencies and configuration.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())