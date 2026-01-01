"""
Shared Utilities - Cache Operations

Common utilities for cache key generation, validation, and management.
"""
import hashlib
import re
import time
from typing import Dict, Any, List, Optional


def generate_cache_key(prefix: str, *components: str) -> str:
    """
    Generate a standardized cache key from components.
    
    Args:
        prefix: Cache key prefix (e.g., "chat", "screen", "config")
        components: Components to include in the key
        
    Returns:
        Standardized cache key
    """
    # Normalize components
    normalized_components = []
    for component in components:
        if component:
            # Convert to string and normalize
            normalized = str(component).lower().strip()
            # Remove special characters
            normalized = re.sub(r'[^a-zA-Z0-9_\-]', '_', normalized)
            normalized_components.append(normalized)
    
    # Create cache key
    key = f"{prefix}:{':'.join(normalized_components)}"
    
    # Ensure key isn't too long (Redis has 512MB key limit, but keep practical)
    if len(key) > 250:
        # Hash long keys
        key_hash = hashlib.md5(key.encode()).hexdigest()[:16]
        key = f"{prefix}:hashed_{key_hash}"
    
    return key


def generate_query_cache_key(message: str) -> str:
    """Generate cache key specifically for chat queries"""
    return generate_cache_key("chat", message)


def generate_screen_cache_key(file_path: str, screen_name: str) -> str:
    """Generate cache key specifically for screen context"""
    return generate_cache_key("screen", file_path, screen_name)


def generate_config_cache_key(config_type: str, identifier: str = "") -> str:
    """Generate cache key specifically for configuration data"""
    return generate_cache_key("config", config_type, identifier)


def is_cacheable_query(message: str, cacheable_patterns: Optional[List[str]] = None) -> bool:
    """
    Check if a query should be cached based on patterns.
    
    Args:
        message: Query message to check
        cacheable_patterns: Optional list of patterns to match against
        
    Returns:
        True if query should be cached
    """
    if not message or len(message.strip()) < 3:
        return False
    
    # Default cacheable patterns
    if cacheable_patterns is None:
        cacheable_patterns = [
            "click", "tap", "press", "select", "open", "close",
            "navigate", "go to", "show", "display", "help"
        ]
    
    message_lower = message.lower().strip()
    
    # Check if message contains any cacheable patterns
    return any(pattern in message_lower for pattern in cacheable_patterns)


def calculate_cache_priority(data: Dict[str, Any]) -> int:
    """
    Calculate cache priority based on data characteristics.
    
    Args:
        data: Data to calculate priority for
        
    Returns:
        Priority score (higher = more important to cache)
    """
    priority = 0
    
    # Size factor (smaller data gets higher priority)
    data_size = len(str(data))
    if data_size < 1000:
        priority += 10
    elif data_size < 5000:
        priority += 5
    
    # Complexity factor (complex data gets higher priority)
    if isinstance(data, dict):
        priority += min(len(data), 10)  # Cap at 10 points
        
        # Check for expensive computations
        if any(key in data for key in ["coordinates", "elements", "screen_context"]):
            priority += 15
    
    # Recency factor (newer data gets slight boost)
    if "timestamp" in data or "_created_at" in data:
        priority += 5
    
    return priority


def should_evict_cache_entry(entry: Dict[str, Any], max_age_seconds: int = 3600) -> bool:
    """
    Determine if a cache entry should be evicted.
    
    Args:
        entry: Cache entry with metadata
        max_age_seconds: Maximum age before eviction
        
    Returns:
        True if entry should be evicted
    """
    if not entry:
        return True
    
    # Check age-based eviction
    created_at = entry.get("created_at", entry.get("timestamp", time.time()))
    age = time.time() - created_at
    
    if age > max_age_seconds:
        return True
    
    # Check access-based eviction
    last_accessed = entry.get("last_accessed", created_at)
    idle_time = time.time() - last_accessed
    
    # Evict if idle for more than half the max age
    if idle_time > (max_age_seconds / 2):
        return True
    
    return False


def normalize_cache_data(data: Any) -> Dict[str, Any]:
    """
    Normalize data for consistent cache storage.
    
    Args:
        data: Data to normalize
        
    Returns:
        Normalized data dictionary
    """
    if isinstance(data, dict):
        normalized = data.copy()
    elif isinstance(data, str):
        normalized = {"text": data}
    elif isinstance(data, (list, tuple)):
        normalized = {"items": list(data)}
    else:
        normalized = {"value": data}
    
    # Add metadata
    if "_cache_metadata" not in normalized:
        normalized["_cache_metadata"] = {
            "cached_at": time.time(),
            "access_count": 0,
            "data_type": type(data).__name__
        }
    
    return normalized


def extract_cache_statistics(cache_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract statistics from a cache dictionary.
    
    Args:
        cache_dict: Dictionary representing a cache
        
    Returns:
        Cache statistics
    """
    total_entries = len(cache_dict)
    total_size = 0
    oldest_entry = time.time()
    newest_entry = 0
    
    for key, value in cache_dict.items():
        # Calculate size (rough estimation)
        total_size += len(str(key)) + len(str(value))
        
        # Track age
        if isinstance(value, dict):
            created_at = value.get("_cache_metadata", {}).get("cached_at", time.time())
            oldest_entry = min(oldest_entry, created_at)
            newest_entry = max(newest_entry, created_at)
    
    return {
        "total_entries": total_entries,
        "estimated_size_bytes": total_size,
        "oldest_entry_age_seconds": time.time() - oldest_entry if oldest_entry < time.time() else 0,
        "newest_entry_age_seconds": time.time() - newest_entry if newest_entry > 0 else 0,
        "average_entry_size": total_size / max(1, total_entries)
    }