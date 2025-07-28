#!/usr/bin/env python3
"""
Test script for Web Application Integration
Tests the web app's integration with existing MCP services
"""
import asyncio
import json
import websockets
import base64
import os
import sys
import tempfile
import wave
import numpy as np
from pathlib import Path
import httpx

# Add project root to path
sys.path.append('.')

async def test_health_endpoint():
    """Test the health check endpoint"""
    print("🏥 Testing health endpoint...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data['status']}")
                print(f"   Active connections: {data.get('active_connections', 0)}")
                print(f"   Services: {data.get('services', {})}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

async def test_websocket_connection():
    """Test WebSocket connection and basic messaging"""
    print("\n🔌 Testing WebSocket connection...")
    try:
        uri = "ws://localhost:8000/ws/test_client_123"
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connected successfully")
            
            # Test ping
            await websocket.send(json.dumps({"type": "ping"}))
            response = await websocket.recv()
            data = json.loads(response)
            
            if data.get("type") == "pong":
                print("✅ Ping/pong test passed")
            else:
                print(f"❌ Unexpected ping response: {data}")
                
            return True
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

async def test_chat_message():
    """Test chat message processing"""
    print("\n💬 Testing chat message processing...")
    try:
        uri = "ws://localhost:8000/ws/test_client_456"
        async with websockets.connect(uri) as websocket:
            # Skip connection message
            await websocket.recv()
            
            # Send test message
            test_message = {
                "type": "chat_message",
                "message": "Hello, how are you?",
                "context": {"test": True}
            }
            
            await websocket.send(json.dumps(test_message))
            print("📤 Sent test message: 'Hello, how are you?'")
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            data = json.loads(response)
            
            if data.get("type") == "chat_response":
                print("✅ Chat response received")
                print(f"   Response: {data.get('response', {})}")
                return True
            else:
                print(f"❌ Unexpected response type: {data.get('type')}")
                print(f"   Data: {data}")
                return False
                
    except asyncio.TimeoutError:
        print("❌ Chat message test timed out")
        return False
    except Exception as e:
        print(f"❌ Chat message test failed: {e}")
        return False

def create_test_audio():
    """Create a test WAV audio file"""
    print("\n🎵 Creating test audio file...")
    
    # Generate a simple tone (440 Hz for 2 seconds)
    sample_rate = 16000
    duration = 2.0
    frequency = 440.0
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_data = np.sin(2 * np.pi * frequency * t) * 0.3
    
    # Convert to 16-bit PCM
    audio_int16 = (audio_data * 32767).astype(np.int16)
    
    # Create temporary WAV file
    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    
    with wave.open(temp_file.name, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())
    
    print(f"✅ Test audio created: {temp_file.name}")
    return temp_file.name

async def test_audio_processing():
    """Test audio processing through WebSocket"""
    print("\n🎤 Testing audio processing...")
    
    try:
        # Create test audio
        audio_file = create_test_audio()
        
        # Read and encode audio
        with open(audio_file, 'rb') as f:
            audio_bytes = f.read()
        
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Clean up temp file
        os.unlink(audio_file)
        
        # Send via WebSocket
        uri = "ws://localhost:8000/ws/test_client_789"
        async with websockets.connect(uri) as websocket:
            # Skip connection message
            await websocket.recv()
            
            audio_message = {
                "type": "audio_data",
                "audio": audio_base64,
                "timestamp": "2025-01-27T10:30:00Z"
            }
            
            await websocket.send(json.dumps(audio_message))
            print("📤 Sent test audio data")
            
            # Wait for transcription response
            response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
            data = json.loads(response)
            
            if data.get("type") == "transcription":
                print("✅ Audio transcription received")
                print(f"   Text: '{data.get('text', '')}'")
                print(f"   Confidence: {data.get('confidence', 0.0)}")
                return True
            elif data.get("type") == "error":
                print(f"❌ Audio processing error: {data.get('message')}")
                return False
            else:
                print(f"❌ Unexpected response: {data}")
                return False
                
    except asyncio.TimeoutError:
        print("❌ Audio processing test timed out")
        return False
    except Exception as e:
        print(f"❌ Audio processing test failed: {e}")
        return False

async def test_mcp_services():
    """Test MCP service availability"""
    print("\n🔧 Testing MCP service integration...")
    
    try:
        # Test by checking if services are listed in health endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code == 200:
                data = response.json()
                services = data.get('services', {})
                
                expected_services = ['speech_to_text', 'ollama_agent']
                for service in expected_services:
                    if service in str(services):
                        print(f"✅ {service} service detected")
                    else:
                        print(f"⚠️  {service} service not found in health response")
                
                return True
            else:
                print(f"❌ Could not check MCP services: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ MCP service test failed: {e}")
        return False

async def run_all_tests():
    """Run all integration tests"""
    print("🧪 Starting Web Application Integration Tests")
    print("=" * 50)
    
    tests = [
        ("Health Endpoint", test_health_endpoint),
        ("WebSocket Connection", test_websocket_connection),
        ("Chat Message", test_chat_message),
        ("Audio Processing", test_audio_processing),
        ("MCP Services", test_mcp_services)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Web application integration is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

def main():
    """Main test function"""
    print("🚀 Kiosk Speech Web Application Integration Test")
    print("Make sure the web application is running on http://localhost:8000")
    print()
    
    try:
        result = asyncio.run(run_all_tests())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()