# MCP Screenshot Server Research

## Available MCP Screenshot Servers

### 1. m-mcp/screenshot-server
- **Provider**: Community (m-mcp on GitHub)
- **Platform**: Cross-platform Python
- **Dependencies**: Python 3.x, Pillow, uv package manager
- **Status**: Active (March 2025)

**Installation**:
```bash
uv sync
uv run clint.py
```

**Configuration**:
```json
{
  "mcpServers": {
    "mcp-server": {
      "command": "/path/to/uv",
      "args": ["--directory", "/path/to/server", "run", "screenshot.py"]
    }
  }
}
```

**API**: `take_screenshot_image` tool

### 2. Other Notable Servers
- **Screenshot Server by Seth Bang**: Desktop capture capabilities
- **Screenshot Capture by zueai**: Enhanced capture features  
- **Screenpipe by Mediar AI**: Advanced screen recording/capture
- **ScreenshotOne**: Commercial web screenshot service

## Windows WSL Compatibility Assessment

**Limitations Found**:
- Most MCP screenshot servers target native platform screen capture
- No explicit WSL → Windows desktop capture support documented
- Current servers assume local display environment

**Required for Kiosk Project**:
- WSL-based service capturing Windows host desktop
- Cross-boundary screenshot capability
- Real-time capture for Pandasuite monitoring

## Recommendation

**Hybrid Approach**:
1. **Investigate existing MCP servers** for architecture patterns and MCP protocol implementation
2. **Extend existing server** (likely m-mcp/screenshot-server) with WSL-Windows interop
3. **Custom WSL bridge component** for Windows desktop access

**Next Steps**:
1. Clone and analyze m-mcp/screenshot-server implementation
2. Test WSL compatibility and Windows desktop access
3. Implement WSL-specific Windows interop layer if needed