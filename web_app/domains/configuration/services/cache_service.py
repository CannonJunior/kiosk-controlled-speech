"""
Configuration Domain - Cache Management Service

Multi-tier caching service for screen context and response caching with optimization.
"""
import hashlib
import logging
import threading
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from difflib import SequenceMatcher

from web_app.domains.configuration.models.optimization_models import (
    CacheEntry, CacheStatistics
)
from web_app.domains.configuration.models.config_models import CacheConfiguration

logger = logging.getLogger(__name__)


class QueryNormalizer:
    """Utility for normalizing queries for similarity matching"""
    
    @staticmethod
    def normalize(text: str) -> str:
        """Normalize query text for comparison"""
        if not text:
            return ""
        
        # Convert to lowercase
        normalized = text.lower().strip()
        
        # Remove common punctuation
        for char in ".,!?;:\"'()[]{}":
            normalized = normalized.replace(char, "")
        
        # Normalize whitespace
        normalized = " ".join(normalized.split())
        
        # Remove common filler words
        filler_words = {"um", "uh", "like", "you", "know", "the", "a", "an"}
        words = [word for word in normalized.split() if word not in filler_words]
        
        return " ".join(words)
    
    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """Calculate similarity between two normalized texts"""
        norm1 = QueryNormalizer.normalize(text1)
        norm2 = QueryNormalizer.normalize(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        return SequenceMatcher(None, norm1, norm2).ratio()


class ScreenContextCache:
    """
    Cache for parsed screen context data with file modification time tracking.
    
    Provides efficient caching of screen element data with automatic invalidation
    when underlying configuration files change.
    """
    
    def __init__(self, config: CacheConfiguration):
        self.config = config
        self.statistics = CacheStatistics(name="screen_context", max_size=config.max_size)
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        
    def _get_cache_key(self, file_path: str, screen_name: str) -> str:
        """Generate cache key from file path and screen name"""
        return f"{file_path}:{screen_name}"
    
    def _get_file_mtime(self, file_path: str) -> float:
        """Get file modification time"""
        try:
            return Path(file_path).stat().st_mtime
        except OSError:
            return 0.0
    
    def get(self, file_path: str, screen_name: str) -> Optional[Dict[str, Any]]:
        """
        Get cached screen context if valid.
        
        Args:
            file_path: Path to the configuration file
            screen_name: Name of the screen
            
        Returns:
            Cached screen context data or None if not found/expired
        """
        if not self.config.enabled:
            self.statistics.record_miss()
            return None
            
        cache_key = self._get_cache_key(file_path, screen_name)
        
        with self._lock:
            if cache_key not in self._cache:
                self.statistics.record_miss()
                return None
            
            entry = self._cache[cache_key]
            
            # Check if cache is still valid
            current_mtime = self._get_file_mtime(file_path)
            
            # Get stored file mtime from context hash (stored in entry)
            stored_context = entry.data
            stored_mtime = stored_context.get("_file_mtime", 0)
            
            # Invalidate if file changed or TTL expired
            if (current_mtime != stored_mtime or 
                entry.is_expired(self.config.ttl_seconds)):
                del self._cache[cache_key]
                self.statistics.record_miss()
                return None
            
            # Update access statistics
            entry.update_access()
            self.statistics.record_hit()
            
            logger.debug(f"Screen context cache hit: {screen_name}")
            
            # Return data without internal metadata
            result = stored_context.copy()
            result.pop("_file_mtime", None)
            return result
    
    def set(self, file_path: str, screen_name: str, data: Dict[str, Any]) -> None:
        """
        Cache screen context data.
        
        Args:
            file_path: Path to the configuration file
            screen_name: Name of the screen
            data: Screen context data to cache
        """
        if not self.config.enabled:
            return
            
        cache_key = self._get_cache_key(file_path, screen_name)
        file_mtime = self._get_file_mtime(file_path)
        
        # Add file modification time to data for validation
        data_with_mtime = data.copy()
        data_with_mtime["_file_mtime"] = file_mtime
        
        entry = CacheEntry(
            data=data_with_mtime,
            created_at=time.time(),
            last_accessed=time.time()
        )
        
        with self._lock:
            # Implement LRU eviction if at capacity
            if len(self._cache) >= self.config.max_size:
                self._evict_lru_entries()
            
            self._cache[cache_key] = entry
            self.statistics.total_entries = len(self._cache)
            
            logger.debug(f"Cached screen context: {screen_name}")
    
    def _evict_lru_entries(self):
        """Evict least recently used entries to make space"""
        if not self._cache:
            return
            
        # Sort by last accessed time and remove oldest entries
        sorted_entries = sorted(
            self._cache.items(), 
            key=lambda x: x[1].last_accessed
        )
        
        # Remove 25% of entries to avoid frequent evictions
        num_to_remove = max(1, len(sorted_entries) // 4)
        
        for cache_key, _ in sorted_entries[:num_to_remove]:
            del self._cache[cache_key]
            self.statistics.record_eviction()
        
        logger.debug(f"Evicted {num_to_remove} screen context cache entries")
    
    def clear(self) -> None:
        """Clear all cached data"""
        with self._lock:
            self._cache.clear()
            self.statistics.total_entries = 0
            logger.info("Screen context cache cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            self.statistics.total_entries = len(self._cache)
            return self.statistics.get_summary()


class ResponseCache:
    """
    Cache for Ollama responses based on query similarity and screen context.
    
    Provides intelligent caching of responses with similarity matching to avoid
    redundant processing of similar queries.
    """
    
    def __init__(self, config: CacheConfiguration):
        self.config = config
        self.statistics = CacheStatistics(name="response", max_size=config.max_size)
        self._cache: List[CacheEntry] = []
        self._lock = threading.RLock()
        
    def _generate_context_hash(self, screen_context: Dict[str, Any]) -> str:
        """Generate stable hash for screen context"""
        screen_name = screen_context.get("name", "")
        element_ids = sorted([
            elem.get("id", "") for elem in screen_context.get("elements", [])
        ])
        
        context_str = f"{screen_name}:{':'.join(element_ids)}"
        return hashlib.md5(context_str.encode()).hexdigest()[:16]
    
    def _cleanup_expired(self) -> None:
        """Remove expired cache entries"""
        current_time = time.time()
        
        with self._lock:
            original_count = len(self._cache)
            self._cache = [
                entry for entry in self._cache
                if not entry.is_expired(self.config.ttl_seconds)
            ]
            
            expired_count = original_count - len(self._cache)
            if expired_count > 0:
                logger.debug(f"Removed {expired_count} expired response cache entries")
    
    def _find_similar_entry(self, query: str, context_hash: str) -> Optional[CacheEntry]:
        """Find similar cached entry based on query similarity"""
        best_match = None
        best_similarity = 0.0
        
        normalized_query = QueryNormalizer.normalize(query)
        
        for entry in self._cache:
            # Must be same screen context
            if entry.context_hash != context_hash:
                continue
            
            # Calculate query similarity
            cached_normalized = entry.data.get("normalized_query", "")
            similarity = SequenceMatcher(None, normalized_query, cached_normalized).ratio()
            
            if similarity >= self.config.similarity_threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = entry
        
        return best_match
    
    def get(self, query: str, screen_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached response for similar query.
        
        Args:
            query: Query text to match
            screen_context: Current screen context
            
        Returns:
            Cached response data or None if not found
        """
        if not self.config.enabled:
            self.statistics.record_miss()
            return None
            
        self._cleanup_expired()
        context_hash = self._generate_context_hash(screen_context)
        
        with self._lock:
            similar_entry = self._find_similar_entry(query, context_hash)
            
            if similar_entry:
                # Update access statistics
                similar_entry.update_access()
                self.statistics.record_hit()
                
                logger.debug(f"Response cache hit for query: {query}")
                
                # Return response with cache metadata
                response = similar_entry.data["response"].copy()
                response["cached"] = True
                response["cache_similarity"] = QueryNormalizer.calculate_similarity(
                    query, similar_entry.data["original_query"]
                )
                return response
            
            self.statistics.record_miss()
            return None
    
    def set(self, query: str, screen_context: Dict[str, Any], response: Dict[str, Any]) -> None:
        """
        Cache response for query.
        
        Args:
            query: Original query text
            screen_context: Screen context at time of query
            response: Response data to cache
        """
        if not self.config.enabled:
            return
            
        context_hash = self._generate_context_hash(screen_context)
        normalized_query = QueryNormalizer.normalize(query)
        
        cache_data = {
            "original_query": query,
            "normalized_query": normalized_query,
            "response": response.copy()
        }
        
        entry = CacheEntry(
            data=cache_data,
            created_at=time.time(),
            last_accessed=time.time(),
            context_hash=context_hash
        )
        
        with self._lock:
            # Remove oldest entries if at max size
            if len(self._cache) >= self.config.max_size:
                self._evict_lru_entries()
            
            self._cache.append(entry)
            self.statistics.total_entries = len(self._cache)
            
            logger.debug(f"Cached response for query: {query}")
    
    def _evict_lru_entries(self):
        """Evict least recently used entries to make space"""
        if not self._cache:
            return
            
        # Sort by last access time and remove oldest
        self._cache.sort(key=lambda x: x.last_accessed)
        
        # Remove 25% of entries
        num_to_remove = max(1, len(self._cache) // 4)
        
        for _ in range(num_to_remove):
            if self._cache:
                self._cache.pop(0)
                self.statistics.record_eviction()
        
        logger.debug(f"Evicted {num_to_remove} response cache entries")
    
    def clear(self) -> None:
        """Clear all cached responses"""
        with self._lock:
            self._cache.clear()
            self.statistics.total_entries = 0
            logger.info("Response cache cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics"""
        self._cleanup_expired()
        
        with self._lock:
            context_counts = {}
            for entry in self._cache:
                context_hash = entry.context_hash
                if context_hash:
                    context_counts[context_hash] = context_counts.get(context_hash, 0) + 1
            
            stats = self.statistics.get_summary()
            stats["context_distributions"] = context_counts
            return stats


class CacheService:
    """
    Centralized cache management service.
    
    Coordinates multiple cache types and provides unified cache operations
    and statistics.
    """
    
    def __init__(self, config: CacheConfiguration):
        self.config = config
        self.screen_cache = ScreenContextCache(config)
        self.response_cache = ResponseCache(config)
        
    def get_screen_context(self, file_path: str, screen_name: str) -> Optional[Dict[str, Any]]:
        """Get cached screen context"""
        return self.screen_cache.get(file_path, screen_name)
    
    def set_screen_context(self, file_path: str, screen_name: str, data: Dict[str, Any]) -> None:
        """Cache screen context"""
        self.screen_cache.set(file_path, screen_name, data)
    
    def get_response(self, query: str, screen_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached response for query"""
        return self.response_cache.get(query, screen_context)
    
    def set_response(self, query: str, screen_context: Dict[str, Any], response: Dict[str, Any]) -> None:
        """Cache response for query"""
        self.response_cache.set(query, screen_context, response)
    
    def clear_all_caches(self) -> None:
        """Clear all caches"""
        self.screen_cache.clear()
        self.response_cache.clear()
        logger.info("All caches cleared")
    
    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """Get statistics for all caches"""
        return {
            "screen_context": self.screen_cache.get_statistics(),
            "response": self.response_cache.get_statistics(),
            "configuration": {
                "enabled": self.config.enabled,
                "max_size": self.config.max_size,
                "ttl_seconds": self.config.ttl_seconds,
                "similarity_threshold": self.config.similarity_threshold
            }
        }
    
    def update_configuration(self, new_config: CacheConfiguration) -> None:
        """Update cache configuration"""
        self.config = new_config
        self.screen_cache.config = new_config
        self.response_cache.config = new_config
        
        # Clear caches if disabled
        if not new_config.enabled:
            self.clear_all_caches()
        
        logger.info(f"Cache configuration updated: enabled={new_config.enabled}")