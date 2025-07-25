import asyncio
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import aiofiles
from pathlib import Path

from mcp import ClientSession, stdio_client, StdioServerParameters
from mcp.types import Tool, Resource


@dataclass
class ServerConfig:
    name: str
    command: str
    args: List[str]
    env: Dict[str, str]
    enabled: bool = True


@dataclass
class OrchestrationConfig:
    response_timeout: int = 5000
    retry_attempts: int = 3
    health_check_interval: int = 30
    log_level: str = "INFO"


class MCPOrchestrator:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.clients: Dict[str, ClientSession] = {}
        self.client_contexts: Dict[str, Any] = {}
        self.server_configs: Dict[str, ServerConfig] = {}
        self.orchestration_config = OrchestrationConfig()
        self.running = False
    
    async def load_config(self):
        """Load MCP configuration from file"""
        async with aiofiles.open(self.config_path, 'r') as f:
            config_data = json.loads(await f.read())
        
        # Load server configurations
        for name, server_data in config_data.get("servers", {}).items():
            self.server_configs[name] = ServerConfig(
                name=name,
                command=server_data["command"],
                args=server_data["args"],
                env=server_data.get("env", {}),
                enabled=server_data.get("enabled", True)
            )
        
        # Load orchestration configuration
        if "orchestrator" in config_data:
            orch_data = config_data["orchestrator"]
            self.orchestration_config = OrchestrationConfig(**orch_data)
    
    async def start_servers(self):
        """Start all enabled MCP servers"""
        self.running = True
        
        for name, config in self.server_configs.items():
            if not config.enabled:
                continue
                
            try:
                server_params = StdioServerParameters(
                    command=config.command,
                    args=config.args,
                    env=config.env
                )
                context = stdio_client(server_params)
                read_stream, write_stream = await context.__aenter__()
                session = ClientSession(read_stream, write_stream)
                self.clients[name] = session
                self.client_contexts[name] = context
                print(f"Started MCP server: {name}")
                
            except Exception as e:
                print(f"Failed to start MCP server {name}: {e}")
    
    async def stop_servers(self):
        """Stop all MCP servers"""
        self.running = False
        
        # Stop servers sequentially and handle errors gracefully
        for name in list(self.clients.keys()):
            try:
                if name in self.client_contexts:
                    context = self.client_contexts[name]
                    try:
                        # Try normal exit first
                        await context.__aexit__(None, None, None)
                        print(f"Stopped MCP server: {name}")
                    except (RuntimeError, asyncio.CancelledError, Exception) as e:
                        if "cancel scope" in str(e) or isinstance(e, asyncio.CancelledError):
                            # Handle asyncio/anyio cancellation issues by suppressing the error
                            print(f"Stopped MCP server: {name} (cancellation handled)")
                        else:
                            print(f"Error stopping MCP server {name}: {e}")
                    del self.client_contexts[name]
            except Exception as e:
                print(f"Error stopping MCP server {name}: {e}")
        
        self.clients.clear()
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Call a tool on a specific MCP server"""
        if server_name not in self.clients:
            raise ValueError(f"Server {server_name} not found or not running")
        
        client = self.clients[server_name]
        
        try:
            result = await asyncio.wait_for(
                client.call_tool(tool_name, arguments or {}),
                timeout=self.orchestration_config.response_timeout / 1000
            )
            return result
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tool call {tool_name} on {server_name} timed out")
        except Exception as e:
            raise RuntimeError(f"Tool call failed: {e}")
    
    async def list_tools(self, server_name: str = None) -> Dict[str, List[Tool]]:
        """List tools from all servers or a specific server"""
        if server_name:
            if server_name not in self.clients:
                raise ValueError(f"Server {server_name} not found")
            tools = await self.clients[server_name].list_tools()
            return {server_name: tools}
        
        all_tools = {}
        for name, client in self.clients.items():
            try:
                tools = await client.list_tools()
                all_tools[name] = tools
            except Exception as e:
                print(f"Failed to list tools for {name}: {e}")
                all_tools[name] = []
        
        return all_tools
    
    async def list_resources(self, server_name: str = None) -> Dict[str, List[Resource]]:
        """List resources from all servers or a specific server"""
        if server_name:
            if server_name not in self.clients:
                raise ValueError(f"Server {server_name} not found")
            resources = await self.clients[server_name].list_resources()
            return {server_name: resources}
        
        all_resources = {}
        for name, client in self.clients.items():
            try:
                resources = await client.list_resources()
                all_resources[name] = resources
            except Exception as e:
                print(f"Failed to list resources for {name}: {e}")
                all_resources[name] = []
        
        return all_resources
    
    async def read_resource(self, server_name: str, uri: str) -> str:
        """Read a resource from a specific server"""
        if server_name not in self.clients:
            raise ValueError(f"Server {server_name} not found")
        
        client = self.clients[server_name]
        return await client.read_resource(uri)
    
    async def health_check(self, server_name: str = None) -> Dict[str, Dict[str, Any]]:
        """Perform health check on all servers or a specific server"""
        if server_name:
            if server_name not in self.clients:
                return {server_name: {"status": "not_found", "error": "Server not running"}}
            
            try:
                # Basic connectivity check
                await asyncio.wait_for(
                    self.clients[server_name].list_tools(),
                    timeout=10.0
                )
                return {server_name: {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}}
            except Exception as e:
                return {server_name: {"status": "unhealthy", "error": str(e)}}
        
        health_status = {}
        for name, client in self.clients.items():
            try:
                await asyncio.wait_for(client.list_tools(), timeout=10.0)
                health_status[name] = {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}
            except Exception as e:
                health_status[name] = {"status": "unhealthy", "error": str(e)}
        
        return health_status
    
    async def orchestrate_workflow(self, workflow_steps: List[Dict[str, Any]]) -> List[Any]:
        """Execute a workflow with multiple MCP tool calls"""
        results = []
        
        for step in workflow_steps:
            server_name = step["server"]
            tool_name = step["tool"]
            arguments = step.get("arguments", {})
            
            # Support for conditional execution
            if "condition" in step:
                condition_result = await self._evaluate_condition(step["condition"], results)
                if not condition_result:
                    results.append({"skipped": True, "reason": "condition_failed"})
                    continue
            
            # Execute tool call with retry logic
            for attempt in range(self.orchestration_config.retry_attempts):
                try:
                    result = await self.call_tool(server_name, tool_name, arguments)
                    results.append(result)
                    break
                except Exception as e:
                    if attempt == self.orchestration_config.retry_attempts - 1:
                        results.append({"error": str(e), "failed_step": step})
                        break
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
        
        return results
    
    async def _evaluate_condition(self, condition: Dict[str, Any], previous_results: List[Any]) -> bool:
        """Evaluate a condition for workflow step execution"""
        # Simple condition evaluation - can be extended
        if condition["type"] == "previous_success":
            step_index = condition["step_index"]
            if step_index < len(previous_results):
                result = previous_results[step_index]
                return isinstance(result, dict) and result.get("success", True)
        
        return True