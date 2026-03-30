"""
Enhanced Watch Party System - Premium UI, Chat, Requests, Scheduling
Complete rewrite with modern features and role-based permissions
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import uuid
from enum import Enum

logger = logging.getLogger(__name__)

# Database file location
DB_DIR = Path("./data/watch_party")
DB_DIR.mkdir(parents=True, exist_ok=True)

ENHANCED_DB = DB_DIR / "enhanced.json"
CHAT_DB = DB_DIR / "chat.json"
REQUESTS_DB = DB_DIR / "requests.json"
SCHEDULES_DB = DB_DIR / "schedules.json"


class UserRole(Enum):
    """User roles in watch party"""
    OWNER = "owner"
    ADMIN = "admin"
    MODERATOR = "moderator"
    MEMBER = "member"
    GUEST = "guest"


class RequestType(Enum):
    """Types of requests users can make"""
    PLAY = "play"
    PAUSE = "pause"
    SKIP = "skip"
    REWIND = "rewind"
    FORWARD = "forward"


class RequestStatus(Enum):
    """Status of a request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class EnhancedWatchPartyDB:
    """Enhanced database with chat, requests, and scheduling"""
    
    @staticmethod
    def _ensure_files():
        """Ensure all database files exist"""
        for file in [ENHANCED_DB, CHAT_DB, REQUESTS_DB, SCHEDULES_DB]:
            if not file.exists():
                with open(file, 'w') as f:
                    json.dump({}, f)
    
    # ── Room Management ─────────────────────────────────────────────────────
    
    @staticmethod
    def create_enhanced_room(guild_id: str, movie_id: str, title: str, 
                            owner_id: str) -> Optional[str]:
        """Create enhanced watch room with all features"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            room_id = str(uuid.uuid4())
            
            with open(ENHANCED_DB, 'r') as f:
                rooms = json.load(f)
            
            rooms[room_id] = {
                "id": room_id,
                "guild_id": str(guild_id),
                "movie_id": movie_id,
                "title": title,
                "owner_id": str(owner_id),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "active",  # active, paused, ended
                "viewers": {str(owner_id): {"role": "owner", "joined_at": datetime.now(timezone.utc).isoformat()}},
                "current_time": 0,
                "is_playing": False,
                "scheduled_start": None,
                "scheduled_end": None,
                "settings": {
                    "allow_chat": True,
                    "allow_requests": True,
                    "require_approval": True,
                    "max_viewers": 100,
                    "chat_cooldown": 2  # seconds between messages
                }
            }
            
            with open(ENHANCED_DB, 'w') as f:
                json.dump(rooms, f, indent=2)
            
            logger.info(f"Created enhanced room {room_id}")
            return room_id
        except Exception as e:
            logger.error(f"Error creating enhanced room: {e}")
            return None
    
    @staticmethod
    def get_room(room_id: str) -> Optional[Dict[str, Any]]:
        """Get room details"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(ENHANCED_DB, 'r') as f:
                rooms = json.load(f)
                return rooms.get(room_id)
        except Exception as e:
            logger.error(f"Error getting room: {e}")
            return None
    
    @staticmethod
    def add_viewer(room_id: str, user_id: str, role: str = "member") -> bool:
        """Add viewer to room"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(ENHANCED_DB, 'r') as f:
                rooms = json.load(f)
            
            if room_id in rooms:
                rooms[room_id]["viewers"][str(user_id)] = {
                    "role": role,
                    "joined_at": datetime.now(timezone.utc).isoformat()
                }
                
                with open(ENHANCED_DB, 'w') as f:
                    json.dump(rooms, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Error adding viewer: {e}")
        return False
    
    @staticmethod
    def remove_viewer(room_id: str, user_id: str) -> bool:
        """Remove viewer from room"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(ENHANCED_DB, 'r') as f:
                rooms = json.load(f)
            
            if room_id in rooms and str(user_id) in rooms[room_id]["viewers"]:
                del rooms[room_id]["viewers"][str(user_id)]
                
                with open(ENHANCED_DB, 'w') as f:
                    json.dump(rooms, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Error removing viewer: {e}")
        return False
    
    @staticmethod
    def get_user_role(room_id: str, user_id: str) -> Optional[str]:
        """Get user's role in room"""
        room = EnhancedWatchPartyDB.get_room(room_id)
        if room and str(user_id) in room.get("viewers", {}):
            return room["viewers"][str(user_id)].get("role")
        return None
    
    # ── Chat Management ────────────────────────────────────────────────────
    
    @staticmethod
    def send_message(room_id: str, user_id: str, username: str, 
                    message: str, user_role: str = "member") -> Optional[str]:
        """Send chat message"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            message_id = str(uuid.uuid4())
            
            with open(CHAT_DB, 'r') as f:
                chats = json.load(f)
            
            if room_id not in chats:
                chats[room_id] = []
            
            chats[room_id].append({
                "id": message_id,
                "user_id": str(user_id),
                "username": username,
                "message": message,
                "role": user_role,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reactions": {}
            })
            
            # Keep only last 500 messages per room
            if len(chats[room_id]) > 500:
                chats[room_id] = chats[room_id][-500:]
            
            with open(CHAT_DB, 'w') as f:
                json.dump(chats, f, indent=2)
            
            return message_id
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    @staticmethod
    def get_chat_history(room_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat history"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(CHAT_DB, 'r') as f:
                chats = json.load(f)
            
            messages = chats.get(room_id, [])
            return messages[-limit:]
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []
    
    @staticmethod
    def add_reaction(room_id: str, message_id: str, user_id: str, emoji: str) -> bool:
        """Add reaction to message"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(CHAT_DB, 'r') as f:
                chats = json.load(f)
            
            if room_id in chats:
                for msg in chats[room_id]:
                    if msg["id"] == message_id:
                        if emoji not in msg["reactions"]:
                            msg["reactions"][emoji] = []
                        if str(user_id) not in msg["reactions"][emoji]:
                            msg["reactions"][emoji].append(str(user_id))
                        
                        with open(CHAT_DB, 'w') as f:
                            json.dump(chats, f, indent=2)
                        
                        return True
        except Exception as e:
            logger.error(f"Error adding reaction: {e}")
        return False
    
    # ── Request Management ─────────────────────────────────────────────────
    
    @staticmethod
    def create_request(room_id: str, user_id: str, username: str, 
                      request_type: str, details: Dict = None) -> Optional[str]:
        """Create a play/pause/skip request"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            request_id = str(uuid.uuid4())
            
            with open(REQUESTS_DB, 'r') as f:
                requests = json.load(f)
            
            if room_id not in requests:
                requests[room_id] = []
            
            requests[room_id].append({
                "id": request_id,
                "user_id": str(user_id),
                "username": username,
                "type": request_type,
                "details": details or {},
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "approved_by": None,
                "approved_at": None
            })
            
            with open(REQUESTS_DB, 'w') as f:
                json.dump(requests, f, indent=2)
            
            logger.info(f"Created request {request_id}: {request_type}")
            return request_id
        except Exception as e:
            logger.error(f"Error creating request: {e}")
            return None
    
    @staticmethod
    def get_pending_requests(room_id: str) -> List[Dict[str, Any]]:
        """Get all pending requests"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(REQUESTS_DB, 'r') as f:
                requests = json.load(f)
            
            room_requests = requests.get(room_id, [])
            return [r for r in room_requests if r["status"] == "pending"]
        except Exception as e:
            logger.error(f"Error getting pending requests: {e}")
            return []
    
    @staticmethod
    def approve_request(room_id: str, request_id: str, approved_by: str) -> bool:
        """Approve a request"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(REQUESTS_DB, 'r') as f:
                requests = json.load(f)
            
            if room_id in requests:
                for req in requests[room_id]:
                    if req["id"] == request_id:
                        req["status"] = "approved"
                        req["approved_by"] = str(approved_by)
                        req["approved_at"] = datetime.now(timezone.utc).isoformat()
                        
                        with open(REQUESTS_DB, 'w') as f:
                            json.dump(requests, f, indent=2)
                        
                        return True
        except Exception as e:
            logger.error(f"Error approving request: {e}")
        return False
    
    @staticmethod
    def reject_request(room_id: str, request_id: str) -> bool:
        """Reject a request"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(REQUESTS_DB, 'r') as f:
                requests = json.load(f)
            
            if room_id in requests:
                for req in requests[room_id]:
                    if req["id"] == request_id:
                        req["status"] = "rejected"
                        
                        with open(REQUESTS_DB, 'w') as f:
                            json.dump(requests, f, indent=2)
                        
                        return True
        except Exception as e:
            logger.error(f"Error rejecting request: {e}")
        return False
    
    # ── Scheduling ─────────────────────────────────────────────────────────
    
    @staticmethod
    def schedule_movie(room_id: str, start_time: str, end_time: str = None) -> bool:
        """Schedule movie start time"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(ENHANCED_DB, 'r') as f:
                rooms = json.load(f)
            
            if room_id in rooms:
                rooms[room_id]["scheduled_start"] = start_time
                rooms[room_id]["scheduled_end"] = end_time
                
                with open(ENHANCED_DB, 'w') as f:
                    json.dump(rooms, f, indent=2)
                
                logger.info(f"Scheduled room {room_id} to start at {start_time}")
                return True
        except Exception as e:
            logger.error(f"Error scheduling movie: {e}")
            return False
    
    @staticmethod
    def get_scheduled_movies(guild_id: str) -> List[Dict[str, Any]]:
        """Get all scheduled movies for guild"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(ENHANCED_DB, 'r') as f:
                rooms = json.load(f)
            
            scheduled = [
                r for r in rooms.values()
                if r.get("guild_id") == str(guild_id) and r.get("scheduled_start")
            ]
            
            # Sort by scheduled start time
            scheduled.sort(key=lambda x: x.get("scheduled_start", ""))
            
            return scheduled
        except Exception as e:
            logger.error(f"Error getting scheduled movies: {e}")
            return []
    
    # ── Settings Management ────────────────────────────────────────────────
    
    @staticmethod
    def update_room_settings(room_id: str, settings: Dict[str, Any]) -> bool:
        """Update room settings"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(ENHANCED_DB, 'r') as f:
                rooms = json.load(f)
            
            if room_id in rooms:
                rooms[room_id]["settings"].update(settings)
                
                with open(ENHANCED_DB, 'w') as f:
                    json.dump(rooms, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return False
    
    @staticmethod
    def update_playback(room_id: str, current_time: int, is_playing: bool) -> bool:
        """Update playback state"""
        try:
            EnhancedWatchPartyDB._ensure_files()
            
            with open(ENHANCED_DB, 'r') as f:
                rooms = json.load(f)
            
            if room_id in rooms:
                rooms[room_id]["current_time"] = current_time
                rooms[room_id]["is_playing"] = is_playing
                
                with open(ENHANCED_DB, 'w') as f:
                    json.dump(rooms, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Error updating playback: {e}")
            return False
    
    # ── Statistics ─────────────────────────────────────────────────────────
    
    @staticmethod
    def get_room_stats(room_id: str) -> Dict[str, Any]:
        """Get room statistics"""
        try:
            room = EnhancedWatchPartyDB.get_room(room_id)
            if not room:
                return {}
            
            chat_history = EnhancedWatchPartyDB.get_chat_history(room_id, limit=1000)
            pending_requests = EnhancedWatchPartyDB.get_pending_requests(room_id)
            
            return {
                "room_id": room_id,
                "viewers_count": len(room.get("viewers", {})),
                "messages_count": len(chat_history),
                "pending_requests": len(pending_requests),
                "current_time": room.get("current_time"),
                "is_playing": room.get("is_playing"),
                "created_at": room.get("created_at"),
                "status": room.get("status")
            }
        except Exception as e:
            logger.error(f"Error getting room stats: {e}")
            return {}
