# Configuration Domain

## 🎯 **Domain Purpose**
Manages all application configuration, optimization settings, and performance tuning. This domain provides centralized configuration management for voice activity detection, model selection, and caching strategies.

## 📏 **File Size Limits**
- **Services**: Maximum 300 lines each
- **Models**: Maximum 150 lines each  
- **Current target**: Under construction

## 🏗️ **Domain Architecture**

### **Services**
- **`config_service.py`**: Centralized configuration management and loading
- **`optimization_service.py`**: Performance optimization and caching strategies
- **`model_config_service.py`**: LLM model selection and configuration
- **`cache_service.py`**: Multi-tier caching for screen context and responses

### **Models**
- **`config_models.py`**: Configuration data structures and validation
- **`optimization_models.py`**: Optimization settings and performance metrics

### **Repositories**
- **`config_repository.py`**: Configuration file management and persistence

### **Responsibilities**
- ✅ VAD (Voice Activity Detection) configuration management
- ✅ LLM model selection and optimization presets
- ✅ Screen context caching with file modification tracking
- ✅ Response caching with query similarity matching
- ✅ Performance metrics collection and analysis
- ✅ Configuration file validation and defaults

## 🔗 **Domain Interfaces**

### **Inbound Dependencies**
- **File System**: Configuration file reading and writing
- **Path Resolver**: Configuration path resolution
- **JSON Processing**: Configuration serialization/deserialization

### **Outbound Interfaces**
- **Configuration Objects**: Structured configuration data
- **Optimization Settings**: Performance tuning parameters
- **Cache Management**: Multi-tier caching strategies
- **Performance Metrics**: Optimization statistics and monitoring

## ⚠️ **Domain Invariants**
- All configuration files MUST have valid fallback defaults
- Cache invalidation MUST respect file modification times
- Model configurations MUST include performance characteristics
- Configuration changes MUST be validated before persistence

## 📊 **Performance Characteristics**
- **Configuration loading**: < 100ms for all config files
- **Cache hit ratio**: > 85% for screen context, > 70% for responses
- **Model selection**: < 50ms based on query complexity analysis
- **Cache cleanup**: Automatic with TTL and LRU eviction

## 🧪 **Testing Strategy**
- **Unit tests**: Each configuration service independently
- **Integration tests**: Configuration loading and validation
- **Performance tests**: Cache efficiency and hit ratios
- **Fallback tests**: Configuration file corruption and recovery