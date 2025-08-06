#!/usr/bin/env python3
"""
Text Reading Service
Handles chat-based text reading commands, element lookup, and OCR processing
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from difflib import SequenceMatcher

from web_app.path_resolver import path_resolver

logger = logging.getLogger(__name__)


class TextReadingService:
    """Service for processing text reading commands from chat"""
    
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.kiosk_data = None
        self.text_regions = {}
        self._load_kiosk_data()
    
    def _load_kiosk_data(self):
        """Load kiosk data and extract text regions"""
        try:
            config_path = path_resolver.resolve_config("kiosk_data.json", required=False)
            if not config_path:
                logger.warning("kiosk_data.json not found")
                return
            
            with open(config_path, 'r') as f:
                self.kiosk_data = json.load(f)
            
            # Extract text regions from all screens
            self.text_regions = {}
            for screen_id, screen_data in self.kiosk_data.get("screens", {}).items():
                for element in screen_data.get("elements", []):
                    if element.get("type") == "text_region" and element.get("action") == "read_text":
                        # Store by element ID and also by voice commands
                        element_id = element["id"]
                        self.text_regions[element_id] = {
                            "screen_id": screen_id,
                            "element": element
                        }
                        
                        # Also index by voice commands for fuzzy matching
                        for voice_command in element.get("voice_commands", []):
                            self.text_regions[voice_command.lower()] = {
                                "screen_id": screen_id,
                                "element": element
                            }
            
            logger.info(f"Loaded {len(self.text_regions)} text regions from kiosk data")
            
        except Exception as e:
            logger.error(f"Failed to load kiosk data: {e}")
            self.kiosk_data = None
    
    def is_text_reading_request(self, message: str) -> bool:
        """Check if a message is requesting text reading"""
        message_lower = message.lower().strip()
        
        # Patterns that indicate text reading requests
        read_patterns = [
            r'\bread\s+(?:the\s+)?text',
            r'\bread\s+(?:what|whats)\s+(?:in|on)',
            r'\bread\s+(?:the\s+)?(?:content|contents)',
            r'\bread\s+(?:the\s+)?(?:\w+)',  # "read the footer", "read the header"
            r'\bwhat\s+(?:does|is)\s+(?:in|on|written)',
            r'\bwhat\s+(?:text|content)\s+(?:is|does)',
            r'\bwhat.*(?:say|says)',
            r'\bextract\s+text',
            r'\btell\s+me\s+(?:what|whats)\s+(?:in|on)',
            r'\bsay\s+(?:what|whats)\s+(?:in|on)',
            r'\bshow\s+me\s+(?:the\s+)?text',
            r'\bshow\s+me\s+(?:the\s+)?(?:\w+\s+)?text',  # "show me the header text"
            r'\bwhat.*(?:in\s+the|on\s+the)',
            r'\btell\s+me.*(?:in\s+the|on\s+the)'
        ]
        
        for pattern in read_patterns:
            if re.search(pattern, message_lower):
                return True
        
        return False
    
    def extract_element_reference(self, message: str) -> Optional[str]:
        """Extract element reference from text reading request"""
        message_lower = message.lower().strip()
        
        # Direct element references
        direct_refs = []
        for region_key in self.text_regions.keys():
            if isinstance(region_key, str) and region_key.lower() in message_lower:
                direct_refs.append((region_key, 1.0))  # Exact match score
        
        if direct_refs:
            # Return the longest match (most specific)
            return max(direct_refs, key=lambda x: len(x[0]))[0]
        
        # Fuzzy matching against voice commands
        best_match = None
        best_score = 0.0
        
        for region_key, region_data in self.text_regions.items():
            element = region_data["element"]
            
            # Check voice commands
            for voice_command in element.get("voice_commands", []):
                similarity = SequenceMatcher(None, message_lower, voice_command.lower()).ratio()
                if similarity > best_score and similarity > 0.6:  # Threshold for fuzzy matching
                    best_score = similarity
                    best_match = voice_command.lower()
            
            # Check element name
            element_name = element.get("name", "").lower()
            if element_name:
                similarity = SequenceMatcher(None, message_lower, element_name).ratio()
                if similarity > best_score and similarity > 0.6:
                    best_score = similarity
                    best_match = element["id"]
        
        return best_match
    
    def get_element_region(self, element_ref: str) -> Optional[Dict[str, Any]]:
        """Get element region data by reference"""
        element_ref_lower = element_ref.lower()
        
        if element_ref_lower in self.text_regions:
            return self.text_regions[element_ref_lower]
        
        # Try direct ID lookup
        for region_key, region_data in self.text_regions.items():
            element = region_data["element"]
            if element["id"].lower() == element_ref_lower:
                return region_data
        
        return None
    
    async def process_text_reading_request(self, message: str) -> Dict[str, Any]:
        """Process a text reading request and return OCR + TTS results"""
        try:
            # Extract element reference
            element_ref = self.extract_element_reference(message)
            if not element_ref:
                return {
                    "success": False,
                    "error": "Could not identify which text region to read",
                    "suggestion": "Try specifying an area like 'bottom banner', 'title area', or 'chat messages'"
                }
            
            # Get element region
            region_data = self.get_element_region(element_ref)
            if not region_data:
                return {
                    "success": False,
                    "error": f"Text region '{element_ref}' not found",
                    "available_regions": self._get_available_regions()
                }
            
            element = region_data["element"]
            screen_id = region_data["screen_id"]
            
            # Take screenshot first
            screenshot_result = await self._take_screenshot()
            if not screenshot_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to take screenshot for text reading",
                    "details": screenshot_result.get("error")
                }
            
            screenshot_path = screenshot_result["data"]["screenshot_path"]
            
            # Extract region coordinates
            region = {
                "x": element["coordinates"]["x"],
                "y": element["coordinates"]["y"],
                "width": element["size"]["width"],
                "height": element["size"]["height"]
            }
            
            # Perform OCR
            ocr_result = await self._perform_ocr(screenshot_path, region)
            if not ocr_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to extract text from region",
                    "region": element["name"],
                    "details": ocr_result.get("error")
                }
            
            extracted_text = ocr_result["data"]["text"].strip()
            if not extracted_text:
                return {
                    "success": False,
                    "error": f"No text found in {element['name']}",
                    "region": element["name"],
                    "confidence": ocr_result["data"].get("confidence", 0)
                }
            
            # Generate TTS audio
            tts_result = await self._generate_audio(extracted_text)
            if not tts_result.get("success"):
                # Return text even if TTS fails
                return {
                    "success": True,
                    "text": extracted_text,
                    "region": element["name"],
                    "confidence": ocr_result["data"].get("confidence", 0),
                    "audio_generated": False,
                    "audio_error": tts_result.get("error"),
                    "word_count": len(extracted_text.split())
                }
            
            return {
                "success": True,
                "text": extracted_text,
                "region": element["name"],
                "confidence": ocr_result["data"].get("confidence", 0),
                "audio_generated": True,
                "audio_path": tts_result["data"]["audio_path"],
                "audio_duration": tts_result["data"].get("duration_estimate", 0),
                "word_count": len(extracted_text.split())
            }
            
        except Exception as e:
            logger.error(f"Text reading processing failed: {e}")
            return {
                "success": False,
                "error": f"Text reading failed: {str(e)}"
            }
    
    async def _take_screenshot(self) -> Dict[str, Any]:
        """Take a screenshot for text reading"""
        try:
            result_raw = await self.mcp_client.call_tool("screen_capture_take_screenshot", {})
            return self._parse_tool_result(result_raw)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _perform_ocr(self, screenshot_path: str, region: Dict[str, int]) -> Dict[str, Any]:
        """Perform OCR on screenshot region"""
        try:
            result_raw = await self.mcp_client.call_tool("extract_text_from_region", {
                "image_path": screenshot_path,
                "region": region,
                "language": "eng",
                "preprocess": True
            })
            return self._parse_tool_result(result_raw)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _generate_audio(self, text: str) -> Dict[str, Any]:
        """Generate TTS audio for extracted text"""
        try:
            result_raw = await self.mcp_client.call_tool("text_to_speech", {
                "text": text,
                "rate": 200,  # Default speech rate
                "volume": 0.8  # Default volume
            })
            return self._parse_tool_result(result_raw)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _parse_tool_result(self, result_raw) -> Dict[str, Any]:
        """Parse MCP tool result"""
        if hasattr(result_raw, 'content') and result_raw.content:
            content = result_raw.content[0]
            if hasattr(content, 'text'):
                try:
                    return json.loads(content.text)
                except json.JSONDecodeError:
                    return {"success": False, "error": "Invalid JSON response"}
        
        return {"success": False, "error": "Empty or invalid response"}
    
    def _get_available_regions(self) -> List[str]:
        """Get list of available text regions"""
        regions = set()
        for region_key, region_data in self.text_regions.items():
            if isinstance(region_key, str) and not region_key.startswith("_"):
                element = region_data["element"]
                regions.add(element["name"])
        
        return sorted(list(regions))
    
    def get_text_reading_help(self) -> Dict[str, Any]:
        """Get help information for text reading commands"""
        available_regions = self._get_available_regions()
        
        example_commands = [
            "Read the text in the bottom banner",
            "What does the title area say?",
            "Read the chat messages",
            "Tell me what's in the footer",
            "Extract text from the header"
        ]
        
        return {
            "available_regions": available_regions,
            "example_commands": example_commands,
            "usage_patterns": [
                "read [the] text in [the] <region>",
                "what does [the] <region> say?",
                "tell me what's in [the] <region>",
                "extract text from [the] <region>"
            ]
        }
    
    def reload_kiosk_data(self):
        """Reload kiosk data configuration"""
        self._load_kiosk_data()