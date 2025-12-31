"""
Configuration Domain - Configuration Data Models

Data models for application configuration management and validation.
"""
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class VADConfiguration:
    """Voice Activity Detection configuration"""
    enabled: bool = True
    sensitivity: float = 0.003
    silence_timeout_ms: int = 2500
    speech_start_delay_ms: int = 800
    consecutive_silence_threshold: int = 2
    check_interval_ms: int = 100
    dynamic_timeout: Dict[str, Any] = field(default_factory=dict)
    debugging: Dict[str, Any] = field(default_factory=dict)
    
    def to_client_config(self) -> Dict[str, Any]:
        """Convert to client-side configuration format"""
        return {
            "vadEnabled": self.enabled,
            "vadSensitivity": self.sensitivity,
            "silenceTimeout": self.silence_timeout_ms,
            "speechStartDelay": self.speech_start_delay_ms,
            "consecutiveSilenceThreshold": self.consecutive_silence_threshold,
            "checkInterval": self.check_interval_ms,
            "dynamicTimeout": self.dynamic_timeout,
            "debugging": self.debugging
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VADConfiguration':
        """Create VAD configuration from dictionary"""
        return cls(
            enabled=data.get("enabled", True),
            sensitivity=data.get("sensitivity", 0.003),
            silence_timeout_ms=data.get("silence_timeout_ms", 2500),
            speech_start_delay_ms=data.get("speech_start_delay_ms", 800),
            consecutive_silence_threshold=data.get("consecutive_silence_threshold", 2),
            check_interval_ms=data.get("check_interval_ms", 100),
            dynamic_timeout=data.get("dynamic_timeout", {}),
            debugging=data.get("debugging", {})
        )


@dataclass
class ModelConfiguration:
    """LLM model configuration"""
    name: str
    description: str = ""
    temperature: float = 0.1
    max_tokens: int = 512
    estimated_latency: str = "unknown"
    complexity_threshold: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "estimated_latency": self.estimated_latency,
            "complexity_threshold": self.complexity_threshold
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelConfiguration':
        """Create model configuration from dictionary"""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            temperature=data.get("temperature", 0.1),
            max_tokens=data.get("max_tokens", 512),
            estimated_latency=data.get("estimated_latency", "unknown"),
            complexity_threshold=data.get("complexity_threshold", 3)
        )


@dataclass
class CacheConfiguration:
    """Cache configuration settings"""
    max_size: int = 100
    ttl_seconds: int = 600
    similarity_threshold: float = 0.85
    enabled: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheConfiguration':
        """Create cache configuration from dictionary"""
        return cls(
            max_size=data.get("max_size", 100),
            ttl_seconds=data.get("ttl_seconds", 600),
            similarity_threshold=data.get("similarity_threshold", 0.85),
            enabled=data.get("enabled", True)
        )


@dataclass
class OptimizationPreset:
    """Optimization preset configuration"""
    name: str
    model: str
    temperature: float
    max_tokens: int
    cache_settings: CacheConfiguration
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "name": self.name,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "description": self.description,
            "cache_settings": {
                "max_size": self.cache_settings.max_size,
                "ttl_seconds": self.cache_settings.ttl_seconds,
                "similarity_threshold": self.cache_settings.similarity_threshold,
                "enabled": self.cache_settings.enabled
            }
        }


@dataclass
class ApplicationConfiguration:
    """Main application configuration container"""
    vad_config: VADConfiguration
    models: Dict[str, ModelConfiguration]
    current_model: str = "default"
    fallback_model: str = "default"
    auto_fallback: bool = True
    optimization_presets: Dict[str, OptimizationPreset] = field(default_factory=dict)
    cache_config: CacheConfiguration = field(default_factory=CacheConfiguration)
    
    def get_current_model_config(self) -> Optional[ModelConfiguration]:
        """Get current model configuration"""
        return self.models.get(self.current_model)
    
    def get_fallback_model_config(self) -> Optional[ModelConfiguration]:
        """Get fallback model configuration"""
        return self.models.get(self.fallback_model)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        if self.current_model not in self.models:
            errors.append(f"Current model '{self.current_model}' not found in available models")
        
        if self.fallback_model not in self.models:
            errors.append(f"Fallback model '{self.fallback_model}' not found in available models")
        
        # Validate VAD configuration
        if self.vad_config.sensitivity <= 0 or self.vad_config.sensitivity > 1:
            errors.append("VAD sensitivity must be between 0 and 1")
        
        if self.vad_config.silence_timeout_ms < 100 or self.vad_config.silence_timeout_ms > 10000:
            errors.append("VAD silence timeout must be between 100ms and 10 seconds")
        
        # Validate model configurations
        for model_key, model_config in self.models.items():
            if not model_config.name:
                errors.append(f"Model '{model_key}' must have a name")
            
            if model_config.temperature < 0 or model_config.temperature > 2:
                errors.append(f"Model '{model_key}' temperature must be between 0 and 2")
            
            if model_config.max_tokens < 1 or model_config.max_tokens > 4096:
                errors.append(f"Model '{model_key}' max_tokens must be between 1 and 4096")
        
        return errors
    
    @classmethod
    def create_default(cls) -> 'ApplicationConfiguration':
        """Create default application configuration"""
        default_models = {
            "default": ModelConfiguration(
                name="qwen2.5:1.5b",
                description="Fast lightweight model",
                temperature=0.1,
                max_tokens=512,
                estimated_latency="0.5-1.5s"
            ),
            "balanced": ModelConfiguration(
                name="llama3.1:8b", 
                description="Balanced speed and accuracy",
                temperature=0.1,
                max_tokens=512,
                estimated_latency="1-3s"
            ),
            "accurate": ModelConfiguration(
                name="llama3.1:70b",
                description="High accuracy, slower",
                temperature=0.1,
                max_tokens=512,
                estimated_latency="3-8s"
            )
        }
        
        default_presets = {
            "speed": OptimizationPreset(
                name="speed",
                model="qwen2.5:1.5b",
                temperature=0.3,
                max_tokens=256,
                cache_settings=CacheConfiguration(max_size=50, ttl_seconds=300),
                description="Optimized for fastest response times"
            ),
            "balanced": OptimizationPreset(
                name="balanced",
                model="llama3.1:8b",
                temperature=0.1,
                max_tokens=512,
                cache_settings=CacheConfiguration(max_size=100, ttl_seconds=600),
                description="Balanced performance and accuracy"
            ),
            "accuracy": OptimizationPreset(
                name="accuracy", 
                model="llama3.1:70b",
                temperature=0.05,
                max_tokens=1024,
                cache_settings=CacheConfiguration(max_size=200, ttl_seconds=900),
                description="Optimized for highest accuracy"
            )
        }
        
        return cls(
            vad_config=VADConfiguration(),
            models=default_models,
            optimization_presets=default_presets
        )