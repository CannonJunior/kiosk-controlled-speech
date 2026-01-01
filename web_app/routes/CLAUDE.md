# Routes - API Endpoint Layer

## 🎯 Purpose
HTTP endpoints and request/response handling - thin controllers that delegate to services.

## 📏 File Size Limits
- **Maximum: 200 lines per route module**
- **Preferred: 100-150 lines**
- **Refactor trigger: 180 lines**

## 🏗️ Route Patterns

### **Thin Controllers**
```python
from fastapi import APIRouter, HTTPException, Depends
from services.speech_service import SpeechService

router = APIRouter(prefix="/api/speech")

@router.post("/process")
async def process_speech(
    request: SpeechRequest,
    speech_service: SpeechService = Depends()
):
    """HTTP endpoint - delegate to service immediately"""
    try:
        result = await speech_service.process_audio(request.audio_data)
        return {"success": True, "data": result}
    except SpeechError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### **Consistent Response Format**
```python
# Success response
{"success": True, "data": {...}}

# Error response  
{"success": False, "error": "description"}
```

## 📂 Route Files

### **basic_routes.py** (Target: 100 lines)
- `/`, `/health`, `/troubleshooting`
- Static page serving, health checks

### **config_routes.py** (Target: 150 lines)
- `/api/vad-config`, `/api/kiosk-data`
- Configuration CRUD operations

### **screenshot_routes.py** (Target: 120 lines)
- `/api/screenshots/*`
- Screenshot listing, deletion

### **vignette_routes.py** (Target: 180 lines)
- `/api/vignettes/*`
- Vignette save, load, management

### **optimization_routes.py** (Target: 150 lines)
- `/api/optimization/*`
- Performance settings, metrics

### **websocket_routes.py** (Target: 100 lines)
- `/ws/{client_id}`
- WebSocket endpoint only

## ⚠️ Anti-Patterns
- ❌ Business logic in route handlers
- ❌ Database queries in routes
- ❌ Complex data processing
- ❌ Cross-route dependencies

## ✅ Best Practices
- ✅ Immediate service delegation
- ✅ Consistent error handling
- ✅ Request validation with Pydantic
- ✅ Dependency injection for services