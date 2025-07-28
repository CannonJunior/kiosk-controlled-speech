# 🎤 Kiosk Speech Web Interface

A modern web-based chat interface with real-time speech-to-text capabilities for the Kiosk Controlled Speech system.

## ✨ Features

- **Real-time Speech Recognition**: Browser-based audio capture with WebSocket streaming to WSL
- **Chat Interface**: Modern, responsive web UI for text and voice interaction
- **MCP Integration**: Seamless integration with existing MCP services (speech-to-text, Ollama LLM)
- **Cross-Platform**: Works from Windows browsers connecting to WSL backend
- **Real-time Communication**: WebSocket-based bidirectional communication
- **Audio Processing**: Web Audio API integration with WSL audio processing pipeline

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Windows       │    │      WSL         │    │  MCP Services   │
│   Browser       │◄──►│   FastAPI        │◄──►│ (Existing)      │
│                 │    │   Web Server     │    │                 │
│ • Chat UI       │    │                  │    │ • Speech-to-Text│
│ • Web Audio API │    │ • WebSocket      │    │ • Ollama Agent  │
│ • Real-time STT │    │ • Audio Bridge   │    │ • Orchestrator  │
│ • Mic Capture   │    │ • Session Mgmt   │    │ • Mouse Control │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### 1. Start the Web Application

From the project root directory:

```bash
# Using the startup script (recommended)
./start_web_app.sh

# Or manually
cd /path/to/kiosk-controlled-speech
python -m uvicorn web_app.main:app --host 0.0.0.0 --port 8000
```

### 2. Access from Windows Browser

1. **Get WSL IP Address**: The startup script will display your WSL IP
2. **Open Browser**: Navigate to `http://[WSL_IP]:8000`
3. **Configure Firewall** (if needed): See Windows Configuration section below

### 3. Start Using

1. **Text Chat**: Type messages and press Enter
2. **Voice Input**: Click the microphone button to record speech
3. **Settings**: Click the gear icon to configure audio settings

## 🔧 Windows Configuration

### Firewall Configuration

If you can't access the interface from Windows, configure the firewall:

**PowerShell (Run as Administrator):**
```powershell
# Allow inbound traffic on port 8000
New-NetFirewallRule -DisplayName "WSL Kiosk Port 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

### Port Forwarding (Alternative)

```powershell
# Forward Windows port 8000 to WSL
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=[WSL_IP]

# To remove later:
# netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
```

### Browser Permissions

Ensure your browser allows microphone access:
1. Click the microphone icon in the address bar
2. Select "Allow" for microphone permissions
3. Refresh the page if needed

## 📁 Project Structure

```
web_app/
├── main.py              # FastAPI application and WebSocket handlers
├── static/
│   ├── index.html       # Main chat interface
│   ├── style.css        # Modern UI styles
│   └── app.js           # WebSocket client and Web Audio API
├── README.md            # This file
└── requirements.txt     # Python dependencies
```

## 🔌 API Endpoints

### HTTP Endpoints

- `GET /` - Main chat interface
- `GET /health` - Health check and service status
- `GET /api/sessions` - Active WebSocket sessions info

### WebSocket Endpoint

- `WS /ws/{client_id}` - Real-time communication

#### WebSocket Message Types

**Client → Server:**
```json
{
  "type": "chat_message",
  "message": "Hello, how are you?",
  "context": {...}
}

{
  "type": "audio_data", 
  "audio": "base64_encoded_audio_data",
  "timestamp": "2025-01-27T10:30:00Z"
}

{
  "type": "ping"
}
```

**Server → Client:**
```json
{
  "type": "chat_response",
  "response": {...},
  "original_message": "Hello",
  "timestamp": "2025-01-27T10:30:01Z"
}

{
  "type": "transcription",
  "text": "Hello how are you",
  "confidence": 0.95,
  "timestamp": "2025-01-27T10:30:01Z"
}

{
  "type": "error",
  "message": "Error description"
}
```

## 🎛️ Configuration

### Environment Variables

- `PYTHONPATH` - Set to project root for module imports
- `MCP_CONFIG_PATH` - Path to MCP configuration file (default: `config/mcp_config.json`)

### MCP Services

The web app automatically connects to existing MCP services:
- `speech_to_text` - Audio transcription
- `ollama_agent` - LLM processing
- `screen_capture` - Screenshot analysis
- `mouse_control` - UI automation

## 🔍 Troubleshooting

### Common Issues

**1. Can't access from Windows browser**
- Check WSL IP address: `hostname -I`
- Verify firewall rules
- Try `http://localhost:8000` first (WSL-only access)

**2. WebSocket connection failed**
- Ensure FastAPI server is running
- Check for port conflicts: `netstat -tulpn | grep 8000`
- Verify MCP services are available

**3. Microphone not working**
- Grant browser microphone permissions
- Check available audio devices in browser settings
- Test with other applications

**4. MCP services not responding**
- Check MCP configuration: `config/mcp_config.json`
- Verify Python dependencies are installed
- Review server logs for errors

### Debug Mode

Run with debug logging:
```bash
export PYTHONPATH="$(pwd)"
python -m uvicorn web_app.main:app --host 0.0.0.0 --port 8000 --log-level debug --reload
```

### Logs

Application logs are printed to console. For persistent logging:
```bash
./start_web_app.sh 2>&1 | tee logs/web_app.log
```

## 🛠️ Development

### Local Development

1. **Install Dependencies**:
   ```bash
   pip install fastapi uvicorn fastmcp websockets
   ```

2. **Run in Development Mode**:
   ```bash
   uvicorn web_app.main:app --reload --log-level debug
   ```

3. **Test WebSocket**:
   Open browser developer tools and test WebSocket connection manually.

### Adding Features

- **New Message Types**: Extend `handleWebSocketMessage()` in `app.js`
- **Additional MCP Services**: Update `SpeechWebBridge` in `main.py`
- **UI Components**: Modify `index.html`, `style.css`, and `app.js`

## 📊 Performance

### Optimizations Implemented

- **Audio Streaming**: Chunked audio processing for real-time response
- **WebSocket Heartbeat**: Automatic connection management
- **Error Recovery**: Graceful degradation and reconnection
- **Resource Cleanup**: Automatic cleanup of temporary files and connections

### Performance Metrics

- **Audio Latency**: < 2 seconds from speech to transcription
- **Response Time**: < 3 seconds for LLM processing
- **Memory Usage**: Minimal - temporary audio files cleaned automatically
- **Concurrent Users**: Supports multiple simultaneous sessions

## 🔒 Security Considerations

- **CORS**: Configured for development (restrict in production)
- **File Cleanup**: Temporary audio files automatically removed
- **Input Validation**: WebSocket messages validated before processing
- **Resource Limits**: Audio recording limited to 30 seconds max

## 📝 License

This component is part of the Kiosk Controlled Speech project.

## 🤝 Contributing

1. Test the web interface thoroughly
2. Check browser compatibility (Chrome, Firefox, Edge)
3. Verify WSL networking configuration
4. Test speech recognition accuracy
5. Validate MCP service integration

---

For issues or questions, check the main project documentation or create an issue in the project repository.