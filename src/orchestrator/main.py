#!/usr/bin/env python3
import asyncio
import signal
import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.table import Table
import time

from fastmcp import Client
sys.path.append('.')
from src.data_manager.kiosk_data import KioskDataManager


app = typer.Typer(name="kiosk-orchestrator")
console = Console()


class KioskOrchestrator:
    def __init__(self, config_path: str = "config/mcp_config.json"):
        self.config_path = config_path
        self.data_manager = KioskDataManager("config/kiosk_data.json")
        self.mcp_client = None
        self.mcp_config = None
        
        # State management
        self.current_screen_id: Optional[str] = None
        self.last_screenshot_data: Optional[str] = None
        self.is_listening = False
        self.running = False
        
        # Performance metrics
        self.metrics = {
            "commands_processed": 0,
            "successful_clicks": 0,
            "failed_actions": 0,
            "average_response_time": 0.0,
            "session_start_time": time.time()
        }
    
    async def start(self):
        """Start the kiosk orchestrator"""
        console.print(Panel(
            Text("🎤 Kiosk Voice Control System", style="bold green"),
            subtitle="Starting up..."
        ))
        
        try:
            # Load configuration and data
            await self._load_mcp_config()
            await self.data_manager.load_data()
            
            # Initialize MCP client with context manager
            console.print("🔧 Initializing MCP services...")
            self.mcp_client = Client(self.mcp_config)
            await self.mcp_client.__aenter__()
            
            # Initialize system state
            await self._initialize_system()
            
            self.running = True
            console.print(Panel(
                Text("✅ System Ready", style="bold green"),
                subtitle="Voice control is now active"
            ))
            
            # Start main loop
            await self._main_loop()
            
        except Exception as e:
            console.print(f"❌ Failed to start system: {e}", style="red")
            raise
    
    async def stop(self):
        """Stop the orchestrator and cleanup"""
        console.print("🛑 Stopping kiosk orchestrator...")
        self.running = False
        
        # Stop listening
        if self.is_listening:
            await self._stop_listening()
        
        # Cleanup MCP client
        if self.mcp_client:
            try:
                await self.mcp_client.__aexit__(None, None, None)
            except Exception as e:
                console.print(f"⚠️  MCP client cleanup error: {e}", style="yellow")
        
        # Display final metrics
        self._display_final_metrics()
        
        console.print("✅ System stopped successfully")
    
    async def _initialize_system(self):
        """Initialize system state"""
        # Take initial screenshot
        await self._update_screen_state()
        
        # Start speech recognition
        await self._start_listening()
    
    async def _main_loop(self):
        """Main orchestration loop"""
        with Live(self._create_status_display(), refresh_per_second=1) as live:
            while self.running:
                try:
                    # Update screen state periodically
                    await self._update_screen_state()
                    
                    # Process any queued voice commands
                    await self._process_pending_commands()
                    
                    # Update display
                    live.update(self._create_status_display())
                    
                    # Sleep briefly
                    await asyncio.sleep(0.5)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    console.print(f"⚠️  Loop error: {e}", style="yellow")
                    await asyncio.sleep(1)
    
    async def _update_screen_state(self):
        """Update current screen state"""
        try:
            # Take screenshot
            screenshot_result = await self.mcp_client.call_tool(
                "screen_capture_take_screenshot"
            )
            
            if screenshot_result.get("success"):
                screenshot_data = screenshot_result["data"]["data"]  # Base64 image data
                self.last_screenshot_data = screenshot_data
                
                # Get screen definitions
                all_screens = self.data_manager.get_all_screens()
                screen_definitions = {
                    screen_id: screen.to_dict() 
                    for screen_id, screen in all_screens.items()
                }
                
                # Detect current screen
                detection_result = await self.mcp_client.call_tool(
                    "screen_detector_detect_current_screen", {
                        "screenshot_data": screenshot_data,
                        "screen_definitions": screen_definitions
                    }
                )
                
                if detection_result.get("success"):
                    detected_screen = detection_result["data"].get("detected_screen")
                    if detected_screen != self.current_screen_id:
                        self.current_screen_id = detected_screen
                        console.print(f"📱 Screen changed to: {detected_screen}")
                
        except Exception as e:
            console.print(f"⚠️  Screen state update failed: {e}", style="yellow")
    
    async def _start_listening(self):
        """Start speech recognition"""
        try:
            result = await self.mcp_client.call_tool(
                "speech_to_text_start_listening"
            )
            
            if result.get("success"):
                self.is_listening = True
                console.print("🎤 Voice recognition started")
            else:
                console.print(f"❌ Failed to start listening: {result.get('error')}", style="red")
                
        except Exception as e:
            console.print(f"❌ Speech recognition error: {e}", style="red")
    
    async def _stop_listening(self):
        """Stop speech recognition"""
        try:
            await self.mcp_client.call_tool(
                "speech_to_text_stop_listening"
            )
            self.is_listening = False
            console.print("🔇 Voice recognition stopped")
            
        except Exception as e:
            console.print(f"⚠️  Stop listening error: {e}", style="yellow")
    
    async def _process_pending_commands(self):
        """Process any pending voice commands"""
        # In a real implementation, this would check for speech recognition results
        # For now, this is a placeholder for the speech processing pipeline
        pass
    
    async def process_voice_command(self, voice_text: str) -> Dict[str, Any]:
        """Process a voice command through the full pipeline"""
        start_time = time.time()
        
        try:
            # Get current screen data
            current_screen = None
            if self.current_screen_id:
                screen_obj = self.data_manager.get_screen(self.current_screen_id)
                if screen_obj:
                    current_screen = screen_obj.to_dict()
            
            if not current_screen:
                return {
                    "success": False,
                    "error": "No current screen detected",
                    "voice_text": voice_text
                }
            
            # Check for global commands first
            global_command = self.data_manager.find_global_command(voice_text)
            if global_command:
                return await self._execute_global_command(global_command, voice_text)
            
            # Process command with Ollama agent
            command_result = await self.mcp_client.call_tool(
                "ollama_agent_process_voice_command", {
                    "voice_text": voice_text,
                    "current_screen": current_screen,
                    "context": {
                        "previous_screen": None,  # Could track history
                        "last_action": None,
                        "session_history": []
                    }
                }
            )
            
            if not command_result.get("success"):
                self.metrics["failed_actions"] += 1
                return command_result
            
            action_data = command_result["data"]
            
            # Execute the action
            execution_result = await self._execute_action(action_data)
            
            # Update metrics
            processing_time = time.time() - start_time
            self.metrics["commands_processed"] += 1
            
            if execution_result.get("success"):
                self.metrics["successful_clicks"] += 1
            else:
                self.metrics["failed_actions"] += 1
            
            # Update average response time
            self.metrics["average_response_time"] = (
                (self.metrics["average_response_time"] * (self.metrics["commands_processed"] - 1) + processing_time) 
                / self.metrics["commands_processed"]
            )
            
            return execution_result
            
        except Exception as e:
            self.metrics["failed_actions"] += 1
            return {
                "success": False,
                "error": f"Command processing failed: {e}",
                "voice_text": voice_text
            }
    
    async def _execute_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the processed action"""
        action_type = action_data.get("action")
        
        if action_type == "click":
            return await self._execute_click_action(action_data)
        elif action_type == "help":
            return await self._execute_help_action(action_data)
        elif action_type == "navigate":
            return await self._execute_navigate_action(action_data)
        elif action_type == "clarify":
            return {
                "success": True,
                "action": "clarify",
                "message": action_data.get("message", "Please clarify your command")
            }
        else:
            return {
                "success": False,
                "error": f"Unknown action type: {action_type}"
            }
    
    async def _execute_click_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a mouse click action"""
        try:
            element_id = action_data.get("element_id")
            coordinates = action_data.get("coordinates", {})
            
            if not coordinates or "x" not in coordinates or "y" not in coordinates:
                return {
                    "success": False,
                    "error": "Missing coordinates for click action"
                }
            
            # Execute mouse click
            click_result = await self.mcp_client.call_tool(
                "mouse_control_click", {
                    "x": coordinates["x"],
                    "y": coordinates["y"],
                    "element_id": element_id
                }
            )
            
            if click_result.get("success"):
                console.print(f"🖱️  Clicked {element_id} at ({coordinates['x']}, {coordinates['y']})")
                
                # Wait briefly for screen transition
                await asyncio.sleep(0.5)
                
                # Update screen state
                await self._update_screen_state()
                
                return {
                    "success": True,
                    "action": "click",
                    "element_id": element_id,
                    "coordinates": coordinates,
                    "message": action_data.get("message", f"Clicked {element_id}")
                }
            else:
                return {
                    "success": False,
                    "error": f"Mouse click failed: {click_result.get('error')}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Click execution failed: {e}"
            }
    
    async def _execute_help_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute help action"""
        try:
            # Generate contextual help
            current_screen = None
            if self.current_screen_id:
                screen_obj = self.data_manager.get_screen(self.current_screen_id)
                if screen_obj:
                    current_screen = screen_obj.to_dict()
            
            if current_screen:
                help_result = await self.mcp_client.call_tool(
                    "ollama_agent_generate_help_response", {
                        "current_screen": current_screen
                    }
                )
                
                if help_result.get("success"):
                    help_text = help_result["data"].get("help_text", "No help available")
                    console.print(Panel(help_text, title="Available Commands"))
                    
                    return {
                        "success": True,
                        "action": "help",
                        "help_text": help_text
                    }
            
            return {
                "success": True,
                "action": "help",
                "message": "Help system unavailable"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Help execution failed: {e}"
            }
    
    async def _execute_navigate_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute navigation action"""
        # Similar to click but with screen transition logic
        return await self._execute_click_action(action_data)
    
    async def _execute_global_command(self, global_command, voice_text: str) -> Dict[str, Any]:
        """Execute a global command"""
        action = global_command.action
        
        if action == "show_help":
            return await self._execute_help_action({"action": "help"})
        elif action == "navigate_home":
            # Find home screen and navigate there
            home_screen = self.data_manager.get_screen("home")
            if home_screen:
                # This would involve finding a path to home screen
                return {
                    "success": True,
                    "action": "navigate",
                    "message": "Navigating to home screen"
                }
        
        return {
            "success": False,
            "error": f"Unknown global command: {action}"
        }
    
    async def _load_mcp_config(self):
        """Load MCP configuration"""
        with open(self.config_path, 'r') as f:
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
    
    def _create_status_display(self) -> Panel:
        """Create live status display"""
        table = Table.grid(padding=1)
        table.add_column(style="cyan", no_wrap=True)
        table.add_column(style="white")
        
        # System status
        table.add_row("🎤 Listening:", "✅ Active" if self.is_listening else "❌ Inactive")
        table.add_row("📱 Current Screen:", self.current_screen_id or "Unknown")
        table.add_row("⏱️  Uptime:", f"{int(time.time() - self.metrics['session_start_time'])}s")
        
        # Metrics
        table.add_row("", "")  # Spacer
        table.add_row("📊 Commands:", str(self.metrics["commands_processed"]))
        table.add_row("✅ Successful:", str(self.metrics["successful_clicks"]))
        table.add_row("❌ Failed:", str(self.metrics["failed_actions"]))
        table.add_row("⚡ Avg Response:", f"{self.metrics['average_response_time']:.2f}s")
        
        return Panel(table, title="🎮 Kiosk Control Status", border_style="green")
    
    def _display_final_metrics(self):
        """Display final session metrics"""
        session_duration = time.time() - self.metrics["session_start_time"]
        
        metrics_table = Table(title="Session Summary")
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", style="white")
        
        metrics_table.add_row("Session Duration", f"{int(session_duration)}s")
        metrics_table.add_row("Commands Processed", str(self.metrics["commands_processed"]))
        metrics_table.add_row("Successful Actions", str(self.metrics["successful_clicks"]))
        metrics_table.add_row("Failed Actions", str(self.metrics["failed_actions"]))
        metrics_table.add_row("Average Response Time", f"{self.metrics['average_response_time']:.2f}s")
        
        if self.metrics["commands_processed"] > 0:
            success_rate = (self.metrics["successful_clicks"] / self.metrics["commands_processed"]) * 100
            metrics_table.add_row("Success Rate", f"{success_rate:.1f}%")
        
        console.print(metrics_table)


