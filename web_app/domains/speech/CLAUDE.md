# Speech Domain

## 🎯 **Domain Purpose**
Handles all audio processing, transcription, and speech-to-text functionality. This is a core bounded context for the voice-controlled interface.

## 📏 **File Size Limits**
- **Services**: Maximum 300 lines each
- **Models**: Maximum 150 lines each  
- **Current largest file**: audio_processor.py (198 lines) ✅

## 🏗️ **Domain Architecture**

### **Services**
- **`audio_processor.py`**: Audio data processing and transcription orchestration
- **`transcription_service.py`**: Specialized transcription business logic
- **`vad_processor.py`**: Voice Activity Detection processing

### **Models**
- **`audio_data.py`**: AudioData and TranscriptionResult entities

### **Responsibilities**
- ✅ Convert base64 audio to processable formats
- ✅ Manage temporary file lifecycle  
- ✅ Orchestrate MCP speech-to-text services
- ✅ Provide structured transcription results
- ✅ Track audio processing metrics

## 🔗 **Domain Interfaces**

### **Inbound Dependencies**
- **MCP Client**: For speech-to-text tool calls
- **Error Recovery**: For resilient processing
- **Path Resolver**: For temporary file management

### **Outbound Interfaces**  
- **TranscriptionResult**: Structured result format
- **AudioData**: Internal data representation

## ⚠️ **Domain Invariants**
- All temporary audio files MUST be cleaned up
- Processing metrics MUST be updated on every request
- Base64 decoding errors MUST be caught and reported
- File paths MUST use secure temporary directory

## 📊 **Performance Characteristics**
- **Target processing time**: < 2 seconds per audio chunk
- **Memory management**: Temporary files cleaned immediately after use
- **Error resilience**: Automatic retry via error recovery system

## 🧪 **Testing Strategy**
- **Unit tests**: Each service method independently
- **Integration tests**: Full audio processing pipeline
- **Performance tests**: Large audio file handling
- **Error tests**: Invalid audio data scenarios