"""
Advanced Watch Party Features - Production Ready
Playlist support, voting system, analytics, and enhanced functionality
Optimized for performance, reliability, and zero lag
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
import secrets
import logging
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

# Performance optimization: Cache frequently accessed data
_cache = {}


# ── Playlist Support ───────────────────────────────────────────────────────────

class Playlist:
    """Manage video playlists for watch parties - Optimized for performance"""
    
    __slots__ = ['playlist_id', 'name', 'creator_id', 'videos', 'current_index', 
                 'created_at', 'is_public', 'description', '_video_index']
    
    def __init__(self, playlist_id: str, name: str, creator_id: str):
        self.playlist_id = playlist_id
        self.name = name
        self.creator_id = creator_id
        self.videos: List[Dict] = []
        self.current_index = 0
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.is_public = False
        self.description = ""
        self._video_index = {}  # Fast lookup by video_id
    
    def add_video(self, video_url: str, title: str, duration: int = 0) -> bool:
        """Add video to playlist with validation"""
        if len(self.videos) >= 100:
            logger.warning(f"Playlist {self.playlist_id} at max capacity")
            return False
        
        if not video_url or not title:
            logger.error("Invalid video_url or title")
            return False
        
        video = {
            "video_id": secrets.token_urlsafe(8),
            "url": video_url,
            "title": title[:100],  # Limit title length
            "duration": max(0, duration),
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self.videos.append(video)
        self._video_index[video["video_id"]] = len(self.videos) - 1
        return True
    
    def remove_video(self, video_id: str) -> bool:
        """Remove video from playlist efficiently"""
        if video_id not in self._video_index:
            return False
        
        idx = self._video_index[video_id]
        self.videos.pop(idx)
        
        # Rebuild index
        self._video_index.clear()
        for i, v in enumerate(self.videos):
            self._video_index[v["video_id"]] = i
        
        # Adjust current index if needed
        if self.current_index >= len(self.videos) and self.current_index > 0:
            self.current_index -= 1
        
        return True
    
    def get_current_video(self) -> Optional[Dict]:
        """Get currently playing video"""
        if 0 <= self.current_index < len(self.videos):
            return self.videos[self.current_index].copy()
        return None
    
    def next_video(self) -> Optional[Dict]:
        """Move to next video"""
        if self.current_index < len(self.videos) - 1:
            self.current_index += 1
            return self.get_current_video()
        return None
    
    def previous_video(self) -> Optional[Dict]:
        """Move to previous video"""
        if self.current_index > 0:
            self.current_index -= 1
            return self.get_current_video()
        return None
    
    def reorder_videos(self, video_id: str, new_position: int) -> bool:
        """Reorder videos in playlist"""
        if video_id not in self._video_index or not (0 <= new_position < len(self.videos)):
            return False
        
        old_idx = self._video_index[video_id]
        video = self.videos.pop(old_idx)
        self.videos.insert(new_position, video)
        
        # Rebuild index
        self._video_index.clear()
        for i, v in enumerate(self.videos):
            self._video_index[v["video_id"]] = i
        
        return True
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "playlist_id": self.playlist_id,
            "name": self.name,
            "creator_id": self.creator_id,
            "video_count": len(self.videos),
            "current_index": self.current_index,
            "current_video": self.get_current_video(),
            "videos": [v.copy() for v in self.videos],
            "created_at": self.created_at,
            "is_public": self.is_public,
            "description": self.description,
        }


# ── Voting System ──────────────────────────────────────────────────────────────

class VotingSystem:
    """Manage voting for skip, pause, and other actions - Optimized"""
    
    __slots__ = ['room_id', 'skip_votes', 'pause_votes', 'skip_threshold', 
                 'pause_threshold', '_last_reset']
    
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.skip_votes: set = set()  # Use set for O(1) lookup
        self.pause_votes: set = set()
        self.skip_threshold = 0.5  # 50% of viewers
        self.pause_threshold = 0.75  # 75% of viewers
        self._last_reset = time.time()
    
    def add_skip_vote(self, user_id: str) -> bool:
        """Add skip vote from user"""
        self.skip_votes.add(user_id)
        return True
    
    def remove_skip_vote(self, user_id: str) -> bool:
        """Remove skip vote from user"""
        self.skip_votes.discard(user_id)
        return True
    
    def add_pause_vote(self, user_id: str) -> bool:
        """Add pause vote from user"""
        self.pause_votes.add(user_id)
        return True
    
    def remove_pause_vote(self, user_id: str) -> bool:
        """Remove pause vote from user"""
        self.pause_votes.discard(user_id)
        return True
    
    def check_skip_vote(self, total_viewers: int) -> bool:
        """Check if skip vote threshold reached"""
        if total_viewers == 0:
            return False
        
        votes_needed = max(1, int(total_viewers * self.skip_threshold))
        return len(self.skip_votes) >= votes_needed
    
    def check_pause_vote(self, total_viewers: int) -> bool:
        """Check if pause vote threshold reached"""
        if total_viewers == 0:
            return False
        
        votes_needed = max(1, int(total_viewers * self.pause_threshold))
        return len(self.pause_votes) >= votes_needed
    
    def reset_skip_votes(self):
        """Reset skip votes"""
        self.skip_votes.clear()
        self._last_reset = time.time()
    
    def reset_pause_votes(self):
        """Reset pause votes"""
        self.pause_votes.clear()
    
    def get_skip_progress(self, total_viewers: int) -> float:
        """Get skip vote progress (0-1)"""
        if total_viewers == 0:
            return 0.0
        return min(1.0, len(self.skip_votes) / total_viewers)
    
    def get_pause_progress(self, total_viewers: int) -> float:
        """Get pause vote progress (0-1)"""
        if total_viewers == 0:
            return 0.0
        return min(1.0, len(self.pause_votes) / total_viewers)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "skip_votes": len(self.skip_votes),
            "pause_votes": len(self.pause_votes),
            "skip_threshold": self.skip_threshold,
            "pause_threshold": self.pause_threshold,
        }


# ── Watch History ─────────────────────────────────────────────────────────────

class WatchHistory:
    """Track watch history for users - Optimized for performance"""
    
    __slots__ = ['user_id', 'history', 'max_history', '_title_cache']
    
    def __init__(self, user_id: str, max_history: int = 100):
        self.user_id = user_id
        self.history: List[Dict] = []
        self.max_history = max_history
        self._title_cache = {}  # Cache for quick lookups
    
    def add_watch(self, room_id: str, title: str, duration: int, watched_time: int) -> bool:
        """Add watch to history with validation"""
        if duration <= 0 or watched_time < 0:
            logger.warning(f"Invalid watch data: duration={duration}, watched_time={watched_time}")
            return False
        
        watch = {
            "room_id": room_id,
            "title": title[:100],  # Limit title
            "duration": duration,
            "watched_time": min(watched_time, duration),  # Cap at duration
            "watched_at": datetime.now(timezone.utc).isoformat(),
            "progress": min(100, (watched_time / duration * 100)) if duration > 0 else 0,
        }
        
        self.history.insert(0, watch)
        self._title_cache[room_id] = title
        
        # Keep only recent history
        if len(self.history) > self.max_history:
            self.history = self.history[:self.max_history]
        
        return True
    
    def get_watch_progress(self, room_id: str) -> Optional[int]:
        """Get last watched position for a room"""
        for watch in self.history:
            if watch["room_id"] == room_id:
                return watch["watched_time"]
        return None
    
    def get_recommendations(self, limit: int = 5) -> List[Dict]:
        """Get watch recommendations based on history"""
        if not self.history:
            return []
        
        # Group by title and calculate stats
        title_stats = {}
        for watch in self.history:
            title = watch["title"]
            if title not in title_stats:
                title_stats[title] = {"count": 0, "avg_progress": 0.0, "last_watched": watch["watched_at"]}
            title_stats[title]["count"] += 1
            title_stats[title]["avg_progress"] += watch["progress"]
        
        # Calculate averages
        for title in title_stats:
            title_stats[title]["avg_progress"] /= title_stats[title]["count"]
        
        # Sort by count and return top
        sorted_titles = sorted(
            title_stats.items(),
            key=lambda x: (x[1]["count"], x[1]["avg_progress"]),
            reverse=True
        )
        
        return [{"title": t[0], **t[1]} for t in sorted_titles[:limit]]
    
    def clear_history(self):
        """Clear watch history"""
        self.history.clear()
        self._title_cache.clear()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "watch_count": len(self.history),
            "history": self.history[:10],  # Return last 10
        }


# ── Recommendations Engine ─────────────────────────────────────────────────────

class RecommendationEngine:
    """Generate recommendations based on watch history and preferences"""
    
    def __init__(self):
        self.user_histories: Dict[str, WatchHistory] = {}
    
    def add_user_history(self, user_id: str, history: WatchHistory):
        """Add user watch history"""
        self.user_histories[user_id] = history
    
    def get_recommendations_for_user(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Get recommendations for user"""
        if user_id not in self.user_histories:
            return []
        
        history = self.user_histories[user_id]
        return history.get_recommendations(limit)
    
    def get_trending(self, limit: int = 10) -> List[Dict]:
        """Get trending videos across all users"""
        title_stats = {}
        
        for user_id, history in self.user_histories.items():
            for watch in history.history:
                title = watch["title"]
                if title not in title_stats:
                    title_stats[title] = {"count": 0, "avg_progress": 0}
                title_stats[title]["count"] += 1
                title_stats[title]["avg_progress"] += watch["progress"]
        
        # Calculate averages
        for title in title_stats:
            title_stats[title]["avg_progress"] /= title_stats[title]["count"]
        
        # Sort by count
        sorted_titles = sorted(
            title_stats.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        
        return [{"title": t[0], **t[1]} for t in sorted_titles[:limit]]


# ── Watch Party Analytics ──────────────────────────────────────────────────────

class WatchPartyAnalytics:
    """Track analytics for watch parties"""
    
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.start_time = datetime.now(timezone.utc)
        self.end_time = None
        self.total_viewers = 0
        self.peak_viewers = 0
        self.current_viewers = 0
        self.viewer_join_times: List[str] = []
        self.viewer_leave_times: List[str] = []
        self.chat_messages = 0
        self.reactions = 0
        self.skip_votes = 0
        self.pause_votes = 0
    
    def record_viewer_join(self):
        """Record viewer join"""
        self.total_viewers += 1
        self.current_viewers += 1
        self.peak_viewers = max(self.peak_viewers, self.current_viewers)
        self.viewer_join_times.append(datetime.now(timezone.utc).isoformat())
    
    def record_viewer_leave(self):
        """Record viewer leave"""
        self.current_viewers = max(0, self.current_viewers - 1)
        self.viewer_leave_times.append(datetime.now(timezone.utc).isoformat())
    
    def record_chat_message(self):
        """Record chat message"""
        self.chat_messages += 1
    
    def record_reaction(self):
        """Record emoji reaction"""
        self.reactions += 1
    
    def record_skip_vote(self):
        """Record skip vote"""
        self.skip_votes += 1
    
    def record_pause_vote(self):
        """Record pause vote"""
        self.pause_votes += 1
    
    def end_party(self):
        """End watch party and finalize analytics"""
        self.end_time = datetime.now(timezone.utc)
    
    def get_duration(self) -> int:
        """Get party duration in seconds"""
        end = self.end_time or datetime.now(timezone.utc)
        delta = end - self.start_time
        return int(delta.total_seconds())
    
    def get_avg_viewers(self) -> float:
        """Get average viewers"""
        if self.total_viewers == 0:
            return 0.0
        return self.current_viewers / self.total_viewers
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "room_id": self.room_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.get_duration(),
            "total_viewers": self.total_viewers,
            "peak_viewers": self.peak_viewers,
            "current_viewers": self.current_viewers,
            "avg_viewers": self.get_avg_viewers(),
            "chat_messages": self.chat_messages,
            "reactions": self.reactions,
            "skip_votes": self.skip_votes,
            "pause_votes": self.pause_votes,
        }


