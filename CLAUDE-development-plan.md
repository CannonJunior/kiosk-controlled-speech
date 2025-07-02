# Voice-Controlled Kiosk Development Plan

## Architecture Overview

The system consists of multiple components communicating through the Model Context Protocol (MCP):

- **Windows Host**: Runs Pandasuite Kiosk natively
- **WSL Environment**: Hosts all custom application components
- **MCP Framework**: Enables seamless communication between components

## Component Breakdown

### 1. Speech-to-Text Service (MCP Tool)
**Location**: WSL
**Technology**: OpenAI Whisper (local deployment)
**Responsibilities**:
- Continuous audio capture from microphone
- Real-time speech recognition
- Text output to command interpreter
- Voice activity detection for efficiency

**MCP Interface**:
```json
{
  "name": "speech_to_text",
  "description": "Convert speech input to text commands",
  "inputSchema": {
    "type": "object",
    "properties": {
      "audio_device": {"type": "string"},
      "language": {"type": "string", "default": "en"}
    }
  }
}
```

### 2. Screen Capture Service (MCP Tool)
**Location**: WSL with Windows interop
**Technology**: Investigate existing MCP screenshot tools first, fallback to Python with win32gui, PIL
**Investigation Priority**: Research available MCP servers for screenshot capabilities before custom development
**Responsibilities**:
- Capture Windows desktop screenshots
- Cross-platform screenshot capability through WSL
- Real-time screen state detection
- Image processing for element detection

**MCP Interface**:
```json
{
  "name": "screen_capture",
  "description": "Capture Windows desktop screenshots",
  "inputSchema": {
    "type": "object",
    "properties": {
      "region": {"type": "object", "optional": true},
      "format": {"type": "string", "default": "png"}
    }
  }
}
```

### 3. Mouse Control Service (MCP Tool)
**Location**: WSL with Windows interop
**Technology**: Python with win32api, pynput
**Responsibilities**:
- Execute mouse clicks on Windows desktop
- Support for different click types (left, right, double)
- Coordinate translation between WSL and Windows
- Click validation and error handling

**MCP Interface**:
```json
{
  "name": "mouse_control",
  "description": "Control Windows mouse input",
  "inputSchema": {
    "type": "object",
    "properties": {
      "x": {"type": "number"},
      "y": {"type": "number"},
      "action": {"type": "string", "enum": ["click", "double_click", "right_click"]},
      "element_id": {"type": "string", "optional": true}
    }
  }
}
```

### 4. Kiosk Data Manager (MCP Resource)
**Location**: WSL filesystem
**Technology**: JSON/SQLite database
**Responsibilities**:
- Store clickable element coordinates for each screen
- Manage screen state definitions
- Element visibility rules and conditions
- Screen transition mapping

**Data Structure**:
```json
{
  "screens": {
    "screen_id": {
      "name": "Screen Name",
      "elements": [
        {
          "id": "element_id",
          "name": "Element Name",
          "coordinates": {"x": 100, "y": 200},
          "size": {"width": 50, "height": 30},
          "voice_commands": ["click button", "select option"],
          "conditions": ["visible_when", "enabled_when"]
        }
      ]
    }
  }
}
```

**MCP Interface**:
```json
{
  "name": "kiosk_data",
  "description": "Access kiosk screen and element data",
  "uri": "file://kiosk_data.json"
}
```

### 5. Screen State Detector (MCP Tool)
**Location**: WSL
**Technology**: Computer vision with OpenCV
**Responsibilities**:
- Analyze screenshots to determine current screen
- Identify which elements are currently visible/clickable
- Compare current state with data definitions
- Return available interaction options

**MCP Interface**:
```json
{
  "name": "screen_detector",
  "description": "Detect current screen state and available elements",
  "inputSchema": {
    "type": "object",
    "properties": {
      "screenshot_data": {"type": "string"},
      "confidence_threshold": {"type": "number", "default": 0.8}
    }
  }
}
```

### 6. Ollama Command Agent (MCP Server)
**Location**: WSL
**Technology**: Ollama with Llama 3.1 or similar model
**Responsibilities**:
- Process natural language commands
- Map speech text to actionable instructions
- Handle context and conversation flow
- Generate appropriate mouse actions

