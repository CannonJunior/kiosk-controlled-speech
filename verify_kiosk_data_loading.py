#!/usr/bin/env python3
"""
Verify that kiosk_data.json is being loaded correctly by the web app
"""
import json
import sys
import os
from pathlib import Path

def verify_kiosk_data_loading():
    """Verify kiosk_data.json loading logic matches web app implementation"""
    
    print("🔍 Verifying Kiosk Data Loading")
    print("=" * 35)
    
    # Same path logic as in web_app/main.py
    config_paths = [
        Path("../config/kiosk_data.json"),
        Path("config/kiosk_data.json"),
        Path("./config/kiosk_data.json")
    ]
    
    kiosk_data = None
    found_path = None
    
    for config_path in config_paths:
        print(f"🔍 Checking: {config_path}")
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    kiosk_data = json.load(f)
                found_path = config_path
                print(f"✅ Found and loaded: {config_path}")
                break
            except Exception as e:
                print(f"❌ Error loading {config_path}: {e}")
        else:
            print(f"❌ Not found: {config_path}")
    
    if not kiosk_data:
        print("❌ Could not load kiosk_data.json from any path")
        return False
    
    # Check web_app screen data
    web_app_screen = kiosk_data.get("screens", {}).get("web_app", {})
    if not web_app_screen:
        print("❌ No 'web_app' screen found in kiosk_data.json")
        return False
    
    print(f"✅ Found web_app screen: {web_app_screen.get('name')}")
    
    # Look for mouse control test button
    elements = web_app_screen.get("elements", [])
    mouse_button = None
    
    for element in elements:
        if element.get("id") == "mouseControlTestButton":
            mouse_button = element
            break
    
    if mouse_button:
        print(f"✅ Found mouseControlTestButton:")
        print(f"   📍 Coordinates: {mouse_button.get('coordinates')}")
        print(f"   📏 Size: {mouse_button.get('size')}")
        print(f"   🗣️  Voice commands: {mouse_button.get('voice_commands')}")
        print(f"   🎯 Action: {mouse_button.get('action')}")
        
        # Verify expected coordinates
        expected_coords = {"x": 600, "y": 50}
        actual_coords = mouse_button.get('coordinates')
        
        if actual_coords == expected_coords:
            print("✅ Coordinates match expected values!")
        else:
            print(f"⚠️  Coordinates mismatch: expected {expected_coords}, got {actual_coords}")
            
    else:
        print("❌ mouseControlTestButton not found in web_app elements")
        print("Available elements:")
        for element in elements:
            print(f"   - {element.get('id')}: {element.get('name')}")
        return False
    
    print(f"\n📊 Summary:")
    print(f"   📁 Config file: {found_path}")
    print(f"   🖼️  Screen: {web_app_screen.get('name')}")
    print(f"   🔢 Elements: {len(elements)}")
    print(f"   🎯 Mouse button found: ✅")
    
    return True

def main():
    """Main verification function"""
    try:
        success = verify_kiosk_data_loading()
        if success:
            print("\n🎉 Kiosk data loading verification PASSED!")
        else:
            print("\n❌ Kiosk data loading verification FAILED!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()