### ✅ Rules Currently Being Followed
- **Rule 1**: Creating CLAUDE.md in every new folder
- **Rule 2**: Keeping CLAUDE.md under 100 lines unless critical
- **Rule 3**: Not exceeding 200 lines without permission
- **Rule 4**: Using XML tags in CLAUDE.md files (XML.md created)
- **Rule 5**: Using <file_map> tags to point to files
- **Rule 6**: Creating EXAMPLES.md for code patterns (created)
- **Rule 7**: Using @ syntax for file tagging
- **Rule 8**: Planning to use parallel tasks for complex operations
- **Rule 9**: Will auto /compact at 30% context remaining
- **Rule 10**: Creating MCP servers when possible (MCP.md created)

## 🔄 **CRITICAL: Post-Update Actions Required**

**After ANY code changes to the web application, users MUST:**

### **1. Restart the Server** 
```bash
# Kill existing server process
pkill -f "python.*main.py" || pkill -f "uvicorn"

# Start the server fresh
cd /home/kiosk_user/kiosk-controlled-speech
python3 web_app/main.py
```

### **2. Refresh Browser (Hard Refresh)**
- **Chrome/Edge**: `Ctrl + Shift + R` or `Ctrl + F5`  
- **Firefox**: `Ctrl + Shift + R`
- **Or**: Clear browser cache completely

### **3. Verify Updates Applied**
- Check console logs for new functionality
- Test modified features (e.g., timeout handling, fast-path processing)
- Verify timing metrics appear in chat interface

### **Why This Is Required:**
- **Python backend**: Changes to `web_app/main.py` require server restart
- **JavaScript frontend**: Changes to `vad_app.js` require hard browser refresh
- **Cached responses**: Browser may serve old JS/CSS from cache
- **WebSocket connections**: Need fresh connection for new message handling

**⚠️ ALWAYS provide this guidance after implementing updates!**

