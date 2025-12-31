"""
Configuration Domain - Configuration Management Service

Centralized service for loading, validating, and managing application configuration.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from web_app.path_resolver import path_resolver
from web_app.domains.configuration.models.config_models import (
    ApplicationConfiguration, VADConfiguration, ModelConfiguration,
    CacheConfiguration, OptimizationPreset
)

logger = logging.getLogger(__name__)


class ConfigurationService:
    """
    Service for centralized configuration management.
    
    Responsibilities:
    - Load and validate configuration files
    - Provide typed configuration objects
    - Handle configuration defaults and fallbacks
    - Manage configuration file watching and reloading
    """
    
    def __init__(self):
        self._config: Optional[ApplicationConfiguration] = None
        self._config_file_mtimes: Dict[str, float] = {}
        self._validation_errors: List[str] = []
        
    def load_configuration(self, force_reload: bool = False) -> ApplicationConfiguration:
        """
        Load complete application configuration.
        
        Args:
            force_reload: Force reload even if already loaded
            
        Returns:
            Complete application configuration
        """
        if self._config is not None and not force_reload and not self._config_files_changed():
            return self._config
        
        try:
            logger.info("Loading application configuration...")
            
            # Load individual configuration components
            vad_config = self._load_vad_config()
            model_config = self._load_model_config()
            cache_config = self._load_cache_config()
            optimization_presets = self._load_optimization_presets()
            
            # Create application configuration
            self._config = ApplicationConfiguration(
                vad_config=vad_config,
                models=model_config["models"],
                current_model=model_config.get("current_model", "default"),
                fallback_model=model_config.get("fallback_model", "default"),
                auto_fallback=model_config.get("auto_fallback", True),
                optimization_presets=optimization_presets,
                cache_config=cache_config
            )
            
            # Validate configuration
            self._validation_errors = self._config.validate()
            if self._validation_errors:
                logger.warning(f"Configuration validation warnings: {self._validation_errors}")
            
            # Update file modification times
            self._update_config_file_mtimes()
            
            logger.info("Application configuration loaded successfully")
            return self._config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            
            # Return default configuration on error
            self._config = ApplicationConfiguration.create_default()
            self._validation_errors = [f"Configuration load error: {str(e)}"]
            return self._config
    
    def get_vad_configuration(self) -> VADConfiguration:
        """Get VAD configuration with client defaults"""
        config = self.load_configuration()
        return config.vad_config
    
    def get_model_configuration(self, model_key: Optional[str] = None) -> Optional[ModelConfiguration]:
        """Get specific model configuration"""
        config = self.load_configuration()
        
        if model_key is None:
            return config.get_current_model_config()
        
        return config.models.get(model_key)
    
    def get_available_models(self) -> List[str]:
        """Get list of available model keys"""
        config = self.load_configuration()
        return list(config.models.keys())
    
    def get_optimization_preset(self, preset_name: str) -> Optional[OptimizationPreset]:
        """Get specific optimization preset"""
        config = self.load_configuration()
        return config.optimization_presets.get(preset_name)
    
    def get_available_presets(self) -> List[str]:
        """Get list of available optimization presets"""
        config = self.load_configuration()
        return list(config.optimization_presets.keys())
    
    def update_current_model(self, model_key: str) -> bool:
        """
        Update current model selection.
        
        Args:
            model_key: Model key to set as current
            
        Returns:
            True if updated successfully
        """
        config = self.load_configuration()
        
        if model_key not in config.models:
            logger.error(f"Model key '{model_key}' not found in available models")
            return False
        
        config.current_model = model_key
        
        # Persist the change
        return self._save_model_config(config)
    
    def get_validation_errors(self) -> List[str]:
        """Get current configuration validation errors"""
        return self._validation_errors.copy()
    
    def reload_configuration(self) -> ApplicationConfiguration:
        """Force reload configuration from files"""
        return self.load_configuration(force_reload=True)
    
    def _load_vad_config(self) -> VADConfiguration:
        """Load VAD configuration from file"""
        try:
            config_path = path_resolver.resolve_config("vad_config.json", required=False)
            
            if config_path and config_path.exists():
                with open(config_path, 'r') as f:
                    vad_data = json.load(f)
                
                client_vad = vad_data.get("client_vad", {})
                return VADConfiguration.from_dict(client_vad)
            else:
                logger.info("VAD config file not found, using defaults")
                return VADConfiguration()
                
        except Exception as e:
            logger.error(f"Failed to load VAD config: {e}")
            return VADConfiguration()
    
    def _load_model_config(self) -> Dict[str, Any]:
        """Load model configuration from file"""
        try:
            config_path = path_resolver.resolve_config("model_config.json", required=False)
            
            if config_path and config_path.exists():
                with open(config_path, 'r') as f:
                    model_data = json.load(f)
                
                # Convert model dictionaries to ModelConfiguration objects
                models = {}
                for key, model_dict in model_data.get("models", {}).items():
                    models[key] = ModelConfiguration.from_dict(model_dict)
                
                return {
                    "models": models,
                    "current_model": model_data.get("current_model", "default"),
                    "fallback_model": model_data.get("fallback_model", "default"),
                    "auto_fallback": model_data.get("auto_fallback", True)
                }
            else:
                logger.info("Model config file not found, using defaults")
                default_config = ApplicationConfiguration.create_default()
                return {
                    "models": default_config.models,
                    "current_model": default_config.current_model,
                    "fallback_model": default_config.fallback_model,
                    "auto_fallback": default_config.auto_fallback
                }
                
        except Exception as e:
            logger.error(f"Failed to load model config: {e}")
            default_config = ApplicationConfiguration.create_default()
            return {
                "models": default_config.models,
                "current_model": "default",
                "fallback_model": "default", 
                "auto_fallback": True
            }
    
    def _load_cache_config(self) -> CacheConfiguration:
        """Load cache configuration from file or use defaults"""
        try:
            config_path = path_resolver.resolve_config("cache_config.json", required=False)
            
            if config_path and config_path.exists():
                with open(config_path, 'r') as f:
                    cache_data = json.load(f)
                
                return CacheConfiguration.from_dict(cache_data)
            else:
                return CacheConfiguration()
                
        except Exception as e:
            logger.error(f"Failed to load cache config: {e}")
            return CacheConfiguration()
    
    def _load_optimization_presets(self) -> Dict[str, OptimizationPreset]:
        """Load optimization presets"""
        # For now, return the default presets
        # In a full implementation, these could be loaded from a file
        default_config = ApplicationConfiguration.create_default()
        return default_config.optimization_presets
    
    def _save_model_config(self, config: ApplicationConfiguration) -> bool:
        """Save model configuration to file"""
        try:
            config_path = path_resolver.resolve_config("model_config.json", required=False)
            
            if not config_path:
                # Create config directory if it doesn't exist
                config_dir = Path("config")
                config_dir.mkdir(exist_ok=True)
                config_path = config_dir / "model_config.json"
            
            # Convert models back to dictionary format
            models_dict = {
                key: model.to_dict() for key, model in config.models.items()
            }
            
            config_data = {
                "models": models_dict,
                "current_model": config.current_model,
                "fallback_model": config.fallback_model,
                "auto_fallback": config.auto_fallback,
                "last_updated": datetime.now().isoformat()
            }
            
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Model configuration saved to {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save model config: {e}")
            return False
    
    def _config_files_changed(self) -> bool:
        """Check if any configuration files have been modified"""
        config_files = [
            "vad_config.json",
            "model_config.json",
            "cache_config.json"
        ]
        
        for filename in config_files:
            config_path = path_resolver.resolve_config(filename, required=False)
            if config_path and config_path.exists():
                current_mtime = config_path.stat().st_mtime
                cached_mtime = self._config_file_mtimes.get(filename, 0)
                
                if current_mtime != cached_mtime:
                    return True
        
        return False
    
    def _update_config_file_mtimes(self):
        """Update cached file modification times"""
        config_files = [
            "vad_config.json",
            "model_config.json", 
            "cache_config.json"
        ]
        
        for filename in config_files:
            config_path = path_resolver.resolve_config(filename, required=False)
            if config_path and config_path.exists():
                self._config_file_mtimes[filename] = config_path.stat().st_mtime
    
    def get_configuration_status(self) -> Dict[str, Any]:
        """Get configuration loading status and metadata"""
        return {
            "loaded": self._config is not None,
            "validation_errors": self._validation_errors,
            "file_mtimes": self._config_file_mtimes,
            "last_loaded": datetime.now().isoformat() if self._config else None,
            "available_models": self.get_available_models() if self._config else [],
            "available_presets": self.get_available_presets() if self._config else []
        }