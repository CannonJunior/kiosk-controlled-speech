#!/usr/bin/env python3
"""
Test PowerShell screenshot with corrected syntax
"""

import subprocess
import uuid
from pathlib import Path

def test_powershell_screenshot():
    """Test PowerShell with corrected variable syntax"""
    
    print("🪟 Testing Fixed PowerShell Screenshot")
    print("=" * 40)
    
    # Create a simple temp path
    temp_filename = f"screenshot_{uuid.uuid4().hex}.png"
    win_temp_path = f"C:\\temp\\{temp_filename}"
    
    # Create the temp directory first
    mkdir_cmd = 'powershell.exe -Command "New-Item -ItemType Directory -Force -Path C:\\temp"'
    print("📁 Creating temp directory...")
    
    result = subprocess.run(mkdir_cmd, shell=True, capture_output=True, text=True, timeout=5)
    print(f"📤 Mkdir result: {result.returncode}")
    
    # Fixed PowerShell command with proper escaping
    ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bmp)
$graphics.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bounds.Size)
$bmp.Save('{win_temp_path}')
$graphics.Dispose()
$bmp.Dispose()
Write-Host "Screenshot saved to {win_temp_path}"
"""
    
    # Save script to temp file
    script_path = "/tmp/screenshot.ps1"
    with open(script_path, 'w') as f:
        f.write(ps_script)
    
    # Execute PowerShell script
    ps_cmd = f'powershell.exe -ExecutionPolicy Bypass -File "{script_path}"'
    
    print(f"📝 Executing PowerShell script...")
    print(f"🎯 Target: {win_temp_path}")
    
    result = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True, timeout=15)
    
    print(f"📤 Return code: {result.returncode}")
    print(f"📝 stdout: {result.stdout}")
    if result.stderr:
        print(f"⚠️  stderr: {result.stderr}")
    
    # Check if file was created
    wsl_temp_path = win_temp_path.replace('C:\\', '/mnt/c/').replace('\\', '/')
    print(f"🔄 Checking WSL path: {wsl_temp_path}")
    
    if Path(wsl_temp_path).exists():
        file_size = Path(wsl_temp_path).stat().st_size
        print(f"✅ SUCCESS! Screenshot created: {file_size} bytes")
        
        # Copy to screenshots directory
        screenshots_dir = Path("web_app/static/screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        
        import shutil
        final_path = screenshots_dir / f"powershell_test_{temp_filename}"
        shutil.copy2(wsl_temp_path, final_path)
        
        print(f"📁 Copied to: {final_path}")
        
        # Analyze the image
        try:
            from PIL import Image
            with Image.open(final_path) as img:
                print(f"🖼️  Image analysis:")
                print(f"   - Dimensions: {img.size}")
                print(f"   - Mode: {img.mode}")
                print(f"   - Format: {img.format}")
                
                # Check if it's likely a real screenshot
                if img.size[0] > 800 and img.size[1] > 600:
                    print("📸 This appears to be a real screenshot!")
                else:
                    print("🤔 Unusual dimensions for a screenshot")
                    
        except Exception as e:
            print(f"⚠️  Image analysis failed: {e}")
        
        # Clean up temp file
        try:
            import os
            os.unlink(wsl_temp_path)
            print("🧹 Cleaned up temp file")
        except:
            pass
            
        return True
    else:
        print("❌ Screenshot file not found")
        return False

def test_alternative_methods():
    """Test alternative screenshot approaches"""
    
    print("\n🔧 Testing Alternative Methods")
    print("=" * 30)
    
    # Method 1: Simple PowerShell one-liner with different syntax
    print("🪟 Method 1: PowerShell one-liner...")
    
    temp_file = f"C:\\temp\\alt1_{uuid.uuid4().hex}.png"
    
    # Use single quotes to avoid variable expansion issues
    ps_cmd = f"""powershell.exe -Command "& {{Add-Type -AssemblyName System.Windows.Forms,System.Drawing; [System.Windows.Forms.Screen]::PrimaryScreen.Bounds | %{{$b=$_; $bmp=New-Object System.Drawing.Bitmap($b.Width,$b.Height); $g=[System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($b.X,$b.Y,0,0,$b.Size); $bmp.Save('{temp_file}'); $g.Dispose(); $bmp.Dispose()}}}}" """
    
    result = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True, timeout=10)
    
    print(f"📤 Return code: {result.returncode}")
    if result.stdout:
        print(f"📝 stdout: {result.stdout}")
    if result.stderr:
        print(f"⚠️  stderr: {result.stderr}")
    
    wsl_path = temp_file.replace('C:\\', '/mnt/c/').replace('\\', '/')
    if Path(wsl_path).exists():
        print(f"✅ Method 1 SUCCESS! File: {Path(wsl_path).stat().st_size} bytes")
        return True
    else:
        print("❌ Method 1 failed")
    
    return False

if __name__ == "__main__":
    print("🎯 PowerShell Screenshot Fix Test")
    print("=" * 35)
    
    try:
        success1 = test_powershell_screenshot()
        success2 = test_alternative_methods()
        
        print(f"\n🎯 Final Results:")
        print(f"✅ Script method: {success1}")
        print(f"✅ One-liner method: {success2}")
        
        if success1 or success2:
            print("🎉 At least one method worked!")
        else:
            print("😞 All methods failed")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()