"""
Watch Party Upload Handler - Pre-upload validation and improved UI
Validates file size, format, and integrity before uploading
"""

import os
import mimetypes
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

from watch_party_config import MAX_UPLOAD_MB, ALLOWED_VIDEO_EXTS, UPLOAD_FOLDER
from watch_party_movies_db import MovieDatabase


class UploadValidator:
    """Validate uploads before processing"""
    
    # Video MIME types
    VALID_MIME_TYPES = {
        'video/mp4': '.mp4',
        'video/webm': '.webm',
        'video/x-matroska': '.mkv',
        'video/quicktime': '.mov',
        'video/x-msvideo': '.avi',
        'video/x-m4v': '.m4v',
    }
    
    @staticmethod
    def validate_file_extension(filename: str) -> Tuple[bool, str]:
        """Validate file extension"""
        if not filename:
            return False, "No filename provided"
        
        ext = os.path.splitext(filename)[1].lower()
        if not ext:
            return False, "File has no extension"
        
        if ext not in ALLOWED_VIDEO_EXTS:
            allowed = ", ".join(ALLOWED_VIDEO_EXTS)
            return False, f"Unsupported format '{ext}'. Allowed: {allowed}"
        
        return True, ext
    
    @staticmethod
    def validate_file_size(file_size_bytes: int) -> Tuple[bool, str]:
        """Validate file size"""
        if file_size_bytes <= 0:
            return False, "File size is 0 bytes"
        
        max_bytes = MAX_UPLOAD_MB * 1024 * 1024
        if file_size_bytes > max_bytes:
            size_gb = file_size_bytes / (1024**3)
            max_gb = MAX_UPLOAD_MB / 1024
            return False, f"File too large ({size_gb:.2f}GB). Max: {max_gb:.1f}GB"
        
        return True, f"{file_size_bytes / (1024**2):.1f}MB"
    
    @staticmethod
    def validate_mime_type(file_obj) -> Tuple[bool, str]:
        """Validate MIME type"""
        try:
            file_obj.seek(0)
            # Read first few bytes to check magic numbers
            header = file_obj.read(12)
            file_obj.seek(0)
            
            # Check for common video signatures
            if header.startswith(b'\x00\x00\x00\x20ftyp'):  # MP4
                return True, 'video/mp4'
            elif header.startswith(b'\x1a\x45\xdf\xa3'):  # Matroska/WebM
                return True, 'video/x-matroska'
            elif header.startswith(b'\x00\x00\x00\x14ftyp'):  # MOV
                return True, 'video/quicktime'
            elif header.startswith(b'RIFF') and b'AVI' in header:  # AVI
                return True, 'video/x-msvideo'
            
            return True, 'video/unknown'  # Allow if can't determine
        except Exception as e:
            logger.warning(f"Could not validate MIME type: {e}")
            return True, 'video/unknown'
    
    @staticmethod
    def validate_upload(file_obj, filename: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Complete upload validation
        
        Returns:
            (is_valid, validation_result_dict)
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "file_info": {}
        }
        
        # Validate extension
        ext_valid, ext_msg = UploadValidator.validate_file_extension(filename)
        if not ext_valid:
            result["errors"].append(ext_msg)
            return False, result
        
        result["file_info"]["extension"] = ext_msg
        
        # Get file size
        try:
            file_obj.seek(0, 2)
            file_size = file_obj.tell()
            file_obj.seek(0)
        except Exception as e:
            result["errors"].append(f"Cannot read file size: {e}")
            return False, result
        
        # Validate size
        size_valid, size_msg = UploadValidator.validate_file_size(file_size)
        if not size_valid:
            result["errors"].append(size_msg)
            return False, result
        
        result["file_info"]["size"] = size_msg
        result["file_info"]["size_bytes"] = file_size
        
        # Validate MIME type
        mime_valid, mime_type = UploadValidator.validate_mime_type(file_obj)
        if not mime_valid:
            result["errors"].append(f"Invalid MIME type: {mime_type}")
            return False, result
        
        result["file_info"]["mime_type"] = mime_type
        
        # Check storage space
        try:
            import shutil
            stat = shutil.disk_usage(UPLOAD_FOLDER)
            free_bytes = stat.free
            
            if file_size > free_bytes:
                free_gb = free_bytes / (1024**3)
                needed_gb = file_size / (1024**3)
                result["errors"].append(
                    f"Not enough disk space. Need {needed_gb:.2f}GB, have {free_gb:.2f}GB"
                )
                return False, result
            
            result["file_info"]["disk_free_gb"] = free_gb
        except Exception as e:
            result["warnings"].append(f"Could not check disk space: {e}")
        
        result["valid"] = True
        return True, result
    
    @staticmethod
    def get_validation_message(validation_result: Dict[str, Any]) -> str:
        """Get human-readable validation message"""
        if validation_result["valid"]:
            info = validation_result["file_info"]
            return (
                f"✅ File valid\n"
                f"Size: {info.get('size', 'unknown')}\n"
                f"Format: {info.get('extension', 'unknown')}\n"
                f"Ready to upload"
            )
        else:
            errors = "\n".join(validation_result["errors"])
            return f"❌ Validation failed:\n{errors}"


