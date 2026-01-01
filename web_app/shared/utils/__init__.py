"""
Shared Utilities

Common utility functions used across multiple domains and services.
"""

from .mcp_utils import (
    parse_tool_result, validate_mcp_config, create_mcp_fallback_config,
    extract_server_info, sanitize_mcp_server_name
)
from .cache_utils import (
    generate_cache_key, generate_query_cache_key, generate_screen_cache_key,
    generate_config_cache_key, is_cacheable_query, calculate_cache_priority,
    should_evict_cache_entry, normalize_cache_data, extract_cache_statistics
)

__all__ = [
    # MCP utilities
    'parse_tool_result',
    'validate_mcp_config', 
    'create_mcp_fallback_config',
    'extract_server_info',
    'sanitize_mcp_server_name',
    
    # Cache utilities
    'generate_cache_key',
    'generate_query_cache_key',
    'generate_screen_cache_key', 
    'generate_config_cache_key',
    'is_cacheable_query',
    'calculate_cache_priority',
    'should_evict_cache_entry',
    'normalize_cache_data',
    'extract_cache_statistics'
]