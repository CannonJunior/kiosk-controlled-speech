#!/usr/bin/env python3
"""End-to-end integration test for the voice-controlled kiosk system"""

import asyncio
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.append('.')

from src.mcp.client import MCPOrchestrator
from src.data_manager.kiosk_data import KioskDataManager

async def test_integration():
    """Test the complete integration workflow"""
    print("🚀 Voice-Controlled Kiosk System - Integration Test")
    print("=" * 60)
    
    try:
        # 1. Initialize components
        print("1️⃣  Initializing MCP Orchestrator...")
        orchestrator = MCPOrchestrator("config/mcp_config.json")
        await orchestrator.load_config()
        
        print("2️⃣  Loading Kiosk Data Manager...")
        data_manager = KioskDataManager("config/kiosk_data.json")
        await data_manager.load_data()
        
        # 2. Start servers
        print("3️⃣  Starting MCP servers...")
        await orchestrator.start_servers()
        
        # 3. Health check
        print("4️⃣  Performing health checks...")
        health = await orchestrator.health_check()
        
        healthy_count = 0
        for service, status in health.items():
            if status.get("status") == "healthy":
                print(f"   ✅ {service}: Healthy")
                healthy_count += 1
            else:
                print(f"   ❌ {service}: {status.get('error', 'Unknown error')}")
        
        print(f"   📊 {healthy_count}/{len(health)} services healthy")
        
        # 4. Test individual service capabilities
        print("5️⃣  Testing service capabilities...")
        
        # Test data manager
        try:
            screens = data_manager.get_all_screens()
            print(f"   📱 Data Manager: {len(screens)} screens loaded")
        except Exception as e:
            print(f"   ❌ Data Manager error: {e}")
        
        # Test screen capture (if healthy)
        if "screen_capture" in health and health["screen_capture"].get("status") == "healthy":
            try:
                # Get available tools first
                tools = await orchestrator.list_tools("screen_capture")
                print(f"   📸 Screen Capture: {len(tools.get('screen_capture', []))} tools available")
                
                # Try to take a screenshot
                result = await orchestrator.call_tool("screen_capture", "take_screenshot")
                if result and "success" in str(result):
                    print("   📸 Screenshot capture: Working")
                else:
                    print(f"   📸 Screenshot test result: {result}")
            except Exception as e:
                print(f"   ❌ Screen Capture test error: {e}")
        
        # Test mouse control (if healthy)
        if "mouse_control" in health and health["mouse_control"].get("status") == "healthy":
            try:
                tools = await orchestrator.list_tools("mouse_control")
                print(f"   🖱️  Mouse Control: {len(tools.get('mouse_control', []))} tools available")
            except Exception as e:
                print(f"   ❌ Mouse Control test error: {e}")
        
        # Test speech to text (if healthy)
        if "speech_to_text" in health and health["speech_to_text"].get("status") == "healthy":
            try:
                tools = await orchestrator.list_tools("speech_to_text")
                print(f"   🎤 Speech-to-Text: {len(tools.get('speech_to_text', []))} tools available")
            except Exception as e:
                print(f"   ❌ Speech-to-Text test error: {e}")
        
        # 5. Test workflow components
        print("6️⃣  Testing workflow components...")
        
        # Test voice command matching
        try:
            matches = data_manager.find_elements_by_voice_command("start")
            print(f"   🗣️  Voice matching: Found {len(matches)} matches for 'start'")
            
            for screen_id, element in matches[:2]:  # Show first 2 matches
                print(f"      - {element.name} on {screen_id}")
                
        except Exception as e:
            print(f"   ❌ Voice matching error: {e}")
        
        # Test global commands
        try:
            global_cmd = data_manager.find_global_command("help")
            if global_cmd:
                print(f"   🌐 Global commands: 'help' command found")
            else:
                print(f"   ⚠️  Global commands: 'help' command not found")
        except Exception as e:
            print(f"   ❌ Global command error: {e}")
        
        # 6. System readiness assessment
        print("7️⃣  System Readiness Assessment...")
        
        readiness_score = 0
        max_score = 7
        
        # MCP infrastructure
        if healthy_count >= len(health) * 0.8:  # 80% services healthy
            readiness_score += 1
            print("   ✅ MCP Infrastructure: Ready")
        else:
            print("   ❌ MCP Infrastructure: Needs attention")
        
        # Data management
        if len(screens) > 0:
            readiness_score += 1
            print("   ✅ Data Management: Ready")
        else:
            print("   ❌ Data Management: No screens configured")
        
        # Core services
        core_services = ["screen_capture", "mouse_control", "speech_to_text"]
        core_healthy = sum(1 for service in core_services 
                          if health.get(service, {}).get("status") == "healthy")
        
        if core_healthy >= 2:  # At least 2 core services
            readiness_score += 1
            print(f"   ✅ Core Services: {core_healthy}/3 ready")
        else:
            print(f"   ❌ Core Services: Only {core_healthy}/3 ready")
        
        # Voice processing
        if len(matches) > 0:
            readiness_score += 1
            print("   ✅ Voice Processing: Ready")
        else:
            print("   ❌ Voice Processing: No voice commands configured")
        
        # WSL Windows integration
        try:
            import subprocess
            result = subprocess.run(['powershell.exe', '-Command', 'Write-Output OK'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                readiness_score += 1
                print("   ✅ WSL-Windows Integration: Ready")
            else:
                print("   ❌ WSL-Windows Integration: PowerShell access failed")
        except Exception as e:
            print(f"   ❌ WSL-Windows Integration: {e}")
        
        # Dependencies
        try:
            import cv2, PIL, sounddevice, faster_whisper
            readiness_score += 1
            print("   ✅ Dependencies: All required packages available")
        except ImportError as e:
            print(f"   ❌ Dependencies: Missing package - {e}")
        
        # Configuration
        config_files = ["config/mcp_config.json", "config/kiosk_data.json"]
        if all(Path(f).exists() for f in config_files):
            readiness_score += 1
            print("   ✅ Configuration: All config files present")
        else:
            print("   ❌ Configuration: Missing config files")
        
        # 7. Final assessment
        print("8️⃣  Final Assessment...")
        readiness_percentage = (readiness_score / max_score) * 100
        
        print(f"   📊 System Readiness: {readiness_score}/{max_score} ({readiness_percentage:.1f}%)")
        
        if readiness_percentage >= 80:
            print("   🎉 System is READY for deployment!")
            print("\n   Next steps:")
            print("   1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh")
            print("   2. Pull a model: ollama pull llama3.2")
            print("   3. Start system: python src/orchestrator/main.py start")
            print("   4. Test command: python src/orchestrator/main.py test-command 'start'")
        elif readiness_percentage >= 60:
            print("   ⚠️  System is PARTIALLY ready - some issues need attention")
        else:
            print("   ❌ System is NOT ready - significant issues need resolution")
        
        # Cleanup
        print("\n9️⃣  Cleaning up...")
        await orchestrator.stop_servers()
        print("   ✅ All servers stopped")
        
        return readiness_score >= max_score * 0.8
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

async def main():
    success = await test_integration()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())