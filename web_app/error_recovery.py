#!/usr/bin/env python3
"""
Error Recovery and Resilience Features for Web Application
Provides additional error handling and recovery mechanisms
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Circuit breaker pattern for MCP service calls"""
    
    def __init__(self, failure_threshold: int = 3, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise Exception("Circuit breaker is OPEN - service unavailable")
        
        try:
            result = await func(*args, **kwargs)
            
            # Success - reset circuit breaker
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info("Circuit breaker reset to CLOSED")
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            
            raise e

class RetryPolicy:
    """Retry policy with exponential backoff"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    async def execute(self, func: Callable, *args, **kwargs):
        """Execute function with retry policy"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed")
        
        raise last_exception

class HealthChecker:
    """Periodic health checking for services"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.service_health = {}
        self.running = False
        self.check_task = None
    
    def start(self, services: Dict[str, Callable]):
        """Start health checking"""
        self.services = services
        self.running = True
        self.check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Health checker started")
    
    async def stop(self):
        """Stop health checking"""
        self.running = False
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
        logger.info("Health checker stopped")
    
    async def _health_check_loop(self):
        """Main health checking loop"""
        while self.running:
            try:
                for service_name, health_func in self.services.items():
                    try:
                        await health_func()
                        self.service_health[service_name] = {
                            "status": "healthy",
                            "last_check": time.time()
                        }
                    except Exception as e:
                        self.service_health[service_name] = {
                            "status": "unhealthy",
                            "last_check": time.time(),
                            "error": str(e)
                        }
                        logger.warning(f"Service {service_name} health check failed: {e}")
                
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(self.check_interval)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return self.service_health.copy()

class ResourceManager:
    """Manages temporary resources and cleanup"""
    
    def __init__(self, max_temp_files: int = 100, cleanup_interval: int = 300):
        self.max_temp_files = max_temp_files
        self.cleanup_interval = cleanup_interval
        self.temp_files = set()
        self.cleanup_task = None
        self.running = False
    
    def start(self):
        """Start resource management"""
        self.running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Resource manager started")
    
    async def stop(self):
        """Stop resource management and cleanup"""
        self.running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Final cleanup
        await self._cleanup_temp_files()
        logger.info("Resource manager stopped")
    
    def register_temp_file(self, file_path: str):
        """Register a temporary file for cleanup"""
        self.temp_files.add(file_path)
        
        # Immediate cleanup if too many files
        if len(self.temp_files) > self.max_temp_files:
            asyncio.create_task(self._cleanup_temp_files())
    
    async def _cleanup_loop(self):
        """Periodic cleanup loop"""
        while self.running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_temp_files()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _cleanup_temp_files(self):
        """Clean up temporary files"""
        files_to_remove = set()
        current_time = time.time()
        
        for file_path in self.temp_files.copy():
            try:
                file_obj = Path(file_path)
                if not file_obj.exists():
                    files_to_remove.add(file_path)
                elif current_time - file_obj.stat().st_mtime > 3600:  # 1 hour old
                    file_obj.unlink()
                    files_to_remove.add(file_path)
                    logger.debug(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Error cleaning up {file_path}: {e}")
                files_to_remove.add(file_path)
        
        self.temp_files -= files_to_remove

class ErrorRecoveryManager:
    """Main error recovery and resilience manager"""
    
    def __init__(self):
        self.circuit_breakers = {}
        self.retry_policies = {}
        self.health_checker = HealthChecker()
        self.resource_manager = ResourceManager()
        self.metrics = {
            "total_requests": 0,
            "failed_requests": 0,
            "recovered_requests": 0,
            "circuit_breaker_trips": 0
        }
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker()
        return self.circuit_breakers[service_name]
    
    def get_retry_policy(self, service_name: str) -> RetryPolicy:
        """Get or create retry policy for service"""
        if service_name not in self.retry_policies:
            self.retry_policies[service_name] = RetryPolicy()
        return self.retry_policies[service_name]
    
    async def execute_with_resilience(self, service_name: str, func: Callable, *args, **kwargs):
        """Execute function with full resilience features"""
        self.metrics["total_requests"] += 1
        
        try:
            circuit_breaker = self.get_circuit_breaker(service_name)
            retry_policy = self.get_retry_policy(service_name)
            
            # Execute with circuit breaker and retry
            result = await circuit_breaker.call(
                retry_policy.execute, func, *args, **kwargs
            )
            
            return result
            
        except Exception as e:
            self.metrics["failed_requests"] += 1
            
            # Check if circuit breaker tripped
            if "Circuit breaker is OPEN" in str(e):
                self.metrics["circuit_breaker_trips"] += 1
            
            # Try fallback mechanisms
            fallback_result = await self._try_fallback(service_name, e, *args, **kwargs)
            if fallback_result is not None:
                self.metrics["recovered_requests"] += 1
                return fallback_result
            
            raise e
    
    async def _try_fallback(self, service_name: str, original_error: Exception, *args, **kwargs):
        """Try fallback mechanisms when primary service fails"""
        logger.info(f"Attempting fallback for {service_name} due to: {original_error}")
        
        if service_name == "speech_to_text":
            # Fallback: Return error message asking user to type
            return {
                "success": False,
                "error": "Speech recognition temporarily unavailable. Please type your message.",
                "fallback": True
            }
        
        elif service_name == "ollama_agent":
            # Fallback: Simple rule-based response
            return {
                "success": True,
                "response": {
                    "action": "clarify",
                    "message": "I'm currently experiencing some issues. Please try again in a moment.",
                    "fallback": True
                },
                "fallback": True
            }
        
        return None
    
    async def start(self, service_health_checks: Dict[str, Callable] = None):
        """Start error recovery manager"""
        if service_health_checks:
            self.health_checker.start(service_health_checks)
        self.resource_manager.start()
        logger.info("Error recovery manager started")
    
    async def stop(self):
        """Stop error recovery manager"""
        await self.health_checker.stop()
        await self.resource_manager.stop()
        logger.info("Error recovery manager stopped")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        total = self.metrics["total_requests"]
        if total > 0:
            success_rate = ((total - self.metrics["failed_requests"]) / total) * 100
            recovery_rate = (self.metrics["recovered_requests"] / total) * 100 if total > 0 else 0
        else:
            success_rate = 100.0
            recovery_rate = 0.0
        
        return {
            **self.metrics,
            "success_rate": success_rate,
            "recovery_rate": recovery_rate,
            "health_status": self.health_checker.get_health_status()
        }

# Global instance
error_recovery = ErrorRecoveryManager()