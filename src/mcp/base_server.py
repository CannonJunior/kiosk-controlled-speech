from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
import asyncio
import json
from dataclasses import dataclass
from enum import Enum

from mcp.server import Server
from mcp.types import Tool, Resource


class ServiceStatus(Enum):
    STARTING = "starting"
    RUNNING = "running" 
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ServiceHealth:
    status: ServiceStatus
    last_check: float
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None


class BaseMCPServer(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.server = Server(name)
        self.health = ServiceHealth(ServiceStatus.STOPPED, 0)
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup base MCP handlers"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return await self.get_tools()
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> Any:
            return await self.handle_tool_call(name, arguments)
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            return await self.get_resources()
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            return await self.read_resource_content(uri)
    
    @abstractmethod
    async def get_tools(self) -> List[Tool]:
        """Return list of tools this server provides"""
        pass
    
    @abstractmethod
    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Handle tool call and return result"""
        pass
    
    async def get_resources(self) -> List[Resource]:
        """Return list of resources this server provides (optional)"""
        return []
    
    async def read_resource_content(self, uri: str) -> str:
        """Read resource content by URI (optional)"""
        raise NotImplementedError(f"Resource {uri} not found")
    
    async def start(self, host: str = "localhost", port: int = 8080):
        """Start the MCP server"""
        self.health.status = ServiceStatus.STARTING
        try:
            await self.server.run(host=host, port=port)
            self.health.status = ServiceStatus.RUNNING
        except Exception as e:
            self.health.status = ServiceStatus.ERROR
            self.health.error_message = str(e)
            raise
    
    async def stop(self):
        """Stop the MCP server"""
        self.health.status = ServiceStatus.STOPPING
        # Cleanup logic here
        self.health.status = ServiceStatus.STOPPED
    
    async def health_check(self) -> ServiceHealth:
        """Perform health check and return status"""
        import time
        start_time = time.time()
        
        try:
            # Basic health check - can be overridden by subclasses
            await self._internal_health_check()
            response_time = (time.time() - start_time) * 1000
            
            self.health.last_check = time.time()
            self.health.response_time_ms = response_time
            self.health.error_message = None
            
            if self.health.status == ServiceStatus.ERROR:
                self.health.status = ServiceStatus.RUNNING
                
        except Exception as e:
            self.health.status = ServiceStatus.ERROR
            self.health.error_message = str(e)
            self.health.last_check = time.time()
        
        return self.health
    
    async def _internal_health_check(self):
        """Internal health check - override in subclasses"""
        pass


class MCPToolError(Exception):
    """Custom exception for MCP tool errors"""
    
    def __init__(self, message: str, error_code: str = "TOOL_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def create_tool_response(success: bool, data: Any = None, error: str = None) -> Dict[str, Any]:
    """Create standardized tool response"""
    import time
    response = {
        "success": success,
        "timestamp": time.time()
    }
    
    if success:
        response["data"] = data
    else:
        response["error"] = error
    
    return response