# Annotation Domain

## 🎯 **Domain Purpose**
Manages screenshot capture, annotation workflows, and vignette creation/management. This domain handles all visual content capture, organization, and structured annotation processes for the kiosk interface.

## 📏 **File Size Limits**
- **Services**: Maximum 300 lines each
- **Models**: Maximum 150 lines each  
- **Current target**: Under construction

## 🏗️ **Domain Architecture**

### **Services**
- **`screenshot_service.py`**: Screenshot capture orchestration via MCP integration
- **`vignette_service.py`**: Vignette creation, management, and persistence
- **`gallery_service.py`**: Screenshot gallery management and file operations
- **`annotation_service.py`**: Annotation workflow and metadata management

### **Models**
- **`screenshot_models.py`**: Screenshot data structures and metadata
- **`vignette_models.py`**: Vignette structures with screenshots and annotations
- **`annotation_models.py`**: Annotation data and workflow states

### **Repositories**
- **`vignette_repository.py`**: Vignette persistence and file management
- **`screenshot_repository.py`**: Screenshot file system operations

### **Responsibilities**
- ✅ Screenshot capture via MCP screen_capture service
- ✅ Screenshot gallery management and file operations
- ✅ Vignette creation with screenshot collections
- ✅ Vignette metadata persistence and indexing
- ✅ Screenshot file copying and organization
- ✅ Annotation workflow and metadata management

## 🔗 **Domain Interfaces**

### **Inbound Dependencies**
- **MCP Client**: For screen capture tool integration
- **File System**: Screenshot and vignette file management
- **Path Resolution**: File path management and validation

### **Outbound Interfaces**
- **Screenshot Data**: Structured screenshot information
- **Vignette Collections**: Organized screenshot collections
- **Gallery Listings**: File system based screenshot listings
- **Annotation Metadata**: Structured annotation workflows

## ⚠️ **Domain Invariants**
- All screenshot files MUST be validated before processing
- Vignette names MUST be sanitized for filesystem safety
- Screenshot copying MUST preserve original timestamps
- Vignette index MUST be updated atomically with metadata

## 📊 **Performance Characteristics**
- **Screenshot capture**: < 2 seconds via MCP integration
- **Gallery listing**: < 500ms for 100+ screenshots
- **Vignette creation**: < 1 second for 10 screenshot collection
- **File operations**: Atomic with rollback on failure

## 🧪 **Testing Strategy**
- **Unit tests**: Each service method independently
- **Integration tests**: MCP screenshot capture workflow
- **File system tests**: Vignette creation and persistence
- **Error tests**: File system failures and recovery scenarios