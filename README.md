# Kiosk Controlled Speech System

A voice-controlled interface system for Pandasuite kiosks using the Model Context Protocol (MCP) framework. This system enables natural language voice commands to control kiosk interactions on Windows through WSL.

## Architecture Overview

The system consists of multiple MCP-based microservices:

- **Speech-to-Text Service**: Real-time voice recognition using OpenAI Whisper
- **Screen Capture Service**: Windows desktop capture from WSL
- **Mouse Control Service**: Windows mouse automation from WSL  
- **Screen Detector Service**: Computer vision-based screen state detection
- **Ollama Agent Service**: Natural language command processing
- **Data Manager Service**: Kiosk configuration and element management
- **Main Orchestrator**: Coordinates all services and manages system state

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
- Audio device access from WSL

### Installation

1. **Clone and setup the project:**
```bash
git clone <repository-url>
cd kiosk-controlled-speech
```

2. **Setup WSL environment:**
```bash
chmod +x scripts/setup_wsl.sh
./scripts/setup_wsl.sh
```

3. **Install Python dependencies:**
```bash
pip install -e .
pip install -e ".[dev]"
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your specific configuration
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

1. **Test the system:**
```bash
python scripts/test_system.py
```

2. **Start the full system:**
```bash
python -m src.orchestrator.main start
```

3. **Test individual commands:**
```bash
python -m src.orchestrator.main test-command "click start button"
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
python -m src.orchestrator.main test-command "navigate to new screen"
```

### Adding Voice Commands

1. **Element-specific commands**: Add to element's `voice_commands` array
2. **Global commands**: Add to `global_commands` section
3. **Context-aware commands**: Handled automatically by Ollama agent

### Performance Tuning

- **Speech Recognition**: Adjust `WHISPER_MODEL` and `SPEECH_LANGUAGE` in `.env`
- **Screen Detection**: Tune confidence thresholds in kiosk data
- **Response Time**: Configure `MAX_RESPONSE_TIME_MS` and Ollama parameters

## MCP Services

### Speech-to-Text Service

**Tools:**
- `start_listening`: Begin continuous speech recognition
- `stop_listening`: Stop speech recognition  
- `transcribe_audio`: Process audio data
- `get_audio_devices`: List available input devices

### Screen Capture Service

**Tools:**
- `take_screenshot`: Full desktop capture
- `take_screenshot_region`: Capture specific region
- `save_screenshot`: Save to file

### Mouse Control Service

**Tools:**
- `click`: Perform mouse click at coordinates
- `move_to`: Move cursor to position
- `drag`: Drag between positions
- `scroll`: Scroll at position

### Screen Detector Service

**Tools:**
- `detect_current_screen`: Identify current screen
- `detect_visible_elements`: Find clickable elements
- `validate_element_location`: Verify element position
- `find_text_elements`: OCR-based text detection

### Ollama Agent Service

**Tools:**
- `process_voice_command`: Convert speech to actions
- `generate_help_response`: Contextual help
- `analyze_intent`: Intent classification
- `suggest_alternatives`: Command suggestions

### Data Manager Service

**Tools:**
- `get_screen`: Retrieve screen configuration
- `find_elements_by_voice`: Search by voice command
- `update_element_coordinates`: Modify element positions
- `validate_data`: Check configuration integrity

## Troubleshooting

### Common Issues

1. **Audio not working in WSL**:
   - Ensure PulseAudio is configured: `export PULSE_RUNTIME_PATH="/mnt/wslg/runtime/PulseAudio"`
   - Test with: `python -c "import sounddevice; print(sounddevice.query_devices())"`

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
python -m src.orchestrator.main start
```

### Health Checks

Monitor service health:
```bash
# Check all services
python scripts/test_system.py

# Check specific service
python -c "
import asyncio
from src.mcp.client import MCPOrchestrator
async def check():
    orch = MCPOrchestrator('config/mcp_config.json')
    await orch.load_config()
    await orch.start_servers()
    health = await orch.health_check()
    print(health)
    await orch.stop_servers()
asyncio.run(check())
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
3. **Make changes and test**: `python scripts/test_system.py`
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