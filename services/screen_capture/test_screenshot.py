#!/usr/bin/env python3
"""
Test script for the WSL screenshot MCP server.
"""

import os
import sys
import logging
from mcp_screenshot_server import take_screenshot, take_screenshot_region, save_screenshot, _is_wsl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_environment():
    """Test the environment setup."""
    print("=== Environment Test ===")
    print(f"Operating System: {os.name}")
    print(f"WSL Environment: {_is_wsl()}")
    print(f"Python Version: {sys.version}")
    print()

def test_full_screenshot():
    """Test taking a full screenshot."""
    print("=== Full Screenshot Test ===")
    try:
        screenshot = take_screenshot()
        print(f"✓ Screenshot captured successfully")
        print(f"  Format: {screenshot.format}")
        print(f"  Data size: {len(screenshot.data)} bytes")
        print()
        return True
    except Exception as e:
        print(f"✗ Screenshot failed: {e}")
        print()
        return False

def test_region_screenshot():
    """Test taking a region screenshot."""
    print("=== Region Screenshot Test ===")
    try:
        # Capture top-left 200x200 region
        screenshot = take_screenshot_region(0, 0, 200, 200)
        print(f"✓ Region screenshot captured successfully")
        print(f"  Format: {screenshot.format}")
        print(f"  Data size: {len(screenshot.data)} bytes")
        print()
        return True
    except Exception as e:
        print(f"✗ Region screenshot failed: {e}")
        print()
        return False

def test_save_screenshot():
    """Test saving a screenshot to file."""
    print("=== Save Screenshot Test ===")
    try:
        result = save_screenshot("./test_output/", "test_screenshot.jpg")
        print(f"✓ {result}")
        
        # Verify file exists
        if os.path.exists("./test_output/test_screenshot.jpg"):
            file_size = os.path.getsize("./test_output/test_screenshot.jpg")
            print(f"  File size: {file_size} bytes")
        else:
            print("✗ Screenshot file not found")
            return False
        print()
        return True
    except Exception as e:
        print(f"✗ Save screenshot failed: {e}")
        print()
        return False

def cleanup():
    """Clean up test files."""
    try:
        if os.path.exists("./test_output/test_screenshot.jpg"):
            os.remove("./test_output/test_screenshot.jpg")
        if os.path.exists("./test_output") and not os.listdir("./test_output"):
            os.rmdir("./test_output")
        print("✓ Cleanup completed")
    except Exception as e:
        print(f"⚠ Cleanup warning: {e}")

def main():
    """Run all tests."""
    print("Kiosk Screenshot MCP Server - Test Suite")
    print("=" * 50)
    print()
    
    test_environment()
    
    tests = [
        test_full_screenshot,
        test_region_screenshot,
        test_save_screenshot
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! Screenshot service is working correctly.")
    else:
        print("✗ Some tests failed. Check error messages above.")
    
    cleanup()
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)