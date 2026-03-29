"""
Restore previous XP levels from backup
This script restores user levels to their previous values before the leveling update
"""

import json
from pathlib import Path
from leveling_db import LevelingDB

# Previous level data (manually enter or load from backup)
# Format: {guild_id: {user_id: level}}
PREVIOUS_LEVELS = {
    # Example: 123456789: {111111111: 8, 222222222: 7, 333333333: 9}
    # Add your guild and user data here
}


def _xp_for_level(lvl: int) -> int:
    """Calculate XP needed for a specific level"""
    return 5 * (lvl ** 2) + 50 * lvl + 100


def _total_xp_for_level(lvl: int) -> int:
    """Calculate total XP needed to reach a level"""
    total = 0
    for i in range(lvl):
        total += _xp_for_level(i)
    return total


def restore_levels(guild_id: int, user_levels: dict):
    """Restore user levels for a guild"""
    print(f"\n📊 Restoring levels for guild {guild_id}...")
    
    for user_id, level in user_levels.items():
        # Calculate XP needed for this level
        xp_needed = _total_xp_for_level(level)
        
        # Get current user data
        user_data = LevelingDB.get_user_data(guild_id, user_id)
        
        # Restore XP
        old_xp = user_data.get("xp", 0)
        user_data["xp"] = xp_needed
        user_data["level"] = level
        
        # Save
        LevelingDB.set_user_data(guild_id, user_id, user_data)
        
        print(f"  ✅ User {user_id}: Level {level} (XP: {old_xp} → {xp_needed})")
    
    print(f"✅ Restored {len(user_levels)} users for guild {guild_id}")


def restore_from_backup(backup_file: str):
    """Restore from a backup file"""
    try:
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        print(f"📂 Loading backup from {backup_file}...")
        
        for guild_id_str, guild_data in backup_data.items():
            guild_id = int(guild_id_str)
            users = guild_data.get("users", {})
            
            print(f"\n📊 Restoring {len(users)} users for guild {guild_id}...")
            
            for user_id_str, user_data in users.items():
                user_id = int(user_id_str)
                xp = user_data.get("xp", 0)
                
                # Restore to database
                current_data = LevelingDB.get_user_data(guild_id, user_id)
                current_data["xp"] = xp
                current_data.update(user_data)
                LevelingDB.set_user_data(guild_id, user_id, current_data)
                
                print(f"  ✅ User {user_id}: {xp} XP")
        
        print("\n✅ Backup restored successfully!")
        return True
    except Exception as e:
        print(f"❌ Error restoring backup: {e}")
        return False


def list_backups():
    """List available backups"""
    backups = LevelingDB.list_backups()
    if not backups:
        print("❌ No backups found")
        return
    
    print("\n📂 Available backups:")
    for i, backup in enumerate(backups, 1):
        print(f"  {i}. {backup.name}")


def main():
    print("🔄 WAN Bot - Level Restoration Tool")
    print("=" * 50)
    
    # Show available backups
    list_backups()
    
    # Restore from PREVIOUS_LEVELS dict
    if PREVIOUS_LEVELS:
        print("\n📊 Restoring from PREVIOUS_LEVELS...")
        for guild_id, user_levels in PREVIOUS_LEVELS.items():
            restore_levels(guild_id, user_levels)
    
    print("\n✅ Restoration complete!")
    print("\nTo restore from a backup file, use:")
    print("  restore_from_backup('data/leveling/backups/leveling_YYYYMMDD_HHMMSS.json')")


if __name__ == "__main__":
    main()
