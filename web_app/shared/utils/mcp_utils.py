"""
Shared Utilities - MCP Tool Integration

Common utilities for working with MCP (Model Context Protocol) tools and results.
"""
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_tool_result(result) -> Dict[str, Any]:
    """
    Parse FastMCP tool result into standardized format.
    
    Args:
        result: FastMCP tool result object
        
    Returns:
        Standardized dictionary with success/error information
    """
    if not result:
        return {"success": False, "error": "No result provided"}
    
    if hasattr(result, 'is_error') and result.is_error:
        error_msg = getattr(result, 'error', "Tool call failed")
        return {"success": False, "error": str(error_msg)}
    
    if hasattr(result, 'content') and result.content and len(result.content) > 0:
        text_content = result.content[0].text
        
        # Try to parse as JSON first
        try:
            parsed_data = json.loads(text_content)
            return {"success": True, "data": parsed_data}
        except json.JSONDecodeError:
            # Return as raw text if not valid JSON
            return {"success": True, "data": {"raw_text": text_content}}
    
    return {"success": False, "error": "No content in response"}


def validate_mcp_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate MCP configuration structure.
    
    Args:
        config: MCP configuration dictionary
        
    Returns:
        Validation result with errors and warnings
    """
    errors = []
    warnings = []
    
    # Check for servers section
    if "servers" not in config:
        errors.append("Missing 'servers' section in MCP configuration")
        return {"valid": False, "errors": errors, "warnings": warnings}
    
    servers = config["servers"]
    if not isinstance(servers, dict):
        errors.append("'servers' must be an object/dictionary")
        return {"valid": False, "errors": errors, "warnings": warnings}
    
    if len(servers) == 0:
        warnings.append("No servers configured in MCP configuration")
    
    # Validate each server configuration
    for server_name, server_config in servers.items():
        if not isinstance(server_config, dict):
            errors.append(f"Server '{server_name}' configuration must be an object")
            continue
        
        # Check required fields
        if "command" not in server_config:
            errors.append(f"Server '{server_name}' missing required 'command' field")
        
        # Check optional fields
        if "args" in server_config and not isinstance(server_config["args"], list):
            errors.append(f"Server '{server_name}' args must be an array")
        
        # Check for common configuration issues
        if "env" in server_config and not isinstance(server_config["env"], dict):
            warnings.append(f"Server '{server_name}' env should be an object")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def create_mcp_fallback_config() -> Dict[str, Any]:
    """
    Create fallback MCP configuration when config file is missing or invalid.
    
    Returns:
        Basic MCP configuration with essential servers
    """
    return {
        "mcpServers": {},
        "servers": {
            "ollama_agent": {
                "command": "python",
                "args": ["-m", "services.ollama_agent.mcp_server"],
                "env": {}
            }
        },
        "_metadata": {
            "created_by": "fallback_config",
            "note": "This is a fallback configuration. Update mcp_config.json for custom settings."
        }
    }


def extract_server_info(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Extract server information from MCP configuration for monitoring.
    
    Args:
        config: MCP configuration dictionary
        
    Returns:
        Dictionary mapping server names to their info
    """
    servers_info = {}
    
    servers = config.get("servers", {})
    for name, server_data in servers.items():
        servers_info[name] = {
            "command": server_data.get("command", "unknown"),
            "args_count": len(server_data.get("args", [])),
            "has_env": bool(server_data.get("env")),
            "configured": True
        }
    
    return servers_info


def sanitize_mcp_server_name(name: str) -> str:
    """
    Sanitize MCP server name for safe usage in identifiers.
    
    Args:
        name: Raw server name
        
    Returns:
        Sanitized server name safe for use in code
    """
    # Replace invalid characters with underscores
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    
    # Ensure it starts with a letter or underscore
    if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = f"_{sanitized}"
    
    # Ensure it's not empty
    return sanitized or "unknown_server"