# ── Feature Flags ──────────────────────────────────────────────────────────────

class FeatureFlags:
    """Manage feature flags for watch party"""
    
    def __init__(self):
        self.flags = {
            "playlist_support": True,
            "voting_system": True,
            "watch_history": True,
            "recommendations": True,
            "analytics": True,
            "reactions": True,
            "chat": True,
            "external_urls": True,
            "file_upload": True,
            "looping": True,
            "shuffle": True,
            "autoplay": True,
        }
    
    def is_enabled(self, feature: str) -> bool:
        """Check if feature is enabled"""
        return self.flags.get(feature, False)
    
    def enable_feature(self, feature: str):
        """Enable feature"""
        self.flags[feature] = True
    
    def disable_feature(self, feature: str):
        """Disable feature"""
        self.flags[feature] = False
    
    def toggle_feature(self, feature: str):
        """Toggle feature"""
        self.flags[feature] = not self.flags.get(feature, False)
    
    def get_all_flags(self) -> Dict[str, bool]:
        """Get all feature flags"""
        return self.flags.copy()


# ── Export ─────────────────────────────────────────────────────────────────────

__all__ = [
    "Playlist",
    "VotingSystem",
    "WatchHistory",
    "RecommendationEngine",
    "WatchPartyAnalytics",
    "FeatureFlags",
]
