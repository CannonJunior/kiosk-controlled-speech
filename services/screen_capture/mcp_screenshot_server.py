#!/usr/bin/env python3
"""
WSL-compatible screenshot MCP server for Windows desktop capture.
Based on m-mcp/screenshot-server but enhanced for WSL-Windows interop.
"""

from mcp.server.fastmcp import FastMCP, Image
import io
import os
import subprocess
import tempfile
from mcp.types import ImageContent
from PIL import Image as PILImage
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create server
mcp = FastMCP("kiosk-screenshot-server")

def _is_wsl() -> bool:
    """Check if running in WSL environment."""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower() or 'wsl' in f.read().lower()
    except:
        return False

def _take_windows_screenshot_via_powershell() -> bytes:
    """Take screenshot from WSL using PowerShell on Windows host."""
    try:
        # PowerShell script to take screenshot and save to temp file
        ps_script = """
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        
        $screen = [System.Windows.Forms.Screen]::PrimaryScreen
        $bounds = $screen.Bounds
        $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        
        $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
        
        $tempPath = [System.IO.Path]::GetTempFileName() + '.png'
        $bitmap.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
        
        Write-Output $tempPath
        """
        
        # Execute PowerShell from WSL
        result = subprocess.run([
            'powershell.exe', '-Command', ps_script
        ], capture_output=True, text=True, check=True)
        
        temp_path = result.stdout.strip()
        logger.info(f"Screenshot saved to Windows temp path: {temp_path}")
        
        # Convert Windows path to WSL path and read file
        wsl_path = subprocess.run([
            'wslpath', temp_path
        ], capture_output=True, text=True, check=True).stdout.strip()
        
        # Read the image file
        with open(wsl_path, 'rb') as f:
            image_data = f.read()
        
        # Clean up temp file
        subprocess.run(['powershell.exe', '-Command', f'Remove-Item "{temp_path}"'], 
                      capture_output=True)
        
        return image_data
        
    except subprocess.CalledProcessError as e:
        logger.error(f"PowerShell screenshot failed: {e}")
        raise
    except Exception as e:
        logger.error(f"WSL screenshot error: {e}")
        raise

def _take_native_screenshot() -> bytes:
    """Take screenshot using pyautogui for native Linux environments."""
    try:
        import pyautogui
        buffer = io.BytesIO()
        screenshot = pyautogui.screenshot()
        screenshot.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
        return buffer.getvalue()
    except ImportError:
        logger.error("pyautogui not available for native screenshot")
        raise
    except Exception as e:
        logger.error(f"Native screenshot error: {e}")
        raise

def _compress_image(image_data: bytes, max_size_mb: float = 1.0) -> bytes:
    """Compress image to stay under size limit."""
    max_bytes = int(max_size_mb * 1024 * 1024)
    
    if len(image_data) <= max_bytes:
        return image_data
    
    # Load image and compress
    image = PILImage.open(io.BytesIO(image_data))
    buffer = io.BytesIO()
    
    # Try different quality levels
    for quality in [50, 40, 30, 20, 10]:
        buffer.seek(0)
        buffer.truncate()
        image.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
        
        if len(buffer.getvalue()) <= max_bytes:
            logger.info(f"Compressed to quality {quality}, size: {len(buffer.getvalue())} bytes")
            return buffer.getvalue()
    
    # If still too large, resize image
    width, height = image.size
    for scale in [0.8, 0.6, 0.4]:
        new_size = (int(width * scale), int(height * scale))
        resized = image.resize(new_size, PILImage.Resampling.LANCZOS)
        
        buffer.seek(0)
        buffer.truncate()
        resized.convert("RGB").save(buffer, format="JPEG", quality=30, optimize=True)
        
        if len(buffer.getvalue()) <= max_bytes:
            logger.info(f"Resized to {new_size}, size: {len(buffer.getvalue())} bytes")
            return buffer.getvalue()
    
    logger.warning("Could not compress image below size limit")
    return buffer.getvalue()

@mcp.tool()
def take_screenshot() -> Image:
    """
    Take a screenshot of the Windows desktop (from WSL) or local display.
    Automatically detects WSL environment and uses appropriate capture method.
    """
    try:
        if _is_wsl():
            logger.info("WSL detected, using PowerShell for Windows screenshot")
            image_data = _take_windows_screenshot_via_powershell()
            # Convert PNG to JPEG and compress
            image = PILImage.open(io.BytesIO(image_data))
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
            image_data = buffer.getvalue()
        else:
            logger.info("Native environment, using pyautogui")
            image_data = _take_native_screenshot()
        
        # Compress if needed
        image_data = _compress_image(image_data)
        
        logger.info(f"Screenshot captured, size: {len(image_data)} bytes")
        return Image(data=image_data, format="jpeg")
        
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        raise

@mcp.tool()
def take_screenshot_image() -> ImageContent:
    """
    Take a screenshot and return as ImageContent for MCP protocol.
    """
    return take_screenshot().to_image_content()

@mcp.tool()
def take_screenshot_region(x: int, y: int, width: int, height: int) -> Image:
    """
    Take a screenshot of a specific region of the screen.
    
    Args:
        x: Left coordinate of region
        y: Top coordinate of region  
        width: Width of region
        height: Height of region
    """
    try:
        if _is_wsl():
            # PowerShell script for region capture
            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            
            $bitmap = New-Object System.Drawing.Bitmap {width}, {height}
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            
            $graphics.CopyFromScreen({x}, {y}, 0, 0, [System.Drawing.Size]::new({width}, {height}))
            
            $tempPath = [System.IO.Path]::GetTempFileName() + '.png'
            $bitmap.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
            
            Write-Output $tempPath
            """
            
            result = subprocess.run([
                'powershell.exe', '-Command', ps_script
            ], capture_output=True, text=True, check=True)
            
            temp_path = result.stdout.strip()
            wsl_path = subprocess.run([
                'wslpath', temp_path
            ], capture_output=True, text=True, check=True).stdout.strip()
            
            with open(wsl_path, 'rb') as f:
                image_data = f.read()
            
            subprocess.run(['powershell.exe', '-Command', f'Remove-Item "{temp_path}"'], 
                          capture_output=True)
            
            # Convert to JPEG
            image = PILImage.open(io.BytesIO(image_data))
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
            image_data = buffer.getvalue()
            
        else:
            import pyautogui
            buffer = io.BytesIO()
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            screenshot.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
            image_data = buffer.getvalue()
        
        image_data = _compress_image(image_data)
        logger.info(f"Region screenshot captured: ({x},{y},{width},{height}), size: {len(image_data)} bytes")
        return Image(data=image_data, format="jpeg")
        
    except Exception as e:
        logger.error(f"Region screenshot failed: {e}")
        raise

@mcp.tool()
def save_screenshot(path: str = "./screenshots/", filename: str = "screenshot.jpg") -> str:
    """
    Take a screenshot and save it to the specified path.
    
    Args:
        path: Directory to save screenshot
        filename: Name of the screenshot file
    """
    try:
        os.makedirs(path, exist_ok=True)
        full_path = os.path.join(path, filename)
        
        screenshot = take_screenshot()
        
        with open(full_path, "wb") as f:
            f.write(screenshot.data)
        
        logger.info(f"Screenshot saved to: {full_path}")
        return f"Screenshot saved successfully to {full_path}"
        
    except Exception as e:
        logger.error(f"Save screenshot failed: {e}")
        return f"Failed to save screenshot: {e}"

def run():
    """Run the MCP server."""
    logger.info("Starting Kiosk Screenshot MCP Server")
    logger.info(f"WSL Environment: {_is_wsl()}")
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run()