**System Prompt**:
```
You are a voice assistant for a Kiosk demonstration system. Convert natural language commands into specific mouse actions based on the current screen state and available elements. You have access to:
- Current screen screenshot
- List of clickable elements with coordinates
- Element names and voice command mappings
- Screen transition rules

Always respond with specific action instructions including coordinates and element IDs.
```

### 7. Main Orchestrator (MCP Client)
**Location**: WSL
**Technology**: Python asyncio application
**Responsibilities**:
- Coordinate all MCP tools and resources
- Manage application lifecycle
- Handle error recovery and logging
- Provide user feedback and status updates

## Development Phases

### Phase 1: Foundation Setup (Week 1-2)
1. **WSL Environment Setup**
   - Install required Python packages
   - Configure audio/video access from WSL
   - Set up cross-platform Windows interop
   - Install and configure Ollama

2. **MCP Framework Implementation**
   - Create base MCP server/client infrastructure
   - Implement tool registration system
   - Set up inter-component communication
   - Create logging and monitoring framework

### Phase 2: Core Services (Week 3-4)
1. **Screen Capture Service**
   - Implement Windows desktop capture from WSL
   - Add screenshot processing capabilities
   - Create efficient capture scheduling
   - Test cross-platform compatibility

2. **Mouse Control Service**
   - Implement Windows mouse control from WSL
   - Add coordinate validation
   - Create click action abstractions
   - Test precision and reliability

### Phase 3: Data Management (Week 5)
1. **Kiosk Data Structure**
   - Design comprehensive data schema
   - Create data validation rules
   - Implement CRUD operations
   - Add data import/export tools

2. **Screen Detection Logic**
   - Implement computer vision algorithms
   - Create screen matching algorithms
   - Add element visibility detection
   - Optimize performance for real-time use

### Phase 4: AI Integration (Week 6-7)
1. **Speech-to-Text Service**
   - Deploy Whisper locally on WSL
   - Implement continuous audio processing
   - Add voice activity detection
   - Optimize for low latency

2. **Ollama Command Agent**
   - Deploy and configure Ollama server
   - Create specialized prompt engineering
   - Implement context management
   - Add command validation logic

### Phase 5: Integration & Testing (Week 8-9)
1. **System Integration**
   - Connect all MCP components
   - Implement orchestrator logic
   - Add error handling and recovery
   - Create comprehensive logging

2. **Kiosk Data Collection**
   - Map all Pandasuite screens
   - Define clickable elements and coordinates
   - Create voice command mappings
   - Validate element detection accuracy

### Phase 6: Optimization & Deployment (Week 10)
1. **Performance Optimization**
   - Optimize screenshot capture frequency
   - Reduce AI model response latency
   - Implement efficient caching strategies
   - Add resource usage monitoring

2. **User Interface & Documentation**
   - Create setup and configuration tools
   - Add real-time status monitoring
   - Write comprehensive documentation
   - Create troubleshooting guides

## Technical Considerations

### WSL Configuration
- Enable WSL2 with GUI support for screenshot capture
- Configure audio device passthrough for microphone access
- Set up proper networking for MCP communication
- Install required Windows interop packages

### Security & Permissions
- Configure Windows UAC for automated mouse control
- Set up secure MCP communication channels
- Implement access control for sensitive operations
- Add audit logging for all actions

### Performance Requirements
- Target <500ms end-to-end response time
- Maintain <5% CPU usage during idle periods
- Support continuous operation for 8+ hours
- Handle graceful degradation during high load

### Error Handling
- Implement robust retry mechanisms
- Add fallback modes for component failures
- Create comprehensive error logging
- Provide clear user feedback for issues

## Deployment Architecture

```
Windows Host
├── Pandasuite Kiosk (Native)
└── WSL Environment
    ├── MCP Orchestrator
    ├── Speech-to-Text Service
    ├── Screen Capture Service
    ├── Mouse Control Service
    ├── Screen State Detector
    ├── Ollama Server + Agent
    └── Kiosk Data Manager
```

## Success Metrics

- Voice command recognition accuracy >95%
- Screen state detection accuracy >98%
- Mouse click precision within 5 pixels
- End-to-end response time <500ms
- System uptime >99.5% during demonstrations
- Voice command vocabulary coverage >90% of use cases
