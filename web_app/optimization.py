#!/usr/bin/env python3
"""
Optimization module for kiosk web application
Provides caching and performance improvements for chat processing
"""
import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import threading

logger = logging.getLogger(__name__)

class ScreenContextCache:
    """Caches parsed screen context data with file modification time tracking"""
    
    def __init__(self, cache_ttl: int = 300):  # 5 minutes default TTL
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        
    def _get_cache_key(self, file_path: str, screen_name: str) -> str:
        """Generate cache key from file path and screen name"""
        return f"{file_path}:{screen_name}"
    
    def _get_file_mtime(self, file_path: str) -> float:
        """Get file modification time"""
        try:
            return os.path.getmtime(file_path)
        except OSError:
            return 0.0
    
    def get(self, file_path: str, screen_name: str) -> Optional[Dict[str, Any]]:
        """Get cached screen context if valid"""
        cache_key = self._get_cache_key(file_path, screen_name)
        
        with self._lock:
            if cache_key not in self._cache:
                return None
            
            cached_data = self._cache[cache_key]
            
            # Check if cache is still valid
            current_mtime = self._get_file_mtime(file_path)
            cached_mtime = cached_data.get("file_mtime", 0)
            cache_time = cached_data.get("cache_time", 0)
            
            # Invalidate if file changed or TTL expired
            if (current_mtime != cached_mtime or 
                time.time() - cache_time > self.cache_ttl):
                del self._cache[cache_key]
                return None
            
            logger.debug(f"Cache hit for screen context: {screen_name}")
            return cached_data["data"]
    
    def set(self, file_path: str, screen_name: str, data: Dict[str, Any]) -> None:
        """Cache screen context data"""
        cache_key = self._get_cache_key(file_path, screen_name)
        file_mtime = self._get_file_mtime(file_path)
        
        with self._lock:
            self._cache[cache_key] = {
                "data": data.copy(),
                "file_mtime": file_mtime,
                "cache_time": time.time()
            }
            logger.debug(f"Cached screen context: {screen_name}")
    
    def clear(self) -> None:
        """Clear all cached data"""
        with self._lock:
            self._cache.clear()
            logger.info("Screen context cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                "total_entries": len(self._cache),
                "cache_keys": list(self._cache.keys()),
                "ttl_seconds": self.cache_ttl
            }


class QueryNormalizer:
    """Normalizes queries for similarity matching"""
    
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
        
        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, norm1, norm2).ratio()


