"""
Speech Domain - Audio Processing Service

Handles audio data processing, temporary file management, and transcription orchestration.
Part of the Speech bounded context.
"""
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import json
from web_app.path_resolver import path_resolver
from web_app.error_recovery import error_recovery
from web_app.domains.speech.models.audio_data import AudioData, TranscriptionResult

logger = logging.getLogger(__name__)


def parse_tool_result(result):
    """Parse FastMCP tool result"""
    if result.is_error:
        return {"success": False, "error": "Tool call failed"}
    
    if result.content and len(result.content) > 0:
        text_content = result.content[0].text
        try:
            return json.loads(text_content)
        except json.JSONDecodeError:
            return {"success": True, "data": {"raw_text": text_content}}
    
    return {"success": False, "error": "No content in response"}


class AudioProcessor:
    """
    Domain service for audio processing and transcription.
    
    Responsibilities:
    - Convert base64 audio to temporary files
    - Orchestrate transcription via MCP services
    - Manage temporary file lifecycle
    - Return structured transcription results
    """
    
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.temp_dir = path_resolver.get_temp_path("web_audio")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Audio processing metrics
        self.metrics = {
            "total_processed": 0,
            "successful_transcriptions": 0,
            "failed_transcriptions": 0,
            "avg_processing_time": 0.0
        }
    
    async def process_audio_data(self, audio_data: str, client_id: str) -> TranscriptionResult:
        """
        Process base64 audio data and return transcription with detailed timing.
        
        Args:
            audio_data: Base64 encoded audio data
            client_id: Client identifier for file naming
            
        Returns:
            TranscriptionResult with success status and detailed timing data
        """
        start_time = datetime.now()
        timing_breakdown = {
            "total_start_time": start_time,
            "decode_start_time": None,
            "decode_duration_ms": 0,
            "transcription_start_time": None, 
            "transcription_duration_ms": 0,
            "cleanup_duration_ms": 0,
            "total_duration_ms": 0
        }
        
        self.metrics["total_processed"] += 1
        
        try:
            # Convert base64 to audio file with timing
            timing_breakdown["decode_start_time"] = datetime.now()
            audio_file_data = self._decode_audio_data(audio_data, client_id)
            decode_end = datetime.now()
            timing_breakdown["decode_duration_ms"] = (decode_end - timing_breakdown["decode_start_time"]).total_seconds() * 1000
            
            # Perform transcription with timing
            timing_breakdown["transcription_start_time"] = datetime.now()
            transcription_data = await self._transcribe_audio_file(audio_file_data)
            transcription_end = datetime.now()
            timing_breakdown["transcription_duration_ms"] = (transcription_end - timing_breakdown["transcription_start_time"]).total_seconds() * 1000
            
            # Clean up temporary file with timing
            cleanup_start = datetime.now()
            self._cleanup_temp_file(audio_file_data.temp_file_path)
            cleanup_end = datetime.now()
            timing_breakdown["cleanup_duration_ms"] = (cleanup_end - cleanup_start).total_seconds() * 1000
            
            # Calculate total processing time
            total_end = datetime.now()
            processing_time = (total_end - start_time).total_seconds()
            timing_breakdown["total_duration_ms"] = processing_time * 1000
            
            # Update metrics
            self._update_metrics(True, processing_time)
            
            logger.info(f"Audio processing timing breakdown: {timing_breakdown}")
            
            if transcription_data.get("success"):
                data = transcription_data.get("data", {})
                return TranscriptionResult(
                    success=True,
                    transcription=data.get("text", ""),
                    confidence=data.get("confidence", 0.0),
                    language=data.get("language", "en"),
                    processing_time=processing_time,
                    timing_breakdown=timing_breakdown
                )
            else:
                return TranscriptionResult(
                    success=False,
                    error=transcription_data.get("error", "Transcription failed"),
                    processing_time=processing_time,
                    timing_breakdown=timing_breakdown
                )
                
        except Exception as e:
            total_end = datetime.now()
            processing_time = (total_end - start_time).total_seconds()
            timing_breakdown["total_duration_ms"] = processing_time * 1000
            self._update_metrics(False, processing_time)
            
            logger.error(f"Audio processing error: {e}, Timing: {timing_breakdown}")
            return TranscriptionResult(
                success=False,
                error=f"Audio processing failed: {str(e)}",
                processing_time=processing_time,
                timing_breakdown=timing_breakdown
            )
    
    def _decode_audio_data(self, audio_data: str, client_id: str) -> AudioData:
        """
        Decode base64 audio data and save to temporary file.
        
        Args:
            audio_data: Base64 encoded audio
            client_id: Client identifier
            
        Returns:
            AudioData object with file information
        """
        try:
            audio_bytes = base64.b64decode(audio_data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_file = self.temp_dir / f"audio_{client_id}_{timestamp}.wav"
            
            with open(temp_file, 'wb') as f:
                f.write(audio_bytes)
            
            # Register temp file for cleanup
            error_recovery.resource_manager.register_temp_file(str(temp_file))
            
            return AudioData(
                client_id=client_id,
                temp_file_path=temp_file,
                data_size=len(audio_bytes),
                timestamp=timestamp
            )
            
        except Exception as e:
            raise ValueError(f"Failed to decode audio data: {str(e)}")
    
    async def _transcribe_audio_file(self, audio_data: AudioData) -> Dict[str, Any]:
        """
        Transcribe audio file using MCP speech-to-text service.
        
        Args:
            audio_data: AudioData object with file path
            
        Returns:
            Parsed transcription result
        """
        async def call_speech_service():
            result_raw = await self.mcp_client.call_tool(
                "speech_to_text_transcribe_file", {
                    "file_path": str(audio_data.temp_file_path)
                }
            )
            return parse_tool_result(result_raw)
        
        return await error_recovery.execute_with_resilience(
            "speech_to_text", call_speech_service
        )
    
    def _cleanup_temp_file(self, file_path: Path):
        """
        Clean up temporary audio file.
        
        Args:
            file_path: Path to temporary file
        """
        try:
            file_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
    
    def _update_metrics(self, success: bool, processing_time: float):
        """
        Update processing metrics.
        
        Args:
            success: Whether transcription was successful
            processing_time: Time taken in seconds
        """
        if success:
            self.metrics["successful_transcriptions"] += 1
        else:
            self.metrics["failed_transcriptions"] += 1
        
        # Update average processing time
        total_requests = self.metrics["total_processed"]
        current_avg = self.metrics["avg_processing_time"]
        self.metrics["avg_processing_time"] = (
            (current_avg * (total_requests - 1) + processing_time) / total_requests
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current processing metrics."""
        return self.metrics.copy()