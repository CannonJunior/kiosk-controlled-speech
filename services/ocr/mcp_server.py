#!/usr/bin/env python3
"""
OCR MCP Server
Provides text extraction from images using Tesseract OCR
"""
import asyncio
import base64
import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageEnhance
import pytesseract

from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("OCR Server")

# OCR Configuration
OCR_CONFIG = {
    "tesseract_cmd": None,  # Will auto-detect or use system default
    "default_language": "eng",
    "confidence_threshold": 0.3,
    "preprocessing_enabled": True,
    "supported_formats": [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]
}


class OCRProcessor:
    """Handles OCR processing with preprocessing and optimization"""
    
    def __init__(self):
        self._setup_tesseract()
    
    def _setup_tesseract(self):
        """Setup Tesseract configuration"""
        # Try to find Tesseract executable
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                OCR_CONFIG["tesseract_cmd"] = path
                logger.info(f"Found Tesseract at: {path}")
                break
        else:
            logger.warning("Tesseract not found in common locations, using system PATH")
    
    def preprocess_image(self, image: Image.Image, enhance_text: bool = True) -> Image.Image:
        """
        Preprocess image for better OCR results
        
        Args:
            image: PIL Image object
            enhance_text: Whether to apply text enhancement filters
            
        Returns:
            Preprocessed PIL Image
        """
        try:
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            if not enhance_text:
                return image
            
            # Convert PIL to OpenCV format
            opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Apply preprocessing steps
            processed = self._apply_preprocessing_pipeline(opencv_image)
            
            # Convert back to PIL
            processed_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            return Image.fromarray(processed_rgb)
            
        except Exception as e:
            logger.warning(f"Preprocessing failed, using original image: {e}")
            return image
    
    def _apply_preprocessing_pipeline(self, image: np.ndarray) -> np.ndarray:
        """Apply OCR preprocessing pipeline"""
        
        # 1. Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 2. Noise reduction
        denoised = cv2.medianBlur(gray, 3)
        
        # 3. Contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # 4. Adaptive thresholding for better text separation
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # 5. Morphological operations to clean up text
        kernel = np.ones((2,2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # Convert back to BGR for consistency
        return cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR)
    
    def extract_text(self, 
                    image: Image.Image, 
                    language: str = "eng",
                    config: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract text from image using Tesseract OCR
        
        Args:
            image: PIL Image object
            language: Tesseract language code
            config: Custom Tesseract configuration
            
        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            # Default config for better OCR results
            if config is None:
                config = '--oem 3 --psm 6'  # Use LSTM OCR Engine, uniform text blocks
            
            # Extract text with data (includes confidence scores)
            data = pytesseract.image_to_data(
                image, lang=language, config=config, output_type=pytesseract.Output.DICT
            )
            
            # Extract just the text
            text = pytesseract.image_to_string(
                image, lang=language, config=config
            ).strip()
            
            # Calculate average confidence
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Filter out low-confidence words
            filtered_text = self._filter_by_confidence(data, OCR_CONFIG["confidence_threshold"])
            
            return {
                "success": True,
                "text": text,
                "filtered_text": filtered_text,
                "confidence": round(avg_confidence / 100, 2),  # Convert to 0-1 scale
                "word_count": len(text.split()) if text else 0,
                "character_count": len(text) if text else 0,
                "language": language,
                "config": config,
                "raw_data": {
                    "word_confidences": list(zip(data['text'], data['conf'])),
                    "total_words_detected": len([w for w in data['text'] if w.strip()])
                }
            }
            
        except Exception as e:
            logger.error(f"OCR text extraction failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "confidence": 0.0
            }
    
    def _filter_by_confidence(self, data: Dict, min_confidence: float) -> str:
        """Filter OCR results by confidence threshold"""
        filtered_words = []
        
        for i, conf in enumerate(data['conf']):
            if int(conf) >= (min_confidence * 100):  # Convert to 0-100 scale
                word = data['text'][i].strip()
                if word:  # Skip empty strings
                    filtered_words.append(word)
        
        return ' '.join(filtered_words)


# Global OCR processor instance
ocr_processor = OCRProcessor()


@mcp.tool()
async def extract_text_from_image(
    image_path: str,
    language: str = "eng",
    preprocess: bool = True,
    confidence_threshold: Optional[float] = None
) -> Dict[str, Any]:
    """
    Extract text from an image file using OCR
    
    Args:
        image_path: Path to image file (absolute or relative)
        language: Tesseract language code (default: 'eng')
        preprocess: Whether to apply image preprocessing (default: True)
        confidence_threshold: Minimum confidence for text inclusion (0.0-1.0)
        
    Returns:
        Dictionary containing extracted text and metadata
    """
    try:
        # Validate image path
        image_path = Path(image_path)
        if not image_path.exists():
            return {
                "success": False,
                "error": f"Image file not found: {image_path}",
                "text": ""
            }
        
        # Check file format
        if image_path.suffix.lower() not in OCR_CONFIG["supported_formats"]:
            return {
                "success": False,
                "error": f"Unsupported image format: {image_path.suffix}",
                "supported_formats": OCR_CONFIG["supported_formats"],
                "text": ""
            }
        
        # Load image
        try:
            image = Image.open(image_path)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load image: {e}",
                "text": ""
            }
        
        # Apply preprocessing if requested
        if preprocess and OCR_CONFIG["preprocessing_enabled"]:
            image = ocr_processor.preprocess_image(image)
        
        # Set confidence threshold
        if confidence_threshold is not None:
            original_threshold = OCR_CONFIG["confidence_threshold"]
            OCR_CONFIG["confidence_threshold"] = confidence_threshold
        
        # Extract text
        result = ocr_processor.extract_text(image, language)
        
        # Restore original threshold
        if confidence_threshold is not None:
            OCR_CONFIG["confidence_threshold"] = original_threshold
        
        # Add processing metadata
        result.update({
            "image_path": str(image_path),
            "image_size": image.size,
            "preprocessing_applied": preprocess,
            "tesseract_version": pytesseract.get_tesseract_version()
        })
        
        logger.info(f"OCR completed for {image_path}: {len(result.get('text', ''))} characters extracted")
        return result
        
    except Exception as e:
        logger.error(f"OCR extraction failed for {image_path}: {e}")
        return {
            "success": False,
            "error": str(e),
            "text": "",
            "image_path": str(image_path) if 'image_path' in locals() else None
        }


@mcp.tool()
async def extract_text_from_region(
    image_path: str,
    region: Dict[str, int],
    language: str = "eng",
    preprocess: bool = True
) -> Dict[str, Any]:
    """
    Extract text from a specific region of an image
    
    Args:
        image_path: Path to image file
        region: Dictionary with keys 'x', 'y', 'width', 'height'
        language: Tesseract language code (default: 'eng') 
        preprocess: Whether to apply image preprocessing
        
    Returns:
        Dictionary containing extracted text and metadata
    """
    try:
        # Validate inputs
        required_keys = ['x', 'y', 'width', 'height']
        if not all(key in region for key in required_keys):
            return {
                "success": False,
                "error": f"Region must contain keys: {required_keys}",
                "text": ""
            }
        
        # Load image
        image_path = Path(image_path)
        if not image_path.exists():
            return {
                "success": False,
                "error": f"Image file not found: {image_path}",
                "text": ""
            }
        
        try:
            image = Image.open(image_path)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load image: {e}",
                "text": ""
            }
        
        # Validate region bounds
        x, y, width, height = region['x'], region['y'], region['width'], region['height']
        img_width, img_height = image.size
        
        if (x < 0 or y < 0 or x + width > img_width or y + height > img_height or 
            width <= 0 or height <= 0):
            return {
                "success": False,
                "error": f"Invalid region bounds. Image size: {img_width}x{img_height}, Region: {region}",
                "text": ""
            }
        
        # Crop image to region
        cropped_image = image.crop((x, y, x + width, y + height))
        
        # Apply preprocessing if requested
        if preprocess:
            cropped_image = ocr_processor.preprocess_image(cropped_image)
        
        # Extract text from cropped region
        result = ocr_processor.extract_text(cropped_image, language)
        
        # Add region-specific metadata
        result.update({
            "image_path": str(image_path),
            "region": region,
            "cropped_size": cropped_image.size,
            "original_size": image.size,
            "preprocessing_applied": preprocess
        })
        
        logger.info(f"OCR region extraction completed: {len(result.get('text', ''))} characters from region {region}")
        return result
        
    except Exception as e:
        logger.error(f"OCR region extraction failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "text": "",
            "region": region if 'region' in locals() else None
        }


