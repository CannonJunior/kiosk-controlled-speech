#!/usr/bin/env python3
"""
Simple test that recreates the screenshot logic without MCP wrapper
"""

import asyncio
import os
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

async def test_screenshot_methods():
    """Test each screenshot method manually"""
    
    print("🔬 Manual Screenshot Method Testing")
    print("=" * 40)
    
    # Create screenshots directory
    screenshots_dir = Path("web_app/static/screenshots")
    screenshots_dir.mkdir(exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_screenshot_{timestamp}.png"
    filepath = screenshots_dir / filename
    
    print(f"📁 Target file: {filepath}")
    
    screenshot = None
    method_used = ""
    error_messages = []
    
    # Method 1: PowerShell Direct
    print("\n🪟 Testing PowerShell Direct...")
    try:
        win_temp_path = f"C:\\temp\\screenshot_{uuid.uuid4().hex}.png"
        
        ps_cmd = f'powershell.exe -Command "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; $bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height); $graphics = [System.Drawing.Graphics]::FromImage($bmp); $graphics.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bounds.Size); $bmp.Save(\'{win_temp_path}\'); $graphics.Dispose(); $bmp.Dispose()"'
        
        print(f"📝 Command: {ps_cmd[:100]}...")
        
        result = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True, timeout=15)
        
        print(f"📤 Return code: {result.returncode}")
        if result.stdout:
            print(f"📝 stdout: {result.stdout}")
        if result.stderr:
            print(f"⚠️  stderr: {result.stderr}")
        
        # Convert back to WSL path
        wsl_temp_path = win_temp_path.replace('C:\\', '/mnt/c/').replace('\\', '/')
        print(f"🔄 Checking WSL path: {wsl_temp_path}")
        
        if result.returncode == 0 and Path(wsl_temp_path).exists():
            # Copy to our target location
            import shutil
            shutil.copy2(wsl_temp_path, filepath)
            
            # Clean up temp file
            try:
                os.unlink(wsl_temp_path)
            except:
                pass
            
            method_used = "PowerShell Direct"
            print("✅ PowerShell method succeeded!")
        else:
            error_messages.append(f"PowerShell failed: return code {result.returncode}")
            if result.stderr:
                error_messages.append(f"PowerShell stderr: {result.stderr}")
                
    except Exception as e:
        error_messages.append(f"PowerShell exception: {e}")
        print(f"❌ PowerShell failed: {e}")
    
    # Method 2: Python via Windows
    if not filepath.exists():
        print("\n🐍 Testing Python on Windows...")
        try:
            python_script = '''
import sys
sys.path.insert(0, r"C:\\Python311\\Lib\\site-packages")
try:
    from PIL import ImageGrab
    screenshot = ImageGrab.grab()
    if len(sys.argv) > 1:
        screenshot.save(sys.argv[1])
        print(f"Screenshot saved to {sys.argv[1]}")
    else:
        print("No output path provided")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
'''
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as py_file:
                py_file.write(python_script)
                py_file_path = py_file.name
            
            # Convert to Windows path
            windows_output_path = str(filepath).replace('/mnt/c/', 'C:\\').replace('/', '\\')
            
            cmd = f'python.exe "{py_file_path}" "{windows_output_path}"'
            print(f"📝 Command: {cmd}")
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            print(f"📤 Return code: {result.returncode}")
            if result.stdout:
                print(f"📝 stdout: {result.stdout}")
            if result.stderr:
                print(f"⚠️  stderr: {result.stderr}")
            
            if result.returncode == 0 and filepath.exists():
                method_used = "Windows Python"
                print("✅ Windows Python method succeeded!")
            else:
                error_messages.append(f"Windows Python failed: {result.stderr}")
            
            # Clean up
            try:
                os.unlink(py_file_path)
            except:
                pass
                
        except Exception as e:
            error_messages.append(f"Windows Python exception: {e}")
            print(f"❌ Windows Python failed: {e}")
    
    # Method 3: Create mock if real methods failed
    if not filepath.exists():
        print("\n🎭 Creating mock screenshot...")
        try:
            # Import required modules
            import sys
            sys.path.append('/home/kiosk_user/.local/lib/python3.12/site-packages')
            from PIL import Image, ImageDraw, ImageFont
            
            # Create mock screenshot
            screenshot = Image.new('RGB', (1920, 1080), color='#2d2d2d')
            draw = ImageDraw.Draw(screenshot)
            
            # Add content
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            except:
                font = ImageFont.load_default()
            
            draw.text((50, 100), "WSL Screenshot Test", fill='white', font=font)
            draw.text((50, 150), f"Timestamp: {timestamp}", fill='white', font=font)
            draw.text((50, 200), "Real screenshot methods failed", fill='orange', font=font)
            draw.text((50, 250), "This is a generated placeholder", fill='orange', font=font)
            
            # Save
            screenshot.save(str(filepath))
            method_used = "Mock Generation"
            print("✅ Mock screenshot created")
            
        except Exception as e:
            error_messages.append(f"Mock generation failed: {e}")
            print(f"❌ Mock generation failed: {e}")
    
    # Analyze result
    print(f"\n📊 Final Results:")
    print(f"📁 File exists: {filepath.exists()}")
    
    if filepath.exists():
        file_size = filepath.stat().st_size
        print(f"📁 File size: {file_size} bytes")
        print(f"🛠️  Method used: {method_used}")
        
        # Analyze image
        try:
            from PIL import Image
            with Image.open(filepath) as img:
                print(f"🖼️  Dimensions: {img.size}")
                print(f"🎨 Mode: {img.mode}")
                
                if method_used == "Mock Generation":
                    print("🎭 This is a simulated screenshot")
                else:
                    print("📸 This should be a real screenshot!")
                    
        except Exception as e:
            print(f"⚠️  Image analysis failed: {e}")
    
    if error_messages:
        print(f"\n⚠️  Errors encountered:")
        for error in error_messages:
            print(f"   - {error}")
    
    return filepath.exists(), method_used

async def main():
    """Main test function"""
    
    print("🎯 Simple Screenshot Testing")
    print("=" * 35)
    
    success, method = await test_screenshot_methods()
    
    print(f"\n🎯 Test Summary:")
    print(f"✅ Success: {success}")
    print(f"🛠️  Method: {method}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()