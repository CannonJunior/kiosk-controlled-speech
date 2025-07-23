#!/usr/bin/env python3
"""
Minimal test runner to check imports without package installation
"""
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path.cwd()))

def test_imports():
    """Test basic imports"""
    print("🧪 Testing basic imports...")
    
    try:
        # Test data manager import
        from src.data_manager.kiosk_data import KioskDataManager
        print("  ✅ KioskDataManager imported")
    except ImportError as e:
        print(f"  ❌ KioskDataManager failed: {e}")
    
    try:
        # Test MCP client import
        from src.mcp.client import MCPOrchestrator
        print("  ✅ MCPOrchestrator imported")
    except ImportError as e:
        print(f"  ❌ MCPOrchestrator failed: {e}")
    
    try:
        # Test orchestrator import
        from src.orchestrator.main import KioskOrchestrator
        print("  ✅ KioskOrchestrator imported")
    except ImportError as e:
        print(f"  ❌ KioskOrchestrator failed: {e}")

if __name__ == "__main__":
    test_imports()