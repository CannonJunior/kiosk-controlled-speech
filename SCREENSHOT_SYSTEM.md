# Screenshot System Documentation

This document provides comprehensive documentation for the screenshot capture system in the kiosk-controlled-speech application.

## Overview

The screenshot system enables real-time desktop capture with annotation capabilities and will support text extraction and reading functionality. It consists of three main components:

1. **MCP Screen Capture Service** - Backend desktop capture
2. **Web App Screenshot Gallery** - Frontend UI and gallery management  
3. **Screenshot Text Reading** (Coming in Phase 1 Week 2) - OCR and TTS integration

---

## Architecture

### Component Overview

```
Desktop Screen
     ↓ (PowerShell capture)
MCP Screen Capture Service  
     ↓ (FastMCP protocol)
Web App Backend (FastAPI)
     ↓ (WebSocket/HTTP)
Frontend JavaScript (Gallery UI)
     ↓ (Future: OCR → TTS)
Audio Output (Text Reading)
```

### Data Flow

1. **Capture Request**: User clicks "Take Screenshot" button
2. **MCP Call**: Frontend → Web App → MCP Screen Capture Service
3. **Desktop Capture**: PowerShell/PIL captures screen to file
4. **File Storage**: Screenshot saved to `/web_app/static/screenshots/`
5. **Gallery Update**: Frontend receives screenshot metadata via WebSocket
6. **User Interaction**: Modal viewing, download, delete, annotation
7. **Future**: Region selection → OCR → TTS → Audio playback

---

## Backend Components

### MCP Screen Capture Service

**Location**: `/services/screen_capture/mcp_server.py`

**Key Functions**:

#### `take_screenshot()`
- **Purpose**: Captures full desktop screenshot
- **Method**: Multiple fallback approaches (PowerShell → PIL → subprocess)
- **Output**: Saves PNG file with unique timestamp-based name
- **Returns**: File path, dimensions, file size, metadata

**Implementation Details**:
```python
async def take_screenshot():
    """Take a screenshot and save it to file"""
    # Primary method: PowerShell (Windows)
    # Fallback 1: PIL ImageGrab  
    # Fallback 2: Platform-specific commands
    # Returns: {"path": "screenshot_path", "width": 1920, "height": 1080, "size_bytes": 102400}
```

**Configuration**:
- Screenshot directory: `../web_app/static/screenshots/`
- File naming: `screenshot_YYYYMMDD_HHMMSS_UUID.png`
- Supported formats: PNG (default), JPEG (configurable)

### Web App Backend Integration

**Location**: `/web_app/main.py`

**API Endpoints**:

#### `POST /api/mcp-tool` 
- **Purpose**: Generic MCP tool calling endpoint
- **Screenshot Usage**: Called with `tool_name: "screen_capture_take_screenshot"`
- **Returns**: Screenshot metadata and success status

**WebSocket Integration**:
- Real-time screenshot notifications
- Gallery updates without page refresh
- Progress indicators during capture

---

## Frontend Components

### Screenshot Gallery UI

**Location**: `/web_app/static/app.js` (Screenshot-related functions)

**Key Functions**:

#### `takeScreenshot()`
- **Purpose**: Initiates screenshot capture from UI
- **Process**: Button state management → MCP call → Gallery update
- **UI Feedback**: Loading spinner, success/error messages

#### Screenshot Gallery Management
- **Modal Viewing**: Full-size screenshot display with zoom
- **Thumbnail Grid**: Responsive gallery layout
- **Download/Delete**: Individual screenshot management
- **Metadata Display**: Timestamp, file size, dimensions

**UI Elements**:
```html
<!-- Take Screenshot Button -->
<button id="takeScreenshotButton">
    <i class="fas fa-camera"></i><span>Take Screenshot</span>
</button>

<!-- Gallery Modal -->
<div id="screenshotModal" class="modal">
    <div class="modal-content">
        <img id="screenshotModalImage" />
        <div class="screenshot-actions">
            <button id="downloadScreenshotButton">Download</button>
            <button id="deleteScreenshotButton">Delete</button>
            <!-- Future: Read Text Button -->
        </div>
    </div>
</div>
```

### Drawing/Annotation System

**Current Capabilities**:
- Rectangle drawing on screenshots
- Shape overlay management
- Coordinate tracking for annotations

**Future Extension for Text Reading**:
- Region selection for OCR processing
- Visual feedback for selected text areas
- Integration with OCR confidence indicators

---

## File Management

### Storage Structure

```
web_app/
└── static/
    └── screenshots/
        ├── screenshot_20241206_143022_a1b2c3d4.png
        ├── screenshot_20241206_143045_e5f6g7h8.png
        └── ...
```

### File Naming Convention

**Format**: `screenshot_YYYYMMDD_HHMMSS_UUID.png`
- **YYYY**: 4-digit year
- **MM**: 2-digit month (01-12)
- **DD**: 2-digit day (01-31)
- **HH**: 2-digit hour (00-23)
- **MM**: 2-digit minute (00-59)  
- **SS**: 2-digit second (00-59)
- **UUID**: 8-character unique identifier

**Example**: `screenshot_20241206_143022_a1b2c3d4.png`

### File Cleanup

**Current**: Manual deletion via UI
**Future**: Automatic cleanup of old files (configurable retention period)

---

## Error Handling

### Capture Errors