class ResponseCache:
    """Caches Ollama responses based on query similarity and screen context"""
    
    def __init__(self, max_size: int = 100, cache_ttl: int = 600, similarity_threshold: float = 0.85):
        self.max_size = max_size
        self.cache_ttl = cache_ttl
        self.similarity_threshold = similarity_threshold
        self._cache: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        
    def _generate_context_hash(self, screen_context: Dict[str, Any]) -> str:
        """Generate hash for screen context"""
        # Create stable hash from screen name and element IDs
        screen_name = screen_context.get("name", "")
        element_ids = sorted([elem.get("id", "") for elem in screen_context.get("elements", [])])
        
        context_str = f"{screen_name}:{':'.join(element_ids)}"
        return hashlib.md5(context_str.encode()).hexdigest()[:16]
    
    def _cleanup_expired(self) -> None:
        """Remove expired cache entries"""
        current_time = time.time()
        
        with self._lock:
            self._cache = [
                entry for entry in self._cache
                if current_time - entry["cache_time"] <= self.cache_ttl
            ]
    
    def _find_similar_entry(self, query: str, context_hash: str) -> Optional[Dict[str, Any]]:
        """Find similar cached entry"""
        best_match = None
        best_similarity = 0.0
        
        for entry in self._cache:
            if entry["context_hash"] != context_hash:
                continue
            
            similarity = QueryNormalizer.calculate_similarity(query, entry["normalized_query"])
            
            if similarity >= self.similarity_threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = entry
        
        return best_match
    
    def get(self, query: str, screen_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached response for similar query"""
        self._cleanup_expired()
        
        context_hash = self._generate_context_hash(screen_context)
        
        with self._lock:
            similar_entry = self._find_similar_entry(query, context_hash)
            
            if similar_entry:
                # Update access time for LRU
                similar_entry["last_access"] = time.time()
                logger.debug(f"Response cache hit for query: {query}")
                
                # Return response with cache metadata
                response = similar_entry["response"].copy()
                response["cached"] = True
                response["cache_similarity"] = QueryNormalizer.calculate_similarity(
                    query, similar_entry["original_query"]
                )
                return response
        
        return None
    
    def set(self, query: str, screen_context: Dict[str, Any], response: Dict[str, Any]) -> None:
        """Cache response for query"""
        context_hash = self._generate_context_hash(screen_context)
        normalized_query = QueryNormalizer.normalize(query)
        
        cache_entry = {
            "original_query": query,
            "normalized_query": normalized_query,
            "context_hash": context_hash,
            "response": response.copy(),
            "cache_time": time.time(),
            "last_access": time.time()
        }
        
        with self._lock:
            # Remove oldest entries if at max size
            if len(self._cache) >= self.max_size:
                # Sort by last access time and remove oldest
                self._cache.sort(key=lambda x: x["last_access"])
                self._cache = self._cache[-(self.max_size-1):]
            
            self._cache.append(cache_entry)
            logger.debug(f"Cached response for query: {query}")
    
    def clear(self) -> None:
        """Clear all cached responses"""
        with self._lock:
            self._cache.clear()
            logger.info("Response cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        self._cleanup_expired()
        
        with self._lock:
            context_counts = {}
            for entry in self._cache:
                context_hash = entry["context_hash"]
                context_counts[context_hash] = context_counts.get(context_hash, 0) + 1
            
            return {
                "total_entries": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.cache_ttl,
                "similarity_threshold": self.similarity_threshold,
                "context_distributions": context_counts
            }


class ModelConfigManager:
    """Manages LLM model configuration and selection"""
    
    def __init__(self, config_path: str = "config/model_config.json"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load model configuration from file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
            else:
                # Create default configuration
                self._config = self._get_default_config()
                self._save_config()
        except Exception as e:
            logger.error(f"Failed to load model config: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default model configuration"""
        return {
            "models": {
                "default": {
                    "name": "qwen2.5:1.5b",
                    "description": "Fast lightweight model",
                    "temperature": 0.1,
                    "max_tokens": 512,
                    "estimated_latency": "0.5-1.5s"
                },
                "balanced": {
                    "name": "llama3.1:8b",
                    "description": "Balanced speed and accuracy",
                    "temperature": 0.1,
                    "max_tokens": 512,
                    "estimated_latency": "1-3s"
                },
                "accurate": {
                    "name": "llama3.1:70b",
                    "description": "High accuracy, slower",
                    "temperature": 0.1,
                    "max_tokens": 512,
                    "estimated_latency": "3-8s"
                }
            },
            "current_model": "default",
            "fallback_model": "default",
            "auto_fallback": True
        }
    
    def _save_config(self) -> None:
        """Save configuration to file"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save model config: {e}")
    
    def get_current_model_config(self) -> Dict[str, Any]:
        """Get current model configuration"""
        current_key = self._config.get("current_model", "default")
        return self._config.get("models", {}).get(current_key, self._get_default_config()["models"]["default"])
    
    def set_current_model(self, model_key: str) -> bool:
        """Set current model"""
        if model_key in self._config.get("models", {}):
            self._config["current_model"] = model_key
            self._save_config()
            logger.info(f"Switched to model: {model_key}")
            return True
        return False
    
    def add_model(self, key: str, config: Dict[str, Any]) -> None:
        """Add new model configuration"""
        if "models" not in self._config:
            self._config["models"] = {}
        
        self._config["models"][key] = config
        self._save_config()
        logger.info(f"Added model configuration: {key}")
    
    def get_available_models(self) -> List[str]:
        """Get list of available model keys"""
        return list(self._config.get("models", {}).keys())
    
    def get_model_info(self, model_key: str = None) -> Dict[str, Any]:
        """Get detailed model information"""
        if model_key is None:
            model_key = self._config.get("current_model", "default")
        
        model_config = self._config.get("models", {}).get(model_key, {})
        
        return {
            "key": model_key,
            "name": model_config.get("name", "unknown"),
            "description": model_config.get("description", ""),
            "temperature": model_config.get("temperature", 0.1),
            "max_tokens": model_config.get("max_tokens", 512),
            "estimated_latency": model_config.get("estimated_latency", "unknown")
        }


class OptimizationManager:
    """Central manager for all optimization features"""
    
    def __init__(self):
        self.screen_cache = ScreenContextCache()
        self.response_cache = ResponseCache()
        self.model_config = ModelConfigManager()
        
        # Performance metrics
        self._metrics = {
            "screen_cache_hits": 0,
            "screen_cache_misses": 0,
            "response_cache_hits": 0,
            "response_cache_misses": 0,
            "model_switches": 0,
            "total_queries": 0
        }
        self._metrics_lock = threading.RLock()
    
    def increment_metric(self, metric_name: str) -> None:
        """Increment performance metric"""
        with self._metrics_lock:
            self._metrics[metric_name] = self._metrics.get(metric_name, 0) + 1
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        with self._metrics_lock:
            screen_total = self._metrics["screen_cache_hits"] + self._metrics["screen_cache_misses"]
            response_total = self._metrics["response_cache_hits"] + self._metrics["response_cache_misses"]
            
            return {
                "metrics": self._metrics.copy(),
                "cache_stats": {
                    "screen_cache": {
                        **self.screen_cache.get_stats(),
                        "hit_rate": (self._metrics["screen_cache_hits"] / max(screen_total, 1)) * 100
                    },
                    "response_cache": {
                        **self.response_cache.get_stats(),
                        "hit_rate": (self._metrics["response_cache_hits"] / max(response_total, 1)) * 100
                    }
                },
                "model_config": {
                    "current_model": self.model_config.get_model_info(),
                    "available_models": self.model_config.get_available_models()
                }
            }
    
    def clear_all_caches(self) -> None:
        """Clear all caches"""
        self.screen_cache.clear()
        self.response_cache.clear()
        logger.info("All caches cleared")
    
    def optimize_for_speed(self) -> bool:
        """Configure for maximum speed"""
        return self.model_config.set_current_model("default")
    
    def optimize_for_accuracy(self) -> bool:
        """Configure for maximum accuracy"""
        return self.model_config.set_current_model("accurate")
    
    def optimize_balanced(self) -> bool:
        """Configure for balanced performance"""
        return self.model_config.set_current_model("balanced")


# Global optimization manager instance
optimization_manager = OptimizationManager()