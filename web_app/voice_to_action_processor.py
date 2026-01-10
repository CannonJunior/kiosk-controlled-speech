#!/usr/bin/env python3
"""
Enhanced Voice-to-Action Processing System

High-performance, accurate voice command processing using fast character matching
and fuzzy similarity algorithms. Provides detailed action context and improved
response times compared to LLM-based processing.
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher
import asyncio
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class MatchResult:
    """Results from voice command matching"""
    element_id: str
    element_name: str
    screen_name: str
    screen_id: str
    confidence: float
    match_type: str  # "exact", "partial", "fuzzy", "voice_command"
    matched_text: str
    voice_commands: List[str] = field(default_factory=list)
    coordinates: Dict[str, int] = field(default_factory=dict)
    description: str = ""
    
    def to_action_data(self) -> Dict[str, Any]:
        """Convert to action data format"""
        return {
            "action": "click",
            "element_id": self.element_id,
            "coordinates": self.coordinates,
            "confidence": self.confidence,
            "match_type": self.match_type,
            "matched_text": self.matched_text,
            "screen_name": self.screen_name,
            "screen_id": self.screen_id,
            "element_name": self.element_name,
            "voice_commands": self.voice_commands,
            "description": self.description,
            "message": self._generate_detailed_message()
        }
    
    def _generate_detailed_message(self) -> str:
        """Generate detailed success message with context"""
        coords_str = f"({self.coordinates.get('x', 0)}, {self.coordinates.get('y', 0)})"
        confidence_str = f"{self.confidence:.1%}"
        
        return (
            f"🖱️ Successfully clicked \"{self.element_name}\" at coordinates {coords_str} "
            f"using WSL PowerShell interop. "
            f"📍 Screen: '{self.screen_name}' | 🎯 Element: '{self.element_id}' | "
            f"📝 Description: {self.description} | "
            f"🔍 Match: {self.match_type} ({confidence_str}) | "
            f"💬 Voice: \"{self.matched_text}\" → {self.voice_commands}"
        )

class FastVoiceToActionProcessor:
    """
    High-performance voice-to-action processor using character matching algorithms.
    
    Features:
    - Fast fuzzy string matching (no LLM required for most commands)
    - Detailed action context reporting
    - Multi-screen annotation support
    - Configurable similarity thresholds
    - Performance optimization with caching
    """
    
    def __init__(self, confidence_threshold: float = 0.3, cache_size: int = 100):
        self.confidence_threshold = confidence_threshold
        self.cache_size = cache_size
        self._annotation_cache = {}
        self._similarity_cache = {}
        
        # Performance tracking
        self._stats = {
            "total_processed": 0,
            "cache_hits": 0,
            "avg_processing_time": 0.0,
            "accuracy_rate": 0.0
        }
    
    async def process_voice_command(self, voice_text: str, kiosk_data: Dict[str, Any], 
                                  current_screen_id: str = None) -> Dict[str, Any]:
        """
        Process voice command using fast character matching algorithm.
        
        Args:
            voice_text: Transcribed voice command
            kiosk_data: Complete kiosk annotation data  
            current_screen_id: Current screen ID for prioritization
            
        Returns:
            Action data with detailed context or error information
        """
        start_time = time.time()
        
        try:
            # Normalize input
            voice_text_clean = self._normalize_text(voice_text)
            
            # Check cache first
            cache_key = f"{voice_text_clean}:{current_screen_id}"
            if cache_key in self._similarity_cache:
                self._stats["cache_hits"] += 1
                cached_result = self._similarity_cache[cache_key]
                cached_result["cached"] = True
                return cached_result
            
            # Extract all available annotations
            all_annotations = self._extract_all_annotations(kiosk_data, current_screen_id)
            
            if not all_annotations:
                return self._create_error_response(
                    "No annotations available for matching",
                    voice_text,
                    current_screen_id or "unknown"
                )
            
            # Find best match using multiple algorithms
            best_match = await self._find_best_match(voice_text_clean, all_annotations)
            
            if best_match and best_match.confidence >= self.confidence_threshold:
                # Cache successful result
                action_data = best_match.to_action_data()
                self._cache_result(cache_key, action_data)
                
                # Update stats
                processing_time = (time.time() - start_time) * 1000
                self._update_stats(processing_time, True)
                
                action_data["processing_time_ms"] = processing_time
                action_data["algorithm"] = "fast_character_matching"
                
                return {"success": True, "data": action_data}
            
            else:
                # No good match found
                processing_time = (time.time() - start_time) * 1000
                self._update_stats(processing_time, False)
                
                return self._create_no_match_response(
                    voice_text, 
                    all_annotations,
                    processing_time,
                    current_screen_id or "unknown"
                )
                
        except Exception as e:
            logger.error(f"Error processing voice command '{voice_text}': {e}")
            processing_time = (time.time() - start_time) * 1000
            self._update_stats(processing_time, False)
            
            return {
                "success": False,
                "error": f"Processing failed: {str(e)}",
                "voice_text": voice_text,
                "processing_time_ms": processing_time
            }
    
    def _extract_all_annotations(self, kiosk_data: Dict[str, Any], 
                                current_screen_id: str = None) -> List[Dict[str, Any]]:
        """Extract and flatten all annotations from kiosk data with screen context"""
        annotations = []
        screens = kiosk_data.get("screens", {})
        
        # Prioritize current screen if specified
        screen_order = []
        if current_screen_id and current_screen_id in screens:
            screen_order.append(current_screen_id)
        
        # Add remaining screens
        for screen_id in screens:
            if screen_id != current_screen_id:
                screen_order.append(screen_id)
        
        for screen_id in screen_order:
            screen_data = screens[screen_id]
            screen_name = screen_data.get("name", screen_id)
            
            elements = screen_data.get("elements", [])
            for element in elements:
                annotation = {
                    "element_id": element.get("id", ""),
                    "element_name": element.get("name", ""),
                    "screen_id": screen_id,
                    "screen_name": screen_name,
                    "voice_commands": element.get("voice_commands", []),
                    "coordinates": element.get("coordinates", {}),
                    "description": element.get("description", ""),
                    "is_current_screen": (screen_id == current_screen_id),
                    "priority": 1.0 if screen_id == current_screen_id else 0.8
                }
                annotations.append(annotation)
        
        return annotations
    
    async def _find_best_match(self, voice_text: str, 
                              annotations: List[Dict[str, Any]]) -> Optional[MatchResult]:
        """Find best matching annotation using multiple algorithms"""
        candidates = []
        
        # Store all candidates with scores for debugging
        self._last_matching_candidates = []
        
        # Algorithm 1: Exact voice command matching
        for ann in annotations:
            for voice_cmd in ann["voice_commands"]:
                if voice_text.lower() == voice_cmd.lower():
                    match = MatchResult(
                        element_id=ann["element_id"],
                        element_name=ann["element_name"],
                        screen_name=ann["screen_name"],
                        screen_id=ann["screen_id"],
                        confidence=0.95 * ann["priority"],  # Boost current screen
                        match_type="exact",
                        matched_text=voice_cmd,
                        voice_commands=ann["voice_commands"],
                        coordinates=ann["coordinates"],
                        description=ann["description"]
                    )
                    candidates.append(match)
        
        # Algorithm 2: Partial voice command matching
        for ann in annotations:
            for voice_cmd in ann["voice_commands"]:
                if voice_cmd.lower() in voice_text.lower() or voice_text.lower() in voice_cmd.lower():
                    overlap = min(len(voice_text), len(voice_cmd)) / max(len(voice_text), len(voice_cmd))
                    confidence = 0.8 * overlap * ann["priority"]
                    
                    match = MatchResult(
                        element_id=ann["element_id"],
                        element_name=ann["element_name"],
                        screen_name=ann["screen_name"],
                        screen_id=ann["screen_id"],
                        confidence=confidence,
                        match_type="partial",
                        matched_text=voice_cmd,
                        voice_commands=ann["voice_commands"],
                        coordinates=ann["coordinates"],
                        description=ann["description"]
                    )
                    candidates.append(match)
        
        # Algorithm 3: Fuzzy matching on element names
        for ann in annotations:
            similarity = SequenceMatcher(None, voice_text.lower(), ann["element_name"].lower()).ratio()
            if similarity > 0.4:  # Minimum threshold for element name matching
                confidence = 0.7 * similarity * ann["priority"]
                
                match = MatchResult(
                    element_id=ann["element_id"],
                    element_name=ann["element_name"],
                    screen_name=ann["screen_name"],
                    screen_id=ann["screen_id"],
                    confidence=confidence,
                    match_type="fuzzy_name",
                    matched_text=ann["element_name"],
                    voice_commands=ann["voice_commands"],
                    coordinates=ann["coordinates"],
                    description=ann["description"]
                )
                candidates.append(match)
        
        # Algorithm 4: Fuzzy matching on descriptions
        for ann in annotations:
            if ann["description"]:
                similarity = SequenceMatcher(None, voice_text.lower(), ann["description"].lower()).ratio()
                if similarity > 0.4:  # Lower threshold for descriptions
                    confidence = 0.6 * similarity * ann["priority"]
                    
                    match = MatchResult(
                        element_id=ann["element_id"],
                        element_name=ann["element_name"],
                        screen_name=ann["screen_name"],
                        screen_id=ann["screen_id"],
                        confidence=confidence,
                        match_type="fuzzy_description",
                        matched_text=ann["description"],
                        voice_commands=ann["voice_commands"],
                        coordinates=ann["coordinates"],
                        description=ann["description"]
                    )
                    candidates.append(match)
        
        # Algorithm 5: Word-based matching for multi-word phrases
        voice_words = set(self._normalize_text(voice_text).split())
        for ann in annotations:
            # Check element name words
            element_words = set(self._normalize_text(ann["element_name"]).split())
            word_overlap = len(voice_words.intersection(element_words))
            if word_overlap > 0:
                confidence = 0.5 * (word_overlap / max(len(voice_words), len(element_words))) * ann["priority"]
                
                match = MatchResult(
                    element_id=ann["element_id"],
                    element_name=ann["element_name"],
                    screen_name=ann["screen_name"],
                    screen_id=ann["screen_id"],
                    confidence=confidence,
                    match_type="word_overlap",
                    matched_text=f"Words: {voice_words.intersection(element_words)}",
                    voice_commands=ann["voice_commands"],
                    coordinates=ann["coordinates"],
                    description=ann["description"]
                )
                candidates.append(match)
            
            # Check description words
            if ann["description"]:
                desc_words = set(self._normalize_text(ann["description"]).split())
                word_overlap = len(voice_words.intersection(desc_words))
                if word_overlap > 0:
                    confidence = 0.4 * (word_overlap / max(len(voice_words), len(desc_words))) * ann["priority"]
                    
                    match = MatchResult(
                        element_id=ann["element_id"],
                        element_name=ann["element_name"],
                        screen_name=ann["screen_name"],
                        screen_id=ann["screen_id"],
                        confidence=confidence,
                        match_type="word_overlap_desc",
                        matched_text=f"Desc words: {voice_words.intersection(desc_words)}",
                        voice_commands=ann["voice_commands"],
                        coordinates=ann["coordinates"],
                        description=ann["description"]
                    )
                    candidates.append(match)
        
        # Sort all candidates by confidence and store for debugging
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        # Store top candidates for debugging display
        self._last_matching_candidates = candidates[:5]  # Top 5 for analysis
        
        # Return best candidate if above threshold
        if candidates and candidates[0].confidence >= self.confidence_threshold:
            return candidates[0]
        
        return None
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for better matching"""
        import re
        # Convert to lowercase, remove extra spaces, normalize punctuation
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
        text = re.sub(r'\s+', ' ', text)     # Normalize whitespace
        return text
    
    def _cache_result(self, key: str, result: Dict[str, Any]) -> None:
        """Cache processing result"""
        if len(self._similarity_cache) >= self.cache_size:
            # Simple LRU: remove oldest entry
            oldest_key = next(iter(self._similarity_cache))
            del self._similarity_cache[oldest_key]
        
        self._similarity_cache[key] = result
    
    def _update_stats(self, processing_time_ms: float, success: bool) -> None:
        """Update performance statistics"""
        self._stats["total_processed"] += 1
        
        # Update average processing time
        total = self._stats["total_processed"]
        current_avg = self._stats["avg_processing_time"]
        self._stats["avg_processing_time"] = ((current_avg * (total - 1)) + processing_time_ms) / total
        
        # Update accuracy rate (simplified)
        if success:
            current_accuracy = self._stats["accuracy_rate"]
            self._stats["accuracy_rate"] = ((current_accuracy * (total - 1)) + 1.0) / total
        else:
            current_accuracy = self._stats["accuracy_rate"]
            self._stats["accuracy_rate"] = (current_accuracy * (total - 1)) / total
    
    def _create_error_response(self, error_msg: str, voice_text: str, screen_id: str) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            "success": False,
            "error": error_msg,
            "voice_text": voice_text,
            "screen_id": screen_id,
            "algorithm": "fast_character_matching"
        }
    
    def _create_no_match_response(self, voice_text: str, annotations: List[Dict[str, Any]], 
                                 processing_time: float, screen_id: str) -> Dict[str, Any]:
        """Create response when no good match is found"""
        # Suggest alternatives
        suggestions = []
        for ann in annotations[:5]:  # Top 5 suggestions
            if ann["voice_commands"]:
                suggestions.append({
                    "element_name": ann["element_name"],
                    "voice_commands": ann["voice_commands"][:2],  # First 2 commands
                    "screen": ann["screen_name"]
                })
        
        return {
            "success": False,
            "error": "No matching action found",
            "voice_text": voice_text,
            "screen_id": screen_id,
            "processing_time_ms": processing_time,
            "algorithm": "fast_character_matching",
            "suggestions": suggestions,
            "message": f"❓ No action found for \"{voice_text}\". Try: {', '.join([s['voice_commands'][0] for s in suggestions[:3] if s['voice_commands']])}"
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        return {
            **self._stats,
            "cache_hit_rate": self._stats["cache_hits"] / max(1, self._stats["total_processed"]),
            "cache_size": len(self._similarity_cache)
        }

# Global instance for reuse
_global_processor = None

def get_voice_processor() -> FastVoiceToActionProcessor:
    """Get global voice processor instance"""
    global _global_processor
    if _global_processor is None:
        _global_processor = FastVoiceToActionProcessor()
    return _global_processor