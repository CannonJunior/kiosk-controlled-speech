"""
MCP (Model Context Protocol) Integration Service

Handles MCP client initialization, tool calling, and service management.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastmcp import Client

from web_app.utils.mcp_utils import parse_tool_result, format_tool_error
from web_app.path_resolver import path_resolver

logger = logging.getLogger(__name__)


class MCPService:
    """Service for managing MCP client and tool integrations"""
    
    def __init__(self):
        self.mcp_client: Optional[Client] = None
        self.mcp_config: Optional[Dict[str, Any]] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize MCP services and client"""
        if self._initialized:
            return
            
        try:
            # Load MCP configuration
            await self._load_mcp_config()
            
            # Initialize MCP client with context manager
            self.mcp_client = Client(self.mcp_config)
            await self.mcp_client.__aenter__()
            
            # Debug: List available tools
            try:
                tools = await self.mcp_client.list_tools()
                logger.info(f"Available tools: {[tool.name for tool in tools]}")
            except Exception as e:
                logger.warning(f"Could not list tools: {e}")
            
            self._initialized = True
            logger.info("MCP services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP services: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup MCP client resources"""
        if self.mcp_client:
            try:
                await self.mcp_client.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"MCP client cleanup error: {e}")
        self._initialized = False
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call MCP tool with error handling and result parsing.
        
        Args:
            tool_name: Name of the tool to call
            parameters: Parameters to pass to the tool
            
        Returns:
            Parsed tool result
            
        Raises:
            RuntimeError: If MCP service not initialized
        """
        if not self._initialized or not self.mcp_client:
            raise RuntimeError("MCP service not initialized")
        
        try:
            logger.debug(f"Calling MCP tool: {tool_name} with parameters: {parameters}")
            result_raw = await self.mcp_client.call_tool(tool_name, parameters)
            result = parse_tool_result(result_raw)
            
            if result.get("success"):
                logger.debug(f"Tool {tool_name} succeeded")
            else:
                logger.warning(f"Tool {tool_name} failed: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"MCP tool call error for {tool_name}: {e}")
            return format_tool_error(tool_name, e)
    
    async def list_available_tools(self) -> List[str]:
        """
        Get list of available MCP tools.
        
        Returns:
            List of tool names
        """
        if not self._initialized or not self.mcp_client:
            return []
        
        try:
            tools = await self.mcp_client.list_tools()
            return [tool.name for tool in tools]
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            return []
    
    async def check_tool_availability(self, tool_name: str) -> bool:
        """
        Check if a specific tool is available.
        
        Args:
            tool_name: Tool to check
            
        Returns:
            True if tool is available, False otherwise
        """
        available_tools = await self.list_available_tools()
        return tool_name in available_tools
    
    def is_initialized(self) -> bool:
        """Check if MCP service is properly initialized"""
        return self._initialized and self.mcp_client is not None
    
    async def _load_mcp_config(self):
        """Load MCP configuration from config file"""
        config_path = path_resolver.resolve_config("mcp_config.json", required=True)
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Convert to FastMCP Client format
            self.mcp_config = {
                "mcpServers": {}
            }
            
            for name, server_data in config_data.get("servers", {}).items():
                if server_data.get("enabled", True):
                    self.mcp_config["mcpServers"][name] = {
                        "command": server_data["command"],
                        "args": server_data["args"]
                    }
                    
                    # Add environment variables if present
                    if "env" in server_data:
                        for key, value in server_data["env"].items():
                            os.environ[key] = value
                            
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            # Fallback configuration
            self.mcp_config = self._get_fallback_config()
    
    def _get_fallback_config(self) -> Dict[str, Any]:
        """Get fallback MCP configuration if config file fails to load"""
        return {
            "mcpServers": {
                "speech_to_text": {
                    "command": "python3",
                    "args": ["services/speech_to_text/mcp_server.py"]
                },
                "ollama_agent": {
                    "command": "python3", 
                    "args": ["services/ollama_agent/mcp_server.py"]
                },
                "mouse_control": {
                    "command": "python3",
                    "args": ["services/mouse_control/mcp_server.py"]
                },
                "screen_capture": {
                    "command": "python3",
                    "args": ["services/screen_capture/mcp_server.py"]
                },
                "screen_detector": {
                    "command": "python3",
                    "args": ["services/screen_detector/mcp_server.py"]
                }
            }
        }