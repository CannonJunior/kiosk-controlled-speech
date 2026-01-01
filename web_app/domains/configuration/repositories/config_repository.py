"""
Configuration Domain - Configuration File Repository

Repository for persisting and loading configuration data from files.
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from web_app.path_resolver import path_resolver

logger = logging.getLogger(__name__)


class ConfigurationFileRepository:
    """
    Repository for managing configuration file persistence.
    
    Responsibilities:
    - Load configuration from JSON files
    - Save configuration data with backup
    - Validate file integrity
    - Handle file watching for changes
    """
    
    def __init__(self):
        self._file_locks = {}  # For thread safety per file
        
    def load_config_file(self, filename: str, required: bool = False) -> Optional[Dict[str, Any]]:
        """
        Load configuration from JSON file.
        
        Args:
            filename: Name of configuration file
            required: Whether file is required to exist
            
        Returns:
            Configuration data or None if not found
        """
        try:
            config_path = path_resolver.resolve_config(filename, required=required)
            
            if not config_path or not config_path.exists():
                if required:
                    raise FileNotFoundError(f"Required config file not found: {filename}")
                logger.debug(f"Optional config file not found: {filename}")
                return None
            
            logger.debug(f"Loading config file: {config_path}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Successfully loaded config: {filename}")
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file {filename}: {e}")
            raise ValueError(f"Invalid JSON in config file {filename}: {e}")
        except Exception as e:
            logger.error(f"Failed to load config file {filename}: {e}")
            if required:
                raise
            return None
    
    def save_config_file(self, filename: str, data: Dict[str, Any], 
                        create_backup: bool = True) -> bool:
        """
        Save configuration data to JSON file.
        
        Args:
            filename: Name of configuration file
            data: Configuration data to save
            create_backup: Whether to create backup before overwriting
            
        Returns:
            True if saved successfully
        """
        try:
            # Resolve or create config path
            config_path = path_resolver.resolve_config(filename, required=False)
            
            if not config_path:
                # Create config directory and file path
                config_dir = Path("config")
                config_dir.mkdir(exist_ok=True)
                config_path = config_dir / filename
            
            # Create backup if file exists and backup requested
            if create_backup and config_path.exists():
                backup_path = self._create_backup(config_path)
                logger.debug(f"Created backup: {backup_path}")
            
            # Add metadata to configuration
            config_data = data.copy()
            config_data["_metadata"] = {
                "last_updated": datetime.now().isoformat(),
                "updated_by": "configuration_service",
                "version": "1.0"
            }
            
            # Write configuration file atomically
            temp_path = config_path.with_suffix(config_path.suffix + '.tmp')
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename to final location
            temp_path.replace(config_path)
            
            logger.info(f"Successfully saved config: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config file {filename}: {e}")
            return False
    
    def _create_backup(self, file_path: Path) -> Path:
        """Create backup of configuration file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f".backup_{timestamp}")
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def list_config_files(self) -> List[str]:
        """List all configuration files in config directory"""
        try:
            config_dir = Path("config")
            if not config_dir.exists():
                return []
            
            json_files = []
            for file_path in config_dir.glob("*.json"):
                if not file_path.name.startswith("._") and "backup" not in file_path.name:
                    json_files.append(file_path.name)
            
            return sorted(json_files)
            
        except Exception as e:
            logger.error(f"Failed to list config files: {e}")
            return []
    
    def get_file_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get metadata about configuration file"""
        try:
            config_path = path_resolver.resolve_config(filename, required=False)
            
            if not config_path or not config_path.exists():
                return None
            
            stat = config_path.stat()
            
            # Try to load metadata from file
            metadata = {}
            try:
                data = self.load_config_file(filename)
                if data and "_metadata" in data:
                    metadata = data["_metadata"]
            except Exception:
                pass  # Ignore metadata loading errors
            
            return {
                "filename": filename,
                "path": str(config_path),
                "size_bytes": stat.st_size,
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info for {filename}: {e}")
            return None
    
    def validate_config_file(self, filename: str) -> Dict[str, Any]:
        """
        Validate configuration file structure and content.
        
        Args:
            filename: Name of configuration file to validate
            
        Returns:
            Validation result with errors and warnings
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "file_info": None
        }
        
        try:
            # Check if file exists
            config_path = path_resolver.resolve_config(filename, required=False)
            if not config_path or not config_path.exists():
                result["errors"].append(f"Configuration file not found: {filename}")
                return result
            
            # Get file info
            result["file_info"] = self.get_file_info(filename)
            
            # Try to parse JSON
            try:
                data = self.load_config_file(filename)
                if data is None:
                    result["errors"].append("Failed to load configuration data")
                    return result
            except json.JSONDecodeError as e:
                result["errors"].append(f"Invalid JSON syntax: {e}")
                return result
            except Exception as e:
                result["errors"].append(f"Failed to read file: {e}")
                return result
            
            # Validate specific configuration types
            if filename == "vad_config.json":
                self._validate_vad_config(data, result)
            elif filename == "model_config.json":
                self._validate_model_config(data, result)
            elif filename == "mcp_config.json":
                self._validate_mcp_config(data, result)
            
            # File is valid if no errors
            result["valid"] = len(result["errors"]) == 0
            
        except Exception as e:
            result["errors"].append(f"Validation error: {e}")
        
        return result
    
    def _validate_vad_config(self, data: Dict[str, Any], result: Dict[str, Any]):
        """Validate VAD configuration structure"""
        if "client_vad" not in data:
            result["errors"].append("Missing 'client_vad' section")
            return
        
        client_vad = data["client_vad"]
        
        # Check required fields
        required_fields = ["sensitivity", "silence_timeout_ms"]
        for field in required_fields:
            if field not in client_vad:
                result["errors"].append(f"Missing required field: client_vad.{field}")
        
        # Validate ranges
        if "sensitivity" in client_vad:
            sens = client_vad["sensitivity"]
            if not isinstance(sens, (int, float)) or sens <= 0 or sens > 1:
                result["errors"].append("sensitivity must be a number between 0 and 1")
        
        if "silence_timeout_ms" in client_vad:
            timeout = client_vad["silence_timeout_ms"]
            if not isinstance(timeout, int) or timeout < 100 or timeout > 10000:
                result["errors"].append("silence_timeout_ms must be between 100 and 10000")
    
    def _validate_model_config(self, data: Dict[str, Any], result: Dict[str, Any]):
        """Validate model configuration structure"""
        if "models" not in data:
            result["errors"].append("Missing 'models' section")
            return
        
        models = data["models"]
        if not isinstance(models, dict) or len(models) == 0:
            result["errors"].append("'models' must be a non-empty object")
            return
        
        # Validate each model
        for model_key, model_config in models.items():
            if "name" not in model_config:
                result["errors"].append(f"Model '{model_key}' missing 'name' field")
            
            if "temperature" in model_config:
                temp = model_config["temperature"]
                if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                    result["errors"].append(f"Model '{model_key}' temperature must be between 0 and 2")
        
        # Check current_model reference
        current_model = data.get("current_model")
        if current_model and current_model not in models:
            result["warnings"].append(f"current_model '{current_model}' not found in available models")
    
    def _validate_mcp_config(self, data: Dict[str, Any], result: Dict[str, Any]):
        """Validate MCP configuration structure"""
        if "servers" not in data:
            result["warnings"].append("No 'servers' section found")
            return
        
        servers = data["servers"]
        if not isinstance(servers, dict):
            result["errors"].append("'servers' must be an object")
            return
        
        # Validate each server configuration
        for server_name, server_config in servers.items():
            if "command" not in server_config:
                result["errors"].append(f"Server '{server_name}' missing 'command' field")
            
            if "args" in server_config and not isinstance(server_config["args"], list):
                result["errors"].append(f"Server '{server_name}' args must be an array")
    
    def cleanup_old_backups(self, max_backups: int = 10) -> int:
        """
        Clean up old backup files, keeping only the most recent ones.
        
        Args:
            max_backups: Maximum number of backup files to keep per config file
            
        Returns:
            Number of backup files removed
        """
        try:
            config_dir = Path("config")
            if not config_dir.exists():
                return 0
            
            # Group backup files by original filename
            backup_groups = {}
            for backup_file in config_dir.glob("*.backup_*"):
                # Extract original filename from backup name
                original_name = backup_file.name.split(".backup_")[0] + ".json"
                if original_name not in backup_groups:
                    backup_groups[original_name] = []
                backup_groups[original_name].append(backup_file)
            
            removed_count = 0
            
            for original_name, backup_files in backup_groups.items():
                if len(backup_files) <= max_backups:
                    continue
                
                # Sort by modification time (newest first)
                backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                
                # Remove excess backups
                for backup_file in backup_files[max_backups:]:
                    try:
                        backup_file.unlink()
                        removed_count += 1
                        logger.debug(f"Removed old backup: {backup_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove backup {backup_file}: {e}")
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old backup files")
            
            return removed_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup backups: {e}")
            return 0
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of all configuration files"""
        files = self.list_config_files()
        summary = {
            "total_files": len(files),
            "files": {},
            "validation_summary": {
                "valid": 0,
                "invalid": 0,
                "warnings": 0
            }
        }
        
        for filename in files:
            file_info = self.get_file_info(filename)
            validation = self.validate_config_file(filename)
            
            summary["files"][filename] = {
                "exists": file_info is not None,
                "size_bytes": file_info["size_bytes"] if file_info else 0,
                "valid": validation["valid"],
                "error_count": len(validation["errors"]),
                "warning_count": len(validation["warnings"])
            }
            
            # Update summary counts
            if validation["valid"]:
                summary["validation_summary"]["valid"] += 1
            else:
                summary["validation_summary"]["invalid"] += 1
            
            if validation["warnings"]:
                summary["validation_summary"]["warnings"] += 1
        
        return summary