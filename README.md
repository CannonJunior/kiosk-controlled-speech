# Kiosk Controlled Speech System

A voice-controlled interface system for Pandasuite kiosks using the FastMCP framework. This system enables natural language voice commands to control kiosk interactions on Windows through WSL with discrete service lifespans.

## Recent Updates - Audio Implementation Complete ✅

**Session Progress (2025-07-27):**
- ✅ **Windows Audio Forwarding**: Implemented PowerShell-based audio capture for WSL
- ✅ **File-based Transcription**: Added `transcribe_file` MCP tool for audio file processing  
- ✅ **Automatic Fallback**: Speech-to-text automatically detects and uses Windows audio when WSL audio fails
- ✅ **Complete Integration**: End-to-end testing shows successful audio recording, transfer, and transcription
- ✅ **Production Ready**: Test shows audio file (160KB WAV) → transcription ("You") in ~1 second

**Key Files for Audio Functionality:**
- **WSL**: `test_speech_to_text.py` - Complete speech-to-text testing
- **PowerShell**: `windows_audio_recorder.ps1` - Windows-side audio recording
- **WSL**: `windows_audio_capture.py` - Audio bridge integration
- **WSL**: `services/speech_to_text/mcp_server.py` - Updated with file transcription support

## Architecture Overview

The system uses **FastMCP** with discrete service lifespans instead of continuously running services:

- **Speech-to-Text Service**: Real-time voice recognition using FastMCP
- **Screen Capture Service**: Windows desktop capture from WSL
- **Mouse Control Service**: Windows mouse automation from WSL  
- **Screen Detector Service**: Computer vision-based screen state detection
- **Ollama Agent Service**: Natural language command processing
- **Data Manager Service**: Kiosk configuration and element management
- **Main Orchestrator**: Coordinates all services using FastMCP Client pattern

### New Architecture Benefits

- **Discrete Lifespans**: Services start/stop on-demand rather than running continuously
- **Better Resource Management**: No persistent connections to maintain
- **Simplified Deployment**: Uses FastMCP's battle-tested patterns
- **Improved Error Handling**: FastMCP manages connection lifecycle automatically

## Features

- 🎤 **Real-time Speech Recognition**: Continuous voice command processing
- 🖥️ **Cross-platform Screen Capture**: Windows desktop capture from WSL environment
- 🖱️ **Intelligent Mouse Control**: Precise click automation with validation
- 🤖 **AI-powered Command Processing**: Natural language understanding via Ollama
- 🎯 **Computer Vision Detection**: Automatic screen state and element recognition
- 📊 **Performance Monitoring**: Real-time metrics and health monitoring
- 🔧 **Hot-swappable Configuration**: Dynamic kiosk data management

## Quick Start

### Prerequisites

- Windows 10/11 with WSL2 enabled
- Python 3.9+ in WSL environment
- Ollama installed and running
- PowerShell 5.1+ (for Windows audio forwarding)
- Audio device access (automatically handled via Windows-side recording)

### Installation

1. **Clone and setup the project:**
```bash
git clone <repository-url>
cd kiosk-project
```

2. **Install dependencies using uv:**
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize project and install dependencies
uv sync
```

3. **Dependencies are managed automatically:**
```bash
# With uv, dependencies are automatically managed
# No need to manually activate environments - use 'uv run' prefix
```

4. **Service dependencies are managed via pyproject.toml:**
```bash
# All dependencies including service-specific ones are in pyproject.toml
# Run any additional service setup if needed
```

### Configuration

1. **Kiosk Data Configuration** (`config/kiosk_data.json`):
   - Define screens, elements, and voice commands
   - Set detection criteria for screen identification
   - Configure global commands and settings

2. **MCP Services Configuration** (`config/mcp_config.json`):
   - Configure MCP server endpoints
   - Set service-specific parameters
   - Define orchestration settings

### Running the System

1. **Quick test of all FastMCP services:**
```bash
# Run comprehensive service test using uv
uv run test_fastmcp_services.py
```

2. **Test individual FastMCP services:**
```bash
# Test mouse control service
timeout 5 uv run services/mouse_control/mcp_server.py

# Test screen detector service
timeout 5 uv run services/screen_detector/mcp_server.py

# Test speech-to-text service
timeout 5 uv run services/speech_to_text/mcp_server_fastmcp.py
```

3. **Start the full system:**
```bash
uv run python -m src.orchestrator.main start
```

4. **Test individual commands:**
```bash
uv run python -m src.orchestrator.main test-command "click start button"
```

### Testing Speech-to-Text with Windows Audio Forwarding

**Complete Audio Test (WSL):**
```bash
# Test speech-to-text with Windows audio forwarding
uv run test_speech_to_text.py

