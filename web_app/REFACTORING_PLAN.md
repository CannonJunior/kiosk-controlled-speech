# Web Application Refactoring Plan
*Enhanced with 2024 Industry Best Practices & AI-Assisted Development*

## Overview
Both `main.py` (2,347 lines) and `app.js` (6,666 lines) have exceeded manageable sizes and token limits. This plan applies **Domain-Driven Design (DDD)** principles and modern **AI-assisted development practices** to break them into modular, maintainable components while preserving all functionality.

## 🏗️ **Architectural Philosophy (2024 Best Practices)**

### **Domain-Driven Design Alignment**
Following 2024 DDD microservices patterns, each module represents a **bounded context**:
- **Speech Domain**: Audio processing, transcription, VAD
- **Communication Domain**: WebSocket, messaging, real-time events  
- **Configuration Domain**: Settings, kiosk data, optimization
- **Annotation Domain**: Screenshot workflows, vignettes, drawing
- **UI Domain**: Interface components, state management, overlays

### **Single Responsibility & Independence**
Each service/module must be:
- **Deployable independently** (following microservices principles)
- **Testable in isolation** (clear interfaces, dependency injection)
- **Scalable separately** (focused responsibilities)
- **Maintainable by single team** (cognitive load management)

## Phase 1: Backend Refactoring (main.py)

### **Target Architecture (DDD-Aligned)**
```
web_app/
├── main.py                    # FastAPI app, startup, DI container (120 lines)
├── domains/                   # Domain-driven bounded contexts
│   ├── speech/               # Speech Processing Domain
│   │   ├── services/         # Business logic
│   │   │   ├── audio_processor.py     # Audio processing
│   │   │   ├── transcription_service.py # Speech-to-text
│   │   │   └── vad_processor.py       # Voice activity detection
│   │   ├── models/           # Domain entities
│   │   │   ├── audio_data.py # Audio data structures
│   │   │   └── transcription.py # Transcription entities
│   │   └── repositories/     # Data access (if needed)
│   ├── communication/        # Real-time Communication Domain
│   │   ├── services/
│   │   │   ├── websocket_manager.py # Connection management
│   │   │   └── message_router.py    # Message routing
│   │   └── models/
│   │       └── websocket_models.py  # Session, message types
│   ├── configuration/        # Configuration Domain
│   │   ├── services/
│   │   │   ├── config_manager.py    # Configuration management
│   │   │   └── optimization_service.py # Performance settings
│   │   └── models/
│   │       └── config_models.py     # Settings structures
│   └── annotation/          # Annotation Domain
│       ├── services/
│       │   ├── screenshot_service.py # Screenshot management
│       │   ├── vignette_service.py  # Vignette workflows
│       │   └── drawing_service.py   # Drawing operations
│       └── models/
│           └── annotation_models.py # Annotation entities
├── infrastructure/           # Cross-cutting concerns
│   ├── mcp/                 # MCP tool integration
│   │   ├── mcp_client.py    # Client wrapper
│   │   └── tool_registry.py # Available tools
│   ├── monitoring/          # Observability
│   │   ├── metrics.py       # Performance tracking
│   │   └── logging.py       # Structured logging
│   └── cache/              # Caching layer
│       └── redis_client.py  # Cache implementation
├── api/                     # Application layer (thin controllers)
│   ├── v1/                  # API versioning
│   │   ├── speech_routes.py     # Speech endpoints
│   │   ├── config_routes.py     # Configuration endpoints
│   │   ├── annotation_routes.py # Annotation endpoints
│   │   └── websocket_routes.py  # WebSocket endpoint
│   └── middleware/          # Request/response middleware
│       └── error_handler.py # Global error handling
└── shared/                  # Shared utilities
    ├── types/               # Common types
    ├── exceptions/          # Domain exceptions
    └── utils/              # Pure functions
```

### **Key Improvements from 2024 Research**
1. **Domain Boundaries**: Each domain is a bounded context with its own services, models, and repositories
2. **Separation of Infrastructure**: MCP, monitoring, caching separated from business logic
3. **API Versioning**: Future-proof API design with v1/ namespace
4. **Dependency Injection**: Clean DI container in main.py for testability
5. **Observability**: Built-in metrics, logging, and monitoring patterns

