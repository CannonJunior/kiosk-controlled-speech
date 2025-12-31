"""
Communication Domain - Session Management Service

Manages user sessions, authentication state, and session-specific data.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """Extended user session with application state"""
    client_id: str
    session_id: str
    created_at: datetime
    last_activity: datetime
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    session_context: Dict[str, Any] = field(default_factory=dict)
    processing_history: List[Dict[str, Any]] = field(default_factory=list)
    is_authenticated: bool = False
    user_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
    
    def get_session_age(self) -> timedelta:
        """Get total session age"""
        return datetime.now() - self.created_at
    
    def get_idle_time(self) -> timedelta:
        """Get time since last activity"""
        return datetime.now() - self.last_activity
    
    def add_processing_record(self, record: Dict[str, Any]):
        """Add processing record to history"""
        record["timestamp"] = datetime.now().isoformat()
        self.processing_history.append(record)
        
        # Keep only last 100 records per session
        if len(self.processing_history) > 100:
            self.processing_history = self.processing_history[-100:]
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get session summary for monitoring"""
        return {
            "client_id": self.client_id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "session_age_seconds": self.get_session_age().total_seconds(),
            "idle_time_seconds": self.get_idle_time().total_seconds(),
            "processing_history_count": len(self.processing_history),
            "is_authenticated": self.is_authenticated,
            "has_preferences": bool(self.user_preferences),
            "context_keys": list(self.session_context.keys())
        }


class SessionService:
    """
    Service for managing user sessions and session state.
    
    Responsibilities:
    - Create and manage user sessions
    - Track session state and preferences
    - Maintain processing history per session
    - Handle session expiration and cleanup
    """
    
    def __init__(self):
        self.sessions: Dict[str, UserSession] = {}
        self.session_timeout_minutes = 30  # Default session timeout
        self.max_sessions = 1000  # Maximum concurrent sessions
        
        # Session statistics
        self.session_stats = {
            "total_sessions_created": 0,
            "total_sessions_expired": 0,
            "total_sessions_cleaned": 0,
            "start_time": datetime.now()
        }
    
    def create_session(self, client_id: str, initial_context: Optional[Dict[str, Any]] = None) -> UserSession:
        """
        Create new user session.
        
        Args:
            client_id: Unique client identifier
            initial_context: Optional initial session context
            
        Returns:
            Created user session
        """
        # Generate session ID (could use UUID4 for production)
        session_id = f"session_{client_id}_{int(datetime.now().timestamp())}"
        
        # Create session
        session = UserSession(
            client_id=client_id,
            session_id=session_id,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            session_context=initial_context or {}
        )
        
        # Store session
        self.sessions[client_id] = session
        self.session_stats["total_sessions_created"] += 1
        
        # Check session limits
        if len(self.sessions) > self.max_sessions:
            self._cleanup_oldest_sessions(self.max_sessions // 10)  # Remove 10% of oldest
        
        logger.info(f"Created new session for client {client_id}: {session_id}")
        return session
    
    def get_session(self, client_id: str) -> Optional[UserSession]:
        """Get session by client ID"""
        return self.sessions.get(client_id)
    
    def update_session_activity(self, client_id: str, activity_data: Optional[Dict[str, Any]] = None):
        """
        Update session activity timestamp and optionally add activity data.
        
        Args:
            client_id: Client to update
            activity_data: Optional activity data to record
        """
        if client_id in self.sessions:
            session = self.sessions[client_id]
            session.update_activity()
            
            if activity_data:
                session.add_processing_record({
                    "type": "activity",
                    "data": activity_data
                })
    
    def update_session_preferences(self, client_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Update user preferences for session.
        
        Args:
            client_id: Client to update
            preferences: User preferences to merge
            
        Returns:
            True if updated successfully
        """
        if client_id not in self.sessions:
            return False
        
        session = self.sessions[client_id]
        session.user_preferences.update(preferences)
        session.update_activity()
        
        logger.info(f"Updated preferences for session {client_id}")
        return True
    
    def update_session_context(self, client_id: str, context: Dict[str, Any]) -> bool:
        """
        Update session context data.
        
        Args:
            client_id: Client to update
            context: Context data to merge
            
        Returns:
            True if updated successfully
        """
        if client_id not in self.sessions:
            return False
        
        session = self.sessions[client_id]
        session.session_context.update(context)
        session.update_activity()
        
        return True
    
    def record_processing_activity(self, client_id: str, activity_type: str, details: Dict[str, Any]):
        """
        Record processing activity for session.
        
        Args:
            client_id: Client performing activity
            activity_type: Type of processing activity
            details: Activity details
        """
        if client_id in self.sessions:
            session = self.sessions[client_id]
            session.add_processing_record({
                "type": activity_type,
                "details": details
            })
            session.update_activity()
    
    def remove_session(self, client_id: str) -> bool:
        """
        Remove session by client ID.
        
        Args:
            client_id: Client session to remove
            
        Returns:
            True if session was removed
        """
        if client_id in self.sessions:
            del self.sessions[client_id]
            logger.info(f"Removed session for client {client_id}")
            return True
        return False
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up sessions that have exceeded the timeout period.
        
        Returns:
            Number of sessions cleaned up
        """
        timeout_threshold = datetime.now() - timedelta(minutes=self.session_timeout_minutes)
        expired_clients = []
        
        for client_id, session in list(self.sessions.items()):
            if session.last_activity < timeout_threshold:
                expired_clients.append(client_id)
        
        cleaned_count = 0
        for client_id in expired_clients:
            if self.remove_session(client_id):
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.session_stats["total_sessions_expired"] += cleaned_count
            logger.info(f"Cleaned up {cleaned_count} expired sessions")
        
        return cleaned_count
    
    def _cleanup_oldest_sessions(self, count: int):
        """Clean up oldest sessions when session limit reached"""
        if not self.sessions:
            return
        
        # Sort by creation time and remove oldest
        sorted_sessions = sorted(
            self.sessions.items(),
            key=lambda x: x[1].created_at
        )
        
        for i in range(min(count, len(sorted_sessions))):
            client_id, _ = sorted_sessions[i]
            self.remove_session(client_id)
            self.session_stats["total_sessions_cleaned"] += 1
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """Get session management statistics"""
        uptime = (datetime.now() - self.session_stats["start_time"]).total_seconds()
        
        # Calculate session age distribution
        if self.sessions:
            session_ages = [session.get_session_age().total_seconds() for session in self.sessions.values()]
            avg_session_age = sum(session_ages) / len(session_ages)
            idle_times = [session.get_idle_time().total_seconds() for session in self.sessions.values()]
            avg_idle_time = sum(idle_times) / len(idle_times)
        else:
            avg_session_age = avg_idle_time = 0
        
        return {
            "current_sessions": len(self.sessions),
            "max_sessions": self.max_sessions,
            "session_timeout_minutes": self.session_timeout_minutes,
            "total_sessions_created": self.session_stats["total_sessions_created"],
            "total_sessions_expired": self.session_stats["total_sessions_expired"],
            "total_sessions_cleaned": self.session_stats["total_sessions_cleaned"],
            "uptime_seconds": uptime,
            "average_session_age_seconds": avg_session_age,
            "average_idle_time_seconds": avg_idle_time,
            "active_client_ids": list(self.sessions.keys()),
            "session_utilization": len(self.sessions) / self.max_sessions * 100
        }
    
    def get_all_session_summaries(self) -> List[Dict[str, Any]]:
        """Get summary information for all active sessions"""
        return [session.get_session_summary() for session in self.sessions.values()]