# Test with custom duration (in seconds)
uv run test_speech_to_text.py 10
```

**Windows Audio Test (PowerShell):**
```powershell
# Test Windows audio recording directly (run in Windows PowerShell)
powershell.exe -ExecutionPolicy Bypass -File windows_audio_recorder.ps1 -Duration 5 -OutputFile "test_audio.wav"
```

**Audio Integration Test (WSL):**
```bash
# Test Windows audio capture integration (run in WSL terminal)
uv run python windows_audio_capture.py
```

### Testing FastMCP Services

Each service can be tested independently using FastMCP's built-in capabilities:

```bash
# Test mouse control tools
uv run python -c "
import asyncio
from fastmcp import Client

async def test_mouse():
    config = {'mcpServers': {'mouse_control': {'command': 'python', 'args': ['services/mouse_control/mcp_server.py']}}}
    async with Client(config) as client:
        result = await client.call_tool('mouse_control_click', {'x': 100, 'y': 200})
        print('Mouse click result:', result)

asyncio.run(test_mouse())
"

# Test screen detector tools
uv run python -c "
import asyncio
from fastmcp import Client

async def test_detector():
    config = {'mcpServers': {'screen_detector': {'command': 'python', 'args': ['services/screen_detector/mcp_server.py']}}}
    async with Client(config) as client:
        tools = await client.list_tools()
        print('Available tools:', [t.name for t in tools])

asyncio.run(test_detector())
"
```

## Usage

### Voice Commands

The system supports natural language commands:

- **Navigation**: "click start", "go back", "open menu"
- **Help**: "help", "what can I do", "show commands"  
- **Global**: "go home", "return to main screen"

### System Status

The orchestrator provides real-time status including:
- Voice recognition status
- Current screen detection
- Command processing metrics
- Service health monitoring

## Development

### Project Structure

```
kiosk-controlled-speech/
├── src/                          # Core application code
│   ├── mcp/                     # MCP framework base classes
│   ├── data_manager/            # Kiosk data management
│   └── orchestrator/            # Main orchestration logic
├── services/                    # MCP microservices
│   ├── speech_to_text/         # Whisper-based speech recognition
│   ├── screen_capture/         # Windows screenshot capture
│   ├── mouse_control/          # Mouse automation
│   ├── screen_detector/        # Computer vision detection
│   └── ollama_agent/           # AI command processing
├── config/                      # Configuration files
├── scripts/                     # Setup and utility scripts
└── tests/                       # Test suite
```

### Adding New Screens

1. **Update kiosk data** (`config/kiosk_data.json`):
```json
{
  "screens": {
    "new_screen": {
      "name": "New Screen",
      "description": "Description of the screen",
      "detection_criteria": {
        "title_text": "Screen Title",
        "elements": ["button1", "button2"]
      },
      "elements": [
        {
          "id": "button1",
          "name": "Button Name",
          "coordinates": {"x": 100, "y": 200},
          "size": {"width": 150, "height": 50},
          "voice_commands": ["click button", "press button"],
          "conditions": ["always_visible"],
          "action": "click",
          "next_screen": "target_screen"
        }
      ]
    }
  }
}
```

2. **Test screen detection**:
```bash
uv run python -m src.orchestrator.main test-command "navigate to new screen"
```

### Adding Voice Commands

1. **Element-specific commands**: Add to element's `voice_commands` array
2. **Global commands**: Add to `global_commands` section
3. **Context-aware commands**: Handled automatically by Ollama agent

### FastMCP Tool Naming Convention

FastMCP tools use their function names directly:

- Mouse control service tools: `click`, `move_to`, `get_position`, `drag`, `scroll`, `configure`
- Screen detector tools: `detect_current_screen`, `analyze_screen_elements`
- Speech service tools: `start_listening`, `stop_listening`, `get_status`, `process_audio_data`
- Screen capture tools: `take_screenshot`, `get_screen_info`

When multiple services are used together, tool names must be unique across all services to avoid conflicts.

### Performance Tuning

- **Speech Recognition**: Adjust `WHISPER_MODEL` and `SPEECH_LANGUAGE` in `.env`
- **Screen Detection**: Tune confidence thresholds in kiosk data
- **Response Time**: Configure `MAX_RESPONSE_TIME_MS` and Ollama parameters

## FastMCP Services

The system now uses FastMCP with discrete service lifespans. Each service exposes tools that are called on-demand.

### Speech-to-Text Service

**Architecture Update: Windows Audio Forwarding for WSL**

The speech-to-text service now includes Windows-side audio forwarding to overcome WSL audio limitations:

**Components:**
- **WSL Speech Service**: Whisper-based transcription (`services/speech_to_text/mcp_server.py`)
- **Windows Audio Recorder**: PowerShell script for Windows audio capture (`windows_audio_recorder.ps1`)
- **Audio Bridge**: Python integration for Windows-WSL audio transfer (`windows_audio_capture.py`)

**FastMCP Tools:**
- `start_listening`: Begin continuous speech recognition (Linux audio only)
- `stop_listening`: Stop speech recognition
- `transcribe_file`: Transcribe audio file to text (supports Windows-recorded files)
- `transcribe_audio`: Transcribe base64 audio data
- `record_and_transcribe`: Record and transcribe (Linux audio, with Windows fallback)
- `get_audio_devices`: List available audio devices
- `get_status`: Get current recognition status

**Windows Audio Forwarding Test:**
```bash
# Complete test with automatic Windows fallback (WSL)
uv run test_speech_to_text.py

