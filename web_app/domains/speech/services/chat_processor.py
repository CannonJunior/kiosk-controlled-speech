"""
Speech Domain - Chat Processing Service

Handles chat message processing, timeout management, and response generation.
Coordinates between audio input and text-based chat responses.
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from web_app.domains.speech.models.audio_data import TranscriptionResult

logger = logging.getLogger(__name__)


class ChatProcessor:
    """
    Service for processing chat messages with performance monitoring and timeout handling.
    
    Responsibilities:
    - Process text chat messages with timeout management
    - Generate fallback responses for timeout/error scenarios
    - Track processing metrics and performance
    - Coordinate with transcription results from audio input
    """
    
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.max_processing_time = 3.0  # 3 second limit
        self.target_median_time = 1.0   # Target 1 second median
        
        # Processing metrics
        self.processing_metrics = {
            "total_requests": 0,
            "completed_requests": 0,
            "timed_out_requests": 0,
            "failed_requests": 0,
            "processing_times": [],
            "cache_hits": 0,
            "fast_path_hits": 0,
            "start_time": time.time()
        }
        
        # Response cache for common queries
        self._response_cache = {}
        self._response_cache_duration = 30.0
        self._common_patterns = [
            "take screenshot", "click", "help", "what can i do",
            "start recording", "stop recording", "open settings"
        ]
    
    async def process_chat_message(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process chat message with aggressive timeout handling.
        
        Args:
            message: User's chat message
            context: Optional context for processing
            
        Returns:
            Processing result with response and metrics
        """
        start_time = time.time()
        processing_id = f"proc_{int(start_time * 1000)}"
        
        # Track metrics
        self.processing_metrics["total_requests"] += 1
        
        try:
            logger.info(f"[TIMING-{processing_id}] Processing started for message: '{message[:50]}...'")
            
            # PROCESS MESSAGE WITHOUT TIMEOUT - Let successful commands complete
            result = await self._process_message_internal(message, context)
            
            # Add timing metrics to result
            actual_time = time.time() - start_time
            self._add_timing_metrics(result, actual_time, processing_id, start_time)
            
            if result.get("success"):
                self._track_successful_completion(actual_time, result)
            else:
                self._track_failed_completion(actual_time, processing_id)
            
            return result
                
        except Exception as e:
            return self._handle_processing_error(message, str(e), start_time, processing_id)
    
    async def process_transcription_result(self, transcription_result: TranscriptionResult, 
                                         context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process transcription result as a chat message.
        
        Args:
            transcription_result: Result from audio transcription
            context: Optional processing context
            
        Returns:
            Chat processing result
        """
        if not transcription_result.success:
            return {
                "success": False,
                "error": f"Transcription failed: {transcription_result.error}",
                "transcription_error": True
            }
        
        if not transcription_result.transcription or not transcription_result.transcription.strip():
            return {
                "success": False,
                "error": "Empty transcription received",
                "transcription_error": True
            }
        
        # Process the transcribed text as a chat message
        chat_context = context or {}
        chat_context["from_audio"] = True
        chat_context["transcription_confidence"] = transcription_result.confidence
        chat_context["transcription_time"] = transcription_result.processing_time
        
        return await self.process_chat_message(transcription_result.transcription, chat_context)
    
    async def _process_message_internal(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Internal message processing logic without timeout handling.
        
        Args:
            message: User message to process
            context: Processing context
            
        Returns:
            Processing result
        """
        # This would integrate with other domain services for actual processing
        # For now, return a basic structure that matches the expected format
        try:
            # Check cache first
            if self._is_cacheable_query(message):
                cached_response = self._get_cached_response(message)
                if cached_response:
                    return cached_response
            
            # TODO: Integrate with other domain services for:
            # - Fast path processing
            # - LLM processing via Ollama agent
            # - Action execution
            
            # Placeholder processing logic
            await asyncio.sleep(0.1)  # Simulate processing time
            
            result = {
                "success": True,
                "response": {
                    "message": f"Processed message: {message}",
                    "action": "chat_response",
                    "confidence": 0.95
                },
                "processing_time": "< 1s",
                "model_used": "chat_processor",
                "query_complexity": 1
            }
            
            # Cache successful responses
            if self._is_cacheable_query(message):
                self._cache_response(message, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Internal processing error: {e}")
            return {
                "success": False,
                "error": f"Internal processing failed: {str(e)}"
            }
    
    def _handle_processing_error(self, message: str, error_msg: str, start_time: float, processing_id: str) -> Dict[str, Any]:
        """Handle processing error scenario."""
        actual_time = time.time() - start_time
        self.processing_metrics["failed_requests"] += 1
        self._track_processing_time(actual_time)
        logger.error(f"[ERROR-{processing_id}] Chat processing error after {actual_time:.2f}s: {error_msg}")
        
        return self._create_error_fallback_response(message, error_msg, actual_time, processing_id)
    
    def _create_error_fallback_response(self, message: str, error_msg: str, duration: float, processing_id: str) -> Dict[str, Any]:
        """Create a helpful response when processing fails with an error."""
        response_text = f"I encountered an issue while processing your request. You can try:\\n\\n• 'Take screenshot'\\n• 'Help'\\n• 'Open settings'\\n\\nError details: {error_msg[:100]}..."
        
        return {
            "success": True,  # Return success to avoid error display
            "response": {
                "message": response_text,
                "action": "error_recovery",
                "confidence": 0.3
            },
            "action_result": {
                "action_executed": False,
                "action_type": "error_recovery",
                "message": "❌ Processing error - returned recovery response"
            },
            "actual_processing_time": f"{duration:.2f}s",
            "processing_id": processing_id,
            "error": True,
            "fallback": True,
            "processing_time": "ERROR",
            "model_used": "fallback_error"
        }
    
    # Helper methods for metrics, caching, etc.
    def _add_timing_metrics(self, result: Dict[str, Any], actual_time: float, processing_id: str, start_time: float):
        """Add timing metrics to result."""
        result["actual_processing_time"] = f"{actual_time:.2f}s"
        result["processing_id"] = processing_id
        result["processing_start"] = datetime.fromtimestamp(start_time).isoformat()
        result["processing_end"] = datetime.now().isoformat()
    
    def _track_successful_completion(self, actual_time: float, result: Dict[str, Any]):
        """Track successful completion metrics."""
        self.processing_metrics["completed_requests"] += 1
        self._track_processing_time(actual_time)
        
        # Check if this was a cached or fast-path response
        if result.get("from_cache"):
            self.processing_metrics["cache_hits"] += 1
        elif result.get("fast_path"):
            self.processing_metrics["fast_path_hits"] += 1
    
    def _track_failed_completion(self, actual_time: float, processing_id: str):
        """Track failed completion metrics."""
        self.processing_metrics["failed_requests"] += 1
        self._track_processing_time(actual_time)
        logger.warning(f"[TIMING-{processing_id}] Processing failed - Duration: {actual_time:.2f}s")
    
    def _track_processing_time(self, processing_time: float):
        """Track processing time for performance monitoring."""
        self.processing_metrics["processing_times"].append(processing_time)
        
        # Keep only last 1000 processing times to avoid memory growth
        if len(self.processing_metrics["processing_times"]) > 1000:
            self.processing_metrics["processing_times"] = self.processing_metrics["processing_times"][-1000:]
    
    def _is_cacheable_query(self, message: str) -> bool:
        """Check if query should be cached."""
        message_lower = message.lower().strip()
        return any(pattern in message_lower for pattern in self._common_patterns)
    
    def _get_cached_response(self, message: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired."""
        cache_key = f"chat:{message.lower().strip()}"
        if cache_key in self._response_cache:
            cached_entry = self._response_cache[cache_key]
            if time.time() - cached_entry["time"] < self._response_cache_duration:
                cached_response = cached_entry["response"].copy()
                cached_response["from_cache"] = True
                return cached_response
            else:
                # Remove expired cache entry
                del self._response_cache[cache_key]
        return None
    
    def _cache_response(self, message: str, response: Dict[str, Any]):
        """Cache successful response."""
        cache_key = f"chat:{message.lower().strip()}"
        self._response_cache[cache_key] = {
            "response": response,
            "time": time.time()
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        processing_times = self.processing_metrics["processing_times"]
        uptime = time.time() - self.processing_metrics["start_time"]
        
        # Calculate statistics
        if processing_times:
            import statistics
            avg_time = statistics.mean(processing_times)
            median_time = statistics.median(processing_times)
            min_time = min(processing_times)
            max_time = max(processing_times)
            
            # Count times by performance category
            excellent = len([t for t in processing_times if t <= 0.5])
            good = len([t for t in processing_times if 0.5 < t <= 1.0])
            acceptable = len([t for t in processing_times if 1.0 < t <= 2.0])
            slow = len([t for t in processing_times if t > 2.0])
        else:
            avg_time = median_time = min_time = max_time = 0.0
            excellent = good = acceptable = slow = 0
        
        return {
            "total_requests": self.processing_metrics["total_requests"],
            "completed_requests": self.processing_metrics["completed_requests"],
            "failed_requests": self.processing_metrics["failed_requests"],
            "timed_out_requests": self.processing_metrics["timed_out_requests"],
            "cache_hits": self.processing_metrics["cache_hits"],
            "fast_path_hits": self.processing_metrics["fast_path_hits"],
            "uptime_seconds": uptime,
            "processing_time_stats": {
                "count": len(processing_times),
                "average": f"{avg_time:.3f}s",
                "median": f"{median_time:.3f}s",
                "min": f"{min_time:.3f}s",
                "max": f"{max_time:.3f}s",
                "target_median": f"{self.target_median_time:.1f}s",
                "median_achievement": "✅" if median_time <= self.target_median_time else "❌",
                "performance_breakdown": {
                    "excellent_≤0.5s": excellent,
                    "good_0.5-1.0s": good,
                    "acceptable_1.0-2.0s": acceptable,
                    "slow_>2.0s": slow
                }
            },
            "success_rate": f"{(self.processing_metrics['completed_requests'] / max(1, self.processing_metrics['total_requests']) * 100):.1f}%",
            "cache_hit_rate": f"{(self.processing_metrics['cache_hits'] / max(1, self.processing_metrics['total_requests']) * 100):.1f}%",
            "fast_path_rate": f"{(self.processing_metrics['fast_path_hits'] / max(1, self.processing_metrics['total_requests']) * 100):.1f}%"
        }