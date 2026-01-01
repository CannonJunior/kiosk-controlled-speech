"""
MCP Tool Integration Utilities

Pure functions for parsing and handling MCP tool results.
No state, no external dependencies beyond typing.
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
        Standardized dictionary with success, data, and error fields
    """
    if result.is_error:
        return {
            "success": False, 
            "error": "Tool call failed",
            "details": getattr(result, 'error_details', None)
        }
    
    if result.content and len(result.content) > 0:
        text_content = result.content[0].text
        
        try:
            # Try to parse as JSON first
            parsed_data = json.loads(text_content)
            return {
                "success": True,
                "data": parsed_data
            }
        except json.JSONDecodeError:
            # If not JSON, return as raw text
            return {
                "success": True,
                "data": {"raw_text": text_content}
            }
    
    return {
        "success": False,
        "error": "No content in response"
    }


def format_tool_error(tool_name: str, error: Exception) -> Dict[str, Any]:
    """
    Format tool execution error for consistent error handling.
    
    Args:
        tool_name: Name of the tool that failed
        error: Exception that occurred
        
    Returns:
        Formatted error response
    """
    return {
        "success": False,
        "error": f"Tool '{tool_name}' failed: {str(error)}",
        "tool": tool_name,
        "error_type": type(error).__name__
    }


def validate_tool_parameters(parameters: Dict[str, Any], required_fields: list) -> Optional[str]:
    """
    Validate that required parameters are present for tool calls.
    
    Args:
        parameters: Tool parameters to validate
        required_fields: List of required field names
        
    Returns:
        Error message if validation fails, None if valid
    """
    missing_fields = []
    
    for field in required_fields:
        if field not in parameters or parameters[field] is None:
            missing_fields.append(field)
    
    if missing_fields:
        return f"Missing required parameters: {', '.join(missing_fields)}"
    
    return None


def extract_tool_data(result: Dict[str, Any], expected_fields: list) -> Dict[str, Any]:
    """
    Extract expected fields from tool result data.
    
    Args:
        result: Parsed tool result
        expected_fields: List of field names to extract
        
    Returns:
        Dictionary with extracted fields, None for missing fields
    """
    if not result.get("success") or "data" not in result:
        return {}
    
    data = result["data"]
    extracted = {}
    
    for field in expected_fields:
        extracted[field] = data.get(field)
    
    return extracted


def create_tool_context(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create context information for tool execution logging and debugging.
    
    Args:
        tool_name: Name of the tool being executed
        parameters: Parameters passed to the tool
        
    Returns:
        Context dictionary for logging
    """
    return {
        "tool": tool_name,
        "parameter_count": len(parameters),
        "parameter_keys": list(parameters.keys()),
        "timestamp": None  # Will be set by caller if needed
    }