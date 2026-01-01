"""
Communication Domain - WebSocket Connection Models

Data models for WebSocket connections and client sessions.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from fastapi import WebSocket


@dataclass
class ClientSession:
    """Client session information and tracking"""
    client_id: str
    connected_at: datetime
    last_activity: datetime
    message_count: int = 0
    session_data: Dict[str, Any] = field(default_factory=dict)
    
    def update_activity(self):
        """Update last activity timestamp and increment message count"""
        self.last_activity = datetime.now()
        self.message_count += 1
    
    def get_session_duration(self) -> float:
        """Get session duration in seconds"""
        return (datetime.now() - self.connected_at).total_seconds()
    
    def get_idle_time(self) -> float:
        """Get idle time in seconds since last activity"""
        return (datetime.now() - self.last_activity).total_seconds()


@dataclass
class WebSocketConnection:
    """WebSocket connection wrapper with session management"""
    client_id: str
    websocket: WebSocket
    is_active: bool = True
    session: Optional[ClientSession] = None
    
    def __post_init__(self):
        """Initialize connection state"""
        if self.session is None:
            self.session = ClientSession(
                client_id=self.client_id,
                connected_at=datetime.now(),
                last_activity=datetime.now()
            )
    
    async def send_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Send message through WebSocket connection.
        
        Args:
            message_data: Message to send as JSON
            
        Returns:
            True if sent successfully, False if failed
        """
        if not self.is_active:
            return False
            
        try:
            import json
            await self.websocket.send_text(json.dumps(message_data))
            self.session.update_activity()
            return True
        except Exception:
            self.is_active = False
            return False
    
    def disconnect(self):
        """Mark connection as inactive"""
        self.is_active = False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for monitoring"""
        return {
            "client_id": self.client_id,
            "connected_at": self.session.connected_at.isoformat(),
            "last_activity": self.session.last_activity.isoformat(),
            "message_count": self.session.message_count,
            "session_duration": f"{self.session.get_session_duration():.1f}s",
            "idle_time": f"{self.session.get_idle_time():.1f}s",
            "is_active": self.is_active
        }


@dataclass
class MessageEnvelope:
    """Wrapper for incoming WebSocket messages"""
    client_id: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    raw_data: Optional[str] = None
    
    @classmethod
    def from_raw_data(cls, client_id: str, raw_data: str) -> 'MessageEnvelope':
        """Create message envelope from raw WebSocket data"""
        import json
        
        try:
            payload = json.loads(raw_data)
            message_type = payload.get("type", "unknown")
            
            return cls(
                client_id=client_id,
                message_type=message_type,
                payload=payload,
                raw_data=raw_data
            )
        except json.JSONDecodeError as e:
            # Return error envelope for invalid JSON
            return cls(
                client_id=client_id,
                message_type="error",
                payload={
                    "error": "json_decode_error", 
                    "details": str(e),
                    "raw_data": raw_data[:100]  # Limit raw data for logging
                },
                raw_data=raw_data
            )
    
    def is_valid(self) -> bool:
        """Check if message envelope is valid"""
        return (
            self.message_type != "error" and 
            self.message_type != "unknown" and
            isinstance(self.payload, dict)
        )
    
    def get_context(self) -> Dict[str, Any]:
        """Get message context for processing"""
        return self.payload.get("context", {})