**Common Issues**:
1. **Permission Denied**: Screen capture blocked by security software
2. **Display Detection**: Multiple monitors, virtual displays
3. **File System**: Disk space, write permissions
4. **Service Availability**: MCP server connection issues

**Error Recovery**:
- Fallback capture methods (PowerShell → PIL → subprocess)
- Graceful degradation with user feedback
- Retry mechanisms for transient failures

### UI Error Handling

**User Feedback**:
- Visual error indicators on failed capture
- Toast notifications for success/failure
- Detailed error messages in console logs

---

## Performance Characteristics

### Screenshot Capture

**Typical Performance**:
- **Capture Time**: 500ms - 2 seconds (depending on screen resolution)
- **File Size**: 500KB - 5MB (1080p-4K screenshots)
- **Processing Overhead**: Minimal (direct file save)

**Optimization Opportunities**:
- Image compression settings
- Resolution scaling for faster capture
- Asynchronous processing pipeline

### Gallery Performance

**Current State**:
- Thumbnail generation: On-demand
- Modal loading: Direct file serving
- Memory usage: Efficient (no in-memory caching)

**Scalability Considerations**:
- Gallery pagination for large screenshot collections
- Thumbnail pre-generation
- CDN integration for file serving

---

## Future Enhancements (Phase 1 Week 2)

### Text Reading Integration

**Planned Components**:

#### 1. OCR Service Integration
- **Technology**: Tesseract OCR or cloud APIs
- **Input**: Screenshot region selection
- **Output**: Extracted text with confidence scores

#### 2. Region Selection UI
- **Interactive Selection**: Mouse-based region drawing
- **Visual Feedback**: Highlight selected areas
- **Coordinate Capture**: X, Y, width, height for OCR processing

#### 3. Text-to-Speech Integration  
- **TTS Engine**: Windows SAPI or cloud services
- **Audio Generation**: Convert extracted text to speech
- **Playback Controls**: Play/pause/stop audio controls

#### 4. Workflow Integration
**Complete Flow**: Screenshot → Region Select → OCR → TTS → Audio Playback

### Enhanced Gallery Features

**Planned Additions**:
- **Text Annotations**: Display extracted text overlay
- **Search Functionality**: Search screenshots by extracted text
- **OCR History**: Track text reading sessions
- **Export Options**: Text export, audio file download

---

## Configuration

### Screenshot Settings

**Default Configuration**:
```json
{
  "screenshot": {
    "format": "PNG",
    "quality": 95,
    "directory": "static/screenshots",
    "max_storage_mb": 1000,
    "retention_days": 30
  }
}
```

### Future OCR Settings

**Planned Configuration**:
```json
{
  "ocr": {
    "engine": "tesseract",
    "language": "eng",
    "confidence_threshold": 0.7,
    "preprocessing": true
  },
  "tts": {
    "engine": "sapi",
    "voice": "default",
    "speed": 1.0,
    "volume": 0.8
  }
}
```

---

## Troubleshooting

### Common Issues

#### Screenshot Not Captured
1. **Check MCP Service**: Verify screen capture MCP server is running
2. **Permissions**: Ensure application has screen capture permissions
3. **Display Issues**: Check for multiple monitors or virtual displays
4. **File System**: Verify write permissions to screenshots directory

#### Gallery Not Loading
1. **File Permissions**: Check static file serving permissions
2. **Path Issues**: Verify screenshot directory exists and is accessible
3. **Browser Cache**: Clear browser cache if thumbnails not updating

#### Performance Issues
1. **Large Files**: Check screenshot file sizes (>5MB may cause slow loading)
2. **Storage Space**: Monitor available disk space
3. **Network**: For remote access, consider file size optimization

### Debug Information

**Logging Locations**:
- **MCP Service**: Console output from screen capture server
- **Web App**: FastAPI logs with screenshot capture events
- **Frontend**: Browser console for UI interaction errors

**Key Metrics to Monitor**:
- Screenshot capture success rate
- Average file sizes
- Gallery loading performance
- Error frequency and types

---

## API Reference

### MCP Tool Calls

#### Take Screenshot
```python
# Call via /api/mcp-tool endpoint
POST /api/mcp-tool
{
    "tool_name": "screen_capture_take_screenshot",
    "args": {}
}

# Response
{
    "success": true,
    "data": {
        "screenshot_path": "screenshots/screenshot_20241206_143022_a1b2c3d4.png",
        "full_path": "/home/user/project/web_app/static/screenshots/screenshot_20241206_143022_a1b2c3d4.png",
        "width": 1920,
        "height": 1080,
        "file_size_bytes": 1048576,
        "timestamp": "2024-12-06T14:30:22"
    }
}
```

### WebSocket Messages

#### Screenshot Capture Success
```json
{
    "type": "screenshot_captured",
    "screenshot_data": {
        "path": "screenshots/screenshot_20241206_143022_a1b2c3d4.png",
        "width": 1920,
        "height": 1080,
        "size": 1048576,
        "timestamp": "2024-12-06T14:30:22"
    }
}
```

#### Future: Text Reading Messages
```json
{
    "type": "text_extraction_complete",
    "screenshot_id": "screenshot_20241206_143022_a1b2c3d4",
    "extracted_text": "Sample extracted text...",
    "confidence": 0.92,
    "audio_available": true
}
```

---

This documentation will be updated as the text reading functionality is implemented in Phase 1 Week 2.