# Manual Windows audio test (PowerShell)
powershell.exe -ExecutionPolicy Bypass -File windows_audio_recorder.ps1 -Duration 5

# Test Windows audio integration (WSL)
uv run python windows_audio_capture.py
```

**Direct MCP Testing:**
```bash
# Test speech service with file transcription
uv run python -c "
import asyncio
from services.speech_to_text.mcp_server import SpeechToTextServer

async def test_speech():
    server = SpeechToTextServer()
    # Test audio file transcription
    result = await server.handle_tool_call('transcribe_file', {
        'file_path': '/tmp/audio_capture/test_audio.wav',
        'language': 'en'
    })
    print('Transcription result:', result)

asyncio.run(test_speech())
"
```

### Screen Capture Service

**FastMCP Tools:**
- `take_screenshot`: Full desktop capture
- `get_screen_info`: Get screen dimensions and info

**Testing:**
```bash
# Test screen capture
uv run python -c "
import asyncio
from fastmcp import Client

async def test_capture():
    config = {'mcpServers': {'screen_capture': {'command': 'python', 'args': ['services/screen_capture/mcp_server.py']}}}
    async with Client(config) as client:
        result = await client.call_tool('take_screenshot')
        print('Screenshot taken:', result.content[0].text)

asyncio.run(test_capture())
"
```

### Mouse Control Service

**FastMCP Tools:**
- `click`: Perform mouse click at coordinates
- `move_to`: Move cursor to position
- `drag`: Drag between positions
- `scroll`: Scroll at position
- `get_position`: Get current cursor position
- `configure`: Configure mouse settings

**Testing:**
```bash
# Test mouse control (returns mock data for safety)
uv run python -c "
import asyncio
import json
from fastmcp import Client

async def test_mouse():
    config = {'mcpServers': {'mouse_control': {'command': 'python', 'args': ['services/mouse_control/mcp_server.py']}}}
    async with Client(config) as client:
        # List available tools
        tools = await client.list_tools()
        print('Mouse tools:', [t.name for t in tools])
        
        # Test click (mock implementation)
        result = await client.call_tool('click', {'x': 100, 'y': 200})
        print('Click result:', json.loads(result.content[0].text))

asyncio.run(test_mouse())
"
```

### Screen Detector Service

**FastMCP Tools:**
- `detect_current_screen`: Identify current screen
- `analyze_screen_elements`: Find clickable elements

**Testing:**
```bash
# Test screen detection
uv run python -c "
import asyncio
import json
from fastmcp import Client

async def test_detector():
    config = {'mcpServers': {'screen_detector': {'command': 'python', 'args': ['services/screen_detector/mcp_server.py']}}}
    async with Client(config) as client:
        # Test screen detection with mock data
        result = await client.call_tool('detect_current_screen', {
            'screenshot_data': 'mock_base64_data',
            'screen_definitions': {'home': {'name': 'Home Screen'}}
        })
        data = json.loads(result.content[0].text)
        print('Detected screen:', data['detected_screen'])

