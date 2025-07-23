#!/usr/bin/env python3
"""Simple MCP server test"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create server instance
server = Server("test-server")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="echo",
            description="Echo back the input",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                },
                "required": ["message"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "echo":
        message = arguments.get("message", "")
        return [TextContent(type="text", text=f"Echo: {message}")]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())