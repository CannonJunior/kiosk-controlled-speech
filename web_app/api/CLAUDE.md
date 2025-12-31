# API Layer

## 🎯 **Purpose**
Thin application layer providing versioned REST APIs and WebSocket endpoints that orchestrate domain services. This layer contains no business logic - only request/response handling and domain service coordination.

## 📏 **File Size Limits**
- **Route handlers**: Maximum 200 lines each
- **Middleware**: Maximum 150 lines each
- **Current largest file**: TBD

## 🏗️ **Architecture**

### **API Versioning Strategy**
```
api/
├── v1/                    # Version 1 endpoints
│   ├── speech_routes.py       # Speech domain endpoints
│   ├── communication_routes.py # WebSocket endpoints  
│   ├── configuration_routes.py # Config/optimization endpoints
│   ├── annotation_routes.py   # Screenshot/vignette endpoints
│   └── health_routes.py       # Health check endpoints
├── middleware/            # Request/response middleware
│   ├── error_handler.py       # Global error handling
│   ├── cors_middleware.py     # CORS configuration
│   └── metrics_middleware.py  # Request metrics
└── dependencies/          # FastAPI dependency injection
    ├── domain_services.py     # Service injection
    └── auth.py               # Authentication (future)
```

## 🔗 **Responsibilities**

### **Route Handlers (Thin Controllers)**
- ✅ HTTP request parsing and validation
- ✅ Domain service orchestration 
- ✅ HTTP response formatting
- ✅ Error handling and status codes
- ✅ OpenAPI documentation generation

### **Middleware Stack**
- ✅ CORS handling for cross-origin requests
- ✅ Request/response logging and metrics
- ✅ Global error handling with proper status codes
- ✅ Request timing and performance monitoring

### **Dependency Injection**
- ✅ Domain service lifecycle management
- ✅ Infrastructure service injection
- ✅ Configuration-based service assembly

## ⚠️ **API Layer Invariants**
- Route handlers MUST contain no business logic
- All business logic MUST be delegated to domain services
- HTTP status codes MUST be semantically correct
- API versioning MUST be preserved for backward compatibility

## 📊 **Performance Targets**
- **Route handler overhead**: < 5ms per request
- **Error response time**: < 100ms
- **Health check response**: < 50ms
- **WebSocket upgrade**: < 200ms

## 🧪 **Testing Strategy**
- **Unit tests**: Route handler logic without domain services
- **Integration tests**: Full request/response cycles
- **Contract tests**: API schema validation
- **Performance tests**: Response time benchmarks