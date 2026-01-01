# Utils - Shared Utilities

## 🎯 Purpose
Pure functions, helpers, and shared utilities - no state, no side effects.

## 📏 File Size Limits
- **Maximum: 200 lines per utility file**
- **Preferred: 100-150 lines**
- **Refactor trigger: 180 lines**

## 🏗️ Utility Patterns

### **Pure Functions**
```python
def parse_tool_result(result: ToolResult) -> dict:
    \"\"\"Parse MCP tool result - pure function\"\"\"
    if result.is_error:
        return {"success": False, "error": "Tool call failed"}
    # Processing logic
    return {"success": True, "data": parsed_data}
```

### **Stateless Helpers**
```python
class PerformanceUtils:
    @staticmethod
    def calculate_metrics(processing_times: List[float]) -> dict:
        \"\"\"Calculate performance metrics - no instance state\"\"\"
        return {
            "average": statistics.mean(processing_times),
            "median": statistics.median(processing_times)
        }
```

## 📂 Utility Files

### **mcp_utils.py** (Target: 100 lines)
- MCP result parsing
- Tool result formatting
- Error handling helpers

### **performance_utils.py** (Target: 120 lines)
- Metrics calculation
- Performance monitoring helpers
- Cache management utilities

### **text_utils.py** (Target: 80 lines)
- Text similarity calculations
- String processing helpers
- Pattern matching utilities

## ⚠️ Anti-Patterns
- ❌ Global state or class variables
- ❌ Database or file I/O
- ❌ External service calls
- ❌ Complex business logic

## ✅ Best Practices
- ✅ Pure functions when possible
- ✅ Clear input/output contracts
- ✅ Comprehensive error handling
- ✅ Well-documented interfaces