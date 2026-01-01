# Services - Business Logic Layer

## 🎯 Purpose
Business logic and domain services - no HTTP handling, pure business operations.

## 📏 File Size Limits
- **Maximum: 300 lines per service**
- **Preferred: 150-250 lines**
- **Refactor trigger: 280 lines**

## 🏗️ Service Patterns

### **Single Responsibility**
- One domain per service (speech, websocket, optimization)
- Clear, focused purpose
- No cross-domain logic mixing

### **Service Structure**
```python
class SpeechService:
    """Handles speech processing business logic"""
    
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        # Dependency injection, no globals
    
    async def process_audio(self, audio_data: bytes) -> SpeechResult:
        """Process audio data - core business method"""
        # Business logic here
        pass
```

### **Error Handling**
- Raise domain-specific exceptions
- Let routes handle HTTP status codes
- Include context for debugging

## 📂 Service Files

### **speech_service.py** (Target: 250 lines)
- Audio processing, transcription
- Chat message processing, fast-path logic
- Performance metrics tracking

### **mcp_service.py** (Target: 150 lines)  
- MCP tool integration
- Result parsing utilities
- Tool discovery and health checks

### **websocket_service.py** (Target: 200 lines)
- Connection management 
- Message broadcasting
- Session tracking

### **optimization_service.py** (Target: 180 lines)
- Model configuration
- Performance monitoring
- Cache management

## ⚠️ Anti-Patterns
- ❌ HTTP request/response handling
- ❌ Route decorators or FastAPI dependencies
- ❌ Direct database access (use repositories)
- ❌ Cross-service direct calls (use interfaces)

## ✅ Best Practices
- ✅ Async/await for I/O operations
- ✅ Type hints for all public methods
- ✅ Clear error messages and logging
- ✅ Testable interfaces with dependency injection