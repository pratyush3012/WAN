"""
Premium Watch Party API - Chat, Requests, Scheduling, Approvals
Flask/FastAPI endpoints for enhanced watch party features
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)

from watch_party_enhanced import EnhancedWatchPartyDB, RequestType, RequestStatus
from watch_party_movies_db import MovieDatabase


class PremiumWatchPartyAPI:
    """API handlers for premium watch party features"""
    
    # ── Chat Endpoints ────────────────────────────────────────────────────
    
    @staticmethod
    def send_chat_message(room_id: str, user_id: str, username: str, 
                         message: str, user_role: str = "member") -> Dict[str, Any]:
        """Send chat message — everyone can chat, guests included"""
        try:
            # Check message length
            if len(message) > 500:
                return {
                    "success": False,
                    "error": "Message too long (max 500 chars)"
                }
            
            # Send message
            message_id = EnhancedWatchPartyDB.send_message(
                room_id=room_id,
                user_id=user_id,
                username=username,
                message=message,
                user_role=user_role
            )
            
            if message_id:
                return {
                    "success": True,
                    "message": {
                        "id": message_id,
                        "user_id": user_id,
                        "username": username,
                        "message": message,
                        "role": user_role,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to send message"
                }
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_chat_history(room_id: str, limit: int = 50) -> Dict[str, Any]:
        """Get chat history"""
        try:
            messages = EnhancedWatchPartyDB.get_chat_history(room_id, limit)
            return {
                "success": True,
                "messages": messages,
                "count": len(messages)
            }
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return {
                "success": False,
                "error": str(e),
                "messages": []
            }
    
    @staticmethod
    def add_reaction(room_id: str, message_id: str, user_id: str, 
                    emoji: str) -> Dict[str, Any]:
        """Add reaction to message"""
        try:
            success = EnhancedWatchPartyDB.add_reaction(
                room_id=room_id,
                message_id=message_id,
                user_id=user_id,
                emoji=emoji
            )
            
            return {
                "success": success,
                "message_id": message_id,
                "emoji": emoji
            }
        except Exception as e:
            logger.error(f"Error adding reaction: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ── Request Endpoints ─────────────────────────────────────────────────
    
    @staticmethod
    def create_request(room_id: str, user_id: str, username: str, 
                      request_type: str, details: Dict = None) -> Dict[str, Any]:
        """Create a request (play/pause/skip/etc)"""
        try:
            # Check if user has permission
            room = EnhancedWatchPartyDB.get_room(room_id)
            if not room:
                return {
                    "success": False,
                    "error": "Room not found"
                }
            
            if not room.get("settings", {}).get("allow_requests"):
                return {
                    "success": False,
                    "error": "Requests are disabled"
                }
            
            # Create request
            request_id = EnhancedWatchPartyDB.create_request(
                room_id=room_id,
                user_id=user_id,
                username=username,
                request_type=request_type,
                details=details
            )
            
            if request_id:
                return {
                    "success": True,
                    "request_id": request_id,
                    "type": request_type,
                    "status": "pending"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to create request"
                }
        except Exception as e:
            logger.error(f"Error creating request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_pending_requests(room_id: str) -> Dict[str, Any]:
        """Get all pending requests"""
        try:
            requests = EnhancedWatchPartyDB.get_pending_requests(room_id)
            return {
                "success": True,
                "requests": requests,
                "count": len(requests)
            }
        except Exception as e:
            logger.error(f"Error getting requests: {e}")
            return {
                "success": False,
                "error": str(e),
                "requests": []
            }
    
    @staticmethod
    def approve_request(room_id: str, request_id: str, approved_by: str) -> Dict[str, Any]:
        """Approve a request"""
        try:
            success = EnhancedWatchPartyDB.approve_request(
                room_id=room_id,
                request_id=request_id,
                approved_by=approved_by
            )
            
            if success:
                return {
                    "success": True,
                    "request_id": request_id,
                    "status": "approved"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to approve request"
                }
        except Exception as e:
            logger.error(f"Error approving request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def reject_request(room_id: str, request_id: str) -> Dict[str, Any]:
        """Reject a request"""
        try:
            success = EnhancedWatchPartyDB.reject_request(
                room_id=room_id,
                request_id=request_id
            )
            
            if success:
                return {
                    "success": True,
                    "request_id": request_id,
                    "status": "rejected"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to reject request"
                }
        except Exception as e:
            logger.error(f"Error rejecting request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ── Scheduling Endpoints ──────────────────────────────────────────────
    
    @staticmethod
    def schedule_movie(room_id: str, start_time: str, end_time: str = None) -> Dict[str, Any]:
        """Schedule movie start time"""
        try:
            success = EnhancedWatchPartyDB.schedule_movie(
                room_id=room_id,
                start_time=start_time,
                end_time=end_time
            )
            
            if success:
                return {
                    "success": True,
                    "room_id": room_id,
                    "start_time": start_time,
                    "end_time": end_time
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to schedule movie"
                }
        except Exception as e:
            logger.error(f"Error scheduling movie: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_scheduled_movies(guild_id: str) -> Dict[str, Any]:
        """Get all scheduled movies"""
        try:
            movies = EnhancedWatchPartyDB.get_scheduled_movies(guild_id)
            return {
                "success": True,
                "movies": movies,
                "count": len(movies)
            }
        except Exception as e:
            logger.error(f"Error getting scheduled movies: {e}")
            return {
                "success": False,
                "error": str(e),
                "movies": []
            }
    
    # ── Viewer Management ─────────────────────────────────────────────────
    
    @staticmethod
    def get_viewers(room_id: str) -> Dict[str, Any]:
        """Get all viewers in room"""
        try:
            room = EnhancedWatchPartyDB.get_room(room_id)
            if not room:
                return {
                    "success": False,
                    "error": "Room not found",
                    "viewers": []
                }
            
            viewers = []
            for user_id, viewer_data in room.get("viewers", {}).items():
                viewers.append({
                    "user_id": user_id,
                    "role": viewer_data.get("role"),
                    "joined_at": viewer_data.get("joined_at")
                })
            
            return {
                "success": True,
                "viewers": viewers,
                "count": len(viewers)
            }
        except Exception as e:
            logger.error(f"Error getting viewers: {e}")
            return {
                "success": False,
                "error": str(e),
                "viewers": []
            }
    
    # ── Room Settings ─────────────────────────────────────────────────────
    
    @staticmethod
    def update_settings(room_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update room settings"""
        try:
            success = EnhancedWatchPartyDB.update_room_settings(
                room_id=room_id,
                settings=settings
            )
            
            if success:
                return {
                    "success": True,
                    "room_id": room_id,
                    "settings": settings
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to update settings"
                }
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ── Statistics ────────────────────────────────────────────────────────
    
    @staticmethod
    def get_room_stats(room_id: str) -> Dict[str, Any]:
        """Get room statistics"""
        try:
            stats = EnhancedWatchPartyDB.get_room_stats(room_id)
            return {
                "success": True,
                "stats": stats
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "success": False,
                "error": str(e),
                "stats": {}
            }


