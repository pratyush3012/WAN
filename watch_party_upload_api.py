"""
Watch Party Upload API - Flask endpoints for guild-specific uploads with announcements
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple
from flask import request, jsonify, session
import asyncio
import discord

logger = logging.getLogger(__name__)

from watch_party_upload_fixed import GuildUploadManager, UploadConfig, UploadValidator
from watch_party_movies_db import MovieDatabase


class UploadAPI:
    """API endpoints for watch party uploads"""
    
    def __init__(self, bot):
        self.bot = bot
        self.upload_manager = GuildUploadManager(bot)
    
    def register_routes(self, app):
        """Register upload API routes"""
        
        @app.route('/api/watch/upload', methods=['POST'])
        def upload_movie():
            """Upload a movie to specific guild"""
            try:
                # Get guild ID from request
                guild_id = request.form.get('guild_id')
                if not guild_id:
                    return jsonify({"error": "guild_id required"}), 400
                
                # Verify user is in guild
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    return jsonify({"error": "Guild not found"}), 404
                
                # Check if file provided
                if 'file' not in request.files:
                    return jsonify({"error": "No file provided"}), 400
                
                file = request.files['file']
                if not file.filename:
                    return jsonify({"error": "Empty filename"}), 400
                
                # Validate file
                is_valid, validation_result = UploadValidator.validate_upload(file, file.filename)
                if not is_valid:
                    errors = validation_result.get("errors", [])
                    return jsonify({"error": errors[0] if errors else "Validation failed"}), 400
                
                # Get upload info
                title = request.form.get('title', file.filename[:80])
                user_id = session.get('user_id', 'unknown')
                username = session.get('username', 'Unknown')
                
                file_info = validation_result.get("file_info", {})
                file_size = file_info.get("size_bytes", 0)
                ext = file_info.get("extension", ".mp4")
                
                # Create upload directory
                upload_dir = Path("./uploads/watch_party")
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                # Save file with guild-specific naming
                safe_name = f"{guild_id}_{int(datetime.now(timezone.utc).timestamp())}{ext}"
                file_path = upload_dir / safe_name
                
                file.seek(0)
                file.save(str(file_path))
                
                # Start upload tracking
                upload_id = asyncio.run_coroutine_threadsafe(
                    self.upload_manager.start_upload(
                        guild_id=guild_id,
                        user_id=user_id,
                        username=username,
                        title=title,
                        file_path=str(file_path),
                        file_size=file_size
                    ),
                    self.bot.loop
                ).result()
                
                if not upload_id:
                    return jsonify({"error": "Failed to start upload"}), 500
                
                # Save to database
                movie_id = MovieDatabase.add_movie(
                    guild_id=guild_id,
                    title=title,
                    file_path=str(file_path),
                    file_size=file_size,
                    uploader_id=user_id,
                    duration=0
                )
                
                if not movie_id:
                    return jsonify({"error": "Failed to save to database"}), 500
                
                # Complete upload and send announcements
                success = asyncio.run_coroutine_threadsafe(
                    self.upload_manager.complete_upload(upload_id, movie_id),
                    self.bot.loop
                ).result()
                
                if not success:
                    return jsonify({"error": "Failed to send announcements"}), 500
                
                logger.info(f"✅ Movie uploaded: {title} (ID: {movie_id}) to guild {guild_id}")
                
                return jsonify({
                    "success": True,
                    "movie_id": movie_id,
                    "upload_id": upload_id,
                    "title": title,
                    "size_mb": round(file_size / (1024**2), 1),
                    "message": "Movie uploaded successfully! Announcement sent to Discord."
                }), 200
            
            except Exception as e:
                logger.error(f"❌ Upload error: {e}")
                return jsonify({"error": str(e)}), 500
        
        @app.route('/api/watch/upload/status/<upload_id>', methods=['GET'])
        def get_upload_status(upload_id):
            """Get upload status"""
            try:
                upload_info = self.upload_manager.get_upload_info(upload_id)
                if not upload_info:
                    return jsonify({"error": "Upload not found"}), 404
                
                return jsonify({
                    "upload_id": upload_id,
                    "status": upload_info.get("status"),
                    "title": upload_info.get("title"),
                    "username": upload_info.get("username"),
                    "size_mb": round(upload_info.get("file_size", 0) / (1024**2), 1),
                    "started_at": upload_info.get("started_at"),
                    "completed_at": upload_info.get("completed_at")
                }), 200
            
            except Exception as e:
                logger.error(f"❌ Error getting upload status: {e}")
                return jsonify({"error": str(e)}), 500
        
        @app.route('/api/watch/uploads/<guild_id>', methods=['GET'])
        def get_guild_uploads(guild_id):
            """Get all uploads for a guild"""
            try:
                uploads = self.upload_manager.get_active_uploads(guild_id)
                
                return jsonify({
                    "guild_id": guild_id,
                    "total": len(uploads),
                    "uploads": [
                        {
                            "title": u.get("title"),
                            "username": u.get("username"),
                            "status": u.get("status"),
                            "size_mb": round(u.get("file_size", 0) / (1024**2), 1),
                            "started_at": u.get("started_at")
                        }
                        for u in uploads
                    ]
                }), 200
            
            except Exception as e:
                logger.error(f"❌ Error getting guild uploads: {e}")
                return jsonify({"error": str(e)}), 500
        
        @app.route('/api/watch/upload-channel/<guild_id>', methods=['GET', 'POST'])
        def manage_upload_channel(guild_id):
            """Get or set upload channel for guild"""
            try:
                if request.method == 'GET':
                    channel_id = UploadConfig.get_upload_channel(guild_id)
                    return jsonify({
                        "guild_id": guild_id,
                        "channel_id": channel_id
                    }), 200
                
                elif request.method == 'POST':
                    data = request.get_json()
                    channel_id = data.get('channel_id')
                    
                    if not channel_id:
                        return jsonify({"error": "channel_id required"}), 400
                    
                    if UploadConfig.set_upload_channel(guild_id, channel_id):
                        return jsonify({
                            "success": True,
                            "guild_id": guild_id,
                            "channel_id": channel_id,
                            "message": "Upload channel configured"
                        }), 200
                    else:
                        return jsonify({"error": "Failed to set channel"}), 500
            
            except Exception as e:
                logger.error(f"❌ Error managing upload channel: {e}")
                return jsonify({"error": str(e)}), 500


def register_upload_routes(app, bot):
    """Register all upload routes"""
    upload_api = UploadAPI(bot)
    upload_api.register_routes(app)
