#!/usr/bin/env python3
import asyncio
from typing import Any, Dict

from fastmcp import FastMCP

mcp = FastMCP("Screen Detector Server")
import cv2
import numpy as np
from PIL import Image as PILImage

from mcp.types import Tool
from src.mcp.base_server import BaseMCPServer, MCPToolError, create_tool_response


class ScreenDetectorServer(BaseMCPServer):
    def __init__(self):
        super().__init__("screen_detector", "Detect current screen state and available elements")
        
        # Computer vision configuration
        self.template_cache: Dict[str, np.ndarray] = {}
        self.last_analysis_result = None
        
        # Detection thresholds
        self.default_confidence_threshold = 0.8
        self.color_match_threshold = 0.85
        self.text_match_threshold = 0.7
        
        # Performance optimization
        self.enable_caching = True
        self.max_cache_size = 50
    
    async def get_tools(self) -> List[Tool]:
        return [
            Tool(
                name="detect_current_screen",
                description="Analyze screenshot to determine current screen",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screenshot_data": {
                            "type": "string",
                            "description": "Base64 encoded screenshot image"
                        },
                        "screen_definitions": {
                            "type": "object",
                            "description": "Screen definitions with detection criteria"
                        },
                        "confidence_threshold": {
                            "type": "number",
                            "default": 0.8,
                            "description": "Minimum confidence for screen detection"
                        }
                    },
                    "required": ["screenshot_data", "screen_definitions"]
                }
            ),
            Tool(
                name="detect_visible_elements",
                description="Identify which elements are currently visible/clickable",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screenshot_data": {
                            "type": "string",
                            "description": "Base64 encoded screenshot image"
                        },
                        "element_definitions": {
                            "type": "object",
                            "description": "Element definitions for current screen"
                        },
                        "confidence_threshold": {
                            "type": "number",
                            "default": 0.8,
                            "description": "Minimum confidence for element detection"
                        }
                    },
                    "required": ["screenshot_data", "element_definitions"]
                }
            ),
            Tool(
                name="validate_element_location",
                description="Validate that an element exists at expected coordinates",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screenshot_data": {
                            "type": "string",
                            "description": "Base64 encoded screenshot image"
                        },
                        "element_id": {
                            "type": "string",
                            "description": "Element identifier"
                        },
                        "expected_x": {"type": "number"},
                        "expected_y": {"type": "number"},
                        "tolerance": {
                            "type": "number",
                            "default": 10,
                            "description": "Pixel tolerance for position validation"
                        }
                    },
                    "required": ["screenshot_data", "element_id", "expected_x", "expected_y"]
                }
            ),
            Tool(
                name="find_text_elements",
                description="Find text elements on screen using OCR",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screenshot_data": {
                            "type": "string",
                            "description": "Base64 encoded screenshot image"
                        },
                        "target_text": {
                            "type": "string",
                            "description": "Text to search for"
                        },
                        "confidence_threshold": {
                            "type": "number",
                            "default": 0.7,
                            "description": "OCR confidence threshold"
                        }
                    },
                    "required": ["screenshot_data", "target_text"]
                }
            ),
            Tool(
                name="analyze_color_regions",
                description="Analyze color patterns and regions in screenshot",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screenshot_data": {
                            "type": "string",
                            "description": "Base64 encoded screenshot image"
                        },
                        "color_signature": {
                            "type": "string",
                            "description": "Expected color signature (hex or rgb)"
                        },
                        "region": {
                            "type": "object",
                            "description": "Specific region to analyze (optional)",
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                                "width": {"type": "number"},
                                "height": {"type": "number"}
                            }
                        }
                    },
                    "required": ["screenshot_data"]
                }
            ),
            Tool(
                name="get_screen_dimensions",
                description="Get screenshot dimensions and basic statistics",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screenshot_data": {
                            "type": "string",
                            "description": "Base64 encoded screenshot image"
                        }
                    },
                    "required": ["screenshot_data"]
                }
            ),
            Tool(
                name="cache_template",
                description="Cache a template for future template matching",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "template_id": {
                            "type": "string",
                            "description": "Unique identifier for template"
                        },
                        "template_data": {
                            "type": "string",
                            "description": "Base64 encoded template image"
                        }
                    },
                    "required": ["template_id", "template_data"]
                }
            ),
            Tool(
                name="clear_cache",
                description="Clear template cache",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    
    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        try:
            if name == "detect_current_screen":
                return await self._detect_current_screen(arguments)
            elif name == "detect_visible_elements":
                return await self._detect_visible_elements(arguments)
            elif name == "validate_element_location":
                return await self._validate_element_location(arguments)
            elif name == "find_text_elements":
                return await self._find_text_elements(arguments)
            elif name == "analyze_color_regions":
                return await self._analyze_color_regions(arguments)
            elif name == "get_screen_dimensions":
                return await self._get_screen_dimensions(arguments)
            elif name == "cache_template":
                return await self._cache_template(arguments)
            elif name == "clear_cache":
                return await self._clear_cache()
            else:
                raise MCPToolError(f"Unknown tool: {name}")
                
        except Exception as e:
            return create_tool_response(False, error=str(e))
    
    def _decode_image(self, base64_data: str) -> np.ndarray:
        """Decode base64 image to OpenCV format"""
        try:
            image_data = base64.b64decode(base64_data)
            image = PILImage.open(io.BytesIO(image_data))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to OpenCV format (BGR)
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            return cv_image
            
        except Exception as e:
            raise MCPToolError(f"Failed to decode image: {e}")
    
    async def _detect_current_screen(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Detect current screen based on detection criteria"""
        screenshot_data = arguments["screenshot_data"]
        screen_definitions = arguments["screen_definitions"]
        confidence_threshold = arguments.get("confidence_threshold", self.default_confidence_threshold)
        
        cv_image = self._decode_image(screenshot_data)
        
        screen_matches = []
        
        for screen_id, screen_data in screen_definitions.items():
            detection_criteria = screen_data.get("detection_criteria", {})
            confidence = await self._calculate_screen_confidence(cv_image, detection_criteria)
            
            if confidence >= confidence_threshold:
                screen_matches.append({
                    "screen_id": screen_id,
                    "confidence": confidence,
                    "criteria_met": detection_criteria
                })
        
        # Sort by confidence
        screen_matches.sort(key=lambda x: x["confidence"], reverse=True)
        
        best_match = screen_matches[0] if screen_matches else None
        
        return create_tool_response(True, {
            "detected_screen": best_match["screen_id"] if best_match else None,
            "confidence": best_match["confidence"] if best_match else 0.0,
            "all_matches": screen_matches,
            "total_screens_checked": len(screen_definitions)
        })
    
    async def _calculate_screen_confidence(self, cv_image: np.ndarray, criteria: Dict[str, Any]) -> float:
        """Calculate confidence score for screen detection"""
        total_score = 0.0
        total_weight = 0.0
        
        # Text-based detection
        if "title_text" in criteria and criteria["title_text"]:
            text_score = await self._check_text_presence(cv_image, criteria["title_text"])
            total_score += text_score * 0.4  # 40% weight
            total_weight += 0.4
        
        # Element-based detection
        if "elements" in criteria and criteria["elements"]:
            element_score = await self._check_elements_presence(cv_image, criteria["elements"])
            total_score += element_score * 0.3  # 30% weight
            total_weight += 0.3
        
        # Color signature detection
        if "color_signature" in criteria and criteria["color_signature"]:
            color_score = await self._check_color_signature(cv_image, criteria["color_signature"])
            total_score += color_score * 0.2  # 20% weight
            total_weight += 0.2
        
        # Unique features detection
        if "unique_features" in criteria and criteria["unique_features"]:
            feature_score = await self._check_unique_features(cv_image, criteria["unique_features"])
            total_score += feature_score * 0.1  # 10% weight
            total_weight += 0.1
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    async def _check_text_presence(self, cv_image: np.ndarray, target_text: str) -> float:
        """Check for text presence using basic image processing"""
        # Simplified text detection - in production, use pytesseract
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            # Apply threshold
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            
            # Find contours (very basic text region detection)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Basic heuristic: if we have text-like contours, assume text is present
            text_like_contours = [c for c in contours if cv2.contourArea(c) > 100 and cv2.contourArea(c) < 10000]
            
            if len(text_like_contours) > 5:  # Arbitrary threshold
                return 0.8  # High confidence if multiple text-like regions found
            elif len(text_like_contours) > 2:
                return 0.5  # Medium confidence
            else:
                return 0.1  # Low confidence
                
        except Exception:
            return 0.0
    
    async def _check_elements_presence(self, cv_image: np.ndarray, element_ids: List[str]) -> float:
        """Check for presence of expected UI elements"""
        # Simplified element detection using basic shape detection
        try:
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            # Detect rectangles (buttons, panels)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Count rectangular shapes (potential UI elements)
            rectangular_shapes = 0
            for contour in contours:
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                if len(approx) == 4 and cv2.contourArea(contour) > 500:
                    rectangular_shapes += 1
            
            # Score based on expected vs found elements
            expected_count = len(element_ids)
            if expected_count == 0:
                return 1.0
            
            score = min(rectangular_shapes / expected_count, 1.0)
            return score
            
        except Exception:
            return 0.0
    
    async def _check_color_signature(self, cv_image: np.ndarray, color_signature: str) -> float:
        """Check for specific color patterns"""
        try:
            # Convert color signature to BGR values
            if color_signature.startswith('#'):
                # Hex color
                hex_color = color_signature[1:]
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                target_color = np.array([b, g, r])  # BGR format
            else:
                # Assume RGB format like "255,0,0"
                rgb_values = [int(x.strip()) for x in color_signature.split(',')]
                target_color = np.array([rgb_values[2], rgb_values[1], rgb_values[0]])  # BGR
            
            # Calculate color histogram
            hist = cv2.calcHist([cv_image], [0, 1, 2], None, [256, 256, 256], [0, 256, 0, 256, 0, 256])
            
            # Create mask for target color (with tolerance)
            tolerance = 30
            lower = np.clip(target_color - tolerance, 0, 255)
            upper = np.clip(target_color + tolerance, 0, 255)
            
            mask = cv2.inRange(cv_image, lower, upper)
            color_pixels = cv2.countNonZero(mask)
            total_pixels = cv_image.shape[0] * cv_image.shape[1]
            
            color_ratio = color_pixels / total_pixels
            
            # Score based on color presence
            if color_ratio > 0.1:  # 10% of image
                return min(color_ratio * 2, 1.0)
            else:
                return color_ratio * 5  # Boost small percentages
                
        except Exception:
            return 0.0
    
    async def _check_unique_features(self, cv_image: np.ndarray, features: List[str]) -> float:
        """Check for unique visual features"""
        # Placeholder for advanced feature detection
        # In production, this could use SIFT, ORB, or deep learning features
        return 0.5  # Default moderate confidence
    
    async def _detect_visible_elements(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Detect which elements are currently visible"""
        screenshot_data = arguments["screenshot_data"]
        element_definitions = arguments["element_definitions"]
        confidence_threshold = arguments.get("confidence_threshold", self.default_confidence_threshold)
        
        cv_image = self._decode_image(screenshot_data)
        
        visible_elements = []
        
        for element in element_definitions.get("elements", []):
            element_id = element["id"]
            coordinates = element["coordinates"]
            size = element["size"]
            
            # Check if element region exists and is interactive
            visibility_score = await self._check_element_visibility(
                cv_image, coordinates, size
            )
            
            if visibility_score >= confidence_threshold:
                visible_elements.append({
                    "element_id": element_id,
                    "coordinates": coordinates,
                    "size": size,
                    "visibility_score": visibility_score,
                    "voice_commands": element.get("voice_commands", [])
                })
        
        return create_tool_response(True, {
            "visible_elements": visible_elements,
            "total_checked": len(element_definitions.get("elements", [])),
            "visibility_threshold": confidence_threshold
        })
    
    async def _check_element_visibility(self, cv_image: np.ndarray, coordinates: Dict[str, int], 
                                      size: Dict[str, int]) -> float:
        """Check if element at given coordinates is visible and interactive"""
        try:
            x, y = coordinates["x"], coordinates["y"]
            width, height = size["width"], size["height"]
            
            # Extract region of interest
            roi = cv_image[y:y+height, x:x+width]
            
            if roi.size == 0:
                return 0.0
            
            # Check if region looks like a UI element
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            
            # Check for edges (buttons usually have defined borders)
            edges = cv2.Canny(gray_roi, 50, 150)
            edge_density = np.sum(edges > 0) / (width * height)
            
            # Check color variance (interactive elements usually have distinct colors)
            color_variance = np.var(gray_roi)
            
            # Combine metrics
            visibility_score = min((edge_density * 1000 + color_variance / 1000) / 2, 1.0)
            
            return max(visibility_score, 0.1)  # Minimum score for existing regions
            
        except Exception:
            return 0.0
    
    async def _validate_element_location(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validate element exists at expected coordinates"""
        screenshot_data = arguments["screenshot_data"]
        element_id = arguments["element_id"]
        expected_x = int(arguments["expected_x"])
        expected_y = int(arguments["expected_y"])
        tolerance = arguments.get("tolerance", 10)
        
        cv_image = self._decode_image(screenshot_data)
        
        # Check region around expected coordinates
        x_start = max(0, expected_x - tolerance)
        y_start = max(0, expected_y - tolerance)
        x_end = min(cv_image.shape[1], expected_x + tolerance)
        y_end = min(cv_image.shape[0], expected_y + tolerance)
        
        roi = cv_image[y_start:y_end, x_start:x_end]
        
        # Basic validation - check if region has UI-like characteristics
        if roi.size > 0:
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edge_density = np.sum(cv2.Canny(gray_roi, 50, 150) > 0) / roi.size
            
            is_valid = edge_density > 0.01  # Threshold for "interactive" region
            confidence = min(edge_density * 100, 1.0)
        else:
            is_valid = False
            confidence = 0.0
        
        return create_tool_response(True, {
            "element_id": element_id,
            "is_valid": is_valid,
            "confidence": confidence,
            "checked_region": {
                "x": x_start, "y": y_start, 
                "width": x_end - x_start, "height": y_end - y_start
            }
        })
    
    async def _find_text_elements(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Find text elements using basic image processing"""
        screenshot_data = arguments["screenshot_data"]
        target_text = arguments["target_text"]
        confidence_threshold = arguments.get("confidence_threshold", self.text_match_threshold)
        
        cv_image = self._decode_image(screenshot_data)
        
        # Simplified text detection - in production use pytesseract
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Find text-like regions
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        text_regions = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if 100 < area < 10000:  # Text-like size
                x, y, w, h = cv2.boundingRect(contour)
                text_regions.append({
                    "x": int(x), "y": int(y), 
                    "width": int(w), "height": int(h),
                    "confidence": min(area / 1000, 1.0)  # Rough confidence
                })
        
        return create_tool_response(True, {
            "target_text": target_text,
            "text_regions": text_regions,
            "regions_found": len(text_regions)
        })
    
    async def _analyze_color_regions(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze color patterns in screenshot"""
        screenshot_data = arguments["screenshot_data"]
        color_signature = arguments.get("color_signature")
        region = arguments.get("region")
        
        cv_image = self._decode_image(screenshot_data)
        
        # Extract region if specified
        if region:
            x, y = int(region["x"]), int(region["y"])
            w, h = int(region["width"]), int(region["height"])
            cv_image = cv_image[y:y+h, x:x+w]
        
        # Calculate color statistics
        mean_color = np.mean(cv_image, axis=(0, 1))
        dominant_colors = []
        
        # Find dominant colors using clustering (simplified)
        pixels = cv_image.reshape(-1, 3)
        unique_colors, counts = np.unique(pixels, axis=0, return_counts=True)
        
        # Get top 5 colors
        top_indices = np.argsort(counts)[-5:]
        for idx in top_indices:
            color = unique_colors[idx]
            count = counts[idx]
            percentage = count / len(pixels) * 100
            dominant_colors.append({
                "color": [int(c) for c in color],
                "percentage": float(percentage)
            })
        
        result = {
            "mean_color": [int(c) for c in mean_color],
            "dominant_colors": dominant_colors,
            "total_unique_colors": len(unique_colors)
        }
        
        # Check specific color if provided
        if color_signature:
            match_score = await self._check_color_signature(cv_image, color_signature)
            result["color_match_score"] = match_score
        
        return create_tool_response(True, result)
    
    async def _get_screen_dimensions(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get screenshot dimensions and statistics"""
        screenshot_data = arguments["screenshot_data"]
        cv_image = self._decode_image(screenshot_data)
        
        height, width, channels = cv_image.shape
        
        # Calculate basic statistics
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (width * height)
        
        return create_tool_response(True, {
            "width": width,
            "height": height,
            "channels": channels,
            "total_pixels": width * height,
            "edge_density": float(edge_density),
            "mean_brightness": float(np.mean(gray))
        })
    
    async def _cache_template(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Cache template for future matching"""
        template_id = arguments["template_id"]
        template_data = arguments["template_data"]
        
        if not self.enable_caching:
            return create_tool_response(False, error="Caching is disabled")
        
        # Manage cache size
        if len(self.template_cache) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.template_cache))
            del self.template_cache[oldest_key]
        
        # Store template
        template_image = self._decode_image(template_data)
        self.template_cache[template_id] = template_image
        
        return create_tool_response(True, {
            "template_id": template_id,
            "cached": True,
            "cache_size": len(self.template_cache)
        })
    
    async def _clear_cache(self) -> Dict[str, Any]:
        """Clear template cache"""
        cache_size = len(self.template_cache)
        self.template_cache.clear()
        self.last_analysis_result = None
        
        return create_tool_response(True, {
            "cleared_templates": cache_size,
            "cache_size": 0
        })


async def main():
    """Main function to run the screen detector MCP server"""
    server = ScreenDetectorServer()
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())