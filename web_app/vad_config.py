#!/usr/bin/env python3
"""
VAD Configuration Loader
Centralized configuration management for Voice Activity Detection
"""
import json
import os
from pathlib import Path
from typing import Dict, Any

class VADConfig:
    """Centralized VAD configuration loader"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config/vad_config.json relative to project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "vad_config.json"
        
        self.config_path = Path(config_path)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"VAD config file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in VAD config file: {e}")
    
    def reload(self):
        """Reload configuration from file"""
        self._config = self._load_config()
    
    @property
    def client_vad(self) -> Dict[str, Any]:
        """Get client-side VAD configuration"""
        return self._config.get("client_vad", {})
    
    @property
    def server_vad(self) -> Dict[str, Any]:
        """Get server-side VAD configuration"""
        return self._config.get("server_vad", {})
    
    @property
    def speech_service(self) -> Dict[str, Any]:
        """Get speech service configuration"""
        return self._config.get("speech_service", {})
    
    def get_client_defaults(self) -> Dict[str, Any]:
        """Get default settings for web client"""
        client_config = self.client_vad
        return {
            "vadEnabled": client_config.get("enabled", True),
            "vadSensitivity": client_config.get("sensitivity", 0.003),
            "silenceTimeout": client_config.get("silence_timeout_ms", 2500),
            "speechStartDelay": client_config.get("speech_start_delay_ms", 800),
            "consecutiveSilenceThreshold": client_config.get("consecutive_silence_threshold", 2),
            "checkInterval": client_config.get("check_interval_ms", 100),
            "dynamicTimeout": client_config.get("dynamic_timeout", {}),
            "debugging": client_config.get("debugging", {})
        }
    
    def get_ui_settings(self) -> Dict[str, Any]:
        """Get UI configuration for settings panel"""
        ui_config = self.client_vad.get("ui_settings", {})
        timeout_range = ui_config.get("timeout_range", {})
        
        return {
            "timeoutRange": {
                "min": timeout_range.get("min_seconds", 1.5),
                "max": timeout_range.get("max_seconds", 6.0),
                "step": timeout_range.get("step", 0.5),
                "default": timeout_range.get("default", 2.5)
            }
        }

# Global instance for easy access
vad_config = VADConfig()

def get_vad_config() -> VADConfig:
    """Get the global VAD configuration instance"""
    return vad_config