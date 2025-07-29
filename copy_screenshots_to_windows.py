#!/usr/bin/env python3
"""
Copy screenshots from WSL to Windows environment
"""

import subprocess
import shutil
from pathlib import Path

def copy_to_windows():
    """Copy screenshots to Windows directories"""
    
    print("📁 Copying Screenshots to Windows")
    print("=" * 35)
    
    # Source directory (WSL)
    wsl_screenshots = Path("/home/kiosk_user/kiosk-controlled-speech/web_app/static/screenshots")
    
    # Windows destinations
    windows_destinations = [
        "/mnt/c/Users/Public/Screenshots",  # Public folder
        "/mnt/c/temp/screenshots",          # Temp folder
        f"/mnt/c/Users/{get_windows_username()}/Desktop/Screenshots"  # User desktop
    ]
    
    if not wsl_screenshots.exists():
        print(f"❌ Source directory not found: {wsl_screenshots}")
        return
    
    # Get all PNG files
    png_files = list(wsl_screenshots.glob("*.png"))
    print(f"📸 Found {len(png_files)} screenshot files")
    
    for dest in windows_destinations:
        dest_path = Path(dest)
        
        try:
            # Create destination directory
            dest_path.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created: {dest}")
            
            # Copy files
            copied = 0
            for png_file in png_files:
                dest_file = dest_path / png_file.name
                shutil.copy2(png_file, dest_file)
                copied += 1
            
            print(f"✅ Copied {copied} files to {dest}")
            
        except Exception as e:
            print(f"❌ Failed to copy to {dest}: {e}")
    
    # Show files in Windows Explorer
    try:
        # Open first successful destination in Explorer
        for dest in windows_destinations:
            if Path(dest).exists():
                windows_path = str(dest).replace('/mnt/c/', 'C:\\').replace('/', '\\')
                subprocess.run(f'explorer.exe "{windows_path}"', shell=True)
                print(f"🪟 Opened {windows_path} in Explorer")
                break
    except Exception as e:
        print(f"⚠️  Could not open Explorer: {e}")

def get_windows_username():
    """Get Windows username"""
    try:
        result = subprocess.run(['cmd.exe', '/c', 'echo %USERNAME%'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return "Public"  # Fallback

def show_access_methods():
    """Show different ways to access files"""
    
    print(f"\n🔗 Ways to Access Screenshots from Windows:")
    print("=" * 45)
    
    wsl_path = "/home/kiosk_user/kiosk-controlled-speech/web_app/static/screenshots"
    
    print(f"1. 🪟 Windows Explorer:")
    print(f"   \\\\wsl$\\Ubuntu{wsl_path}")
    
    print(f"\n2. 📁 File paths:")
    print(f"   WSL: {wsl_path}")
    print(f"   Win: C:\\Users\\Public\\Screenshots")
    
    print(f"\n3. 💻 Command line:")
    print(f"   copy {wsl_path}\\*.png C:\\temp\\")

if __name__ == "__main__":
    copy_to_windows()
    show_access_methods()