"""
Speech Domain - Audio Data Models

Data structures for audio processing and transcription results.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class AudioData:
    """
    Represents decoded audio data with temporary file information.
    """
    client_id: str
    temp_file_path: Path
    data_size: int
    timestamp: str


@dataclass
class TranscriptionResult:
    """
    Result of audio transcription processing with detailed timing.
    """
    success: bool
    processing_time: float
    transcription: Optional[str] = None
    confidence: Optional[float] = None
    language: Optional[str] = None
    error: Optional[str] = None
    timing_breakdown: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses with detailed timing."""
        result = {
            "success": self.success,
            "processing_time": f"{self.processing_time:.3f}s"
        }
        
        if self.success:
            result.update({
                "transcription": self.transcription,
                "confidence": self.confidence,
                "language": self.language
            })
        else:
            result["error"] = self.error
        
        # Include detailed timing breakdown if available
        if self.timing_breakdown:
            result["timing_breakdown"] = {
                "decode_duration_ms": f"{self.timing_breakdown.get('decode_duration_ms', 0):.1f}ms",
                "transcription_duration_ms": f"{self.timing_breakdown.get('transcription_duration_ms', 0):.1f}ms", 
                "cleanup_duration_ms": f"{self.timing_breakdown.get('cleanup_duration_ms', 0):.1f}ms",
                "total_duration_ms": f"{self.timing_breakdown.get('total_duration_ms', 0):.1f}ms"
            }
            
        return result