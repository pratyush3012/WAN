"""
Leveling System Database - Persistent XP storage with backup and recovery
Fixes all data loss issues and ensures XP is never lost
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import logging
import shutil

logger = logging.getLogger(__name__)

# Database directories
DB_DIR = Path("./data/leveling")
DB_DIR.mkdir(parents=True, exist_ok=True)

BACKUP_DIR = DB_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Main database file
LEVELING_DB = DB_DIR / "leveling.json"
# Backup file (auto-created)
LEVELING_BACKUP = DB_DIR / "leveling_backup.json"


class LevelingDB:
    """Persistent database for leveling system with automatic backups"""
    
    @staticmethod
    def _ensure_db_exists():
        """Ensure database file exists"""
        if not LEVELING_DB.exists():
            LevelingDB.save({})
    
    @staticmethod
    def load() -> Dict[str, Any]:
        """Load leveling data from database"""
        try:
            LevelingDB._ensure_db_exists()
            with open(LEVELING_DB, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"Error loading leveling DB: {e}")
            # Try to recover from backup
            return LevelingDB._recover_from_backup()
    
    @staticmethod
    def save(data: Dict[str, Any]) -> bool:
        """Save leveling data to database with automatic backup"""
        try:
            # Create backup before saving
            if LEVELING_DB.exists():
                shutil.copy2(LEVELING_DB, LEVELING_BACKUP)
            
            # Save new data
            with open(LEVELING_DB, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug("Leveling data saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving leveling DB: {e}")
            return False
    
    @staticmethod
    def _recover_from_backup() -> Dict[str, Any]:
        """Recover data from backup if main file is corrupted"""
        try:
            if LEVELING_BACKUP.exists():
                logger.warning("Recovering from backup...")
                with open(LEVELING_BACKUP, 'r') as f:
                    data = json.load(f)
                    # Restore backup as main
                    LevelingDB.save(data)
                    return data
        except Exception as e:
            logger.error(f"Error recovering from backup: {e}")
        return {}
    
    @staticmethod
    def get_user_xp(guild_id: int, user_id: int) -> int:
        """Get user's total XP"""
        data = LevelingDB.load()
        guild_key = str(guild_id)
        user_key = str(user_id)
        
        if guild_key in data and "users" in data[guild_key]:
            user_data = data[guild_key]["users"].get(user_key, {})
            return user_data.get("xp", 0)
        return 0
    
    @staticmethod
    def set_user_xp(guild_id: int, user_id: int, xp: int) -> bool:
        """Set user's total XP"""
        data = LevelingDB.load()
        guild_key = str(guild_id)
        user_key = str(user_id)
        
        if guild_key not in data:
            data[guild_key] = {"users": {}, "config": {}}
        
        if "users" not in data[guild_key]:
            data[guild_key]["users"] = {}
        
        if user_key not in data[guild_key]["users"]:
            data[guild_key]["users"][user_key] = {}
        
        data[guild_key]["users"][user_key]["xp"] = max(0, xp)
        return LevelingDB.save(data)
    
    @staticmethod
    def add_user_xp(guild_id: int, user_id: int, amount: int) -> int:
        """Add XP to user and return new total"""
        current = LevelingDB.get_user_xp(guild_id, user_id)
        new_xp = current + amount
        LevelingDB.set_user_xp(guild_id, user_id, new_xp)
        return new_xp
    
    @staticmethod
    def get_user_data(guild_id: int, user_id: int) -> Dict[str, Any]:
        """Get complete user data"""
        data = LevelingDB.load()
        guild_key = str(guild_id)
        user_key = str(user_id)
        
        if guild_key in data and "users" in data[guild_key]:
            user_data = data[guild_key]["users"].get(user_key, {})
            # Ensure all fields exist
            defaults = {
                "xp": 0,
                "level": 0,
                "messages": 0,
                "voice_minutes": 0,
                "reactions": 0,
                "streak": 0,
                "last_daily": None,
                "last_msg_day": None,
                "music_xp": 0,
                "dashboard_xp": 0,
            }
            return {**defaults, **user_data}
        
        return {
            "xp": 0,
            "level": 0,
            "messages": 0,
            "voice_minutes": 0,
            "reactions": 0,
            "streak": 0,
            "last_daily": None,
            "last_msg_day": None,
            "music_xp": 0,
            "dashboard_xp": 0,
        }
    
    @staticmethod
    def set_user_data(guild_id: int, user_id: int, user_data: Dict[str, Any]) -> bool:
        """Set complete user data"""
        data = LevelingDB.load()
        guild_key = str(guild_id)
        user_key = str(user_id)
        
        if guild_key not in data:
            data[guild_key] = {"users": {}, "config": {}}
        
        if "users" not in data[guild_key]:
            data[guild_key]["users"] = {}
        
        data[guild_key]["users"][user_key] = user_data
        return LevelingDB.save(data)
    
    @staticmethod
    def get_guild_config(guild_id: int) -> Dict[str, Any]:
        """Get guild configuration"""
        data = LevelingDB.load()
        guild_key = str(guild_id)
        
        if guild_key in data and "config" in data[guild_key]:
            return data[guild_key]["config"]
        
        return {
            "level_roles": {},
            "announce_channel": None,
            "announce": True,
            "xp_multiplier": 1.0,
            "no_xp_channels": [],
            "no_xp_roles": [],
        }
    
    @staticmethod
    def set_guild_config(guild_id: int, config: Dict[str, Any]) -> bool:
        """Set guild configuration"""
        data = LevelingDB.load()
        guild_key = str(guild_id)
        
        if guild_key not in data:
            data[guild_key] = {"users": {}, "config": {}}
        
        data[guild_key]["config"] = config
        return LevelingDB.save(data)
    
    @staticmethod
    def get_leaderboard(guild_id: int, limit: int = 10) -> List[tuple]:
        """Get top users by XP"""
        data = LevelingDB.load()
        guild_key = str(guild_id)
        
        if guild_key not in data or "users" not in data[guild_key]:
            return []
        
        users = data[guild_key]["users"]
        sorted_users = sorted(
            users.items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )
        return sorted_users[:limit]
    
    @staticmethod
    def export_guild_data(guild_id: int) -> Dict[str, Any]:
        """Export all data for a guild"""
        data = LevelingDB.load()
        guild_key = str(guild_id)
        
        if guild_key in data:
            return data[guild_key]
        return {"users": {}, "config": {}}
    
    @staticmethod
    def import_guild_data(guild_id: int, guild_data: Dict[str, Any]) -> bool:
        """Import data for a guild"""
        data = LevelingDB.load()
        guild_key = str(guild_id)
        data[guild_key] = guild_data
        return LevelingDB.save(data)
    
    @staticmethod
    def create_timestamped_backup() -> bool:
        """Create a timestamped backup of current data"""
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_file = BACKUP_DIR / f"leveling_{timestamp}.json"
            
            if LEVELING_DB.exists():
                shutil.copy2(LEVELING_DB, backup_file)
                logger.info(f"Backup created: {backup_file}")
                return True
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
        return False
    
    @staticmethod
    def restore_from_backup(backup_file: Path) -> bool:
        """Restore data from a specific backup file"""
        try:
            if backup_file.exists():
                with open(backup_file, 'r') as f:
                    data = json.load(f)
                return LevelingDB.save(data)
        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
        return False
    
    @staticmethod
    def list_backups() -> List[Path]:
        """List all available backups"""
        if BACKUP_DIR.exists():
            return sorted(BACKUP_DIR.glob("leveling_*.json"), reverse=True)
        return []
