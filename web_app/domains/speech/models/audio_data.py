"""
Speech Domain - Audio Data Models

Data structures for audio processing and transcription results.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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
    Result of audio transcription processing.
    """
    success: bool
    processing_time: float
    transcription: Optional[str] = None
    confidence: Optional[float] = None
    language: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
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
            
        return result