asyncio.run(test_detector())
"
```

### Ollama Agent Service

**FastMCP Tools:**
- `process_voice_command`: Convert speech to actions
- `generate_help_response`: Contextual help
- `analyze_intent`: Intent classification
- `health_check`: Check Ollama connectivity

**Prerequisites:**
```bash
# Install and start Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &
ollama pull qwen2.5:1.5b  # Or your preferred model
```

**Testing:**
```bash
# Test Ollama agent (requires Ollama running)
uv run python -c "
import asyncio
from fastmcp import Client

async def test_ollama():
    config = {'mcpServers': {'ollama_agent': {'command': 'python', 'args': ['services/ollama_agent/mcp_server.py']}}}
    async with Client(config) as client:
        # Check Ollama health
        health = await client.call_tool('health_check')
        print('Ollama health:', health.content[0].text)

asyncio.run(test_ollama())
"
```

## Troubleshooting

### Common Issues

1. **Audio not working in WSL**:
   - **Solution**: System now automatically uses Windows audio forwarding
   - **Test Windows audio**: `uv run python windows_audio_capture.py`
   - **Test complete system**: `uv run test_speech_to_text.py`
   - **Manual troubleshooting**: Check PowerShell execution policy with `powershell.exe Get-ExecutionPolicy`

2. **Screenshot capture fails**:
   - Verify WSL can access Windows desktop: `powershell.exe Get-Process`
   - Check Windows interop is enabled

3. **Ollama connection errors**:
   - Ensure Ollama is running: `ollama serve`
   - Check model is available: `ollama list`
   - Verify network configuration

4. **Mouse clicks not working**:
   - Run as administrator if needed
   - Check coordinate validation settings
   - Verify Windows permissions

### Debug Mode

Enable verbose logging:
```bash
export LOG_LEVEL=DEBUG
uv run python -m src.orchestrator.main start
```

### Health Checks

Monitor FastMCP service health:
```bash
# Test all services individually using uv

# Quick service tests
timeout 3 uv run python services/mouse_control/mcp_server.py || echo "Mouse service OK"
timeout 3 uv run python services/screen_detector/mcp_server.py || echo "Screen detector OK"
timeout 3 uv run python services/screen_capture/mcp_server.py || echo "Screen capture OK"
timeout 3 uv run python services/speech_to_text/mcp_server_fastmcp.py || echo "Speech service OK"

# Test full system integration
uv run python -c "
import asyncio
import json
from fastmcp import Client

async def health_check():
    config = {
        'mcpServers': {
            'mouse_control': {'command': 'python', 'args': ['services/mouse_control/mcp_server.py']},
            'screen_detector': {'command': 'python', 'args': ['services/screen_detector/mcp_server.py']},
            'screen_capture': {'command': 'python', 'args': ['services/screen_capture/mcp_server.py']}
        }
    }
    
    async with Client(config) as client:
        # List tools from all servers
        tools = await client.list_tools()
        print(f'Total tools available: {len(tools)}')
        
        # Test a simple tool call
        result = await client.call_tool('get_position')
        data = json.loads(result.content[0].text)
        print('Mouse position test:', data)

asyncio.run(health_check())
"
```

### FastMCP Debugging

Enable FastMCP debugging:
```bash
# Run individual service with verbose output
FASTMCP_DEBUG=1 uv run python services/mouse_control/mcp_server.py

# Check tool definitions
uv run python -c "
import asyncio
from fastmcp import Client

async def debug_tools():
    config = {'mcpServers': {'mouse_control': {'command': 'python', 'args': ['services/mouse_control/mcp_server.py']}}}
    async with Client(config) as client:
        tools = await client.list_tools()
        for tool in tools:
            print(f'Tool: {tool.name} - {tool.description}')

asyncio.run(debug_tools())
"
```

## Performance Metrics

The system tracks:
- **Response Time**: End-to-end command processing time (target: <500ms)
- **Recognition Accuracy**: Voice command recognition rate (target: >95%)
- **Click Precision**: Mouse positioning accuracy (target: ±5 pixels)
- **Uptime**: System availability (target: >99.5%)

## Security Considerations

- **Sandboxed Execution**: MCP services run in isolated processes
- **Input Validation**: All coordinates and commands are validated
- **Access Control**: Limited to kiosk application interactions
- **Audit Logging**: All actions are logged for review

## Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/new-feature`
3. **Make changes and test**: `uv run python scripts/test_system.py`
4. **Submit a pull request**

### Development Guidelines

- Follow PEP 8 style guidelines
- Add type hints to all functions
- Include docstrings for public APIs
- Write tests for new functionality
- Update documentation

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions and support:
- Check the troubleshooting section
- Review the test outputs
- Submit issues with system logs
- Include configuration details in bug reports
