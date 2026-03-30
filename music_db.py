"""
Music Database - Persistent storage for queues, settings, and history
Ensures music state persists across bot restarts
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set

logger = logging.getLogger(__name__)

# Database file location
DB_DIR = Path("./data/music")
DB_DIR.mkdir(parents=True, exist_ok=True)

QUEUES_FILE = DB_DIR / "queues.json"
SETTINGS_FILE = DB_DIR / "settings.json"
HISTORY_FILE = DB_DIR / "history.json"


class MusicDatabase:
    """Persistent database for music player state"""
    
    @staticmethod
    def _ensure_files():
        """Ensure database files exist"""
        for file in [QUEUES_FILE, SETTINGS_FILE, HISTORY_FILE]:
            if not file.exists():
                with open(file, 'w') as f:
                    json.dump({}, f)
    
    # ── Queue Management ────────────────────────────────────────────────────────
    
    @staticmethod
    def save_queue(guild_id: str, queue_data: List[Dict[str, Any]]) -> bool:
        """Save guild queue to database"""
        try:
            MusicDatabase._ensure_files()
            
            with open(QUEUES_FILE, 'r') as f:
                queues = json.load(f)
            
            queues[str(guild_id)] = {
                "songs": queue_data,
                "count": len(queue_data),
                "saved_at": datetime.now(timezone.utc).isoformat()
            }
            
            with open(QUEUES_FILE, 'w') as f:
                json.dump(queues, f, indent=2)
            
            logger.info(f"Saved queue for guild {guild_id} ({len(queue_data)} songs)")
            return True
        except Exception as e:
            logger.error(f"Error saving queue: {e}")
            return False
    
    @staticmethod
    def load_queue(guild_id: str) -> List[Dict[str, Any]]:
        """Load guild queue from database"""
        try:
            MusicDatabase._ensure_files()
            
            with open(QUEUES_FILE, 'r') as f:
                queues = json.load(f)
                queue_data = queues.get(str(guild_id), {}).get("songs", [])
                logger.info(f"Loaded queue for guild {guild_id} ({len(queue_data)} songs)")
                return queue_data
        except Exception as e:
            logger.error(f"Error loading queue: {e}")
        return []
    
    @staticmethod
    def clear_queue(guild_id: str) -> bool:
        """Clear saved queue for a guild"""
        try:
            MusicDatabase._ensure_files()
            
            with open(QUEUES_FILE, 'r') as f:
                queues = json.load(f)
            
            if str(guild_id) in queues:
                del queues[str(guild_id)]
                
                with open(QUEUES_FILE, 'w') as f:
                    json.dump(queues, f, indent=2)
                
                logger.info(f"Cleared queue for guild {guild_id}")
                return True
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
        return False
    
    # ── Settings Management ─────────────────────────────────────────────────────
    
    @staticmethod
    def save_settings(guild_id: str, settings: Dict[str, Any]) -> bool:
        """Save music settings for a guild"""
        try:
            MusicDatabase._ensure_files()
            
            with open(SETTINGS_FILE, 'r') as f:
                all_settings = json.load(f)
            
            all_settings[str(guild_id)] = {
                **settings,
                "saved_at": datetime.now(timezone.utc).isoformat()
            }
            
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(all_settings, f, indent=2)
            
            logger.info(f"Saved settings for guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    @staticmethod
    def load_settings(guild_id: str) -> Dict[str, Any]:
        """Load music settings for a guild"""
        try:
            MusicDatabase._ensure_files()
            
            with open(SETTINGS_FILE, 'r') as f:
                all_settings = json.load(f)
                settings = all_settings.get(str(guild_id), {})
                
                if settings:
                    logger.info(f"Loaded settings for guild {guild_id}")
                
                return settings
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
        return {}
    
    @staticmethod
    def get_setting(guild_id: str, key: str, default: Any = None) -> Any:
        """Get a specific setting"""
        settings = MusicDatabase.load_settings(guild_id)
        return settings.get(key, default)
    
    @staticmethod
    def set_setting(guild_id: str, key: str, value: Any) -> bool:
        """Set a specific setting"""
        settings = MusicDatabase.load_settings(guild_id)
        settings[key] = value
        return MusicDatabase.save_settings(guild_id, settings)
    
    # ── History & Played Songs ──────────────────────────────────────────────────
    
    @staticmethod
    def save_played_songs(guild_id: str, played_songs: Set[str]) -> bool:
        """Save played songs for autoplay tracking"""
        try:
            MusicDatabase._ensure_files()
            
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            
            history[str(guild_id)] = {
                "played_songs": list(played_songs),
                "count": len(played_songs),
                "saved_at": datetime.now(timezone.utc).isoformat()
            }
            
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)
            
            logger.info(f"Saved {len(played_songs)} played songs for guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving played songs: {e}")
            return False
    
    @staticmethod
    def load_played_songs(guild_id: str) -> Set[str]:
        """Load played songs for autoplay tracking"""
        try:
            MusicDatabase._ensure_files()
            
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
                songs = history.get(str(guild_id), {}).get("played_songs", [])
                
                if songs:
                    logger.info(f"Loaded {len(songs)} played songs for guild {guild_id}")
                
                return set(songs)
        except Exception as e:
            logger.error(f"Error loading played songs: {e}")
        return set()
    
    @staticmethod
    def add_played_song(guild_id: str, song_title: str) -> bool:
        """Add a song to played history"""
        try:
            played_songs = MusicDatabase.load_played_songs(guild_id)
            played_songs.add(song_title.lower())
            
            # Limit to 1000 songs to prevent unbounded growth
            if len(played_songs) > 1000:
                # Keep only the most recent 500
                played_songs = set(list(played_songs)[-500:])
            
            return MusicDatabase.save_played_songs(guild_id, played_songs)
        except Exception as e:
            logger.error(f"Error adding played song: {e}")
            return False
    
    @staticmethod
    def clear_played_songs(guild_id: str) -> bool:
        """Clear played songs history"""
        try:
            MusicDatabase._ensure_files()
            
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            
            if str(guild_id) in history:
                del history[str(guild_id)]
                
                with open(HISTORY_FILE, 'w') as f:
                    json.dump(history, f, indent=2)
                
                logger.info(f"Cleared played songs for guild {guild_id}")
                return True
        except Exception as e:
            logger.error(f"Error clearing played songs: {e}")
        return False
    
    # ── Dashboard Management ────────────────────────────────────────────────────
    
    @staticmethod
    def save_dashboard_info(guild_id: str, channel_id: int, message_id: int) -> bool:
        """Save dashboard channel and message IDs"""
        return MusicDatabase.set_setting(
            guild_id,
            "dashboard",
            {
                "channel_id": channel_id,
                "message_id": message_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        )
    
    @staticmethod
    def get_dashboard_info(guild_id: str) -> Optional[Dict[str, Any]]:
        """Get dashboard channel and message IDs"""
        return MusicDatabase.get_setting(guild_id, "dashboard")
    
    # ── Export/Import ──────────────────────────────────────────────────────────
    
    @staticmethod
    def export_all_data(guild_id: str) -> Dict[str, Any]:
        """Export all music data for a guild"""
        return {
            "queue": MusicDatabase.load_queue(guild_id),
            "settings": MusicDatabase.load_settings(guild_id),
            "played_songs": list(MusicDatabase.load_played_songs(guild_id)),
            "exported_at": datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def import_data(guild_id: str, data: Dict[str, Any]) -> bool:
        """Import music data for a guild"""
        try:
            if "queue" in data:
                MusicDatabase.save_queue(guild_id, data["queue"])
            
            if "settings" in data:
                MusicDatabase.save_settings(guild_id, data["settings"])
            
            if "played_songs" in data:
                MusicDatabase.save_played_songs(guild_id, set(data["played_songs"]))
            
            logger.info(f"Imported music data for guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"Error importing data: {e}")
            return False
    
    # ── Cleanup ────────────────────────────────────────────────────────────────
    
    @staticmethod
    def cleanup_old_data(days: int = 30) -> int:
        """Remove data older than specified days"""
        try:
            cutoff_date = datetime.now(timezone.utc).timestamp() - (days * 86400)
            removed_count = 0
            
            for file in [QUEUES_FILE, SETTINGS_FILE, HISTORY_FILE]:
                if not file.exists():
                    continue
                
                with open(file, 'r') as f:
                    data = json.load(f)
                
                to_remove = []
                for guild_id, guild_data in data.items():
                    saved_at = guild_data.get("saved_at")
                    if saved_at:
                        try:
                            saved_timestamp = datetime.fromisoformat(saved_at).timestamp()
                            if saved_timestamp < cutoff_date:
                                to_remove.append(guild_id)
                        except:
                            pass
                
                for guild_id in to_remove:
                    del data[guild_id]
                    removed_count += 1
                
                with open(file, 'w') as f:
                    json.dump(data, f, indent=2)
            
            logger.info(f"Cleaned up {removed_count} old entries")
            return removed_count
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            return 0
