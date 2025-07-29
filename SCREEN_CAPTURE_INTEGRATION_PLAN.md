# Web App + WSL MCP Screen Capture Integration Plan

## 🎯 Overview

Plan to integrate the working PowerShell screen capture from WSL with the web application, replacing the current browser-based screenshot methods with real screen capture.

## 📋 Current State Analysis

### ✅ What Works Now:
- **PowerShell Script Method**: Successfully captures real screenshots (1280x720, 76KB)
- **MCP Server**: FastMCP server running with screenshot tools
- **Web App**: Browser-based screenshot API (limited to page content)
- **File Serving**: Static file serving for screenshots

### ❌ Current Issues:
- Web app uses browser APIs (limited to page/tab content)
- No integration between web app and WSL MCP server
- PowerShell method not integrated into MCP server
- Browser security prevents silent screen capture

## 🏗️ Integration Architecture

```
┌─────────────────┐    HTTP POST     ┌──────────────────┐    MCP Call    ┌─────────────────┐
│   Browser       │ ────────────────▶│   FastAPI        │ ──────────────▶│   MCP Server    │
│   (Frontend)    │                  │   (Web App)      │                │   (WSL)         │
└─────────────────┘                  └──────────────────┘                └─────────────────┘
                                               │                                   │
                                               │                                   ▼
                                               │                          ┌─────────────────┐
                                               │                          │   PowerShell    │
                                               │                          │   Script        │
                                               │                          └─────────────────┘
                                               │                                   │
                                               │                                   ▼
                                               │                          ┌─────────────────┐
                                               │ ◀────────────────────────│   Windows       │
                                               │      Screenshot File     │   Desktop       │
                                               ▼                          └─────────────────┘
                                    ┌──────────────────┐
                                    │   Static Files   │
                                    │   /screenshots/  │
                                    └──────────────────┘
```

## 📝 Implementation Plan

### Phase 1: Fix MCP Server Screenshot Method

#### 1.1 Update MCP Server PowerShell Implementation
- **File**: `services/screen_capture/mcp_server.py`
- **Action**: Replace failing PowerShell one-liner with working script method
- **Method**: Use temporary PowerShell script files instead of inline commands

```python
# Current (failing):
ps_cmd = f'powershell.exe -Command "Add-Type... $bmp.Save('{path}')"'

# New (working):
script_content = f"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bmp)
$graphics.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bounds.Size)
$bmp.Save('{win_path}')
$graphics.Dispose()
$bmp.Dispose()
"""
# Save to temp .ps1 file and execute with -File parameter
```

#### 1.2 Test MCP Integration
- **Script**: `test_mcp_screenshot.py` (update existing)
- **Verify**: MCP server returns real screenshot data
- **Validate**: File creation and metadata

### Phase 2: Web App Backend Integration

#### 2.1 Enhance MCP Tool Endpoint
- **File**: `web_app/main.py`
- **Current**: `/api/mcp-tool` endpoint exists
- **Enhancement**: Ensure proper error handling and response formatting

```python
@app.post("/api/mcp-tool")
async def call_mcp_tool(request: Request):
    # Existing endpoint - verify it works with updated MCP server
    # Add logging for screenshot calls
    # Handle file path responses properly
```

#### 2.2 Add Screenshot-Specific Endpoint (Optional)
- **New**: `/api/screenshot/take` endpoint for simplified calling
- **Purpose**: Dedicated screenshot endpoint with better error handling

### Phase 3: Frontend Integration

#### 3.1 Update JavaScript Screenshot Method
- **File**: `web_app/static/app.js`
- **Current**: Browser-based APIs (Screen Capture, html2canvas, canvas)
- **New**: Call WSL MCP server via existing `/api/mcp-tool` endpoint

```javascript
async takeScreenshot() {
    try {
        // Call MCP tool instead of browser APIs
        const response = await this.callMCPTool('screen_capture_take_screenshot', {});
        
        if (response.success) {
            // Handle response with real screenshot path
            const screenshot = {
                id: Date.now().toString(),
                timestamp: new Date().toISOString(),
                path: response.data.screenshot_path,
                filename: response.data.filename,
                size: response.data.size,
                method: response.data.method // "PowerShell Script"
            };
            
            this.addScreenshotToGallery(screenshot);
        }
    } catch (error) {
        this.showError('Failed to take screenshot: ' + error.message);
    }
}
```