### Current Functionality Distribution
- **main.py current**: 2,347 lines, everything in one file
- **main.py target**: ~150 lines, just app setup
- **services/**: ~800 lines, business logic extraction
- **routes/**: ~1,200 lines, API endpoint separation
- **models/utils**: ~200 lines, shared components

## Phase 2: Frontend Refactoring (app.js)

### Target Architecture  
```
web_app/static/
├── js/
│   ├── app.js                 # Main coordinator (200 lines)
│   ├── core/                  # Core infrastructure
│   │   ├── WebSocketManager.js # Communication
│   │   ├── ConfigManager.js    # Configuration
│   │   └── StateManager.js     # Global state
│   ├── ui/                    # UI components
│   │   ├── DOMManager.js       # Element discovery
│   │   ├── UIStateManager.js   # Mode toggles
│   │   ├── ModalManager.js     # Dialogs
│   │   └── SettingsManager.js  # Settings panel
│   ├── audio/                 # Audio functionality
│   │   ├── AudioManager.js     # Recording, devices
│   │   ├── VADProcessor.js     # Voice detection
│   │   └── SpeechProcessor.js  # Transcription
│   ├── elements/              # Element management
│   │   ├── ElementManager.js   # Tables, dropdowns
│   │   ├── OverlayManager.js   # Positioning
│   │   └── CoordinateManager.js # Conversions
│   ├── annotation/            # Annotation system
│   │   ├── AnnotationMode.js   # Main mode class
│   │   ├── ScreenshotManager.js # Screenshot handling
│   │   └── VignetteManager.js  # Vignette organization
│   └── utils/                 # Utilities
│       ├── TextUtils.js       # Similarity
│       └── UIUtils.js         # Helpers
└── index.html                 # Updated script imports
```

### Current Functionality Distribution
- **app.js current**: 6,666 lines, everything in one file
- **app.js target**: ~200 lines, coordination only
- **core/**: ~800 lines, infrastructure
- **ui/**: ~1,500 lines, interface components
- **audio/**: ~1,200 lines, speech/recording
- **elements/**: ~1,000 lines, element management
- **annotation/**: ~1,800 lines, annotation system
- **utils/**: ~400 lines, shared utilities

## 🤖 **AI-Assisted Implementation Strategy (2024 Best Practices)**

### **Claude Code Memory Management**
Following enterprise AI development patterns:

1. **Bootstrap Pattern**: Use `/init` to analyze codebase and generate comprehensive CLAUDE.md files
2. **Quick Memory Pattern**: Prefix instructions with `#` to add to memory instantly
3. **Checkpoint Pattern**: Update memory files before major refactoring phases
4. **Batch Processing**: Refactor 5-10 files per session for optimal accuracy

### **Incremental Refactoring Strategy** 
*Based on 2024 industry safety patterns:*

#### **Phase-Gate Approach**
- **Surgical Extraction**: 50-100 lines at a time, not entire modules
- **Test After Each Step**: Automated tests must pass between extractions  
- **Git Worktrees**: Multiple Claude sessions on different domains simultaneously
- **Feature Flags**: Toggle new architecture during development

#### **Risk Management Protocol**
- **Advisory Mode First**: Keep Claude in advisory mode for initial weeks
- **Acceptance Tests**: Clear criteria for each phase before proceeding
- **Rollback Strategy**: Preserve original files as `.backup` during entire process
- **Performance Benchmarks**: Measure latency, memory usage before/after

### **Critical Preservation Requirements (Enhanced)**

#### **1. WebSocket Message Flow**
- **Protocol Contracts**: Document all message types with JSON schemas
- **Event Sourcing**: Track all state changes through events
- **Backward Compatibility**: Maintain existing client expectations

#### **2. State Management** 
- **State Machine Documentation**: Map current state transitions
- **Immutable State Updates**: Prevent race conditions in concurrent refactoring
- **State Validation**: Assert state consistency at domain boundaries

#### **3. Coordinate System Integrity**
- **Pixel-Perfect Preservation**: Screenshot overlay positioning is business-critical
- **Mathematical Invariants**: Document coordinate transformation formulas
- **Visual Regression Tests**: Automated screenshot comparisons

#### **4. VAD Processing Algorithms**
- **Signal Processing Integrity**: Audio algorithms cannot be modified
- **Performance Characteristics**: Maintain real-time processing requirements
- **Calibration Data**: Preserve threshold settings and configuration

#### **5. Domain Event Flows** *(New - from DDD research)*
- **Event Choreography**: Map inter-domain event dependencies
- **Eventual Consistency**: Handle async domain interactions properly
- **Event Versioning**: Support schema evolution across domains

### **Refactoring Phases (AI-Enhanced)**

#### **Phase 1: Foundation & Memory** (1-2 days)
- ✅ Create DDD directory structure
- ✅ Generate CLAUDE.md files with Bootstrap Pattern
- ⏳ Establish git worktree branches for parallel development
- ⏳ Set up feature flags for architecture switching

#### **Phase 2: Domain Extraction** (1 week, parallel streams)
*Use multiple Claude sessions via git worktrees:*
- **Stream A**: Speech Domain extraction (audio, transcription, VAD)
- **Stream B**: Communication Domain extraction (WebSocket, messaging)  
- **Stream C**: Configuration Domain extraction (settings, optimization)
- **Stream D**: Annotation Domain extraction (screenshots, vignettes)

#### **Phase 3: Infrastructure Layer** (3-4 days)
- Extract MCP integration to infrastructure layer
- Implement monitoring and observability patterns
- Add caching layer with proper invalidation

#### **Phase 4: Frontend Domain Modules** (1 week, parallel streams)
- **Stream A**: Core infrastructure (WebSocket, state management)
- **Stream B**: Audio domain (recording, VAD, transcription) 
- **Stream C**: UI domain (components, overlays, modals)
- **Stream D**: Annotation domain (screenshot workflows)

#### **Phase 5: Integration & Testing** (2-3 days)
- Update all imports with dependency injection
- End-to-end testing with feature flag toggles
- Performance regression testing
- Documentation updates

## 🎯 **Success Criteria (Enhanced with 2024 Metrics)**

### **Technical Quality Gates**
- [ ] **Functional Parity**: All current features work identically (automated regression tests)
- [ ] **File Size Compliance**: No file exceeds domain limits (300 backend, 400 frontend)
- [ ] **Domain Boundaries**: Clear separation of concerns with DDD bounded contexts
- [ ] **Performance Baselines**: <2% degradation in response times, memory usage
- [ ] **Test Coverage**: >80% unit test coverage per domain, >90% integration coverage
- [ ] **Documentation**: CLAUDE.md files at every level with architecture decisions

### **AI Development Quality Gates** *(New - from 2024 research)*
- [ ] **Context Efficiency**: Token usage <200k per Claude session
- [ ] **Memory Persistence**: Key architecture decisions preserved in memory files
- [ ] **Batch Success Rate**: >95% of 5-10 file batches complete without errors
- [ ] **Parallel Development**: 4 concurrent git worktree streams without conflicts

### **Business Value Metrics** *(Enterprise patterns)*
- [ ] **Feature Velocity**: 25% faster new feature development time
- [ ] **Maintenance Overhead**: 50% reduction in cross-domain change impact
- [ ] **Onboarding Speed**: New developers productive within 2 days per domain
- [ ] **Cognitive Load**: Any single developer can understand one complete domain

### **Observability & Monitoring** *(Cloud-native requirements)*
- [ ] **Error Tracking**: Domain-specific error rates and alerting
- [ ] **Performance Monitoring**: Per-domain latency and throughput metrics  
- [ ] **Dependency Health**: MCP tool availability and response times
- [ ] **User Experience**: WebSocket connection stability and audio processing quality

## ⚠️ **Enhanced Risk Mitigation (2024 Safety Patterns)**

### **Development Safety**
- **Multi-Session Isolation**: Git worktrees prevent Claude session conflicts
- **Feature Flag Protection**: Toggle between old/new architecture during development
- **Continuous Integration**: Automated tests run on every domain extraction
- **Performance Monitoring**: Real-time alerts if refactoring degrades performance

### **Data & State Protection** 
- **Immutable Backups**: Original files preserved throughout entire process
- **State Snapshots**: Database/config snapshots before each phase
- **Transaction Boundaries**: Atomic commits per domain extraction
- **Rollback Procedures**: One-command rollback to previous working state

### **Business Continuity**
- **Zero-Downtime Migration**: Feature flags allow gradual rollout
- **User Session Preservation**: WebSocket connections maintained during updates
- **Configuration Continuity**: All user settings and customizations preserved
- **Audit Trail**: Complete log of all changes with rationale and impact analysis

## 📊 **Monitoring Dashboard (Post-Refactoring)**

### **Real-Time Health Metrics**
```
Domain Health Status:
├── Speech Domain: ✅ Healthy (avg: 45ms, errors: 0.1%)
├── Communication Domain: ✅ Healthy (connections: 234, uptime: 99.9%)  
├── Configuration Domain: ✅ Healthy (cache hit: 94%, sync: 100%)
└── Annotation Domain: ✅ Healthy (screenshots: 1.2k, processing: 2ms)

AI Development Metrics:
├── File Size Compliance: ✅ 100% (largest file: 287 lines)
├── Token Usage Efficiency: ✅ 85% (avg: 170k tokens per session)
├── Memory Persistence: ✅ Active (last update: 2 hours ago)
└── Parallel Development: ✅ 4 streams (0 conflicts last week)
```

This enhanced plan incorporates cutting-edge 2024 practices for both large-scale web application architecture and AI-assisted development, ensuring the refactoring is not just successful but sets the foundation for years of sustainable growth.