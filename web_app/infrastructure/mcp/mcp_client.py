"""
Infrastructure Layer - MCP Client Wrapper

Enhanced MCP client with connection management, health monitoring, and tool registry.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastmcp import Client

from web_app.path_resolver import path_resolver
from web_app.utils.mcp_utils import parse_tool_result, format_tool_error

logger = logging.getLogger(__name__)


class EnhancedMCPClient:
    """
    Enhanced MCP client wrapper with infrastructure capabilities.
    
    Responsibilities:
    - MCP configuration management and client initialization
    - Health monitoring and tool availability checking
    - Connection lifecycle management
    - Tool result parsing and error handling
    """
    
    def __init__(self):
        self.mcp_client: Optional[Client] = None
        self.mcp_config: Optional[Dict[str, Any]] = None
        self._initialized = False
        self._available_tools: List[str] = []
        self._health_status = "unknown"
    
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
            
            # Discover available tools
            await self._discover_tools()
            
            self._initialized = True
            self._health_status = "healthy"
            logger.info("Enhanced MCP client initialized successfully")
            
        except Exception as e:
            self._health_status = "error"
            logger.error(f"Failed to initialize MCP client: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup MCP client resources"""
        if self.mcp_client:
            try:
                await self.mcp_client.__aexit__(None, None, None)
                self._health_status = "disconnected"
            except Exception as e:
                logger.error(f"MCP client cleanup error: {e}")
        self._initialized = False
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call MCP tool with enhanced error handling and monitoring.
        
        Args:
            tool_name: Name of the tool to call
            parameters: Parameters to pass to the tool
            
        Returns:
            Parsed tool result with success/error information
            
        Raises:
            RuntimeError: If MCP client not initialized
        """
        if not self._initialized or not self.mcp_client:
            raise RuntimeError("MCP client not initialized")
        
        # Check if tool is available
        if tool_name not in self._available_tools:
            logger.warning(f"Tool {tool_name} not in available tools list: {self._available_tools}")
        
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
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check of MCP services.
        
        Returns:
            Health status with detailed information
        """
        if not self._initialized:
            return {
                "status": "not_initialized",
                "available_tools": [],
                "servers": {},
                "error": "MCP client not initialized"
            }
        
        try:
            # Test basic connectivity
            tools = await self.mcp_client.list_tools()
            current_tools = [tool.name for tool in tools]
            
            # Update available tools if changed
            if set(current_tools) != set(self._available_tools):
                logger.info(f"Tool availability changed: {current_tools}")
                self._available_tools = current_tools
            
            # Check individual server health
            server_health = {}
            for server_name in self.mcp_config.get("mcpServers", {}).keys():
                server_health[server_name] = await self._check_server_health(server_name)
            
            self._health_status = "healthy"
            return {
                "status": "healthy",
                "available_tools": current_tools,
                "tool_count": len(current_tools),
                "servers": server_health,
                "config_loaded": bool(self.mcp_config)
            }
            
        except Exception as e:
            self._health_status = "error"
            logger.error(f"MCP health check failed: {e}")
            return {
                "status": "error",
                "available_tools": self._available_tools,  # Use cached version
                "servers": {},
                "error": str(e)
            }
    
    async def _discover_tools(self):
        """Discover and cache available tools"""
        try:
            tools = await self.mcp_client.list_tools()
            self._available_tools = [tool.name for tool in tools]
            logger.info(f"Discovered {len(self._available_tools)} MCP tools")
        except Exception as e:
            logger.warning(f"Could not discover tools: {e}")
            self._available_tools = []
    
    async def _check_server_health(self, server_name: str) -> Dict[str, Any]:
        """
        Check health of individual MCP server.
        
        Args:
            server_name: Name of the server to check
            
        Returns:
            Server health information
        """
        try:
            # Try to call a health check tool if available
            health_tool = f"{server_name}_health_check"
            if health_tool in self._available_tools:
                result = await self.call_tool(health_tool, {})
                return {
                    "status": "healthy" if result.get("success") else "unhealthy",
                    "details": result.get("data", {}),
                    "error": result.get("error")
                }
            else:
                # Server is available if any of its tools are working
                server_tools = [tool for tool in self._available_tools if tool.startswith(f"{server_name}_")]
                return {
                    "status": "available" if server_tools else "unknown",
                    "available_tools": server_tools,
                    "tool_count": len(server_tools)
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _load_mcp_config(self):
        """Load MCP configuration from config file with enhanced error handling"""
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
            
            logger.info(f"Loaded MCP config with {len(self.mcp_config['mcpServers'])} servers")
                            
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            # Use fallback configuration
            self.mcp_config = self._get_fallback_config()
    
    def _get_fallback_config(self) -> Dict[str, Any]:
        """Get fallback MCP configuration if config file fails to load"""
        logger.info("Using fallback MCP configuration")
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
    
    def get_status(self) -> Dict[str, Any]:
        """Get current client status and metrics"""
        return {
            "initialized": self._initialized,
            "health_status": self._health_status,
            "available_tools": len(self._available_tools),
            "config_loaded": bool(self.mcp_config),
            "servers_configured": len(self.mcp_config.get("mcpServers", {})) if self.mcp_config else 0
        }
    
    def is_tool_available(self, tool_name: str) -> bool:
        """Check if a specific tool is available"""
        return tool_name in self._available_tools
    
    def get_available_tools(self) -> List[str]:
        """Get list of currently available tools"""
        return self._available_tools.copy()