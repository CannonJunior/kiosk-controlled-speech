#!/usr/bin/env python3
"""
Centralized Model Configuration Manager

Single source of truth for all Ollama model configurations throughout the project.
All model references should go through this manager to ensure consistency.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ModelConfig:
    """Individual model configuration"""
    name: str
    description: str
    temperature: float
    max_tokens: int
    estimated_latency: str
    complexity_threshold: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "estimated_latency": self.estimated_latency,
            "complexity_threshold": self.complexity_threshold
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelConfig':
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            temperature=data.get("temperature", 0.1),
            max_tokens=data.get("max_tokens", 512),
            estimated_latency=data.get("estimated_latency", "unknown"),
            complexity_threshold=data.get("complexity_threshold", 3)
        )

class CentralizedModelManager:
    """
    Centralized manager for all model configurations.
    
    This is the ONLY place in the codebase that should define model configurations.
    All other components should get model info through this manager.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to the centralized config file
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "model_config.json"
        
        self.config_path = Path(config_path)
        self._config_cache = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from JSON file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._config_cache = json.load(f)
                logger.info(f"Loaded model config from {self.config_path}")
            else:
                logger.warning(f"Config file not found at {self.config_path}, using defaults")
                self._create_default_config()
        except Exception as e:
            logger.error(f"Error loading model config: {e}")
            self._create_default_config()
    
    def _create_default_config(self) -> None:
        """Create default configuration"""
        self._config_cache = {
            "models": {
                "default": {
                    "name": "qwen:0.5b",
                    "description": "Fastest lightweight model",
                    "temperature": 0.05,
                    "max_tokens": 256,
                    "estimated_latency": "0.1-0.5s",
                    "complexity_threshold": 1
                },
                "qwen2.5": {
                    "name": "qwen2.5:1.5b", 
                    "description": "Fast lightweight Qwen2.5 model",
                    "temperature": 0.05,
                    "max_tokens": 512,
                    "estimated_latency": "0.2-0.8s",
                    "complexity_threshold": 2
                },
                "balanced": {
                    "name": "llama3.1:8b",
                    "description": "Balanced speed and accuracy",
                    "temperature": 0.1,
                    "max_tokens": 512,
                    "estimated_latency": "1-3s",
                    "complexity_threshold": 3
                },
                "accurate": {
                    "name": "llama3.1:70b",
                    "description": "High accuracy, slower",
                    "temperature": 0.1,
                    "max_tokens": 512,
                    "estimated_latency": "3-8s",
                    "complexity_threshold": 5
                }
            },
            "current_model": "default",
            "fallback_model": "default",
            "auto_fallback": True
        }
    
    def save_config(self) -> None:
        """Save current configuration to file"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self._config_cache, f, indent=2)
            logger.info(f"Saved model config to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving model config: {e}")
    
    def reload_config(self) -> None:
        """Reload configuration from file"""
        self._config_cache = None
        self._load_config()
    
    def get_current_model(self) -> str:
        """Get the name of the current model"""
        current_key = self._config_cache.get("current_model", "default")
        model_config = self._config_cache.get("models", {}).get(current_key, {})
        return model_config.get("name", "qwen:0.5b")
    
    def get_current_model_config(self) -> ModelConfig:
        """Get current model configuration object"""
        current_key = self._config_cache.get("current_model", "default")
        model_data = self._config_cache.get("models", {}).get(current_key, {})
        if not model_data:
            # Fallback to default
            model_data = self._config_cache.get("models", {}).get("default", {})
        return ModelConfig.from_dict(model_data)
    
    def get_model_config(self, model_key: str) -> Optional[ModelConfig]:
        """Get configuration for a specific model by key"""
        model_data = self._config_cache.get("models", {}).get(model_key)
        if model_data:
            return ModelConfig.from_dict(model_data)
        return None
    
    def get_all_models(self) -> Dict[str, ModelConfig]:
        """Get all available model configurations"""
        models = {}
        for key, data in self._config_cache.get("models", {}).items():
            models[key] = ModelConfig.from_dict(data)
        return models
    
    def get_model_names(self) -> List[str]:
        """Get list of all model names (not keys)"""
        return [data.get("name", "unknown") for data in self._config_cache.get("models", {}).values()]
    
    def get_optimization_presets(self) -> Dict[str, Dict[str, Any]]:
        """Get optimization presets using current model configurations"""
        current_model = self.get_current_model()
        current_config = self.get_current_model_config()
        
        return {
            "speed": {
                "model": current_model,
                "temperature": 0.3,
                "max_tokens": 256,
                "name": "Speed",
                "description": "Fast responses with higher temperature for quick interactions"
            },
            "balanced": {
                "model": current_model,
                "temperature": current_config.temperature,
                "max_tokens": current_config.max_tokens,
                "name": "Balanced",
                "description": "Good balance of speed and accuracy for general use"
            },
            "accuracy": {
                "model": current_model,
                "temperature": 0.0,
                "max_tokens": max(current_config.max_tokens, 768),
                "name": "Accuracy",
                "description": "Most accurate responses with lower temperature for complex tasks"
            }
        }
    
    def get_fallback_models(self) -> List[str]:
        """Get list of fallback model names for error situations"""
        models = self.get_model_names()
        # Ensure qwen:0.5b is always first as the most reliable fallback
        if "qwen:0.5b" in models:
            models.remove("qwen:0.5b")
            models.insert(0, "qwen:0.5b")
        return models
    
    def set_current_model(self, model_key: str) -> bool:
        """Set the current model by key"""
        if model_key in self._config_cache.get("models", {}):
            self._config_cache["current_model"] = model_key
            self.save_config()
            return True
        return False
    
    def find_model_key_by_name(self, model_name: str) -> Optional[str]:
        """Find model key by model name"""
        for key, data in self._config_cache.get("models", {}).items():
            if data.get("name") == model_name:
                return key
        return None

# Global instance - singleton pattern
_global_model_manager = None

def get_model_manager() -> CentralizedModelManager:
    """Get the global model manager instance"""
    global _global_model_manager
    if _global_model_manager is None:
        _global_model_manager = CentralizedModelManager()
    return _global_model_manager

def reload_model_config():
    """Reload the global model configuration"""
    global _global_model_manager
    if _global_model_manager is not None:
        _global_model_manager.reload_config()