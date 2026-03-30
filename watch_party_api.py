"""
Watch Party API Handler - REST endpoints for watch party functionality
Handles movie uploads, room creation, and playback management
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)

from watch_party_movies_db import MovieDatabase
from watch_party_upload import UploadManager, UploadValidator, UploadProgress
from watch_party_config import UPLOAD_FOLDER, MAX_UPLOAD_MB


class WatchPartyAPI:
    """Handle watch party API requests"""
    
    @staticmethod
    def handle_movie_upload(guild_id: str, file_obj, filename: str, 
                           title: str, uploader_id: str = None,
                           required_role_id: str = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Handle movie file upload
        
        Returns:
            (success, response_dict)
        """
        try:
            # Validate upload
            is_valid, validation_result = UploadValidator.validate_upload(file_obj, filename)
            
            if not is_valid:
                return False, {
                    "error": "Validation failed",
                    "details": validation_result["errors"]
                }
            
            # Create upload folder if needed
            Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename
            file_ext = os.path.splitext(filename)[1]
            unique_filename = f"{guild_id}_{datetime.now(timezone.utc).timestamp()}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            
            # Save file
            file_obj.seek(0)
            with open(file_path, 'wb') as f:
                f.write(file_obj.read())
            
            file_size = os.path.getsize(file_path)
            
            # Save to database
            movie_id = UploadManager.save_uploaded_movie(
                guild_id=guild_id,
                title=title,
                file_path=file_path,
                file_size=file_size,
                uploader_id=uploader_id,
                required_role_id=required_role_id
            )
            
            if not movie_id:
                # Clean up file if database save failed
                try:
                    os.remove(file_path)
                except:
                    pass
                
                return False, {
                    "error": "Failed to save movie to database"
                }
            
            # Create watch room
            room_id = UploadManager.create_watch_room(guild_id, movie_id)
            
            if not room_id:
                return False, {
                    "error": "Failed to create watch room"
                }
            
            logger.info(f"Successfully uploaded movie {movie_id} for guild {guild_id}")
            
            return True, {
                "success": True,
                "movie_id": movie_id,
                "room_id": room_id,
                "title": title,
                "file_size": file_size,
                "file_size_mb": round(file_size / (1024**2), 2)
            }
        
        except Exception as e:
            logger.error(f"Error handling movie upload: {e}")
            return False, {
                "error": str(e)
            }
    
    @staticmethod
    def handle_url_upload(guild_id: str, title: str, video_url: str,
                         uploader_id: str = None,
                         required_role_id: str = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Handle URL-based movie creation
        
        Returns:
            (success, response_dict)
        """
        try:
            # Save to database with URL as file_path
            movie_id = MovieDatabase.add_movie(
                guild_id=guild_id,
                title=title,
                file_path=video_url,
                file_size=0,  # Unknown for URLs
                uploader_id=uploader_id,
                required_role_id=required_role_id
            )
            
            if not movie_id:
                return False, {
                    "error": "Failed to save movie to database"
                }
            
            # Create watch room
            room_id = MovieDatabase.create_watch_room(guild_id, movie_id)
            
            if not room_id:
                return False, {
                    "error": "Failed to create watch room"
                }
            
            logger.info(f"Successfully created URL movie {movie_id} for guild {guild_id}")
            
            return True, {
                "success": True,
                "movie_id": movie_id,
                "room_id": room_id,
                "title": title,
                "video_url": video_url
            }
        
        except Exception as e:
            logger.error(f"Error handling URL upload: {e}")
            return False, {
                "error": str(e)
            }
    
    @staticmethod
    def get_guild_movies(guild_id: str) -> Dict[str, Any]:
        """Get all movies for a guild"""
        try:
            movies = MovieDatabase.get_guild_movies(guild_id, active_only=True)
            
            return {
                "success": True,
                "movies": movies,
                "count": len(movies)
            }
        except Exception as e:
            logger.error(f"Error getting guild movies: {e}")
            return {
                "success": False,
                "error": str(e),
                "movies": []
            }
    
    @staticmethod
    def get_guild_watch_rooms(guild_id: str) -> Dict[str, Any]:
        """Get all active watch rooms for a guild"""
        try:
            rooms = MovieDatabase.get_guild_watch_rooms(guild_id, active_only=True)
            
            return {
                "success": True,
                "rooms": rooms,
                "count": len(rooms)
            }
        except Exception as e:
            logger.error(f"Error getting guild watch rooms: {e}")
            return {
                "success": False,
                "error": str(e),
                "rooms": []
            }
    
    @staticmethod
    def delete_movie(movie_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Delete a movie"""
        try:
            movie = MovieDatabase.get_movie(movie_id)
            if not movie:
                return False, {"error": "Movie not found"}
            
            # Delete file if it's a local upload
            file_path = movie.get("file_path")
            if file_path and file_path.startswith(UPLOAD_FOLDER):
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Could not delete file {file_path}: {e}")
            
            # Mark as deleted in database
            success = MovieDatabase.delete_movie(movie_id)
            
            if success:
                logger.info(f"Deleted movie {movie_id}")
                return True, {"success": True, "movie_id": movie_id}
            else:
                return False, {"error": "Failed to delete movie"}
        
        except Exception as e:
            logger.error(f"Error deleting movie: {e}")
            return False, {"error": str(e)}
    
    @staticmethod
    def start_watch_room(room_id: str, user_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Start watching a movie in a room"""
        try:
            room = MovieDatabase.get_watch_room(room_id)
            if not room:
                return False, {"error": "Room not found"}
            
            # Add viewer
            MovieDatabase.add_viewer_to_room(room_id, user_id)
            
            # Update playback state
            MovieDatabase.update_room_playback(room_id, 0, True)
            
            # Get movie info
            movie = MovieDatabase.get_movie(room.get("movie_id"))
            
            logger.info(f"User {user_id} started watching room {room_id}")
            
            return True, {
                "success": True,
                "room_id": room_id,
                "movie": movie,
                "viewers": room.get("viewers", [])
            }
        
        except Exception as e:
            logger.error(f"Error starting watch room: {e}")
            return False, {"error": str(e)}
    
    @staticmethod
    def update_playback(room_id: str, current_time: int, is_playing: bool) -> Tuple[bool, Dict[str, Any]]:
        """Update playback state"""
        try:
            success = MovieDatabase.update_room_playback(room_id, current_time, is_playing)
            
            if success:
                room = MovieDatabase.get_watch_room(room_id)
                return True, {
                    "success": True,
                    "room_id": room_id,
                    "current_time": current_time,
                    "is_playing": is_playing,
                    "viewers": room.get("viewers", [])
                }
            else:
                return False, {"error": "Failed to update playback"}
        
        except Exception as e:
            logger.error(f"Error updating playback: {e}")
            return False, {"error": str(e)}
    
    @staticmethod
    def close_room(room_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Close a watch room"""
        try:
            success = MovieDatabase.close_watch_room(room_id)
            
            if success:
                logger.info(f"Closed watch room {room_id}")
                return True, {"success": True, "room_id": room_id}
            else:
                return False, {"error": "Failed to close room"}
        
        except Exception as e:
            logger.error(f"Error closing room: {e}")
            return False, {"error": str(e)}