# ── Flask Integration Example ──────────────────────────────────────────────

def register_premium_routes(app):
    """Register premium watch party routes with Flask app"""
    
    @app.route('/api/watch/chat/<room_id>', methods=['POST'])
    def send_chat(room_id):
        data = request.get_json()
        result = PremiumWatchPartyAPI.send_chat_message(
            room_id=room_id,
            user_id=data.get('user_id'),
            username=data.get('username'),
            message=data.get('message'),
            user_role=data.get('user_role', 'member')
        )
        return jsonify(result), (200 if result['success'] else 400)
    
    @app.route('/api/watch/chat/<room_id>', methods=['GET'])
    def get_chat(room_id):
        limit = request.args.get('limit', 50, type=int)
        result = PremiumWatchPartyAPI.get_chat_history(room_id, limit)
        return jsonify(result), 200
    
    @app.route('/api/watch/request/<room_id>', methods=['POST'])
    def create_request(room_id):
        data = request.get_json()
        result = PremiumWatchPartyAPI.create_request(
            room_id=room_id,
            user_id=data.get('user_id'),
            username=data.get('username'),
            request_type=data.get('request_type'),
            details=data.get('details')
        )
        return jsonify(result), (200 if result['success'] else 400)
    
    @app.route('/api/watch/requests/<room_id>', methods=['GET'])
    def get_requests(room_id):
        result = PremiumWatchPartyAPI.get_pending_requests(room_id)
        return jsonify(result), 200
    
    @app.route('/api/watch/request/<room_id>/<request_id>/approve', methods=['POST'])
    def approve_request(room_id, request_id):
        data = request.get_json() or {}
        result = PremiumWatchPartyAPI.approve_request(
            room_id=room_id,
            request_id=request_id,
            approved_by=data.get('approved_by')
        )
        return jsonify(result), (200 if result['success'] else 400)
    
    @app.route('/api/watch/request/<room_id>/<request_id>/reject', methods=['POST'])
    def reject_request(room_id, request_id):
        result = PremiumWatchPartyAPI.reject_request(room_id, request_id)
        return jsonify(result), (200 if result['success'] else 400)
    
    @app.route('/api/watch/schedule/<room_id>', methods=['POST'])
    def schedule_movie(room_id):
        data = request.get_json()
        result = PremiumWatchPartyAPI.schedule_movie(
            room_id=room_id,
            start_time=data.get('start_time'),
            end_time=data.get('end_time')
        )
        return jsonify(result), (200 if result['success'] else 400)
    
    @app.route('/api/watch/viewers/<room_id>', methods=['GET'])
    def get_viewers(room_id):
        result = PremiumWatchPartyAPI.get_viewers(room_id)
        return jsonify(result), 200
    
    @app.route('/api/watch/stats/<room_id>', methods=['GET'])
    def get_stats(room_id):
        result = PremiumWatchPartyAPI.get_room_stats(room_id)
        return jsonify(result), 200
