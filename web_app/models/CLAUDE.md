# Models - Data Structures

## 🎯 Purpose
Pydantic models, data classes, and type definitions - no business logic.

## 📏 File Size Limits
- **Maximum: 150 lines per model file**
- **Preferred: 50-100 lines**
- **Refactor trigger: 120 lines**

## 🏗️ Model Patterns

### **Request/Response Models**
```python
from pydantic import BaseModel
from typing import Optional, List

class SpeechRequest(BaseModel):
    audio_data: str
    processing_mode: str = "llm"
    context: Optional[dict] = None

class SpeechResponse(BaseModel):
    success: bool
    transcription: str
    confidence: float
    processing_time: str
```

### **Domain Models**
```python
@dataclass
class WebSocketConnection:
    client_id: str
    connected_at: datetime
    message_count: int
    last_activity: datetime
```

## 📂 Model Files

### **request_models.py** (Target: 100 lines)
- API request/response schemas
- Validation rules

### **speech_models.py** (Target: 80 lines)
- Speech processing data structures
- Audio processing types

### **websocket_models.py** (Target: 60 lines)
- WebSocket message types
- Connection tracking models

## ⚠️ Anti-Patterns
- ❌ Business logic in models
- ❌ Database operations
- ❌ Complex calculations
- ❌ External service calls

## ✅ Best Practices
- ✅ Clear validation rules
- ✅ Type hints for all fields
- ✅ Immutable data where possible
- ✅ Self-documenting field names