class UploadProgress:
    """Track upload progress"""
    
    def __init__(self, total_bytes: int):
        self.total_bytes = total_bytes
        self.uploaded_bytes = 0
        self.chunk_size = 65536  # 64KB chunks
    
    def get_progress_percent(self) -> float:
        """Get progress as percentage"""
        if self.total_bytes == 0:
            return 0.0
        return (self.uploaded_bytes / self.total_bytes) * 100
    
    def get_progress_info(self) -> Dict[str, Any]:
        """Get progress information"""
        total_mb = self.total_bytes / (1024**2)
        uploaded_mb = self.uploaded_bytes / (1024**2)
        percent = self.get_progress_percent()
        
        # Estimate time remaining
        if uploaded_mb > 0 and percent < 100:
            # Assume 5MB/s average speed
            remaining_mb = total_mb - uploaded_mb
            estimated_seconds = remaining_mb / 5
        else:
            estimated_seconds = 0
        
        return {
            "percent": round(percent, 1),
            "uploaded_mb": round(uploaded_mb, 1),
            "total_mb": round(total_mb, 1),
            "estimated_seconds": int(estimated_seconds),
            "status": self._get_status_text(percent)
        }
    
    @staticmethod
    def _get_status_text(percent: float) -> str:
        """Get status text based on progress"""
        if percent < 25:
            return "Starting upload..."
        elif percent < 50:
            return "Uploading..."
        elif percent < 75:
            return "Almost there..."
        elif percent < 100:
            return "Finalizing..."
        else:
            return "Complete!"
    
    def update(self, chunk_bytes: int):
        """Update progress"""
        self.uploaded_bytes += chunk_bytes
        if self.uploaded_bytes > self.total_bytes:
            self.uploaded_bytes = self.total_bytes


class UploadManager:
    """Manage file uploads and database persistence"""
    
    @staticmethod
    def save_uploaded_movie(guild_id: str, title: str, file_path: str, 
                           file_size: int, uploader_id: str = None,
                           required_role_id: str = None, duration: int = 0) -> Optional[str]:
        """
        Save uploaded movie to database
        
        Returns:
            movie_id if successful, None otherwise
        """
        try:
            movie_id = MovieDatabase.add_movie(
                guild_id=guild_id,
                title=title,
                file_path=file_path,
                file_size=file_size,
                duration=duration,
                uploader_id=uploader_id,
                required_role_id=required_role_id
            )
            
            if movie_id:
                logger.info(f"Saved movie {movie_id} to database for guild {guild_id}")
            
            return movie_id
        except Exception as e:
            logger.error(f"Error saving movie to database: {e}")
            return None
    
    @staticmethod
    def get_guild_movies(guild_id: str) -> list:
        """Get all active movies for a guild"""
        return MovieDatabase.get_guild_movies(guild_id, active_only=True)
    
    @staticmethod
    def delete_movie(movie_id: str) -> bool:
        """Delete a movie"""
        return MovieDatabase.delete_movie(movie_id)
    
    @staticmethod
    def create_watch_room(guild_id: str, movie_id: str) -> Optional[str]:
        """Create a watch room for a movie"""
        return MovieDatabase.create_watch_room(guild_id, movie_id)
