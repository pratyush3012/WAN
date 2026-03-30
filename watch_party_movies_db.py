"""
Watch Party Movies Database - Persistent storage for uploaded movies
Ensures movies persist across refreshes and restarts
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import logging
import uuid

logger = logging.getLogger(__name__)

# Database file location
DB_DIR = Path("./data/watch_party")
DB_DIR.mkdir(parents=True, exist_ok=True)

MOVIES_FILE = DB_DIR / "movies.json"
MOVIE_ROOMS_FILE = DB_DIR / "movie_rooms.json"


class MovieDatabase:
    """Persistent database for uploaded movies"""
    
    @staticmethod
    def _ensure_files():
        """Ensure database files exist"""
        if not MOVIES_FILE.exists():
            with open(MOVIES_FILE, 'w') as f:
                json.dump({}, f)
        if not MOVIE_ROOMS_FILE.exists():
            with open(MOVIE_ROOMS_FILE, 'w') as f:
                json.dump({}, f)
    
    @staticmethod
    def add_movie(guild_id: str, title: str, file_path: str, file_size: int, 
                  duration: int = 0, uploader_id: str = None, 
                  required_role_id: str = None) -> Optional[str]:
        """
        Add a new movie to the database
        
        Returns:
            movie_id if successful, None otherwise
        """
        try:
            MovieDatabase._ensure_files()
            
            movie_id = str(uuid.uuid4())
            
            with open(MOVIES_FILE, 'r') as f:
                movies = json.load(f)
            
            movies[movie_id] = {
                "id": movie_id,
                "guild_id": str(guild_id),
                "title": title,
                "file_path": file_path,
                "file_size": file_size,
                "duration": duration,
                "uploader_id": str(uploader_id) if uploader_id else None,
                "required_role_id": required_role_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "views": 0,
                "active": True
            }
            
            with open(MOVIES_FILE, 'w') as f:
                json.dump(movies, f, indent=2)
            
            logger.info(f"Added movie {movie_id}: {title}")
            return movie_id
        except Exception as e:
            logger.error(f"Error adding movie: {e}")
            return None
    
    @staticmethod
    def get_movie(movie_id: str) -> Optional[Dict[str, Any]]:
        """Get a movie by ID"""
        try:
            MovieDatabase._ensure_files()
            
            with open(MOVIES_FILE, 'r') as f:
                movies = json.load(f)
                return movies.get(movie_id)
        except Exception as e:
            logger.error(f"Error getting movie: {e}")
            return None
    
    @staticmethod
    def get_guild_movies(guild_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all movies for a guild"""
        try:
            MovieDatabase._ensure_files()
            
            with open(MOVIES_FILE, 'r') as f:
                movies = json.load(f)
            
            guild_movies = [
                m for m in movies.values() 
                if m.get("guild_id") == str(guild_id)
            ]
            
            if active_only:
                guild_movies = [m for m in guild_movies if m.get("active", True)]
            
            # Sort by creation date (newest first)
            guild_movies.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return guild_movies
        except Exception as e:
            logger.error(f"Error getting guild movies: {e}")
            return []
    
    @staticmethod
    def delete_movie(movie_id: str) -> bool:
        """Delete a movie from the database"""
        try:
            MovieDatabase._ensure_files()
            
            with open(MOVIES_FILE, 'r') as f:
                movies = json.load(f)
            
            if movie_id in movies:
                # Mark as inactive instead of deleting
                movies[movie_id]["active"] = False
                movies[movie_id]["deleted_at"] = datetime.now(timezone.utc).isoformat()
                
                with open(MOVIES_FILE, 'w') as f:
                    json.dump(movies, f, indent=2)
                
                logger.info(f"Deleted movie {movie_id}")
                return True
        except Exception as e:
            logger.error(f"Error deleting movie: {e}")
        return False
    
    @staticmethod
    def update_movie_views(movie_id: str) -> bool:
        """Increment view count for a movie"""
        try:
            MovieDatabase._ensure_files()
            
            with open(MOVIES_FILE, 'r') as f:
                movies = json.load(f)
            
            if movie_id in movies:
                movies[movie_id]["views"] = movies[movie_id].get("views", 0) + 1
                
                with open(MOVIES_FILE, 'w') as f:
                    json.dump(movies, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Error updating views: {e}")
        return False
    
    @staticmethod
    def create_watch_room(guild_id: str, movie_id: str, room_name: str = None) -> Optional[str]:
        """
        Create a watch room for a movie
        
        Returns:
            room_id if successful, None otherwise
        """
        try:
            MovieDatabase._ensure_files()
            
            movie = MovieDatabase.get_movie(movie_id)
            if not movie:
                logger.error(f"Movie {movie_id} not found")
                return None
            
            room_id = str(uuid.uuid4())
            
            with open(MOVIE_ROOMS_FILE, 'r') as f:
                rooms = json.load(f)
            
            rooms[room_id] = {
                "id": room_id,
                "guild_id": str(guild_id),
                "movie_id": movie_id,
                "movie_title": movie.get("title"),
                "room_name": room_name or f"Watch: {movie.get('title')}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "viewers": [],
                "current_time": 0,
                "is_playing": False,
                "active": True
            }
            
            with open(MOVIE_ROOMS_FILE, 'w') as f:
                json.dump(rooms, f, indent=2)
            
            logger.info(f"Created watch room {room_id} for movie {movie_id}")
            return room_id
        except Exception as e:
            logger.error(f"Error creating watch room: {e}")
            return None
    
    @staticmethod
    def get_watch_room(room_id: str) -> Optional[Dict[str, Any]]:
        """Get a watch room by ID"""
        try:
            MovieDatabase._ensure_files()
            
            with open(MOVIE_ROOMS_FILE, 'r') as f:
                rooms = json.load(f)
                return rooms.get(room_id)
        except Exception as e:
            logger.error(f"Error getting watch room: {e}")
            return None
    
    @staticmethod
    def get_guild_watch_rooms(guild_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all watch rooms for a guild"""
        try:
            MovieDatabase._ensure_files()
            
            with open(MOVIE_ROOMS_FILE, 'r') as f:
                rooms = json.load(f)
            
            guild_rooms = [
                r for r in rooms.values() 
                if r.get("guild_id") == str(guild_id)
            ]
            
            if active_only:
                guild_rooms = [r for r in guild_rooms if r.get("active", True)]
            
            # Sort by creation date (newest first)
            guild_rooms.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return guild_rooms
        except Exception as e:
            logger.error(f"Error getting guild watch rooms: {e}")
            return []
    
    @staticmethod
    def add_viewer_to_room(room_id: str, user_id: str) -> bool:
        """Add a viewer to a watch room"""
        try:
            MovieDatabase._ensure_files()
            
            with open(MOVIE_ROOMS_FILE, 'r') as f:
                rooms = json.load(f)
            
            if room_id in rooms:
                viewers = rooms[room_id].get("viewers", [])
                if str(user_id) not in viewers:
                    viewers.append(str(user_id))
                    rooms[room_id]["viewers"] = viewers
                    
                    with open(MOVIE_ROOMS_FILE, 'w') as f:
                        json.dump(rooms, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Error adding viewer: {e}")
        return False
    
    @staticmethod
    def remove_viewer_from_room(room_id: str, user_id: str) -> bool:
        """Remove a viewer from a watch room"""
        try:
            MovieDatabase._ensure_files()
            
            with open(MOVIE_ROOMS_FILE, 'r') as f:
                rooms = json.load(f)
            
            if room_id in rooms:
                viewers = rooms[room_id].get("viewers", [])
                if str(user_id) in viewers:
                    viewers.remove(str(user_id))
                    rooms[room_id]["viewers"] = viewers
                    
                    with open(MOVIE_ROOMS_FILE, 'w') as f:
                        json.dump(rooms, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Error removing viewer: {e}")
        return False
    
    @staticmethod
    def update_room_playback(room_id: str, current_time: int, is_playing: bool) -> bool:
        """Update room playback state"""
        try:
            MovieDatabase._ensure_files()
            
            with open(MOVIE_ROOMS_FILE, 'r') as f:
                rooms = json.load(f)
            
            if room_id in rooms:
                rooms[room_id]["current_time"] = current_time
                rooms[room_id]["is_playing"] = is_playing
                rooms[room_id]["last_updated"] = datetime.now(timezone.utc).isoformat()
                
                with open(MOVIE_ROOMS_FILE, 'w') as f:
                    json.dump(rooms, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Error updating playback: {e}")
        return False
    
    @staticmethod
    def close_watch_room(room_id: str) -> bool:
        """Close a watch room"""
        try:
            MovieDatabase._ensure_files()
            
            with open(MOVIE_ROOMS_FILE, 'r') as f:
                rooms = json.load(f)
            
            if room_id in rooms:
                rooms[room_id]["active"] = False
                rooms[room_id]["closed_at"] = datetime.now(timezone.utc).isoformat()
                
                with open(MOVIE_ROOMS_FILE, 'w') as f:
                    json.dump(rooms, f, indent=2)
                
                logger.info(f"Closed watch room {room_id}")
                return True
        except Exception as e:
            logger.error(f"Error closing watch room: {e}")
        return False
    
    @staticmethod
    def export_all_movies(guild_id: str) -> Dict[str, Any]:
        """Export all movies and rooms for a guild"""
        return {
            "movies": MovieDatabase.get_guild_movies(guild_id, active_only=False),
            "rooms": MovieDatabase.get_guild_watch_rooms(guild_id, active_only=False),
            "exported_at": datetime.now(timezone.utc).isoformat()
        }