@mcp.tool() 
async def get_ocr_capabilities() -> Dict[str, Any]:
    """
    Get OCR service capabilities and configuration
    
    Returns:
        Dictionary with OCR service information
    """
    try:
        # Get Tesseract version and available languages
        version = pytesseract.get_tesseract_version()
        languages = pytesseract.get_languages(config='')
        
        return {
            "success": True,
            "tesseract_version": str(version),
            "tesseract_path": OCR_CONFIG["tesseract_cmd"],
            "available_languages": languages,
            "default_language": OCR_CONFIG["default_language"],
            "confidence_threshold": OCR_CONFIG["confidence_threshold"],
            "preprocessing_enabled": OCR_CONFIG["preprocessing_enabled"],
            "supported_formats": OCR_CONFIG["supported_formats"],
            "capabilities": {
                "text_extraction": True,
                "region_extraction": True,
                "confidence_scoring": True,
                "multiple_languages": True,
                "preprocessing": True,
                "batch_processing": False  # Future enhancement
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get OCR capabilities: {e}")
        return {
            "success": False,
            "error": str(e),
            "tesseract_available": False
        }


@mcp.tool()
async def extract_text_from_base64(
    base64_image: str,
    language: str = "eng",
    preprocess: bool = True,
    image_format: str = "PNG"
) -> Dict[str, Any]:
    """
    Extract text from a base64-encoded image
    
    Args:
        base64_image: Base64 encoded image data
        language: Tesseract language code
        preprocess: Whether to apply preprocessing
        image_format: Image format (PNG, JPEG, etc.)
        
    Returns:
        Dictionary containing extracted text and metadata
    """
    try:
        # Decode base64 image
        try:
            # Handle data URL prefix if present
            if base64_image.startswith('data:image'):
                base64_image = base64_image.split(',')[1]
            
            image_data = base64.b64decode(base64_image)
            image = Image.open(io.BytesIO(image_data))
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to decode base64 image: {e}",
                "text": ""
            }
        
        # Apply preprocessing if requested
        if preprocess:
            image = ocr_processor.preprocess_image(image)
        
        # Extract text
        result = ocr_processor.extract_text(image, language)
        
        # Add processing metadata
        result.update({
            "source": "base64",
            "image_size": image.size,
            "image_format": image_format,
            "preprocessing_applied": preprocess
        })
        
        logger.info(f"OCR completed for base64 image: {len(result.get('text', ''))} characters extracted")
        return result
        
    except Exception as e:
        logger.error(f"OCR base64 extraction failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "text": ""
        }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()