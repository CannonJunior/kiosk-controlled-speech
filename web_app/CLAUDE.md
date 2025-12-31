# Web Application Module

## 🏗️ Architecture Principles

### **File Size Limits (CRITICAL)**
- **Maximum file size: 500 lines** (hard limit)
- **Preferred file size: 200-300 lines** 
- **If approaching 400 lines**: Immediately refactor into smaller modules
- **Use modular imports**: Never duplicate code between files

### **Separation of Concerns**
- **`main.py`**: Only FastAPI app setup, middleware, startup/shutdown (150 lines max)
- **`services/`**: Business logic, no HTTP handling
- **`routes/`**: HTTP endpoints only, delegate to services
- **`models/`**: Data structures and validation
- **`utils/`**: Pure functions, no state

### **Module Organization**
```
web_app/
├── main.py              # FastAPI app (150 lines max)
├── services/            # Business logic
├── routes/             # API endpoints  
├── models/             # Data structures
├── utils/              # Shared utilities
└── static/             # Frontend assets
    └── js/             # Modular JavaScript
```

## 📂 Directory Guidelines

### **services/ - Business Logic**
- One service per domain (speech, websocket, optimization)
- Maximum 300 lines per service
- No direct HTTP handling
- Clear single responsibility

### **routes/ - API Endpoints**
- Group related endpoints in single files
- Maximum 200 lines per route module
- Thin controllers - delegate to services
- Consistent error handling

### **static/js/ - Frontend Modules**
- Maximum 400 lines per JavaScript module
- Clear module boundaries with imports/exports
- Separate UI, business logic, and infrastructure
- Event-driven architecture

## 🔧 Best Practices

### **Code Organization**
1. **Immediate refactoring trigger**: File > 400 lines
2. **Shared functionality**: Extract to utils/ or services/
3. **API consistency**: Use same patterns across routes
4. **Error handling**: Centralized error management

### **Dependencies**
- **Circular imports**: Strictly forbidden
- **Clear interfaces**: Well-defined service contracts  
- **Minimal coupling**: Services should be independently testable
- **Dependency injection**: Use FastAPI's built-in DI

### **Testing Strategy**
- **Unit tests**: For all services and utilities
- **Integration tests**: For complete workflows
- **Route tests**: For all API endpoints
- **Frontend tests**: For critical user flows

## ⚠️ Anti-Patterns to Avoid

### **File Size Anti-Patterns**
- ❌ Single file with multiple responsibilities
- ❌ Copy/pasting code instead of extracting shared functions
- ❌ Monolithic classes with too many methods
- ❌ Route handlers with embedded business logic

### **Architecture Anti-Patterns**  
- ❌ Services calling routes
- ❌ Routes containing business logic
- ❌ Circular dependencies between modules
- ❌ Global state mutations

## 🎯 Current Status

### **Refactored Files**
- ✅ Directory structure created
- ✅ CLAUDE.md files established
- 🔄 **In Progress**: Breaking down main.py (2,347 lines → target: 150 lines)
- ⏳ **Next**: Breaking down app.js (6,666 lines → target: 200 lines)

### **Monitoring**
- **Check file sizes weekly**
- **Refactor when approaching limits**
- **Review module boundaries quarterly**
- **Update documentation with changes**

---

**Remember**: The goal is sustainable, maintainable code that can grow without hitting token limits. Always prefer smaller, focused modules over large monolithic files.