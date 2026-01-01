#!/usr/bin/env python3
"""
Path Resolution Service
Centralized path resolution for configuration files and resources
"""
import tempfile
from pathlib import Path
from typing import Optional, List


class PathResolver:
    """Centralized path resolution for configuration and resource files"""
    
    def __init__(self, project_root: Optional[Path] = None, config_dir: str = "config", temp_dir: Optional[str] = None):
        """
        Initialize PathResolver with configurable paths
        
        Args:
            project_root: Root directory of the project (auto-detected if None)
            config_dir: Name of configuration directory (default: "config")
            temp_dir: Temporary directory path (auto-created if None)
        """
        self.project_root = project_root or self._detect_project_root()
        self.config_dir_name = config_dir
        self.temp_dir = Path(temp_dir or tempfile.gettempdir()) / "kiosk_speech"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def _detect_project_root(self) -> Path:
        """Auto-detect project root by looking for key files"""
        current = Path.cwd()
        
        # Special case: if we're running from web_app, go up one level to find services
        if current.name == "web_app":
            potential_root = current.parent
            if (potential_root / "services").exists() and (potential_root / "config").exists():
                return potential_root
        
        # Look for project markers going up the directory tree
        markers = [
            "services",  # This is the key marker - services directory
            ".git",
            "pyproject.toml"
        ]
        
        for parent in [current] + list(current.parents):
            if any((parent / marker).exists() for marker in markers):
                # Ensure this parent also has the services directory
                if (parent / "services").exists():
                    return parent
        
        # Fallback to current working directory
        return current
    
    def resolve_config(self, filename: str, required: bool = True) -> Optional[Path]:
        """
        Resolve configuration file path with multiple fallback locations
        
        Args:
            filename: Configuration file name (e.g., "model_config.json")
            required: If True, raise FileNotFoundError if file not found
            
        Returns:
            Path to configuration file, or None if not found and not required
            
        Raises:
            FileNotFoundError: If file not found and required=True
        """
        search_paths = self._get_config_search_paths(filename)
        
        for path in search_paths:
            if path.exists() and path.is_file():
                return path
        
        if required:
            search_locations = "\n".join(f"  - {path}" for path in search_paths)
            raise FileNotFoundError(
                f"Configuration file '{filename}' not found in any of these locations:\n{search_locations}"
            )
        
        return None
    
    def _get_config_search_paths(self, filename: str) -> List[Path]:
        """Get list of paths to search for configuration files"""
        return [
            # Project root config directory
            self.project_root / self.config_dir_name / filename,
            # Parent directory config (for services)
            self.project_root.parent / self.config_dir_name / filename,
            # Current working directory config
            Path.cwd() / self.config_dir_name / filename,
            # Same directory as calling script
            Path.cwd() / filename,
            # Absolute path if filename is already absolute
            Path(filename) if Path(filename).is_absolute() else Path("/dev/null")  # dummy for non-absolute
        ]
    
    def get_temp_path(self, filename: str) -> Path:
        """
        Get path for temporary file
        
        Args:
            filename: Name for temporary file
            
        Returns:
            Path in temporary directory
        """
        return self.temp_dir / filename
    
    def get_config_dir(self) -> Path:
        """Get primary configuration directory path"""
        config_path = self.project_root / self.config_dir_name
        config_path.mkdir(parents=True, exist_ok=True)
        return config_path
    
    def resolve_resource(self, resource_path: str, resource_type: str = "static") -> Optional[Path]:
        """
        Resolve resource file path (e.g., screenshots, audio files)
        
        Args:
            resource_path: Relative path to resource
            resource_type: Type of resource directory (default: "static")
            
        Returns:
            Full path to resource, or None if not found
        """
        search_paths = [
            self.project_root / "web_app" / resource_type / resource_path,
            self.project_root / resource_type / resource_path,
            Path.cwd() / resource_type / resource_path,
            Path(resource_path)  # If already absolute
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        return None
    
    def create_temp_file(self, suffix: str = "", prefix: str = "kiosk_") -> Path:
        """
        Create a temporary file path
        
        Args:
            suffix: File extension (e.g., ".wav", ".png")
            prefix: File prefix (default: "kiosk_")
            
        Returns:
            Path to temporary file (file not created yet)
        """
        import uuid
        filename = f"{prefix}{uuid.uuid4().hex[:8]}{suffix}"
        return self.get_temp_path(filename)
    
    def cleanup_temp_files(self, pattern: str = "*", older_than_hours: int = 24):
        """
        Clean up temporary files matching pattern and older than specified hours
        
        Args:
            pattern: Glob pattern for files to clean (default: "*")
            older_than_hours: Remove files older than this many hours
        """
        import time
        
        if not self.temp_dir.exists():
            return
        
        cutoff_time = time.time() - (older_than_hours * 3600)
        
        for temp_file in self.temp_dir.glob(pattern):
            try:
                if temp_file.is_file() and temp_file.stat().st_mtime < cutoff_time:
                    temp_file.unlink()
            except (OSError, IOError):
                # Ignore files that can't be removed (in use, permissions, etc.)
                continue


# Global instance for convenience
path_resolver = PathResolver()