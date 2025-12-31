# Communication Domain

## 🎯 **Domain Purpose**
Handles all real-time communication between client and server, including WebSocket management, message routing, and session lifecycle. This is a core bounded context for the real-time interface.

## 📏 **File Size Limits**
- **Services**: Maximum 300 lines each
- **Models**: Maximum 150 lines each  
- **Current target**: Under construction

## 🏗️ **Domain Architecture**

### **Services**
- **`websocket_manager.py`**: WebSocket connection lifecycle and session management
- **`message_router.py`**: Message type routing and dispatch orchestration
- **`session_service.py`**: User session tracking and management

### **Models**
- **`websocket_connection.py`**: WebSocket connection and session data entities
- **`message_types.py`**: Message type definitions and validation

### **Responsibilities**
- ✅ WebSocket connection accept/disconnect lifecycle
- ✅ Client session management and tracking
- ✅ Message type routing and validation
- ✅ Real-time communication coordination
- ✅ Connection error handling and recovery

## 🔗 **Domain Interfaces**

### **Inbound Dependencies**
- **FastAPI WebSocket**: Core WebSocket infrastructure
- **JSON Processing**: Message serialization/deserialization
- **Error Handling**: WebSocket-specific error management

### **Outbound Interfaces**
- **Message Events**: Structured message dispatch to other domains
- **Session State**: Connection and user session information
- **Connection Status**: Real-time connection health monitoring

## ⚠️ **Domain Invariants**
- All WebSocket connections MUST be properly accepted and tracked
- Client sessions MUST be cleaned up on disconnect
- Message routing MUST validate message types before dispatch
- Connection errors MUST be gracefully handled without crashing

## 📊 **Performance Characteristics**
- **Connection establishment**: < 100ms per client
- **Message routing**: < 10ms per message
- **Session cleanup**: Immediate on disconnect
- **Concurrent connections**: Support 1000+ simultaneous clients

## 🧪 **Testing Strategy**
- **Unit tests**: Each service method independently  
- **Integration tests**: Full WebSocket communication flow
- **Load tests**: Multiple concurrent connections
- **Error tests**: Connection failure and recovery scenarios