#### 3.2 Update UI Messaging
- **Change**: Remove browser permission prompts
- **Add**: Status messages for WSL screenshot process
- **Show**: Method used (PowerShell Script vs Mock)

### Phase 4: File Management

#### 4.1 Screenshot Storage Strategy
- **Current**: `web_app/static/screenshots/`
- **Keep**: Same directory structure for static serving
- **Add**: Cleanup mechanism for old screenshots

#### 4.2 Cross-Platform Paths
- **WSL Path**: `/home/kiosk_user/kiosk-controlled-speech/web_app/static/screenshots/`
- **Windows Path**: `C:\temp\` (temporary) → copy to WSL
- **Web Path**: `/static/screenshots/filename.png`

### Phase 5: Error Handling & Fallbacks

#### 5.1 Graceful Degradation
```python
# Priority order:
1. PowerShell Script (real screenshot)
2. PowerShell One-liner (if script fails)
3. Python Windows (if PowerShell fails)
4. Mock Generation (if all real methods fail)
```

#### 5.2 User Feedback
- **Success**: "📸 Real screenshot captured via PowerShell"
- **Fallback**: "🎭 Mock screenshot generated (real capture failed)"
- **Error**: Specific error messages with troubleshooting tips

## 🔧 Implementation Steps

### Step 1: Fix MCP Server (30 minutes)
```bash
# Edit MCP server to use working PowerShell script method
nano services/screen_capture/mcp_server.py

# Test the fix
python3 test_mcp_screenshot.py
```

### Step 2: Update Web App Frontend (15 minutes)
```bash
# Update JavaScript to call MCP instead of browser APIs
nano web_app/static/app.js

# Test via web interface
```

### Step 3: Integration Testing (15 minutes)
```bash
# Start web app
cd web_app && python3 main.py

# Test screenshot button in browser
# Verify real screenshots are captured and displayed
```

### Step 4: Validation (10 minutes)
```bash
# Verify file sizes and dimensions indicate real screenshots
# Check that method shows "PowerShell Script" not "Mock"
# Confirm gallery displays real screen content
```

## 📊 Success Criteria

### ✅ Technical Success:
- [ ] MCP server captures real screenshots via PowerShell
- [ ] Web app calls MCP server successfully
- [ ] Screenshots display in web gallery
- [ ] File sizes > 50KB (indicating real content)
- [ ] Dimensions match screen resolution (not 1920x1080 mock)

### ✅ User Experience Success:
- [ ] Click "Take Screenshot" → real desktop capture appears
- [ ] No browser permission prompts
- [ ] Screenshot shows actual Windows desktop content
- [ ] Gallery updates with real screenshots
- [ ] Download functionality works

### ✅ Error Handling Success:
- [ ] Graceful fallback to mock if PowerShell fails
- [ ] Clear error messages for troubleshooting
- [ ] System continues working even if screenshots fail

## 🚀 Expected Outcome

After implementation:

1. **User clicks "Take Screenshot"** in web app
2. **JavaScript calls** `/api/mcp-tool` endpoint  
3. **FastAPI calls** MCP server in WSL
4. **MCP server executes** PowerShell script
5. **PowerShell captures** real Windows desktop
6. **File saved** to WSL screenshots directory
7. **Web app displays** real screenshot in gallery
8. **User sees** actual desktop content, not browser page

## 🔍 Testing Strategy

### Unit Tests:
- MCP server PowerShell method
- Web app MCP endpoint
- JavaScript screenshot function

### Integration Tests:
- End-to-end screenshot capture flow
- Error handling scenarios
- File system operations

### Manual Tests:
- User workflow testing
- Cross-browser compatibility
- Performance validation

## 📈 Performance Considerations

- **Screenshot Time**: ~2-3 seconds (PowerShell + file operations)
- **File Size**: 50-200KB typical for real screenshots
- **Concurrent Users**: MCP server handles one screenshot at a time
- **Storage**: Implement cleanup for old screenshots

## 🔒 Security Considerations

- **PowerShell Execution**: Limited to screenshot functionality
- **File Access**: Restricted to screenshots directory
- **User Permissions**: No additional Windows permissions required
- **Network**: MCP communication stays local (WSL ↔ Web App)

---

## 📋 Next Steps

1. **Implement Phase 1**: Fix MCP server PowerShell method
2. **Test Integration**: Verify MCP → Web App communication
3. **Update Frontend**: Replace browser APIs with MCP calls
4. **Validate Results**: Confirm real screenshots appear in gallery
5. **Document**: Update user instructions for real screenshot capability