@app.command()
def start(
    config: str = typer.Option("config/mcp_config.json", help="MCP configuration file"),
    data: str = typer.Option("config/kiosk_data.json", help="Kiosk data file")
):
    """Start the kiosk voice control system"""
    
    async def main():
        orchestrator = KioskOrchestrator(config)
        
        # Handle graceful shutdown
        def signal_handler():
            asyncio.create_task(orchestrator.stop())
        
        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, lambda s, f: signal_handler())
        
        try:
            await orchestrator.start()
        except KeyboardInterrupt:
            await orchestrator.stop()
    
    asyncio.run(main())


@app.command()
def test_command(
    command: str = typer.Argument(help="Voice command to test"),
    config: str = typer.Option("config/mcp_config.json", help="MCP configuration file")
):
    """Test a voice command without full system startup"""
    
    async def test():
        orchestrator = KioskOrchestrator(config)
        
        try:
            # Quick initialization
            await orchestrator._load_mcp_config()
            await orchestrator.data_manager.load_data()
            orchestrator.mcp_client = Client(orchestrator.mcp_config)
            await orchestrator.mcp_client.__aenter__()
            
            # Test command
            console.print(f"Testing command: '{command}'")
            result = await orchestrator.process_voice_command(command)
            
            if result.get("success"):
                console.print("✅ Command processed successfully", style="green")
                console.print(f"Action: {result.get('action')}")
                console.print(f"Message: {result.get('message')}")
            else:
                console.print("❌ Command failed", style="red")
                console.print(f"Error: {result.get('error')}")
            
        finally:
            if orchestrator.mcp_client:
                try:
                    await orchestrator.mcp_client.__aexit__(None, None, None)
                except Exception:
                    pass
    
    asyncio.run(test())


if __name__ == "__main__":
    app()