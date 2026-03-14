"""
WAN Bot - Enhanced Ultimate Web Dashboard
Complete server control with enterprise-grade security and performance!
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
import discord
from discord.ext import commands
import asyncio
import threading
import os
from datetime import datetime, timedelta
import json
import secrets
import bcrypt
import csv
import io
from functools import wraps
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler('dashboard.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('dashboard')

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('DASHBOARD_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV', 'development') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Initialize extensions
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 300})
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Global bot instance
bot_instance = None

# Dashboard data cache with timestamps
dashboard_cache = {
    'servers': {},
    'analytics': {},
    'logs': [],
    'active_users': 0,
    'bot_status': 'offline',
    'last_update': None
}

# User management with bcrypt
ADMIN_USERS = {
    'admin': {
        'password_hash': bcrypt.hashpw('admin'.encode(), bcrypt.gensalt()),
        'permissions': ['all'],
        'created_at': datetime.utcnow().isoformat()
    }
}

# Custom exceptions
class DashboardError(Exception):
    """Base exception for dashboard errors"""
    pass

class AuthenticationError(DashboardError):
    """Authentication failed"""
    pass

class PermissionError(DashboardError):
    """Insufficient permissions"""
    pass

# Decorators
def require_auth(f):
    """Decorator for routes requiring authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_permission(permission):
    """Decorator for routes requiring specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            user = ADMIN_USERS.get(session['user_id'])
            if not user or (permission not in user['permissions'] and 'all' not in user['permissions']):
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Helper functions
def verify_password(password: str, hashed: bytes) -> bool:
    """Verify password against hash"""
    try:
        return bcrypt.checkpw(password.encode(), hashed)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def hash_password(password: str) -> bytes:
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

async def run_async(coro):
    """Run async coroutine in bot's event loop"""
    if bot_instance and bot_instance.loop:
        return await asyncio.run_coroutine_threadsafe(coro, bot_instance.loop).result(timeout=10)
    raise DashboardError("Bot not ready")

# Error handlers
@app.errorhandler(DashboardError)
def handle_dashboard_error(error):
    logger.error(f"Dashboard error: {error}")
    return jsonify({'error': str(error)}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# Routes
@app.route('/')
def index():
    """Main landing page"""
    if 'user_id' in session:
        return render_template('ultimate_dashboard.html', username=session.get('username'))
    return render_template('landing.html')

@app.route('/manage')
@require_auth
def manage():
    """Server management page"""
    return render_template('server_management.html', username=session.get('username'))

@app.route('/auth')
def auth():
    """Authenticate with token from Discord command"""
    token = request.args.get('token')
    
    if not token:
        return redirect(url_for('login'))
    
    # Get webdashboard cog to verify token
    if bot_instance:
        webdashboard_cog = bot_instance.get_cog('WebDashboardCog')
        if webdashboard_cog:
            loop = bot_instance.loop
            if loop and loop.is_running():
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(webdashboard_cog.verify_token(token), loop)
                token_data = future.result(timeout=5)
            else:
                token_data = None
            
            if token_data:
                # Set session
                session.permanent = True
                session['user_id'] = str(token_data['user_id'])
                session['guild_id'] = str(token_data['guild_id'])
                session['role'] = token_data['role']
                session['username'] = f"User {token_data['user_id']}"
                session['login_time'] = datetime.utcnow().isoformat()
                
                logger.info(f"Token auth successful for user {token_data['user_id']} with role {token_data['role']}")
                return redirect(url_for('index'))
    
    return redirect(url_for('login'))

@app.route('/admin')
@require_auth
@require_permission('admin')
def admin_dashboard():
    """Admin dashboard with full control"""
    return render_template('ultimate_dashboard.html', username=session.get('username'), admin=True)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Login page with rate limiting"""
    if request.method == 'POST':
        try:
            data = request.json
            username = data.get('username', '').strip()
            password = data.get('password', '')
            
            if not username or not password:
                return jsonify({'success': False, 'error': 'Username and password required'}), 400
            
            user = ADMIN_USERS.get(username)
            if user and verify_password(password, user['password_hash']):
                session.permanent = True
                session['user_id'] = username
                session['username'] = username
                session['login_time'] = datetime.utcnow().isoformat()
                
                logger.info(f"User {username} logged in from {request.remote_addr}")
                return jsonify({'success': True})
            
            logger.warning(f"Failed login attempt for {username} from {request.remote_addr}")
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return jsonify({'success': False, 'error': 'Login failed'}), 500
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout and clear session"""
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"User {username} logged out")
    return redirect(url_for('login'))

@app.route('/api/bot/status')
@require_auth
def bot_status():
    """Get bot status"""
    try:
        if bot_instance and bot_instance.is_ready():
            # Fix timezone issue - make both timezone-aware
            if hasattr(bot_instance, 'start_time'):
                now = datetime.now(bot_instance.start_time.tzinfo)
                uptime = now - bot_instance.start_time
            else:
                uptime = timedelta(0)
            
            return jsonify({
                'status': 'online',
                'latency': round(bot_instance.latency * 1000, 2),
                'servers': len(bot_instance.guilds),
                'users': sum(g.member_count for g in bot_instance.guilds),
                'uptime': str(uptime).split('.')[0],  # Remove microseconds
                'commands': len(bot_instance.tree.get_commands()),
                'cogs': len(bot_instance.cogs),
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return jsonify({'status': 'offline', 'timestamp': datetime.utcnow().isoformat()})
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return jsonify({'error': 'Failed to get bot status'}), 500

@app.route('/api/servers')
@require_auth
def get_servers():
    """Get all servers"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        servers = []
        for guild in bot_instance.guilds:
            servers.append({
                'id': str(guild.id),
                'name': guild.name,
                'icon': str(guild.icon.url) if guild.icon else None,
                'member_count': guild.member_count,
                'owner': str(guild.owner) if guild.owner else f"User {guild.owner_id}",
                'owner_id': str(guild.owner_id),
                'created_at': guild.created_at.isoformat(),
                'boost_level': guild.premium_tier,
                'boost_count': guild.premium_subscription_count or 0
            })

        return jsonify({'servers': servers, 'total': len(servers)})
    except Exception as e:
        logger.error(f"Error getting servers: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>')
@require_auth
def get_server_details(server_id):
    """Get detailed server information"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        try:
            guild_id_int = int(server_id)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid server ID'}), 400

        guild = bot_instance.get_guild(guild_id_int)
        if not guild:
            # Log all known guild IDs to help debug
            known = [str(g.id) for g in bot_instance.guilds]
            logger.warning(f"Guild {server_id} not found. Known guilds: {known}")
            return jsonify({'error': 'Server not found', 'known_guilds': known}), 404

        # Chunk members if not already cached (needed for accurate member stats)
        if not guild.chunked:
            try:
                future = asyncio.run_coroutine_threadsafe(guild.chunk(), bot_instance.loop)
                future.result(timeout=10)
            except Exception as chunk_err:
                logger.warning(f"Could not chunk guild {guild.id}: {chunk_err}")

        # Detailed server info
        channels = {
            'text': [{'id': str(c.id), 'name': c.name, 'category': c.category.name if c.category else None}
                     for c in guild.text_channels],
            'voice': [{'id': str(c.id), 'name': c.name, 'category': c.category.name if c.category else None}
                      for c in guild.voice_channels],
            'categories': [{'id': str(c.id), 'name': c.name} for c in guild.categories]
        }

        roles = [{'id': str(r.id), 'name': r.name, 'color': str(r.color), 'members': len(r.members),
                  'position': r.position} for r in guild.roles]

        cached_members = guild.members
        members = {
            'total': guild.member_count,
            'online': len([m for m in cached_members if m.status != discord.Status.offline]),
            'bots': len([m for m in cached_members if m.bot]),
            'humans': len([m for m in cached_members if not m.bot])
        }

        # owner may be None if not cached — fetch safely
        owner_id = guild.owner_id
        owner_name = str(guild.owner) if guild.owner else f"User {owner_id}"

        return jsonify({
            'id': str(guild.id),
            'name': guild.name,
            'icon': str(guild.icon.url) if guild.icon else None,
            'banner': str(guild.banner.url) if guild.banner else None,
            'description': guild.description,
            'owner': {'id': str(owner_id), 'name': owner_name},
            'channels': channels,
            'roles': roles,
            'members': members,
            'boost_level': guild.premium_tier,
            'boost_count': guild.premium_subscription_count or 0,
            'verification_level': str(guild.verification_level),
            'created_at': guild.created_at.isoformat(),
            'features': list(guild.features)
        })
    except Exception as e:
        logger.error(f"Error getting server details for {server_id}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to get server details: {str(e)}'}), 500

@app.route('/api/export/<format>')
@require_auth
@require_permission('export')
def export_data(format):
    """Export data in various formats"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        
        if format == 'csv':
            # Export servers as CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Server ID', 'Name', 'Members', 'Owner', 'Created At'])
            
            for guild in bot_instance.guilds:
                writer.writerow([
                    guild.id,
                    guild.name,
                    guild.member_count,
                    str(guild.owner),
                    guild.created_at.isoformat()
                ])
            
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'servers_{datetime.now().strftime("%Y%m%d")}.csv'
            )
        
        elif format == 'json':
            # Export as JSON
            data = {
                'exported_at': datetime.utcnow().isoformat(),
                'bot_status': {
                    'servers': len(bot_instance.guilds),
                    'users': sum(g.member_count for g in bot_instance.guilds)
                },
                'servers': [
                    {
                        'id': str(g.id),
                        'name': g.name,
                        'members': g.member_count,
                        'owner': str(g.owner)
                    } for g in bot_instance.guilds
                ]
            }
            return jsonify(data)
        
        return jsonify({'error': 'Invalid format'}), 400
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return jsonify({'error': 'Export failed'}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    checks = {
        'bot': bot_instance.is_ready() if bot_instance else False,
        'cache': cache.cache is not None,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    status = 'healthy' if checks['bot'] else 'degraded'
    return jsonify({'status': status, 'checks': checks})

@app.route('/api/server/<server_id>/audit')
@require_auth
def get_audit_log(server_id):
    """Get recent audit log events for a server"""
    audit_log = dashboard_cache.get('audit_log', {}).get(str(server_id), [])
    return jsonify({'events': audit_log[:50]})

# ===== Roblox Integration API Endpoints =====

@app.route('/api/roblox/linked-members')
@require_auth
@cache.cached(timeout=30, key_prefix='roblox_members')
def get_roblox_linked_members():
    """Get all linked Roblox accounts"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox integration not loaded'}), 503
        
        members = []
        for discord_id, member_info in roblox_cog.clan_members.items():
            # Get cached player data if available
            player_data = roblox_cog.player_cache.get(discord_id)
            
            member_entry = {
                'discord_id': discord_id,
                'roblox_username': member_info['roblox_username'],
                'roblox_id': member_info['roblox_id'],
                'linked_at': member_info['linked_at']
            }
            
            if player_data:
                member_entry.update({
                    'is_online': player_data.get('is_online', False),
                    'currently_playing': player_data.get('currently_playing', False),
                    'stats': player_data.get('stats', {}),
                    'last_updated': player_data.get('last_updated')
                })
            
            members.append(member_entry)
        
        return jsonify({
            'members': members,
            'total': len(members),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting Roblox members: {e}")
        return jsonify({'error': 'Failed to get Roblox members'}), 500

@app.route('/api/roblox/stats/<int:discord_id>')
@require_auth
def get_roblox_player_stats(discord_id):
    """Get individual player stats"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox integration not loaded'}), 503
        
        if discord_id not in roblox_cog.clan_members:
            return jsonify({'error': 'Player not linked'}), 404
        
        player_data = roblox_cog.player_cache.get(discord_id)
        if not player_data:
            # Fetch fresh data
            member_info = roblox_cog.clan_members[discord_id]
            loop = bot_instance.loop or asyncio.get_event_loop()
            player_data = loop.run_until_complete(
                roblox_cog.fetch_player_data(discord_id, member_info['roblox_username'])
            )
        
        if not player_data:
            return jsonify({'error': 'Failed to fetch player data'}), 500
        
        return jsonify(player_data)
    except Exception as e:
        logger.error(f"Error getting player stats: {e}")
        return jsonify({'error': 'Failed to get player stats'}), 500

@app.route('/api/leaderboard/<category>')
@require_auth
def get_activity_leaderboard(category):
    """Get real Discord activity leaderboard"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        lb_cog = bot_instance.get_cog('Leaderboard')
        if not lb_cog:
            return jsonify({'error': 'Leaderboard cog not loaded'}), 503

        # Use first guild
        guild = bot_instance.guilds[0] if bot_instance.guilds else None
        if not guild:
            return jsonify({'error': 'No guild found'}), 404

        g = lb_cog._guild(guild.id)
        entries = []
        for uid, stats in g.items():
            member = guild.get_member(int(uid))
            score = stats.get("messages", 0) + (stats.get("voice_seconds", 0) // 60) * 2 + int(stats.get("reactions", 0) * 0.5)
            entries.append({
                'user_id': uid,
                'name': member.display_name if member else f"User {uid}",
                'avatar': str(member.display_avatar.url) if member else None,
                'messages': stats.get("messages", 0),
                'voice_seconds': stats.get("voice_seconds", 0),
                'reactions': stats.get("reactions", 0),
                'score': score
            })

        key_map = {
            'score': lambda x: x['score'],
            'messages': lambda x: x['messages'],
            'voice': lambda x: x['voice_seconds'],
            'reactions': lambda x: x['reactions'],
        }
        entries.sort(key=key_map.get(category, key_map['score']), reverse=True)

        return jsonify({
            'category': category,
            'leaderboard': entries[:20],
            'total': len(entries),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return jsonify({'error': 'Failed to get leaderboard'}), 500

@app.route('/api/roblox/clan-stats')
@require_auth
@cache.cached(timeout=60, key_prefix='roblox_clan_stats')
def get_roblox_clan_stats():
    """Get aggregated clan statistics"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox integration not loaded'}), 503
        
        # Collect all player data
        all_stats = []
        online_count = 0
        playing_count = 0
        
        for discord_id, member_info in roblox_cog.clan_members.items():
            player_data = roblox_cog.player_cache.get(discord_id)
            if player_data:
                all_stats.append(player_data)
                if player_data.get('is_online'):
                    online_count += 1
                if player_data.get('currently_playing'):
                    playing_count += 1
        
        # Calculate totals
        total_playtime = sum(p['stats']['playtime'] for p in all_stats)
        total_coins = sum(p['stats']['coins_collected'] for p in all_stats)
        total_kills = sum(p['stats']['kills'] for p in all_stats)
        total_deaths = sum(p['stats']['deaths'] for p in all_stats)
        avg_level = sum(p['stats']['level'] for p in all_stats) / len(all_stats) if all_stats else 0
        
        return jsonify({
            'total_members': len(roblox_cog.clan_members),
            'tracked_members': len(all_stats),
            'online_members': online_count,
            'playing_now': playing_count,
            'totals': {
                'playtime': total_playtime,
                'playtime_hours': total_playtime // 3600,
                'coins_collected': total_coins,
                'kills': total_kills,
                'deaths': total_deaths,
                'kd_ratio': total_kills / max(total_deaths, 1)
            },
            'averages': {
                'level': round(avg_level, 2),
                'playtime_per_member': total_playtime // len(all_stats) if all_stats else 0,
                'coins_per_member': total_coins // len(all_stats) if all_stats else 0
            },
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting clan stats: {e}")
        return jsonify({'error': 'Failed to get clan stats'}), 500

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if 'user_id' not in session:
        return False
    
    logger.info(f"Client connected: {session.get('username')}")
    emit('connected', {'message': 'Connected to WAN Bot Dashboard', 'timestamp': datetime.utcnow().isoformat()})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {session.get('username', 'Unknown')}")

@socketio.on('subscribe_server')
def handle_subscribe(data):
    """Subscribe to server-specific updates"""
    server_id = data.get('server_id')
    if server_id:
        join_room(f'server_{server_id}')
        emit('subscribed', {'server_id': server_id})

@socketio.on('unsubscribe_server')
def handle_unsubscribe(data):
    """Unsubscribe from server updates"""
    server_id = data.get('server_id')
    if server_id:
        leave_room(f'server_{server_id}')
        emit('unsubscribed', {'server_id': server_id})

def broadcast_update(event_type: str, data: dict, room: str = None):
    """Broadcast update to all connected clients or specific room"""
    try:
        # Store audit events in memory for late-joining clients
        if event_type == 'audit':
            guild_id = str(data.get('guild_id', ''))
            if guild_id not in dashboard_cache.get('audit_log', {}):
                if 'audit_log' not in dashboard_cache:
                    dashboard_cache['audit_log'] = {}
                dashboard_cache['audit_log'][guild_id] = []
            dashboard_cache['audit_log'][guild_id].insert(0, data)
            dashboard_cache['audit_log'][guild_id] = dashboard_cache['audit_log'][guild_id][:100]

        if room:
            socketio.emit(event_type, data, room=room)
        else:
            socketio.emit(event_type, data, broadcast=True)
    except Exception as e:
        logger.error(f"Error broadcasting update: {e}")

def start_web_dashboard(bot, host='0.0.0.0', port=5000):
    """Start the enhanced web dashboard"""
    global bot_instance
    bot_instance = bot
    
    logger.info(f"🌐 Starting Enhanced Web Dashboard on http://{host}:{port}")
    logger.info("✨ Features: Security, Caching, Rate Limiting, Export, WebSocket")
    
    try:
        socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")

if __name__ == '__main__':
    print("⚠️  Run this through bot.py, not directly!")
    print("The enhanced web dashboard will start automatically with the bot.")


# ===== MUSIC API ENDPOINTS =====

@app.route('/api/server/<server_id>/music/play', methods=['POST'])
@require_auth
def music_play(server_id):
    """Play a song via dashboard"""
    try:
        query = request.json.get('query', '').strip()
        channel_id = request.json.get('channel_id')
        if not query:
            return jsonify({'error': 'No query provided'}), 400
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        music_cog = bot_instance.get_cog('Music')
        if not music_cog:
            return jsonify({'error': 'Music cog not loaded'}), 503

        async def _play():
            vc = guild.voice_client
            if not vc:
                if channel_id:
                    ch = guild.get_channel(int(channel_id))
                else:
                    ch = next((c for c in guild.voice_channels), None)
                if not ch:
                    return {'error': 'No voice channel found'}
                vc = await ch.connect()

            from cogs.music import YTDLSource
            player = await YTDLSource.from_query(query, loop=bot_instance.loop)
            player.requester = guild.me
            queue = music_cog.get_queue(guild.id)

            if vc.is_playing() or vc.is_paused():
                queue.add(player)
                return {'status': 'queued', 'title': player.title, 'queue_size': len(queue.queue)}
            else:
                queue.current = player
                def after(err):
                    music_cog._play_next(guild)
                vc.play(player, after=after)
                broadcast_update('music_update', {
                    'guild_id': server_id,
                    'action': 'now_playing',
                    'title': player.title,
                    'thumbnail': player.thumbnail,
                    'queue_size': len(queue.queue)
                })
                return {'status': 'playing', 'title': player.title}

        future = asyncio.run_coroutine_threadsafe(_play(), bot_instance.loop)
        result = future.result(timeout=35)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error(f"Music play error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/music/control', methods=['POST'])
@require_auth
def music_control(server_id):
    """Pause/resume/skip/stop"""
    try:
        action = request.json.get('action')
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        vc = guild.voice_client
        music_cog = bot_instance.get_cog('Music')

        if action == 'pause' and vc and vc.is_playing():
            vc.pause()
        elif action == 'resume' and vc and vc.is_paused():
            vc.resume()
        elif action == 'skip' and vc and vc.is_playing():
            vc.stop()
        elif action == 'stop':
            future = asyncio.run_coroutine_threadsafe(music_cog.cleanup(int(server_id)), bot_instance.loop)
            future.result(timeout=10)
        else:
            return jsonify({'error': f'Cannot perform {action}'}), 400

        broadcast_update('music_update', {'guild_id': server_id, 'action': action})
        return jsonify({'status': action})
    except Exception as e:
        logger.error(f"Music control error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/music/status')
@require_auth
def music_status(server_id):
    """Get current music status"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        music_cog = bot_instance.get_cog('Music')
        vc = guild.voice_client
        queue = music_cog.get_queue(int(server_id)) if music_cog else None

        return jsonify({
            'connected': vc is not None and vc.is_connected(),
            'playing': vc.is_playing() if vc else False,
            'paused': vc.is_paused() if vc else False,
            'channel': vc.channel.name if vc else None,
            'current': {
                'title': queue.current.title if queue and queue.current else None,
                'thumbnail': queue.current.thumbnail if queue and queue.current else None,
                'duration': queue.current.duration if queue and queue.current else None,
                'url': queue.current.url if queue and queue.current else None,
            },
            'queue': [s.title for s in list(queue.queue)[:20]] if queue else [],
            'queue_size': len(queue.queue) if queue else 0,
            'loop': queue.loop if queue else False,
            'loop_queue': queue.loop_queue if queue else False,
            'voice_channels': [{'id': str(c.id), 'name': c.name} for c in guild.voice_channels]
        })
    except Exception as e:
        logger.error(f"Music status error: {e}")
        return jsonify({'error': str(e)}), 500

# ===== ANNOUNCEMENTS API =====

@app.route('/api/server/<server_id>/announce', methods=['POST'])
@require_auth
def send_announcement(server_id):
    """Send an announcement to a channel"""
    try:
        data = request.json
        channel_id = data.get('channel_id')
        message = data.get('message', '').strip()
        title = data.get('title', '').strip()
        color = data.get('color', '#5865f2')
        ping_everyone = data.get('ping_everyone', False)

        if not message:
            return jsonify({'error': 'Message is required'}), 400
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        async def _send():
            channel = guild.get_channel(int(channel_id)) if channel_id else \
                next((c for c in guild.text_channels if 'announce' in c.name.lower()), guild.text_channels[0])
            if not channel:
                return {'error': 'Channel not found'}

            color_int = int(color.lstrip('#'), 16)
            embed = discord.Embed(color=color_int)
            if title:
                embed.title = title
            embed.description = message
            embed.set_footer(text=f"Announcement from {session.get('username', 'Dashboard')}")

            content = '@everyone' if ping_everyone else None
            await channel.send(content=content, embed=embed)
            return {'status': 'sent', 'channel': channel.name}

        future = asyncio.run_coroutine_threadsafe(_send(), bot_instance.loop)
        result = future.result(timeout=10)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error(f"Announcement error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/channels/text')
@require_auth
def get_text_channels(server_id):
    """Get text channels for announcement target selector"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        channels = [{'id': str(c.id), 'name': c.name} for c in guild.text_channels]
        return jsonify({'channels': channels})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== MANAGEMENT API ENDPOINTS =====
# Import management functions
from web_dashboard_management import (
    create_role_action, edit_role_action, delete_role_action, assign_role_action,
    create_channel_action, edit_channel_action, delete_channel_action,
    update_server_icon_action, update_server_banner_action, create_emoji_action,
    kick_member_action, ban_member_action, timeout_member_action,
    assign_badge_action, update_server_settings_action
)

# Role Management
@app.route('/api/server/<server_id>/roles', methods=['POST'])
@require_auth
@limiter.limit("10 per minute")
def create_role(server_id):
    """Create a new role"""
    return create_role_action(server_id, request.json)

@app.route('/api/server/<server_id>/roles/<role_id>', methods=['PUT'])
@require_auth
@limiter.limit("10 per minute")
def edit_role(server_id, role_id):
    """Edit a role"""
    return edit_role_action(server_id, role_id, request.json)

@app.route('/api/server/<server_id>/roles/<role_id>', methods=['DELETE'])
@require_auth
@limiter.limit("10 per minute")
def delete_role(server_id, role_id):
    """Delete a role"""
    return delete_role_action(server_id, role_id)

@app.route('/api/server/<server_id>/members/<member_id>/roles/<role_id>', methods=['POST'])
@require_auth
@limiter.limit("20 per minute")
def assign_role(server_id, member_id, role_id):
    """Assign role to member"""
    action = request.json.get('action', 'add')
    return assign_role_action(server_id, member_id, role_id, action)

# Channel Management
@app.route('/api/server/<server_id>/channels', methods=['POST'])
@require_auth
@limiter.limit("10 per minute")
def create_channel(server_id):
    """Create a new channel"""
    return create_channel_action(server_id, request.json)

@app.route('/api/server/<server_id>/channels/<channel_id>', methods=['PUT'])
@require_auth
@limiter.limit("10 per minute")
def edit_channel(server_id, channel_id):
    """Edit a channel"""
    return edit_channel_action(server_id, channel_id, request.json)

@app.route('/api/server/<server_id>/channels/<channel_id>', methods=['DELETE'])
@require_auth
@limiter.limit("10 per minute")
def delete_channel(server_id, channel_id):
    """Delete a channel"""
    return delete_channel_action(server_id, channel_id)

# Server Decoration
@app.route('/api/server/<server_id>/icon', methods=['POST'])
@require_auth
@limiter.limit("5 per hour")
def update_server_icon(server_id):
    """Update server icon"""
    icon_url = request.json.get('icon_url')
    return update_server_icon_action(server_id, icon_url)

@app.route('/api/server/<server_id>/banner', methods=['POST'])
@require_auth
@limiter.limit("5 per hour")
def update_server_banner(server_id):
    """Update server banner"""
    banner_url = request.json.get('banner_url')
    return update_server_banner_action(server_id, banner_url)

@app.route('/api/server/<server_id>/emojis', methods=['POST'])
@require_auth
@limiter.limit("10 per hour")
def create_emoji(server_id):
    """Create custom emoji"""
    return create_emoji_action(server_id, request.json)

# Member Management
@app.route('/api/server/<server_id>/members/<member_id>/kick', methods=['POST'])
@require_auth
@limiter.limit("10 per minute")
def kick_member(server_id, member_id):
    """Kick a member"""
    reason = request.json.get('reason', '')
    return kick_member_action(server_id, member_id, reason)

@app.route('/api/server/<server_id>/members/<member_id>/ban', methods=['POST'])
@require_auth
@limiter.limit("10 per minute")
def ban_member(server_id, member_id):
    """Ban a member"""
    reason = request.json.get('reason', '')
    delete_days = request.json.get('delete_days', 0)
    return ban_member_action(server_id, member_id, reason, delete_days)

@app.route('/api/server/<server_id>/members/<member_id>/timeout', methods=['POST'])
@require_auth
@limiter.limit("20 per minute")
def timeout_member(server_id, member_id):
    """Timeout a member"""
    duration = request.json.get('duration', 10)
    reason = request.json.get('reason', '')
    return timeout_member_action(server_id, member_id, duration, reason)

# Badge Management
@app.route('/api/server/<server_id>/members/<member_id>/badge', methods=['POST'])
@require_auth
@limiter.limit("20 per minute")
def assign_badge(server_id, member_id):
    """Assign badge to member"""
    badge_name = request.json.get('badge_name')
    return assign_badge_action(server_id, member_id, badge_name)

# Server Settings
@app.route('/api/server/<server_id>/settings', methods=['PUT'])
@require_auth
@limiter.limit("5 per minute")
def update_server_settings(server_id):
    """Update server settings"""
    return update_server_settings_action(server_id, request.json)

# Get server members list
@app.route('/api/server/<server_id>/members')
@require_auth
def get_server_members(server_id):
    """Get list of server members"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        members = []
        for member in guild.members:
            members.append({
                'id': str(member.id),
                'name': member.name,
                'display_name': member.display_name,
                'avatar': str(member.avatar.url) if member.avatar else None,
                'bot': member.bot,
                'status': str(member.status),
                'roles': [{'id': str(r.id), 'name': r.name, 'color': str(r.color)} for r in member.roles if r.name != '@everyone'],
                'joined_at': member.joined_at.isoformat() if member.joined_at else None
            })
        
        return jsonify({'members': members, 'total': len(members)})
    except Exception as e:
        logger.error(f"Error getting members: {e}")
        return jsonify({'error': 'Failed to get members'}), 500
