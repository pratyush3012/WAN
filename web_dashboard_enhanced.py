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
import re
from datetime import datetime, timedelta, timezone
import json
import secrets
import bcrypt
import csv
import io
import uuid
import time as _time
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
app.config['SECRET_KEY'] = os.getenv('DASHBOARD_SECRET_KEY', 'wan-bot-dashboard-secret-key-change-me-in-env')
app.config['SESSION_COOKIE_SECURE'] = False  # Render handles HTTPS termination; cookies work on HTTP internally
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Initialize extensions
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 300})
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["2000 per day", "500 per hour"],
    storage_uri="memory://"
)

# Global bot instance
bot_instance = None

# Persistent data directory — use ./data locally, /data on Render with disk
_default_data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_DIR = os.getenv('DATA_DIR', _default_data)
# Create it if it doesn't exist (handles case where /data disk isn't mounted)
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except PermissionError:
    DATA_DIR = _default_data
    os.makedirs(DATA_DIR, exist_ok=True)

def data_path(filename):
    """Return absolute path for a data file in the persistent data directory."""
    return os.path.join(DATA_DIR, filename)

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
        'created_at': datetime.now(timezone.utc).isoformat()
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
            # Always return JSON for /api/ routes
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'error': 'Authentication required', 'redirect': '/login'}), 401
            # Save the full URL they were trying to reach so we can redirect back after login
            return redirect(url_for('login', next=request.url))
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
    next_url = request.args.get('next', '').strip()

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
                # Try to get real Discord username
                real_username = f"User {token_data['user_id']}"
                try:
                    guild = bot_instance.get_guild(int(token_data['guild_id']))
                    if guild:
                        member = guild.get_member(int(token_data['user_id']))
                        if member:
                            real_username = member.display_name
                except Exception:
                    pass

                session.permanent = True
                session['user_id'] = str(token_data['user_id'])
                session['guild_id'] = str(token_data['guild_id'])
                session['role'] = token_data['role']
                session['username'] = real_username
                session['login_time'] = datetime.now(timezone.utc).isoformat()

                logger.info(f"Token auth successful for {real_username} ({token_data['user_id']}) with role {token_data['role']}")

                # Redirect to next URL if safe, otherwise go to dashboard
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
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
            # Also check persistent users file
            if not user:
                persistent_users = _load_users()
                pu = persistent_users.get(username)
                if pu:
                    user = {'password_hash': pu['password_hash'].encode() if isinstance(pu['password_hash'], str) else pu['password_hash'], 'permissions': pu.get('permissions', ['dashboard'])}
            if user and verify_password(password, user['password_hash']):
                session.permanent = True
                session['user_id'] = username
                session['username'] = username
                session['login_time'] = datetime.now(timezone.utc).isoformat()
                
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

# ===== DISCORD OAUTH2 =====

@app.route('/login/discord')
def discord_oauth_redirect():
    """Redirect to Discord OAuth2"""
    client_id = os.getenv('DISCORD_CLIENT_ID', '')
    if not client_id:
        return redirect(url_for('login'))
    redirect_uri = os.getenv('DISCORD_REDIRECT_URI', request.host_url.rstrip('/') + '/login/discord/callback')
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=identify+guilds"
        f"&state={state}"
    )
    return redirect(url)

@app.route('/login/discord/callback')
def discord_oauth_callback():
    """Handle Discord OAuth2 callback"""
    import urllib.request, urllib.parse
    error = request.args.get('error')
    if error:
        return redirect(url_for('login') + '?error=' + error)

    code = request.args.get('code')
    state = request.args.get('state')
    if not code or state != session.get('oauth_state'):
        return redirect(url_for('login') + '?error=invalid_state')

    client_id = os.getenv('DISCORD_CLIENT_ID', '')
    client_secret = os.getenv('DISCORD_CLIENT_SECRET', '')
    redirect_uri = os.getenv('DISCORD_REDIRECT_URI', request.host_url.rstrip('/') + '/login/discord/callback')

    if not client_secret:
        logger.error("DISCORD_CLIENT_SECRET not set — OAuth2 login unavailable")
        return redirect(url_for('login') + '?error=not_configured')

    try:
        import urllib.request as urlreq, urllib.parse as urlparse, json as _json

        # Exchange code for token
        token_data = urlparse.urlencode({
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
        }).encode()
        req = urlreq.Request('https://discord.com/api/oauth2/token', data=token_data,
                             headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urlreq.urlopen(req, timeout=10) as resp:
            token_resp = _json.loads(resp.read())

        access_token = token_resp.get('access_token')
        if not access_token:
            return redirect(url_for('login') + '?error=no_token')

        # Fetch user info
        req2 = urlreq.Request('https://discord.com/api/users/@me',
                              headers={'Authorization': f'Bearer {access_token}'})
        with urlreq.urlopen(req2, timeout=10) as resp2:
            user_info = _json.loads(resp2.read())

        # Fetch user guilds
        req3 = urlreq.Request('https://discord.com/api/users/@me/guilds',
                              headers={'Authorization': f'Bearer {access_token}'})
        with urlreq.urlopen(req3, timeout=10) as resp3:
            user_guilds = _json.loads(resp3.read())

        user_id = str(user_info['id'])
        username = user_info.get('username', f'User {user_id}')
        discriminator = user_info.get('discriminator', '0')
        avatar_hash = user_info.get('avatar')
        avatar_url = (
            f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
            if avatar_hash else
            f"https://cdn.discordapp.com/embed/avatars/{int(user_id) % 5}.png"
        )

        # Check if user is in any guild the bot is in (or is bot owner)
        owner_id = os.getenv('OWNER_ID', '')
        bot_guild_ids = {str(g.id) for g in bot_instance.guilds} if bot_instance and bot_instance.is_ready() else set()
        user_guild_ids = {str(g['id']) for g in user_guilds}

        # User must share at least one guild with the bot, or be the owner
        shared = user_guild_ids & bot_guild_ids
        if not shared and user_id != owner_id:
            return redirect(url_for('login') + '?error=no_shared_server')

        # Check if user has Manage Server in any shared guild
        MANAGE_GUILD = 0x20
        authorized_guilds = []
        for g in user_guilds:
            if str(g['id']) in bot_guild_ids:
                perms = int(g.get('permissions', 0))
                if perms & MANAGE_GUILD or perms & 0x8 or user_id == owner_id:  # manage guild or admin or owner
                    authorized_guilds.append(str(g['id']))

        if not authorized_guilds and user_id != owner_id:
            return redirect(url_for('login') + '?error=no_permission')

        session.permanent = True
        session['user_id'] = user_id
        session['username'] = username
        session['discriminator'] = discriminator
        session['avatar_url'] = avatar_url
        session['login_time'] = datetime.now(timezone.utc).isoformat()
        session['auth_method'] = 'discord'
        session['authorized_guilds'] = authorized_guilds if user_id != owner_id else list(bot_guild_ids)
        session.pop('oauth_state', None)

        logger.info(f"Discord OAuth login: {username}#{discriminator} ({user_id})")
        return redirect(url_for('index'))

    except Exception as e:
        logger.error(f"Discord OAuth error: {e}", exc_info=True)
        return redirect(url_for('login') + '?error=oauth_failed')

@app.route('/api/me')
@require_auth
def get_me():
    """Get current logged-in user info"""
    return jsonify({
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'avatar_url': session.get('avatar_url'),
        'auth_method': session.get('auth_method', 'password'),
        'authorized_guilds': session.get('authorized_guilds', []),
    })

@app.route('/api/bot/status')
@require_auth
def bot_status():
    """Get bot status"""
    try:
        if bot_instance and bot_instance.is_ready():
            # Fix timezone issue - always use UTC
            if hasattr(bot_instance, 'start_time'):
                now = datetime.now(timezone.utc)
                start = bot_instance.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                uptime = now - start
            else:
                uptime = timedelta(0)
            
            return jsonify({
                'status': 'online',
                'latency': round(bot_instance.latency * 1000, 2),
                'servers': len(bot_instance.guilds),
                'users': sum(g.member_count for g in bot_instance.guilds),
                'uptime': str(uptime).split('.')[0],
                'uptime_seconds': int(uptime.total_seconds()),
                'commands': len(bot_instance.tree.get_commands()),
                'cogs': len(bot_instance.cogs),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        return jsonify({'status': 'offline', 'timestamp': datetime.now(timezone.utc).isoformat()})
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
                'exported_at': datetime.now(timezone.utc).isoformat(),
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

def _check_nacl():
    try:
        import nacl
        return nacl.__version__
    except ImportError:
        return False
@app.route('/api/health')
@limiter.exempt
def health_check():
    """Health check endpoint - no auth required"""
    cogs_loaded = list(bot_instance.cogs.keys()) if bot_instance and bot_instance.is_ready() else []
    checks = {
        'bot': bot_instance.is_ready() if bot_instance else False,
        'bot_guilds': len(bot_instance.guilds) if bot_instance and bot_instance.is_ready() else 0,
        'session_active': 'user_id' in session,
        'cache': cache.cache is not None,
        'cogs': cogs_loaded,
        'music_loaded': 'Music' in cogs_loaded,
        'cog_errors': getattr(bot_instance, 'cog_errors', {}),
        'nacl_installed': _check_nacl(),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    status = 'healthy' if checks['bot'] else 'degraded'
    # Always return 200 so Render health checks pass even while bot is connecting
    return jsonify({'status': status, 'checks': checks}), 200


@app.route('/api/server/<server_id>/bot-analyzer')
@require_auth
def get_bot_analyzer(server_id):
    """Get bot analyzer data for a server"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        analyzer_cog = bot_instance.get_cog('BotAnalyzer')
        if not analyzer_cog:
            return jsonify({'error': 'BotAnalyzer cog not loaded'}), 503

        raw = analyzer_cog.get_guild_data(int(server_id))
        bots = []
        for bid, entry in raw.items():
            member = guild.get_member(int(bid))
            cmds = sorted(entry.get('commands', {}).items(), key=lambda x: x[1].get('count', 0), reverse=True)
            bots.append({
                'id': bid,
                'name': entry.get('name', f'Bot {bid}'),
                'display_name': entry.get('display_name', entry.get('name', f'Bot {bid}')),
                'avatar': entry.get('avatar') or (str(member.display_avatar.url) if member else None),
                'online': str(member.status) != 'offline' if member else False,
                'message_count': entry.get('message_count', 0),
                'command_count': len(entry.get('commands', {})),
                'prefixes': list(entry.get('prefixes', [])),
                'top_commands': [{'name': k, 'count': v.get('count', 0), 'example': v.get('example_response', '')[:100]} for k, v in cmds[:10]],
                'first_seen': entry.get('first_seen', ''),
                'last_seen': entry.get('last_seen', ''),
            })
        bots.sort(key=lambda x: x['message_count'], reverse=True)
        return jsonify({'bots': bots, 'total': len(bots), 'timestamp': datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.error(f"Bot analyzer error: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/api/server/<server_id>/audit')
@require_auth
def get_audit_log(server_id):
    """Get recent audit log events — combines in-memory cache + Discord audit log"""
    try:
        cached = dashboard_cache.get('audit_log', {}).get(str(server_id), [])
        if cached:
            return jsonify({'events': cached[:50]})
        # Fallback: pull from Discord audit log via bot
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'events': []})
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'events': []})
        async def _fetch_audit():
            events = []
            try:
                async for entry in guild.audit_logs(limit=50):
                    events.append({
                        'type': str(entry.action).split('.')[-1].lower(),
                        'user': str(entry.user) if entry.user else 'Unknown',
                        'target': str(entry.target) if entry.target else '',
                        'reason': entry.reason or '',
                        'timestamp': entry.created_at.isoformat(),
                        'guild_id': str(server_id),
                    })
            except Exception:
                pass
            return events
        loop = bot_instance.loop
        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_fetch_audit(), loop)
            events = future.result(timeout=10)
            return jsonify({'events': events})
        return jsonify({'events': []})
    except Exception as e:
        logger.error(f"Audit log error: {e}")
        return jsonify({'events': []})

@app.route('/api/server/<server_id>/live-stats')
@require_auth
def get_live_stats(server_id):
    """Get today's live activity counters for a server"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        stats = bot_instance._get_live_stats(str(server_id))
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)
        return jsonify({
            'messages_today': stats['messages'],
            'joins_today': stats['joins'],
            'leaves_today': stats['leaves'],
            'commands_today': stats.get('commands', 0),
            'online_now': online,
            'member_count': guild.member_count,
            'date': stats['date'],
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting live stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/invite')
def invite():
    """Public bot invite page"""
    client_id = os.getenv('DISCORD_CLIENT_ID', '')
    # Fall back to bot's own application ID if env var not set
    if not client_id and bot_instance and bot_instance.is_ready():
        client_id = str(bot_instance.user.id)
    invite_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={client_id}"
        f"&permissions=8"
        f"&scope=bot%20applications.commands"
    ) if client_id else '#'
    return render_template('invite.html', invite_url=invite_url, client_id=client_id)

@app.route('/terms')
def terms():
    """Terms of Service page"""
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    """Privacy Policy page"""
    return render_template('privacy.html')

# ===== Roblox Integration API Endpoints =====

@app.route('/api/server/<int:server_id>/roblox/linked-members')
@require_auth
def get_roblox_linked_members(server_id):
    """Get all linked Roblox accounts for a specific server"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox integration not loaded'}), 503
        
        guild = bot_instance.get_guild(server_id)
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        is_demo = not roblox_cog.has_game_api
        members = []
        for discord_id, member_info in roblox_cog.clan_members.items():
            # Filter to this guild only
            if not guild.get_member(discord_id):
                continue
            
            player_data = roblox_cog.player_cache.get(discord_id)
            discord_member = guild.get_member(discord_id)
            
            member_entry = {
                'discord_id': discord_id,
                'discord_name': discord_member.display_name if discord_member else f'User {discord_id}',
                'discord_avatar': str(discord_member.display_avatar.url) if discord_member else None,
                'roblox_username': member_info['roblox_username'],
                'roblox_id': member_info['roblox_id'],
                'linked_at': member_info['linked_at'],
                'source': member_info.get('source', 'manual'),
                # real-time data from cache
                'avatar_url':    player_data.get('avatar_url')      if player_data else None,
                'is_online':     player_data.get('is_online', False) if player_data else False,
                'is_in_game':    player_data.get('is_in_game', False) if player_data else False,
                'last_location': player_data.get('last_location', 'Offline') if player_data else 'Offline',
                'friend_count':  player_data.get('friend_count', 0) if player_data else 0,
                'badge_count':   player_data.get('badge_count', 0)  if player_data else 0,
                'stats':         player_data.get('stats', {'has_game_data': False}) if player_data else {'has_game_data': False},
                'last_updated':  player_data.get('last_updated')     if player_data else None,
            }
            
            members.append(member_entry)
        
        return jsonify({
            'members': members,
            'total': len(members),
            'is_demo': is_demo,
            'auto_dm_enabled': server_id in roblox_cog.auto_dm_guilds,
            'timestamp': datetime.now(timezone.utc).isoformat()
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
            # Fetch fresh data using thread-safe coroutine scheduling
            member_info = roblox_cog.clan_members[discord_id]
            loop = bot_instance.loop
            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    roblox_cog.fetch_player_data(discord_id, member_info['roblox_username']),
                    loop
                )
                player_data = future.result(timeout=10)
            else:
                return jsonify({'error': 'Bot event loop not available'}), 503
        
        if not player_data:
            return jsonify({'error': 'Failed to fetch player data'}), 500
        
        return jsonify(player_data)
    except Exception as e:
        logger.error(f"Error getting player stats: {e}")
        return jsonify({'error': 'Failed to get player stats'}), 500


@app.route('/api/server/<int:server_id>/roblox/link', methods=['POST'])
@require_auth
def roblox_link_member(server_id):
    """Link a Discord member to a Roblox username from the dashboard"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox integration not loaded'}), 503
        data = request.get_json() or {}
        discord_id = int(data.get('discord_id', 0))
        roblox_username = data.get('roblox_username', '').strip()
        if not discord_id or not roblox_username:
            return jsonify({'error': 'discord_id and roblox_username required'}), 400
        loop = bot_instance.loop
        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                roblox_cog.get_user_by_username(roblox_username), loop
            )
            user_info = future.result(timeout=10)
        else:
            return jsonify({'error': 'Bot event loop not available'}), 503
        if not user_info:
            return jsonify({'error': f'Roblox user "{roblox_username}" not found'}), 404
        roblox_cog.clan_members[discord_id] = {
            'discord_id': discord_id,
            'roblox_username': user_info['name'],
            'roblox_id': user_info['id'],
            'linked_at': datetime.now(timezone.utc).isoformat(),
            'source': 'dashboard'
        }
        roblox_cog._save_links()
        return jsonify({'success': True, 'roblox_username': user_info['name'], 'roblox_id': user_info['id']})
    except Exception as e:
        logger.error(f"Error linking Roblox member: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<int:server_id>/roblox/unlink/<int:discord_id>', methods=['DELETE'])
@require_auth
def roblox_unlink_member(server_id, discord_id):
    """Unlink a Discord member from Roblox"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox integration not loaded'}), 503
        if discord_id not in roblox_cog.clan_members:
            return jsonify({'error': 'Member not linked'}), 404
        del roblox_cog.clan_members[discord_id]
        roblox_cog.player_cache.pop(discord_id, None)
        roblox_cog._save_links()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error unlinking Roblox member: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<int:server_id>/roblox/refresh/<int:discord_id>', methods=['POST'])
@require_auth
def roblox_refresh_member(server_id, discord_id):
    """Force refresh cached stats for a member"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox integration not loaded'}), 503
        if discord_id not in roblox_cog.clan_members:
            return jsonify({'error': 'Member not linked'}), 404
        # Clear cache to force refresh
        roblox_cog.player_cache.pop(discord_id, None)
        member_info = roblox_cog.clan_members[discord_id]
        loop = bot_instance.loop
        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                roblox_cog.fetch_player_data(discord_id, member_info['roblox_username']), loop
            )
            player_data = future.result(timeout=10)
        else:
            return jsonify({'error': 'Bot event loop not available'}), 503
        return jsonify({'success': True, 'data': player_data})
    except Exception as e:
        logger.error(f"Error refreshing Roblox member: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<int:server_id>/roblox/clan-stats')
@require_auth
def get_roblox_clan_stats_server(server_id):
    """Get aggregated clan statistics for a specific server"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox integration not loaded'}), 503
        guild = bot_instance.get_guild(server_id)
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        is_demo = not roblox_cog.has_game_api
        all_stats = []
        online_count = 0
        playing_count = 0
        for discord_id, member_info in roblox_cog.clan_members.items():
            if not guild.get_member(discord_id):
                continue
            player_data = roblox_cog.player_cache.get(discord_id)
            if player_data:
                all_stats.append(player_data)
                if player_data.get('is_online'):
                    online_count += 1
                if player_data.get('is_in_game'):
                    playing_count += 1
        total_playtime = sum(p.get('stats', {}).get('playtime', 0) for p in all_stats)
        total_kills = sum(p.get('stats', {}).get('kills', 0) for p in all_stats)
        total_deaths = sum(p.get('stats', {}).get('deaths', 0) for p in all_stats)
        avg_level = sum(p.get('stats', {}).get('level', 0) for p in all_stats) / len(all_stats) if all_stats else 0
        return jsonify({
            'total_linked': len([d for d in roblox_cog.clan_members if guild.get_member(d)]),
            'tracked_members': len(all_stats),
            'online_members': online_count,
            'playing_now': playing_count,
            'is_demo': is_demo,
            'totals': {
                'playtime_hours': total_playtime // 3600,
                'kills': total_kills,
                'deaths': total_deaths,
                'kd_ratio': round(total_kills / max(total_deaths, 1), 2)
            },
            'averages': {'level': round(avg_level, 2)},
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting clan stats: {e}")
        return jsonify({'error': 'Failed to get clan stats'}), 500

@app.route('/api/leaderboard/<category>')
@require_auth
def get_activity_leaderboard(category):
    """Get real Discord activity leaderboard"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        server_id = request.args.get('server_id')
        guild = bot_instance.get_guild(int(server_id)) if server_id else (bot_instance.guilds[0] if bot_instance.guilds else None)
        if not guild:
            return jsonify({'error': 'No guild found'}), 404

        # Use Leveling cog data as the activity source
        lvl_cog = bot_instance.get_cog('Leveling')
        entries = []
        if lvl_cog:
            g = lvl_cog._guild(guild.id)
            for uid, stats in g.get('users', {}).items():
                member = guild.get_member(int(uid))
                xp = stats.get('xp', 0)
                msgs = stats.get('messages', 0)
                from cogs.leveling import _xp_progress
                level, _, _ = _xp_progress(xp)
                score = xp
                entries.append({
                    'user_id': uid,
                    'name': member.display_name if member else f'User {uid}',
                    'avatar': str(member.display_avatar.url) if member else None,
                    'messages': msgs,
                    'voice_seconds': 0,
                    'reactions': 0,
                    'level': level,
                    'xp': xp,
                    'score': score,
                })

        key_map = {
            'score': lambda x: x['score'],
            'messages': lambda x: x['messages'],
            'voice': lambda x: x['voice_seconds'],
            'reactions': lambda x: x['reactions'],
            'level': lambda x: x['level'],
        }
        entries.sort(key=key_map.get(category, key_map['score']), reverse=True)

        return jsonify({
            'category': category,
            'leaderboard': entries[:20],
            'total': len(entries),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return jsonify({'error': 'Failed to get leaderboard'}), 500

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if 'user_id' not in session:
        return False
    
    logger.info(f"Client connected: {session.get('username')}")
    emit('connected', {'message': 'Connected to WAN Bot Dashboard', 'timestamp': datetime.now(timezone.utc).isoformat()})

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
            socketio.emit(event_type, data)
    except Exception as e:
        logger.error(f"Error broadcasting update: {e}")

def start_web_dashboard(bot, host='0.0.0.0', port=5000, ready_event=None):
    """Start the web dashboard using werkzeug threaded server."""
    global bot_instance
    bot_instance = bot

    logger.info(f"🌐 Starting Enhanced Web Dashboard on http://{host}:{port}")

    try:
        from werkzeug.serving import make_server
        server = make_server(host, port, app, threaded=True)
        logger.info(f"✅ Web server bound to port {port}")

        if ready_event:
            ready_event.set()

        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Web server failed: {e}")
        if ready_event:
            ready_event.set()


def start_web_dashboard_with_socket(bot, sock):
    """Legacy — kept for compatibility, delegates to start_web_dashboard."""
    start_web_dashboard(bot)

if __name__ == '__main__':
    print("⚠️  Run this through bot.py, not directly!")
    print("The enhanced web dashboard will start automatically with the bot.")


# ===== GIVEAWAYS API =====

@app.route('/api/server/<server_id>/giveaways')
@require_auth
def get_giveaways(server_id):
    import json as _json, os as _os
    try:
        data = {}
        if _os.path.exists(data_path('giveaways.json')):
            with open(data_path('giveaways.json')) as f:
                data = _json.load(f)
        active = []
        for msg_id, g in data.items():
            if g.get('guild_id') == server_id and not g.get('ended'):
                from datetime import datetime
                ends_at = datetime.fromisoformat(g['ends_at'])
                active.append({
                    'msg_id': msg_id,
                    'prize': g['prize'],
                    'winners': g['winners'],
                    'entries': len(g.get('entries', [])),
                    'ends_ts': int(ends_at.timestamp()),
                })
        return jsonify({'giveaways': active})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/giveaway/start', methods=['POST'])
@require_auth
def start_giveaway(server_id):
    try:
        data = request.json
        prize = data.get('prize', '').strip()
        duration = data.get('duration', '').strip()
        winners = int(data.get('winners', 1))
        channel_id = data.get('channel_id')
        if not prize or not duration:
            return jsonify({'error': 'Prize and duration required'}), 400

        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        giveaway_cog = bot_instance.get_cog('Giveaways')
        if not giveaway_cog:
            return jsonify({'error': 'Giveaway cog not loaded'}), 503

        async def _start():
            ch = guild.get_channel(int(channel_id)) if channel_id else guild.text_channels[0]
            if not ch:
                return {'error': 'Channel not found'}
            # Use cog's parse + create logic
            from cogs.giveaways import _parse_duration, _giveaway_embed, GiveawayView, _save, _load
            from datetime import datetime, timezone, timedelta
            secs = _parse_duration(duration)
            ends_at = datetime.now(timezone.utc) + timedelta(seconds=secs)
            g_data = {
                'prize': prize, 'winners': winners,
                'host_id': str(guild.me.id),
                'guild_id': server_id, 'channel_id': str(ch.id),
                'ends_at': ends_at.isoformat(),
                'entries': [], 'ended': False,
            }
            msg = await ch.send(embed=_giveaway_embed(g_data), view=GiveawayView())
            giveaways = _load()
            giveaways[str(msg.id)] = g_data
            _save(giveaways)
            return {'status': 'started', 'prize': prize}

        future = asyncio.run_coroutine_threadsafe(_start(), bot_instance.loop)
        result = future.result(timeout=15)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/giveaway/end', methods=['POST'])
@require_auth
def end_giveaway_api(server_id):
    try:
        msg_id = request.json.get('message_id')
        giveaway_cog = bot_instance.get_cog('Giveaways') if bot_instance else None
        if not giveaway_cog:
            return jsonify({'error': 'Giveaway cog not loaded'}), 503
        from cogs.giveaways import _load, _save
        giveaways = _load()
        g = giveaways.get(msg_id)
        if not g:
            return jsonify({'error': 'Giveaway not found'}), 404
        async def _end():
            await giveaway_cog._end_giveaway(msg_id, g, giveaways)
            _save(giveaways)
            return {'status': 'ended'}
        future = asyncio.run_coroutine_threadsafe(_end(), bot_instance.loop)
        return jsonify(future.result(timeout=15))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/giveaway/reroll', methods=['POST'])
@require_auth
def reroll_giveaway_api(server_id):
    try:
        msg_id = request.json.get('message_id')
        from cogs.giveaways import _load, _save
        import random
        giveaways = _load()
        g = giveaways.get(msg_id)
        if not g or not g.get('ended'):
            return jsonify({'error': 'Giveaway not found or not ended'}), 404
        entries = g.get('entries', [])
        if not entries:
            return jsonify({'error': 'No entries'}), 400
        new_winners = random.sample(entries, min(g['winners'], len(entries)))
        g['winner_ids'] = new_winners
        _save(giveaways)
        return jsonify({'status': 'rerolled', 'winners': new_winners})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== POLLS API =====

@app.route('/api/server/<server_id>/poll/create', methods=['POST'])
@require_auth
def create_poll_api(server_id):
    try:
        data = request.json
        question = data.get('question', '').strip()
        options = data.get('options', [])
        duration = data.get('duration')
        channel_id = data.get('channel_id')
        if not question or len(options) < 2:
            return jsonify({'error': 'Question and at least 2 options required'}), 400
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        async def _create():
            ch = guild.get_channel(int(channel_id)) if channel_id else guild.text_channels[0]
            from cogs.polls import PollView, _results_embed, _load, _save
            from datetime import datetime, timezone, timedelta
            ends_at = None
            if duration:
                units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
                try:
                    secs = int(duration[:-1]) * units[duration[-1].lower()]
                    ends_at = (datetime.now(timezone.utc) + timedelta(seconds=secs)).isoformat()
                except Exception:
                    pass
            p = {
                'question': question, 'options': options,
                'votes': {str(i): [] for i in range(len(options))},
                'guild_id': server_id, 'channel_id': str(ch.id),
                'host_id': str(guild.me.id),
                'ends_at': ends_at, 'ended': False,
            }
            view = PollView(options)
            msg = await ch.send(embed=_results_embed(p), view=view)
            view2 = PollView(options, str(msg.id))
            await msg.edit(view=view2)
            polls = _load()
            polls[str(msg.id)] = p
            _save(polls)
            return {'status': 'created', 'question': question}

        future = asyncio.run_coroutine_threadsafe(_create(), bot_instance.loop)
        result = future.result(timeout=15)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
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

# ===== MUSIC STATUS STUB =====
@app.route('/server/<server_id>/music')
@require_auth
def music_player_page(server_id):
    """Dedicated YouTube Music-style player page."""
    if not bot_instance:
        return redirect(url_for('index'))
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return redirect(url_for('index'))
    return render_template('music_player.html',
                           server_id=server_id,
                           server_name=guild.name,
                           server_icon=str(guild.icon.url) if guild.icon else '')


@app.route('/api/server/<server_id>/music/search', methods=['POST'])
@require_auth
def music_search(server_id):
    """Search for songs via yt-dlp."""
    try:
        data = request.json or {}
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'No query'}), 400
        import yt_dlp
        results = []
        # Try SoundCloud first, then YouTube
        for prefix in (f"scsearch5:{query}", f"ytsearch5:{query}"):
            try:
                opts = {"format": "bestaudio/best", "quiet": True, "no_warnings": True,
                        "skip_download": True, "noplaylist": True}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(prefix, download=False)
                    for e in (info.get("entries") or []):
                        if not e:
                            continue
                        results.append({
                            "title": e.get("title", "Unknown"),
                            "uploader": e.get("uploader") or e.get("channel") or "Unknown",
                            "duration": e.get("duration", 0),
                            "thumbnail": e.get("thumbnail") or e.get("artwork_url") or "",
                            "url": e.get("webpage_url") or e.get("url") or "",
                            "source": "soundcloud" if "soundcloud" in prefix else "youtube",
                        })
                if results:
                    break
            except Exception:
                continue
        return jsonify({"results": results[:8]})
    except Exception as e:
        logger.error(f"Music search error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/server/<server_id>/music/queue', methods=['GET'])
@require_auth
def music_queue_full(server_id):
    """Get full queue with metadata."""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'queue': []})
        music_cog = bot_instance.get_cog('Music')
        if not music_cog:
            return jsonify({'queue': []})
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'queue': []})
        gp = music_cog._get_player(guild.id)
        queue = []
        for i, s in enumerate(list(gp.queue)):
            queue.append({
                'index': i + 1,
                'title': s.title,
                'uploader': s.uploader,
                'duration': s.duration_str,
                'thumbnail': s.thumbnail or '',
                'url': s.webpage or '',
                'requester': s.requester.display_name if s.requester else 'Unknown',
            })
        return jsonify({'queue': queue, 'total': len(queue)})
    except Exception as e:
        return jsonify({'queue': [], 'error': str(e)})


@app.route('/api/server/<server_id>/music/status')
@require_auth
def music_status(server_id):
    """Get current music player status from the Music cog."""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'playing': False, 'current': None, 'queue': [], 'queue_size': 0, 'volume': 50})
        music_cog = bot_instance.get_cog('Music')
        if not music_cog:
            return jsonify({'playing': False, 'current': None, 'queue': [], 'queue_size': 0, 'volume': 50, 'error': 'Music cog not loaded'})
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'playing': False, 'current': None, 'queue': [], 'queue_size': 0, 'volume': 50})
        gp = music_cog._get_player(guild.id)
        vc = guild.voice_client
        is_playing = bool(vc and (vc.is_playing() or vc.is_paused()))
        current = None
        if gp.current:
            elapsed = gp.current.elapsed
            duration = gp.current.duration or 0
            current = {
                'title': gp.current.title,
                'url': gp.current.webpage,
                'thumbnail': gp.current.thumbnail,
                'duration': gp.current.duration_str,
                'duration_seconds': duration,
                'elapsed': elapsed,
                'uploader': gp.current.uploader,
                'requester': gp.current.requester.display_name if gp.current.requester else 'Unknown',
            }
        queue_full = [
            {
                'index': i + 1,
                'title': s.title,
                'uploader': s.uploader,
                'duration': s.duration_str,
                'duration_seconds': s.duration or 0,
                'thumbnail': s.thumbnail or '',
                'requester': s.requester.display_name if s.requester else 'Unknown',
            }
            for i, s in enumerate(list(gp.queue))
        ]
        return jsonify({
            'playing': is_playing,
            'paused': bool(vc and vc.is_paused()),
            'current': current,
            'track': gp.current.title if gp.current else None,
            'queue': [s['title'] for s in queue_full],
            'queue_full': queue_full,
            'queue_size': len(gp.queue),
            'volume': int(gp.volume * 100),
            'loop': gp.loop,
            'autoplay': gp.autoplay,
            'voice_channel': vc.channel.name if vc else None,
        })
    except Exception as e:
        logger.error(f"Music status error: {e}")
        return jsonify({'playing': False, 'current': None, 'queue': [], 'queue_size': 0, 'volume': 50})


@app.route('/api/server/<server_id>/music/lyrics', methods=['POST'])
@require_auth
def music_lyrics(server_id):
    """Fetch lyrics for a song using multiple fallback APIs."""
    try:
        data = request.json or {}
        title = data.get('title', '').strip()
        artist = data.get('artist', '').strip()
        if not title:
            return jsonify({'error': 'No title'}), 400
        import urllib.request, urllib.parse

        # Clean title: remove feat., (Official), [HD], etc.
        clean_title = re.sub(r'\(.*?\)|\[.*?\]', '', title).strip()
        clean_title = re.sub(r'\s*feat\..*', '', clean_title, flags=re.IGNORECASE).strip()
        clean_title = re.sub(r'\s*ft\..*', '', clean_title, flags=re.IGNORECASE).strip()

        # Parse artist/song from title if not provided
        parts = clean_title.split(' - ', 1)
        if len(parts) == 2:
            artist_name = artist or parts[0].strip()
            song_name = parts[1].strip()
        else:
            artist_name = artist or ''
            song_name = clean_title

        def _try_lyrics_ovh(a, s):
            try:
                url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(a or 'unknown')}/{urllib.parse.quote(s)}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=6)
                d = json.loads(resp.read())
                return d.get('lyrics') or None
            except Exception:
                return None

        def _try_lyricsovh_swap(a, s):
            """Try with artist and song swapped (some songs have artist in title)."""
            if not a:
                return None
            return _try_lyrics_ovh(s, a)

        def _try_happi_dev(a, s):
            """Try happi.dev lyrics API (free tier)."""
            try:
                q = urllib.parse.quote(f"{a} {s}".strip())
                url = f"https://api.happi.dev/v1/music?q={q}&limit=1&apikey=demo"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=5)
                d = json.loads(resp.read())
                results = d.get('result', [])
                if results:
                    # Fetch lyrics for first result
                    lyrics_url = results[0].get('api_lyrics', '')
                    if lyrics_url:
                        req2 = urllib.request.Request(lyrics_url, headers={'User-Agent': 'Mozilla/5.0'})
                        resp2 = urllib.request.urlopen(req2, timeout=5)
                        d2 = json.loads(resp2.read())
                        return d2.get('result', {}).get('lyrics') or None
            except Exception:
                return None

        def _try_lrclib(a, s):
            """Try lrclib.net — free, no key needed."""
            try:
                q = urllib.parse.urlencode({'q': f"{a} {s}".strip()})
                url = f"https://lrclib.net/api/search?{q}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=6)
                results = json.loads(resp.read())
                if results:
                    plain = results[0].get('plainLyrics') or results[0].get('syncedLyrics', '')
                    if plain:
                        # Strip timestamps from synced lyrics
                        plain = re.sub(r'\[\d+:\d+\.\d+\]', '', plain).strip()
                        return plain if len(plain) > 20 else None
            except Exception:
                return None

        # Try all sources in order
        lyrics = (
            _try_lyrics_ovh(artist_name, song_name) or
            _try_lrclib(artist_name, song_name) or
            _try_lyrics_ovh(artist_name, clean_title) or
            _try_lrclib(artist_name, clean_title) or
            _try_lrclib('', song_name) or
            _try_lyricsovh_swap(artist_name, song_name)
        )

        if lyrics:
            return jsonify({'lyrics': lyrics.strip()})
        return jsonify({'lyrics': None, 'error': 'Lyrics not found'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/music/reorder', methods=['POST'])
@require_auth
def music_reorder(server_id):
    """Reorder queue by moving a song from one index to another."""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        music_cog = bot_instance.get_cog('Music')
        guild = bot_instance.get_guild(int(server_id))
        if not guild or not music_cog:
            return jsonify({'error': 'Not found'}), 404
        data = request.json or {}
        from_idx = int(data.get('from', 0))  # 0-based
        to_idx = int(data.get('to', 0))      # 0-based
        gp = music_cog._get_player(guild.id)
        q = list(gp.queue)
        if 0 <= from_idx < len(q) and 0 <= to_idx < len(q):
            song = q.pop(from_idx)
            q.insert(to_idx, song)
            from collections import deque
            gp.queue = deque(q)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/music/play', methods=['POST'])
@require_auth
def music_play(server_id):
    """Play a song from the dashboard."""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        music_cog = bot_instance.get_cog('Music')
        if not music_cog:
            return jsonify({'error': 'Music cog not loaded'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        data = request.json or {}
        query = data.get('query', '').strip()
        channel_id = data.get('channel_id')
        if not query:
            return jsonify({'error': 'No query provided'}), 400

        async def _play():
            # Find a voice channel to join
            vc = guild.voice_client
            if not vc:
                target_ch = None
                if channel_id:
                    target_ch = guild.get_channel(int(channel_id))
                if not target_ch:
                    for ch in guild.voice_channels:
                        if len(ch.members) > 0:
                            target_ch = ch
                            break
                if not target_ch and guild.voice_channels:
                    target_ch = guild.voice_channels[0]
                if not target_ch:
                    return {'error': 'No voice channel available'}
                try:
                    vc = await target_ch.connect()
                except Exception as e:
                    return {'error': f'Could not join voice channel: {e}'}

            # Find a text channel to send now-playing embed to
            text_ch = None
            for name in ('music', 'bot-commands', 'general', 'chat', 'lounge'):
                text_ch = discord.utils.get(guild.text_channels, name=name)
                if text_ch:
                    break
            if not text_ch and guild.text_channels:
                text_ch = guild.text_channels[0]

            requester = guild.me
            song = await music_cog._fetch_song(query, requester)
            if not song:
                return {'error': f'Song not found for: {query}. Try a YouTube URL directly.'}

            gp = music_cog._get_player(guild.id)
            gp.queue.append(song)
            if not vc.is_playing() and not vc.is_paused():
                music_cog._play_next(text_ch, guild, gp)
                return {'status': 'playing', 'title': song.title}
            else:
                return {'status': 'queued', 'title': song.title}

        future = asyncio.run_coroutine_threadsafe(_play(), bot_instance.loop)
        result = future.result(timeout=15)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error(f"Music play error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/music/control', methods=['POST'])
@require_auth
def music_control(server_id):
    """Control music playback: pause, resume, skip, stop, volume, shuffle, loop."""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        music_cog = bot_instance.get_cog('Music')
        if not music_cog:
            return jsonify({'error': 'Music cog not loaded'}), 503
        data = request.json or {}
        action = data.get('action', '')
        vc = guild.voice_client
        gp = music_cog._get_player(guild.id)

        if action == 'pause':
            if vc and vc.is_playing():
                vc.pause()
        elif action == 'resume':
            if vc and vc.is_paused():
                vc.resume()
        elif action == 'skip':
            if vc and (vc.is_playing() or vc.is_paused()):
                vc.stop()
        elif action == 'stop':
            gp.queue.clear()
            gp.loop = False
            if vc:
                vc.stop()
                future = asyncio.run_coroutine_threadsafe(vc.disconnect(), bot_instance.loop)
                future.result(timeout=5)
        elif action == 'shuffle':
            import random
            q = list(gp.queue)
            random.shuffle(q)
            from collections import deque
            gp.queue = deque(q)
        elif action == 'loop':
            gp.loop = not gp.loop
        elif action == 'volume':
            vol = int(data.get('value', 50))
            vol = max(1, min(100, vol))
            gp.volume = vol / 100
            if vc and vc.source:
                vc.source.volume = gp.volume
        elif action == 'remove':
            idx = int(data.get('index', 1)) - 1
            q = list(gp.queue)
            if 0 <= idx < len(q):
                q.pop(idx)
                from collections import deque
                gp.queue = deque(q)
        else:
            return jsonify({'error': f'Unknown action: {action}'}), 400

        return jsonify({'success': True, 'action': action})
    except Exception as e:
        logger.error(f"Music control error: {e}")
        return jsonify({'error': str(e)}), 500

# ===== MANAGEMENT API ENDPOINTS =====
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

# ===== CHATBOT API =====
_CHATBOT_FILE = data_path('chatbot_data.json')

def _load_chatbot():
    try:
        if os.path.exists(_CHATBOT_FILE):
            with open(_CHATBOT_FILE) as f:
                raw = json.load(f)
            # Migrate legacy format (list → dict)
            migrated = {}
            for k, v in raw.items():
                if isinstance(v, list):
                    migrated[k] = {'enabled': True, 'channels': v}
                else:
                    migrated[k] = v
            return migrated
    except Exception:
        pass
    return {}

def _save_chatbot(data):
    try:
        with open(_CHATBOT_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Chatbot save error: {e}")

def _chatbot_guild(data, server_id):
    """Get or create guild entry in chatbot data."""
    sid = str(server_id)
    if sid not in data:
        data[sid] = {'enabled': True, 'channels': []}
    elif isinstance(data[sid], list):
        data[sid] = {'enabled': True, 'channels': data[sid]}
    return data[sid]

@app.route('/api/server/<server_id>/chatbot', methods=['GET'])
@require_auth
def get_chatbot_config(server_id):
    data = _load_chatbot()
    gd = _chatbot_guild(data, server_id)
    channels = gd.get('channels', [])
    enabled = gd.get('enabled', True)
    result = []
    if bot_instance and bot_instance.is_ready():
        guild = bot_instance.get_guild(int(server_id))
        if guild:
            for ch_id in channels:
                ch = guild.get_channel(int(ch_id))
                result.append({'id': ch_id, 'name': ch.name if ch else ch_id})
    return jsonify({'channels': result, 'enabled': enabled})

@app.route('/api/server/<server_id>/chatbot', methods=['POST'])
@require_auth
def save_chatbot_config(server_id):
    body = request.get_json(silent=True) or {}
    action = body.get('action')  # 'add', 'remove', or 'toggle'
    data = _load_chatbot()
    gd = _chatbot_guild(data, server_id)

    if action == 'toggle':
        gd['enabled'] = not gd.get('enabled', True)
        # Sync to live cog
        if bot_instance:
            cog = bot_instance.get_cog('Chatbot')
            if cog:
                cog._guild_data(str(server_id))['enabled'] = gd['enabled']
        _save_chatbot(data)
        return jsonify({'success': True, 'enabled': gd['enabled']})

    channel_id = str(body.get('channel_id', ''))
    if not channel_id:
        return jsonify({'error': 'channel_id required'}), 400

    channels = gd.setdefault('channels', [])
    if action == 'add':
        if channel_id not in channels:
            channels.append(channel_id)
        if bot_instance:
            cog = bot_instance.get_cog('Chatbot')
            if cog:
                cog_gd = cog._guild_data(str(server_id))
                if channel_id not in cog_gd['channels']:
                    cog_gd['channels'].append(channel_id)
    elif action == 'remove':
        gd['channels'] = [c for c in channels if c != channel_id]
        if bot_instance:
            cog = bot_instance.get_cog('Chatbot')
            if cog:
                cog_gd = cog._guild_data(str(server_id))
                cog_gd['channels'] = [c for c in cog_gd['channels'] if c != channel_id]
    else:
        return jsonify({'error': 'action must be add, remove, or toggle'}), 400

    _save_chatbot(data)
    return jsonify({'success': True, 'channels': gd['channels'], 'enabled': gd['enabled']})

# ===== FEATURE TOGGLES =====
# Stored per-guild in a JSON file: {guild_id: {feature: bool}}
_FEATURES_FILE = data_path('feature_toggles.json')
_DEFAULT_FEATURES = {
    'leveling': True, 'automod': True, 'antiraid': True, 'smartmod': True,
    'welcome': True, 'translation': True, 'economy': True, 'tickets': True,
    'starboard': True, 'roblox': True, 'music': True, 'giveaways': True,
    'polls': True, 'badges': True, 'voicexp': True, 'modlog': True,
}

def _load_feature_toggles():
    try:
        if os.path.exists(_FEATURES_FILE):
            with open(_FEATURES_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_feature_toggles(data):
    try:
        with open(_FEATURES_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving feature toggles: {e}")

@app.route('/api/server/<server_id>/features', methods=['GET'])
@require_auth
def get_features(server_id):
    data = _load_feature_toggles()
    guild_features = {**_DEFAULT_FEATURES, **data.get(str(server_id), {})}
    return jsonify({'features': guild_features})

@app.route('/api/server/<server_id>/features', methods=['POST'])
@require_auth
def set_features(server_id):
    body = request.get_json() or {}
    feature = body.get('feature')
    enabled = body.get('enabled')
    if feature is None or enabled is None:
        return jsonify({'error': 'feature and enabled required'}), 400
    data = _load_feature_toggles()
    if str(server_id) not in data:
        data[str(server_id)] = {}
    data[str(server_id)][feature] = bool(enabled)
    _save_feature_toggles(data)
    return jsonify({'success': True, 'feature': feature, 'enabled': bool(enabled)})

# ===== AI BRAIN API =====

@app.route('/api/server/<server_id>/ai-brain', methods=['GET'])
@require_auth
def get_ai_brain(server_id):
    """Get AI Brain status and recent actions for a server."""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        ai_cog = bot_instance.get_cog('AIBrain')
        chatbot_cog = bot_instance.get_cog('Chatbot')

        guild_id = str(server_id)
        ai_mod_enabled = guild_id in ai_cog._mod_enabled if ai_cog else False

        # AI welcome settings
        ai_welcome_enabled = False
        ai_welcome_channel = None
        if ai_cog:
            settings = ai_cog.data.get('settings', {})
            ai_welcome_enabled = guild_id in set(settings.get('ai_welcome_guilds', []))
            ai_welcome_channel = settings.get('ai_welcome_channels', {}).get(guild_id)

        # Chatbot enabled
        chatbot_enabled = False
        if chatbot_cog:
            chatbot_enabled = chatbot_cog._guild_data(guild_id).get('enabled', True)

        # Recent AI actions for this guild
        actions = []
        if ai_cog:
            actions = [a for a in ai_cog.actions_log if a.get('guild') == guild.name][:20]

        # Channel list for welcome channel selector
        channels = [{'id': str(c.id), 'name': c.name} for c in guild.text_channels]

        import os as _os
        gemini_active = bool(_os.getenv('GEMINI_API_KEY', ''))

        return jsonify({
            'gemini_active': gemini_active,
            'ai_mod_enabled': ai_mod_enabled,
            'ai_welcome_enabled': ai_welcome_enabled,
            'ai_welcome_channel': ai_welcome_channel,
            'chatbot_enabled': chatbot_enabled,
            'actions': actions,
            'channels': channels,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"AI Brain GET error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/ai-brain', methods=['POST'])
@require_auth
def set_ai_brain(server_id):
    """Toggle AI Brain features for a server."""
    try:
        body = request.get_json(silent=True) or {}
        feature = body.get('feature')
        enabled = body.get('enabled')
        guild_id = str(server_id)

        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        ai_cog = bot_instance.get_cog('AIBrain')
        chatbot_cog = bot_instance.get_cog('Chatbot')

        if feature == 'mod':
            if not ai_cog:
                return jsonify({'error': 'AI Brain cog not loaded'}), 503
            if enabled:
                ai_cog._mod_enabled.add(guild_id)
            else:
                ai_cog._mod_enabled.discard(guild_id)
            ai_cog._save_settings()
            return jsonify({'success': True, 'feature': 'mod', 'enabled': enabled})

        elif feature == 'welcome':
            if not ai_cog:
                return jsonify({'error': 'AI Brain cog not loaded'}), 503
            if 'settings' not in ai_cog.data:
                ai_cog.data['settings'] = {}
            settings = ai_cog.data['settings']
            welcome_guilds = set(settings.get('ai_welcome_guilds', []))
            if enabled:
                welcome_guilds.add(guild_id)
            else:
                welcome_guilds.discard(guild_id)
            settings['ai_welcome_guilds'] = list(welcome_guilds)
            from cogs.ai_brain import _save as _ai_save
            _ai_save(ai_cog.data)
            return jsonify({'success': True, 'feature': 'welcome', 'enabled': enabled})

        elif feature == 'welcome_channel':
            if not ai_cog:
                return jsonify({'error': 'AI Brain cog not loaded'}), 503
            channel_id = str(body.get('channel_id', ''))
            if not channel_id:
                return jsonify({'error': 'channel_id required'}), 400
            if 'settings' not in ai_cog.data:
                ai_cog.data['settings'] = {}
            settings = ai_cog.data['settings']
            if 'ai_welcome_channels' not in settings:
                settings['ai_welcome_channels'] = {}
            settings['ai_welcome_channels'][guild_id] = channel_id
            from cogs.ai_brain import _save as _ai_save
            _ai_save(ai_cog.data)
            return jsonify({'success': True, 'feature': 'welcome_channel', 'channel_id': channel_id})

        elif feature == 'chatbot':
            if not chatbot_cog:
                return jsonify({'error': 'Chatbot cog not loaded'}), 503
            chatbot_cog._guild_data(guild_id)['enabled'] = bool(enabled)
            from cogs.chatbot import _save as _cb_save
            _cb_save(chatbot_cog.data)
            return jsonify({'success': True, 'feature': 'chatbot', 'enabled': enabled})

        return jsonify({'error': 'Unknown feature'}), 400
    except Exception as e:
        logger.error(f"AI Brain POST error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<server_id>/ai-report')
@require_auth
def get_ai_report(server_id):
    """Generate an AI report for the server using Gemini."""
    try:
        import os as _os
        gemini_key = _os.getenv('GEMINI_API_KEY', '')
        if not gemini_key:
            return jsonify({'error': 'GEMINI_API_KEY not set. Add it to your Render environment variables.'}), 400

        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        stats = {}
        if hasattr(bot_instance, '_get_live_stats'):
            stats = bot_instance._get_live_stats(str(server_id))

        ai_cog = bot_instance.get_cog('AIBrain')
        actions = []
        if ai_cog:
            actions = [a for a in ai_cog.actions_log if a.get('guild') == guild.name][:10]

        cogs_loaded = list(bot_instance.cogs.keys())
        cog_errors = getattr(bot_instance, 'cog_errors', {})

        prompt = (
            f"You are an expert Discord bot analyst. Generate a comprehensive server report.\n\n"
            f"SERVER: {guild.name}\n"
            f"Members: {guild.member_count} | Channels: {len(guild.text_channels)} | Roles: {len(guild.roles)}\n"
            f"Messages today: {stats.get('messages', 0)} | Joins: {stats.get('joins', 0)} | Leaves: {stats.get('leaves', 0)}\n"
            f"Bot features loaded: {len(cogs_loaded)} cogs\n"
            f"Failed cogs: {list(cog_errors.keys()) if cog_errors else 'None'}\n"
            f"Recent AI actions: {len(actions)} (mod/welcome/suggestions)\n\n"
            f"Write a report with these sections:\n"
            f"1. 📊 Server Health (overall status)\n"
            f"2. ✅ What's Working Well\n"
            f"3. 🔧 What Needs Attention\n"
            f"4. 💡 Top 3 Improvement Suggestions\n"
            f"5. 🤖 AI Automation Status\n\n"
            f"Be specific, actionable, and encouraging. Keep it concise."
        )

        import urllib.request as _urlreq
        import json as _json
        payload = _json.dumps({
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'maxOutputTokens': 500, 'temperature': 0.7}
        }).encode()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
        req = _urlreq.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with _urlreq.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read())
        report = data['candidates'][0]['content']['parts'][0]['text'].strip()
        return jsonify({'report': report, 'timestamp': datetime.now(timezone.utc).isoformat()})

    except Exception as e:
        logger.error(f"AI report error: {e}", exc_info=True)
        return jsonify({'error': f'Failed to generate report: {str(e)}'}), 500


@app.route('/api/ai-coder/status')
@require_auth
def get_ai_coder_status():
    """Get AI Coder status and improvement history."""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        cog = bot_instance.get_cog('AICoder')
        if not cog:
            return jsonify({'error': 'AI Coder not loaded'}), 503
        return jsonify(cog.get_status())
    except Exception as e:
        logger.error(f"AI Coder status error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai-coder/run', methods=['POST'])
@require_auth
def run_ai_coder():
    """Trigger an immediate AI improvement cycle."""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        cog = bot_instance.get_cog('AICoder')
        if not cog:
            return jsonify({'error': 'AI Coder not loaded'}), 503
        # Schedule the async task
        import asyncio
        future = asyncio.run_coroutine_threadsafe(cog.run_cycle_now(), bot_instance.loop)
        result = future.result(timeout=5)
        return jsonify({'status': result, 'timestamp': datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.error(f"AI Coder run error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai-coder/generated/<key>')
@require_auth
def get_ai_coder_generated(key):
    """Get AI-generated content for a specific feature."""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        cog = bot_instance.get_cog('AICoder')
        if not cog:
            return jsonify({'error': 'AI Coder not loaded'}), 503
        items = cog.get_generated(key)
        return jsonify({'key': key, 'items': items, 'count': len(items)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== REGISTER / OTP AUTH =====
_USERS_FILE = data_path('dashboard_users.json')
_OTP_STORE = {}  # email -> {otp, expires, pending_user}

def _load_users():
    try:
        if os.path.exists(_USERS_FILE):
            with open(_USERS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_users(data):
    try:
        with open(_USERS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

def _send_otp_email(to_email: str, otp: str, username: str) -> bool:
    """Send OTP via SMTP. Requires SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS env vars."""
    import smtplib
    from email.mime.text import MIMEText
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.warning("SMTP not configured — OTP email not sent")
        return False
    try:
        msg = MIMEText(
            f"Hi {username},\n\nYour WAN Bot Dashboard verification code is:\n\n"
            f"  {otp}\n\nThis code expires in 10 minutes.\n\n"
            f"If you didn't request this, ignore this email.",
            'plain'
        )
        msg['Subject'] = f'WAN Bot Dashboard — Verification Code: {otp}'
        msg['From'] = smtp_user
        msg['To'] = to_email
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, [to_email], msg.as_string())
        return True
    except Exception as e:
        logger.error(f"SMTP error: {e}")
        return False

@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("3 per minute")
def api_register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not username or not email or not password:
        return jsonify({'success': False, 'error': 'All fields required'}), 400
    if len(username) < 3 or len(username) > 32:
        return jsonify({'success': False, 'error': 'Username must be 3–32 characters'}), 400
    if len(password) < 8:
        return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
    if '@' not in email or '.' not in email:
        return jsonify({'success': False, 'error': 'Invalid email address'}), 400
    users = _load_users()
    if username in users:
        return jsonify({'success': False, 'error': 'Username already taken'}), 409
    if any(u.get('email') == email for u in users.values()):
        return jsonify({'success': False, 'error': 'Email already registered'}), 409
    # Generate OTP
    import random as _r
    otp = str(_r.randint(100000, 999999))
    _OTP_STORE[email] = {
        'otp': otp,
        'expires': datetime.now(timezone.utc).timestamp() + 600,
        'pending': {'username': username, 'email': email, 'password_hash': hash_password(password).decode()}
    }
    sent = _send_otp_email(email, otp, username)
    if not sent:
        # Dev fallback: log OTP to console
        logger.info(f"[DEV] OTP for {email}: {otp}")
    return jsonify({'success': True, 'email_sent': sent, 'dev_otp': otp if not sent else None})

@app.route('/api/auth/verify-otp', methods=['POST'])
@limiter.limit("5 per minute")
def api_verify_otp():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()
    entry = _OTP_STORE.get(email)
    if not entry:
        return jsonify({'success': False, 'error': 'No pending verification for this email'}), 400
    if datetime.now(timezone.utc).timestamp() > entry['expires']:
        del _OTP_STORE[email]
        return jsonify({'success': False, 'error': 'OTP expired — please register again'}), 400
    if entry['otp'] != otp:
        return jsonify({'success': False, 'error': 'Incorrect code'}), 400
    # Confirm user
    pending = entry['pending']
    users = _load_users()
    users[pending['username']] = {
        'email': pending['email'],
        'password_hash': pending['password_hash'],
        'permissions': ['dashboard'],
        'created_at': datetime.now(timezone.utc).isoformat(),
        'verified': True
    }
    _save_users(users)
    del _OTP_STORE[email]
    # Auto-login
    session.permanent = True
    session['user_id'] = pending['username']
    session['username'] = pending['username']
    session['login_time'] = datetime.now(timezone.utc).isoformat()
    return jsonify({'success': True})

@app.route('/api/auth/resend-otp', methods=['POST'])
@limiter.limit("2 per minute")
def api_resend_otp():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    entry = _OTP_STORE.get(email)
    if not entry:
        return jsonify({'success': False, 'error': 'No pending verification'}), 400
    import random as _r
    otp = str(_r.randint(100000, 999999))
    entry['otp'] = otp
    entry['expires'] = datetime.now(timezone.utc).timestamp() + 600
    sent = _send_otp_email(email, otp, entry['pending']['username'])
    if not sent:
        logger.info(f"[DEV] Resent OTP for {email}: {otp}")
    return jsonify({'success': True, 'email_sent': sent, 'dev_otp': otp if not sent else None})

# ===== ROBLOX DM BY ROLE =====
@app.route('/api/server/<int:server_id>/roblox/dm-by-role', methods=['POST'])
@require_auth
def roblox_dm_by_role(server_id):
    """Send DM to all members with a specific role asking for their Roblox username"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        data = request.get_json() or {}
        role_id = int(data.get('role_id', 0))
        if not role_id:
            return jsonify({'error': 'role_id required'}), 400
        guild = bot_instance.get_guild(server_id)
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        role = guild.get_role(role_id)
        if not role:
            return jsonify({'error': 'Role not found'}), 404
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox cog not loaded'}), 503
        loop = bot_instance.loop
        if not (loop and loop.is_running()):
            return jsonify({'error': 'Bot loop not available'}), 503
        unlinked = [m for m in role.members if not m.bot and m.id not in roblox_cog.clan_members]
        already_linked = len(role.members) - len(unlinked) - sum(1 for m in role.members if m.bot)

        async def _dm_role():
            sent = failed = 0
            for member in unlinked:
                try:
                    await roblox_cog._send_roblox_dm(member, guild)
                    sent += 1
                    await asyncio.sleep(0.5)
                except Exception:
                    failed += 1
            logger.info(f"DM-by-role complete for {role.name}: {sent} sent, {failed} failed")

        # Fire and forget
        asyncio.run_coroutine_threadsafe(_dm_role(), loop)
        return jsonify({'success': True, 'sent': len(unlinked), 'failed': 0,
                        'already_linked': already_linked, 'role': role.name,
                        'note': f'Sending DMs to {len(unlinked)} members in background'})
    except Exception as e:
        logger.error(f"DM by role error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<int:server_id>/roblox/dm-all', methods=['POST'])
@require_auth
def roblox_dm_all(server_id):
    """DM ALL unlinked members — fires async in background, returns immediately"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(server_id)
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox cog not loaded'}), 503
        loop = bot_instance.loop
        if not (loop and loop.is_running()):
            return jsonify({'error': 'Bot loop not available'}), 503

        unlinked = [m for m in guild.members if not m.bot and m.id not in roblox_cog.clan_members]
        total = len(unlinked)

        async def _dm_all():
            sent = failed = 0
            for member in unlinked:
                try:
                    await roblox_cog._send_roblox_dm(member, guild)
                    sent += 1
                    await asyncio.sleep(0.6)
                except Exception:
                    failed += 1
            logger.info(f"DM-all complete: {sent} sent, {failed} failed")

        # Fire and forget — don't block the HTTP request
        asyncio.run_coroutine_threadsafe(_dm_all(), loop)
        return jsonify({
            'success': True,
            'sent': total,
            'already_linked': len(roblox_cog.clan_members),
            'failed': 0,
            'note': f'Sending DMs to {total} members in background'
        })
    except Exception as e:
        logger.error(f"DM all error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/server/<int:server_id>/roblox/autodm', methods=['POST'])
@require_auth
def roblox_autodm_toggle(server_id):
    """Toggle auto-DM for new joiners"""
    try:
        roblox_cog = bot_instance.get_cog('RobloxIntegration') if bot_instance else None
        if not roblox_cog:
            return jsonify({'error': 'Roblox cog not loaded'}), 503
        data = request.get_json() or {}
        enabled = bool(data.get('enabled', False))
        if enabled:
            roblox_cog.auto_dm_guilds.add(server_id)
        else:
            roblox_cog.auto_dm_guilds.discard(server_id)
        roblox_cog._save_auto_dm()
        return jsonify({'success': True, 'enabled': enabled})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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


@app.route('/api/server/<server_id>/members/<member_id>/profile')
@require_auth
def get_member_profile(server_id, member_id):
    """Get full member profile: roles, join date, XP, warnings, badges"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        member = guild.get_member(int(member_id))
        if not member:
            return jsonify({'error': 'Member not found'}), 404

        profile = {
            'id': str(member.id),
            'name': member.name,
            'display_name': member.display_name,
            'avatar': str(member.display_avatar.url),
            'bot': member.bot,
            'status': str(member.status),
            'joined_at': member.joined_at.isoformat() if member.joined_at else None,
            'created_at': member.created_at.isoformat(),
            'roles': [{'id': str(r.id), 'name': r.name, 'color': str(r.color)} for r in member.roles if r.name != '@everyone'],
            'top_role': member.top_role.name if member.top_role else None,
            'top_role_color': str(member.top_role.color) if member.top_role else '#99aab5',
            'xp': None, 'level': None, 'messages': None,
            'warnings': [], 'badges': [],
            'voice_seconds': None,
        }

        # XP / Leveling
        lvl_cog = bot_instance.get_cog('Leveling')
        if lvl_cog:
            try:
                from cogs.leveling import _xp_progress
                g = lvl_cog._guild(int(server_id))
                u = g.get('users', {}).get(str(member_id), {})
                xp = u.get('xp', 0)
                level, cur_xp, needed = _xp_progress(xp)
                profile['xp'] = xp
                profile['level'] = level
                profile['messages'] = u.get('messages', 0)
                profile['xp_progress'] = round(cur_xp / needed * 100) if needed else 0
            except Exception:
                pass

        # Warnings — read directly from modlog.json
        try:
            import json as _json
            if os.path.exists(data_path('modlog.json')):
                with open(data_path('modlog.json')) as _f:
                    _ml = _json.load(_f)
                cases = _ml.get('cases', {}).get(str(server_id), [])
                profile['warnings'] = [
                    {'reason': c.get('reason', ''), 'mod': c.get('mod', ''), 'timestamp': c.get('timestamp', '')}
                    for c in cases if str(c.get('target_id')) == str(member_id) and c.get('action') == 'warn'
                ][-5:]
        except Exception:
            pass

        # Badges — read from badges.json
        try:
            import json as _json
            if os.path.exists(data_path('badges.json')):
                with open(data_path('badges.json')) as _f:
                    _bd = _json.load(_f)
                profile['badges'] = list(_bd.get(str(server_id), {}).get(str(member_id), {}).keys())
        except Exception:
            pass

        # Voice XP — read directly from voicexp.json
        try:
            import json as _json
            if os.path.exists(data_path('voicexp.json')):
                with open(data_path('voicexp.json')) as _f:
                    _vxp = _json.load(_f)
                u = _vxp.get(str(server_id), {}).get(str(member_id), {})
                profile['voice_seconds'] = u.get('minutes', 0) * 60
        except Exception:
            pass

        return jsonify(profile)
    except Exception as e:
        logger.error(f"Member profile error: {e}")
        return jsonify({'error': str(e)}), 500


# ===== WELCOME / GOODBYE / PROMOTION / AUTOROLE API =====

@app.route('/api/server/<server_id>/welcome', methods=['GET', 'POST'])
@require_auth
def save_welcome_config(server_id):
    """GET: load welcome config. POST: save welcome/goodbye/promo/autorole config"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        welcome_cog = bot_instance.get_cog('Welcome')
        if not welcome_cog:
            return jsonify({'error': 'Welcome cog not loaded'}), 503

        if request.method == 'GET':
            future = asyncio.run_coroutine_threadsafe(
                welcome_cog._get_cfg(int(server_id)), bot_instance.loop)
            cfg = future.result(timeout=5)
            return jsonify(cfg)

        data = request.json
        future = asyncio.run_coroutine_threadsafe(
            welcome_cog._get_cfg(int(server_id)), bot_instance.loop)
        cfg = future.result(timeout=5)
        # Normalize incoming values
        for k, v in data.items():
            if v is None or v == '':
                continue
            # Store channel/role IDs as strings
            if k.endswith('_channel') or k == 'autorole':
                cfg[k] = str(v)
            # Normalize color: always store as #rrggbb so color picker can read it back
            elif k.endswith('_color'):
                s = str(v).strip().lstrip('#')
                if s.startswith('0x') or s.startswith('0X'):
                    s = s[2:]
                cfg[k] = '#' + s.lower()
            else:
                cfg[k] = v
        # Invalidate in-memory cache so next read gets fresh data
        welcome_cog._cache.pop(str(server_id), None)
        save_future = asyncio.run_coroutine_threadsafe(
            welcome_cog._save_cfg(int(server_id), cfg), bot_instance.loop)
        save_future.result(timeout=5)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Welcome config error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/welcome/test', methods=['POST'])
@require_auth
def test_welcome_message(server_id):
    """Send a test welcome/goodbye message"""
    try:
        body = request.get_json(silent=True) or {}
        msg_type = body.get('type', 'join')
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready — wait a moment and try again'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        welcome_cog = bot_instance.get_cog('Welcome')
        if not welcome_cog:
            return jsonify({'error': 'Welcome cog not loaded'}), 503

        event_map = {'join': 'welcome', 'leave': 'goodbye'}
        event = event_map.get(msg_type, 'welcome')

        cfg_future = asyncio.run_coroutine_threadsafe(
            welcome_cog._get_cfg(int(server_id)), bot_instance.loop)
        cfg = cfg_future.result(timeout=5)
        ch_id = cfg.get(f'{event}_channel')
        if not ch_id:
            return jsonify({'error': f'No {event} channel set — save your config first'}), 400

        # Use the bot member as a stand-in, or first real human member
        member = guild.me
        for m in guild.members:
            if not m.bot:
                member = m
                break

        async def _test():
            await welcome_cog._send_embed(member, cfg, event)

        future = asyncio.run_coroutine_threadsafe(_test(), bot_instance.loop)
        future.result(timeout=10)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Welcome test error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ===== VERIFICATION API =====

@app.route('/api/server/<server_id>/verification', methods=['POST'])
@require_auth
def save_verification(server_id):
    """Save verification config and post verification message"""
    try:
        data = request.json
        method = data.get('method', 'none')
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        if method == 'none':
            return jsonify({'success': True, 'message': 'Verification disabled'})

        channel_id = data.get('channel_id')
        role_id = data.get('role_id')
        if not channel_id or not role_id:
            return jsonify({'error': 'Channel and role required'}), 400

        async def _setup():
            channel = guild.get_channel(int(channel_id))
            role = guild.get_role(int(role_id))
            if not channel:
                return {'error': 'Channel not found'}
            if not role:
                return {'error': 'Role not found'}

            if method == 'reaction':
                msg_text = data.get('message', 'React with ✅ to verify!')
                embed = discord.Embed(title="✅ Verification", description=msg_text, color=0x57f287)
                embed.set_footer(text="React with ✅ below to verify yourself")
                msg = await channel.send(embed=embed)
                await msg.add_reaction('✅')
                # Store config in welcome cog if available
                welcome_cog = bot_instance.get_cog('Welcome')
                if welcome_cog:
                    cfg = await welcome_cog._get_cfg(int(server_id))
                    cfg['verify_message_id'] = str(msg.id)
                    cfg['verify_role_id'] = str(role_id)
                    cfg['verify_channel_id'] = str(channel_id)
                    if data.get('unverify_role'):
                        cfg['unverify_role_id'] = str(data['unverify_role'])
                    await welcome_cog._save_cfg(int(server_id), cfg)
                return {'success': True, 'message_id': str(msg.id)}

            elif method == 'button':
                label = data.get('label', '✅ Verify Me')
                msg_text = data.get('message', 'Click the button below to verify!')
                embed = discord.Embed(title="🔐 Verification", description=msg_text, color=0x5865f2)

                class VerifyButton(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=None)
                    @discord.ui.button(label=label, style=discord.ButtonStyle.success, custom_id=f'verify_{server_id}')
                    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
                        r = interaction.guild.get_role(int(role_id))
                        if r:
                            await interaction.user.add_roles(r, reason="Button verification")
                        await interaction.response.send_message("✅ You've been verified!", ephemeral=True)

                msg = await channel.send(embed=embed, view=VerifyButton())
                return {'success': True, 'message_id': str(msg.id)}

            elif method == 'question':
                question = data.get('question', 'What is the server rule #1?')
                answer = data.get('answer', '').lower().strip()
                embed = discord.Embed(title="❓ Verification Question", description=question, color=0xf59e0b)
                embed.set_footer(text="Reply with your answer in this channel")
                await channel.send(embed=embed)
                # Store Q&A in welcome cog
                welcome_cog = bot_instance.get_cog('Welcome')
                if welcome_cog:
                    cfg = await welcome_cog._get_cfg(int(server_id))
                    cfg['verify_question'] = question
                    cfg['verify_answer'] = answer
                    cfg['verify_role_id'] = str(role_id)
                    cfg['verify_channel_id'] = str(channel_id)
                    await welcome_cog._save_cfg(int(server_id), cfg)
                return {'success': True}

            return {'error': 'Unknown method'}

        future = asyncio.run_coroutine_threadsafe(_setup(), bot_instance.loop)
        result = future.result(timeout=15)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error(f"Verification setup error: {e}")
        return jsonify({'error': str(e)}), 500


# ===== REACTION ROLES API =====

@app.route('/api/server/<server_id>/rr/panel', methods=['POST'])
@require_auth
def create_rr_panel(server_id):
    """Create a reaction role panel"""
    try:
        data = request.json
        title = data.get('title', 'Get Your Roles!')
        description = data.get('description', 'React below to get your roles.')
        channel_id = data.get('channel_id')
        if not channel_id:
            return jsonify({'error': 'Channel required'}), 400
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        async def _create():
            channel = guild.get_channel(int(channel_id))
            if not channel:
                return {'error': 'Channel not found'}
            embed = discord.Embed(title=title, description=description, color=0x7c3aed)
            embed.set_footer(text="React below to get your roles!")
            msg = await channel.send(embed=embed)
            return {'success': True, 'message_id': str(msg.id)}

        future = asyncio.run_coroutine_threadsafe(_create(), bot_instance.loop)
        result = future.result(timeout=10)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error(f"RR panel error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/rr/add', methods=['POST'])
@require_auth
def add_reaction_role(server_id):
    """Add a reaction role to a message"""
    try:
        data = request.json
        message_id = data.get('message_id')
        emoji = data.get('emoji')
        role_id = data.get('role_id')
        if not all([message_id, emoji, role_id]):
            return jsonify({'error': 'message_id, emoji, and role_id required'}), 400
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        rr_cog = bot_instance.get_cog('ReactionRoles')
        if not rr_cog:
            return jsonify({'error': 'ReactionRoles cog not loaded'}), 503

        gid = str(server_id)
        if gid not in rr_cog.data:
            rr_cog.data[gid] = {}
        if message_id not in rr_cog.data[gid]:
            rr_cog.data[gid][message_id] = {}
        rr_cog.data[gid][message_id][emoji] = int(role_id)
        rr_cog._save()

        async def _add_reaction():
            for ch in guild.text_channels:
                try:
                    msg = await ch.fetch_message(int(message_id))
                    await msg.add_reaction(emoji)
                    return {'success': True}
                except Exception:
                    continue
            return {'success': True, 'warning': 'Could not add reaction — message not found in text channels'}

        future = asyncio.run_coroutine_threadsafe(_add_reaction(), bot_instance.loop)
        result = future.result(timeout=10)
        return jsonify(result)
    except Exception as e:
        logger.error(f"RR add error: {e}")
        return jsonify({'error': str(e)}), 500


# ===== AUTO RESPONDER API =====

@app.route('/api/server/<server_id>/ar/add', methods=['POST'])
@require_auth
def ar_add(server_id):
    """Add an auto-response trigger"""
    try:
        data = request.json
        trigger = data.get('trigger', '').strip()
        response = data.get('response', '').strip()
        exact = data.get('exact', False)
        if not trigger or not response:
            return jsonify({'error': 'trigger and response required'}), 400
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        ar_cog = bot_instance.get_cog('AutoResponder')
        if not ar_cog:
            return jsonify({'error': 'AutoResponder cog not loaded'}), 503

        rules = ar_cog._guild(int(server_id))
        if any(r['trigger'].lower() == trigger.lower() for r in rules):
            return jsonify({'error': f'Trigger "{trigger}" already exists'}), 400
        rules.append({'trigger': trigger, 'response': response, 'exact': exact, 'enabled': True})
        ar_cog._save()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"AR add error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/ar/remove', methods=['POST'])
@require_auth
def ar_remove(server_id):
    """Remove an auto-response trigger"""
    try:
        trigger = request.json.get('trigger', '').strip()
        if not trigger:
            return jsonify({'error': 'trigger required'}), 400
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        ar_cog = bot_instance.get_cog('AutoResponder')
        if not ar_cog:
            return jsonify({'error': 'AutoResponder cog not loaded'}), 503

        gid = str(server_id)
        before = len(ar_cog.data.get(gid, []))
        ar_cog.data[gid] = [r for r in ar_cog.data.get(gid, []) if r['trigger'].lower() != trigger.lower()]
        ar_cog._save()
        if len(ar_cog.data.get(gid, [])) < before:
            return jsonify({'success': True})
        return jsonify({'error': 'Trigger not found'}), 404
    except Exception as e:
        logger.error(f"AR remove error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/ar/list')
@require_auth
def ar_list(server_id):
    """List auto-response triggers"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        ar_cog = bot_instance.get_cog('AutoResponder')
        if not ar_cog:
            return jsonify({'error': 'AutoResponder cog not loaded'}), 503
        rules = ar_cog.data.get(str(server_id), [])
        return jsonify({'rules': rules, 'total': len(rules)})
    except Exception as e:
        logger.error(f"AR list error: {e}")
        return jsonify({'error': str(e)}), 500


# ===== XP / LEVELING API =====

@app.route('/api/server/<server_id>/xp/leaderboard')
@require_auth
def xp_leaderboard(server_id):
    """Get XP leaderboard for a server"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        lvl_cog = bot_instance.get_cog('Leveling')
        if not lvl_cog:
            return jsonify({'error': 'Leveling cog not loaded'}), 503

        # Ensure data is loaded
        future = asyncio.run_coroutine_threadsafe(lvl_cog._ensure_loaded(), bot_instance.loop)
        future.result(timeout=5)

        from cogs.leveling import _xp_progress
        g = lvl_cog._guild(int(server_id))
        users = g.get('users', {})
        entries = []
        for uid, data in users.items():
            member = guild.get_member(int(uid))
            level, cur_xp, needed = _xp_progress(data.get('xp', 0))
            entries.append({
                'user_id': uid,
                'name': member.display_name if member else f'User {uid}',
                'avatar': str(member.display_avatar.url) if member else None,
                'level': level,
                'xp': data.get('xp', 0),
                'messages': data.get('messages', 0),
                'voice_minutes': data.get('voice_minutes', 0),
                'streak': data.get('streak', 0),
                'cur_xp': cur_xp,
                'needed': needed,
                'progress_pct': int(cur_xp / max(needed, 1) * 100),
            })
        entries.sort(key=lambda x: x['xp'], reverse=True)
        return jsonify({'leaderboard': entries[:20], 'total': len(entries)})
    except Exception as e:
        logger.error(f"XP leaderboard error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/xp/config', methods=['GET', 'POST'])
@require_auth
def xp_config(server_id):
    """Get or update XP config"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        lvl_cog = bot_instance.get_cog('Leveling')
        if not lvl_cog:
            return jsonify({'error': 'Leveling cog not loaded'}), 503

        future = asyncio.run_coroutine_threadsafe(lvl_cog._ensure_loaded(), bot_instance.loop)
        future.result(timeout=5)

        g = lvl_cog._guild(int(server_id))

        if request.method == 'GET':
            cfg = g.get('config', {})
            guild = bot_instance.get_guild(int(server_id))
            # Resolve channel name
            ch_id = cfg.get('announce_channel')
            ch_name = None
            if ch_id and guild:
                ch = guild.get_channel(int(ch_id))
                ch_name = ch.name if ch else None
            return jsonify({
                'announce_channel': ch_id,
                'announce_channel_name': ch_name,
                'announce': cfg.get('announce', True),
                'xp_multiplier': cfg.get('xp_multiplier', 1.0),
                'level_roles': cfg.get('level_roles', {}),
                'no_xp_channels': cfg.get('no_xp_channels', []),
            })

        data = request.json or {}
        if 'channel_id' in data:
            g['config']['announce_channel'] = int(data['channel_id']) if data['channel_id'] else None
        if 'multiplier' in data:
            g['config']['xp_multiplier'] = float(data['multiplier'])
        if 'announce' in data:
            g['config']['announce'] = bool(data['announce'])
        future2 = asyncio.run_coroutine_threadsafe(lvl_cog._persist(), bot_instance.loop)
        future2.result(timeout=5)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"XP config error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/xp/level-role', methods=['POST'])
@require_auth
def xp_level_role(server_id):
    """Set a role for a specific level"""
    try:
        data = request.json
        level = data.get('level')
        role_id = data.get('role_id')
        if not level:
            return jsonify({'error': 'level required'}), 400
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        lvl_cog = bot_instance.get_cog('Leveling')
        if not lvl_cog:
            return jsonify({'error': 'Leveling cog not loaded'}), 503

        future = asyncio.run_coroutine_threadsafe(lvl_cog._ensure_loaded(), bot_instance.loop)
        future.result(timeout=5)

        g = lvl_cog._guild(int(server_id))
        if role_id:
            g['config']['level_roles'][str(level)] = int(role_id)
        else:
            g['config']['level_roles'].pop(str(level), None)
        future2 = asyncio.run_coroutine_threadsafe(lvl_cog._persist(), bot_instance.loop)
        future2.result(timeout=5)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"XP level role error: {e}")
        return jsonify({'error': str(e)}), 500


# ===== ANALYTICS API =====

@app.route('/api/server/<server_id>/analytics')
@require_auth
def server_analytics(server_id):
    """Get server analytics"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        cached_members = guild.members
        online = len([m for m in cached_members if m.status != discord.Status.offline])
        bots = len([m for m in cached_members if m.bot])

        # Use live stats from bot (always available)
        live = bot_instance._get_live_stats(str(server_id))
        messages_today = live.get('messages', 0)
        joins_today = live.get('joins', 0)
        top_channels = []
        # Also try analytics cog for channel breakdown
        analytics_cog = bot_instance.get_cog('Analytics')
        if analytics_cog and hasattr(analytics_cog, 'data'):
            gdata = analytics_cog.data.get(str(server_id), {})
            if not messages_today:
                messages_today = gdata.get('messages_today', 0)
            if not joins_today:
                joins_today = gdata.get('joins_today', 0)
            ch_data = gdata.get('channels', {})
            top_channels = sorted(
                [{'id': k, 'name': guild.get_channel(int(k)).name if guild.get_channel(int(k)) else k, 'messages': v}
                 for k, v in ch_data.items()],
                key=lambda x: x['messages'], reverse=True
            )[:5]

        return jsonify({
            'members': guild.member_count,
            'online': online,
            'bots': bots,
            'humans': guild.member_count - bots,
            'messages_today': messages_today,
            'joins_today': joins_today,
            'boost_level': guild.premium_tier,
            'boost_count': guild.premium_subscription_count or 0,
            'channels': len(guild.channels),
            'roles': len(guild.roles),
            'top_channels': top_channels,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return jsonify({'error': str(e)}), 500


# ===== MODLOG API =====

@app.route('/api/server/<server_id>/modlog/cases')
@require_auth
def modlog_cases(server_id):
    try:
        import json as _json
        if not os.path.exists(data_path('modlog.json')):
            return jsonify({'cases': []})
        with open(data_path('modlog.json')) as f:
            data = _json.load(f)
        cases = data.get('cases', {}).get(str(server_id), [])
        return jsonify({'cases': list(reversed(cases[-50:]))})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/modlog/config', methods=['GET', 'POST'])
@require_auth
def modlog_config(server_id):
    try:
        import json as _json
        if not os.path.exists(data_path('modlog.json')):
            data = {'cases': {}, 'config': {}, 'tempbans': []}
        else:
            with open(data_path('modlog.json')) as f:
                data = _json.load(f)
        if request.method == 'POST':
            body = request.json or {}
            cfg = data.setdefault('config', {}).setdefault(str(server_id), {})
            if 'log_channel' in body:
                cfg['log_channel'] = body['log_channel']
            if 'thresholds' in body:
                cfg['thresholds'] = body['thresholds']
            with open(data_path('modlog.json'), 'w') as f:
                _json.dump(data, f, indent=2)
            return jsonify({'success': True})
        return jsonify(data.get('config', {}).get(str(server_id), {}))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== AUTOMOD API =====

@app.route('/api/server/<server_id>/automod/config', methods=['GET', 'POST'])
@require_auth
def automod_config_api(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('automod.json')):
            with open(data_path('automod.json')) as f:
                data = _json.load(f)
        if request.method == 'POST':
            body = request.json or {}
            data.setdefault(str(server_id), {}).update(body)
            with open(data_path('automod.json'), 'w') as f:
                _json.dump(data, f, indent=2)
            # Sync to in-memory cog settings
            if bot_instance:
                cog = bot_instance.get_cog('AutoMod')
                if cog:
                    sid = int(server_id)
                    for k, v in body.items():
                        if k in cog.settings[sid]:
                            cog.settings[sid][k] = v
            return jsonify({'success': True})
        from cogs.automod import DEFAULT_CFG
        cfg = {**DEFAULT_CFG, **data.get(str(server_id), {})}
        return jsonify(cfg)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== SERVERSTATS API =====

@app.route('/api/server/<server_id>/serverstats')
@require_auth
def serverstats_api(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('serverstats.json')):
            with open(data_path('serverstats.json')) as f:
                data = _json.load(f)
        channels = data.get(str(server_id), {})
        result = []
        if bot_instance:
            guild = bot_instance.get_guild(int(server_id))
            for ch_id, stat_type in channels.items():
                ch = guild.get_channel(int(ch_id)) if guild else None
                result.append({'channel_id': ch_id, 'name': ch.name if ch else ch_id, 'stat': stat_type})
        return jsonify({'channels': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/serverstats/add', methods=['POST'])
@require_auth
def serverstats_add(server_id):
    try:
        body = request.json or {}
        stat = body.get('stat')
        if not stat or not bot_instance:
            return jsonify({'error': 'stat required or bot not ready'}), 400
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Guild not found'}), 404

        from cogs.serverstats import STAT_TYPES
        fn = STAT_TYPES.get(stat)
        if not fn:
            return jsonify({'error': 'Invalid stat type'}), 400

        async def _create():
            overwrites = {guild.default_role: discord.PermissionOverwrite(connect=False)}
            ch = await guild.create_voice_channel(fn(guild), overwrites=overwrites, reason='Stats channel via dashboard')
            import json as _json
            data = {}
            if os.path.exists(data_path('serverstats.json')):
                with open(data_path('serverstats.json')) as f:
                    data = _json.load(f)
            data.setdefault(str(server_id), {})[str(ch.id)] = stat
            with open(data_path('serverstats.json'), 'w') as f:
                _json.dump(data, f, indent=2)
            return ch.id

        future = asyncio.run_coroutine_threadsafe(_create(), bot_instance.loop)
        ch_id = future.result(timeout=10)
        return jsonify({'success': True, 'channel_id': ch_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== SCHEDULER API =====

@app.route('/api/server/<server_id>/scheduler/list')
@require_auth
def scheduler_list(server_id):
    try:
        import json as _json
        jobs = []
        if os.path.exists(data_path('scheduler.json')):
            with open(data_path('scheduler.json')) as f:
                all_jobs = _json.load(f)
            jobs = [j for j in all_jobs if j.get('guild_id') == str(server_id)]
        return jsonify({'jobs': jobs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/scheduler/add', methods=['POST'])
@require_auth
def scheduler_add(server_id):
    try:
        import json as _json
        from datetime import timezone as tz
        body = request.json or {}
        channel_id = body.get('channel_id')
        message = body.get('message')
        when = body.get('when')
        recur = body.get('recur', 'once')
        if not all([channel_id, message, when]):
            return jsonify({'error': 'channel_id, message, when required'}), 400

        now = datetime.now(timezone.utc).replace(tzinfo=timezone.utc)
        try:
            if when.endswith('m'):
                run_at = now + timedelta(minutes=int(when[:-1]))
            elif when.endswith('h'):
                run_at = now + timedelta(hours=int(when[:-1]))
            elif when.endswith('d'):
                run_at = now + timedelta(days=int(when[:-1]))
            else:
                run_at = datetime.fromisoformat(when).replace(tzinfo=timezone.utc)
        except:
            return jsonify({'error': 'Invalid time format'}), 400

        jobs = []
        if os.path.exists(data_path('scheduler.json')):
            with open(data_path('scheduler.json')) as f:
                jobs = _json.load(f)
        job = {
            'id': len(jobs) + 1,
            'guild_id': str(server_id),
            'channel_id': str(channel_id),
            'message': message,
            'run_at': run_at.isoformat(),
            'recur': recur,
            'created_by': 'dashboard',
        }
        jobs.append(job)
        with open(data_path('scheduler.json'), 'w') as f:
            _json.dump(jobs, f, indent=2)
        return jsonify({'success': True, 'job': job})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/scheduler/remove/<int:job_id>', methods=['DELETE'])
@require_auth
def scheduler_remove(server_id, job_id):
    try:
        import json as _json
        if not os.path.exists(data_path('scheduler.json')):
            return jsonify({'error': 'No jobs'}), 404
        with open(data_path('scheduler.json')) as f:
            jobs = _json.load(f)
        new_jobs = [j for j in jobs if not (j.get('guild_id') == str(server_id) and j['id'] == job_id)]
        with open(data_path('scheduler.json'), 'w') as f:
            _json.dump(new_jobs, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== TAGS API =====

@app.route('/api/server/<server_id>/tags')
@require_auth
def tags_list(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('tags.json')):
            with open(data_path('tags.json')) as f:
                data = _json.load(f)
        tags = data.get(str(server_id), {})
        return jsonify({'tags': [{'name': k, **v} for k, v in tags.items()]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/tags/add', methods=['POST'])
@require_auth
def tags_add(server_id):
    try:
        import json as _json
        body = request.json or {}
        name = body.get('name', '').lower()
        content = body.get('content')
        aliases = body.get('aliases', [])
        if not name or not content:
            return jsonify({'error': 'name and content required'}), 400
        data = {}
        if os.path.exists(data_path('tags.json')):
            with open(data_path('tags.json')) as f:
                data = _json.load(f)
        data.setdefault(str(server_id), {})[name] = {
            'content': content, 'aliases': aliases, 'author_id': 'dashboard', 'uses': 0
        }
        with open(data_path('tags.json'), 'w') as f:
            _json.dump(data, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/tags/delete/<tag_name>', methods=['DELETE'])
@require_auth
def tags_delete(server_id, tag_name):
    try:
        import json as _json
        if not os.path.exists(data_path('tags.json')):
            return jsonify({'error': 'Not found'}), 404
        with open(data_path('tags.json')) as f:
            data = _json.load(f)
        gid = str(server_id)
        if gid in data and tag_name.lower() in data[gid]:
            del data[gid][tag_name.lower()]
            with open(data_path('tags.json'), 'w') as f:
                _json.dump(data, f, indent=2)
            return jsonify({'success': True})
        return jsonify({'error': 'Tag not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== ANTIRAID API =====

@app.route('/api/server/<server_id>/antiraid/config', methods=['GET', 'POST'])
@require_auth
def antiraid_config_api(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('antiraid.json')):
            with open(data_path('antiraid.json')) as f:
                data = _json.load(f)
        from cogs.antiraid import DEFAULT_CFG as AR_DEFAULT
        if request.method == 'POST':
            body = request.json or {}
            data.setdefault(str(server_id), {}).update(body)
            with open(data_path('antiraid.json'), 'w') as f:
                _json.dump(data, f, indent=2)
            return jsonify({'success': True})
        cfg = {**AR_DEFAULT, **data.get(str(server_id), {})}
        return jsonify(cfg)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== VOICE XP API =====

@app.route('/api/server/<server_id>/voicexp/leaderboard')
@require_auth
def voicexp_leaderboard(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('voicexp.json')):
            with open(data_path('voicexp.json')) as f:
                data = _json.load(f)
        users = data.get(str(server_id), {})
        guild = bot_instance.get_guild(int(server_id)) if bot_instance else None
        entries = []
        for uid, u in sorted(users.items(), key=lambda x: x[1].get('xp', 0), reverse=True)[:20]:
            member = guild.get_member(int(uid)) if guild else None
            from cogs.voicexp import _level_from_xp
            level, _, _ = _level_from_xp(u.get('xp', 0))
            entries.append({
                'user_id': uid,
                'name': member.display_name if member else f'User {uid}',
                'avatar': str(member.display_avatar.url) if member else None,
                'level': level,
                'xp': u.get('xp', 0),
                'minutes': u.get('minutes', 0),
            })
        return jsonify({'leaderboard': entries})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== HIGHLIGHTS API =====

@app.route('/api/server/<server_id>/highlights')
@require_auth
def highlights_api(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('highlights.json')):
            with open(data_path('highlights.json')) as f:
                data = _json.load(f)
        guild_hl = data.get(str(server_id), {})
        guild = bot_instance.get_guild(int(server_id)) if bot_instance else None
        result = []
        for uid, kws in guild_hl.items():
            member = guild.get_member(int(uid)) if guild else None
            result.append({
                'user_id': uid,
                'name': member.display_name if member else f'User {uid}',
                'keywords': kws,
            })
        return jsonify({'highlights': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== TICKETS API =====

@app.route('/api/server/<server_id>/tickets/config', methods=['GET', 'POST'])
@require_auth
def tickets_config_api(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('tickets.json')):
            with open(data_path('tickets.json')) as f:
                data = _json.load(f)
        if request.method == 'POST':
            body = request.json or {}
            data.setdefault(str(server_id), {}).update(body)
            with open(data_path('tickets.json'), 'w') as f:
                _json.dump(data, f, indent=2)
            return jsonify({'success': True})
        return jsonify(data.get(str(server_id), {}))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== SMARTMOD API =====

@app.route('/api/server/<server_id>/smartmod/config', methods=['GET', 'POST'])
@require_auth
def smartmod_config(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('smartmod.json')):
            with open(data_path('smartmod.json')) as f:
                data = _json.load(f)
        if request.method == 'POST':
            body = request.json or {}
            g = data.setdefault(str(server_id), {})
            if 'enabled' in body: g['enabled'] = body['enabled']
            if 'log_channel' in body: g['log_channel'] = body['log_channel']
            if 'strike_decay_days' in body: g['strike_decay_days'] = int(body['strike_decay_days'])
            with open(data_path('smartmod.json'), 'w') as f:
                _json.dump(data, f, indent=2)
            return jsonify({'success': True})
        g = data.get(str(server_id), {'enabled': True, 'log_channel': None, 'strike_decay_days': 30})
        return jsonify(g)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/smartmod/strikes')
@require_auth
def smartmod_strikes(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('smartmod.json')):
            with open(data_path('smartmod.json')) as f:
                data = _json.load(f)
        g = data.get(str(server_id), {})
        strikes = g.get('strikes', {})
        guild = bot_instance.get_guild(int(server_id)) if bot_instance else None
        result = []
        for uid, count in sorted(strikes.items(), key=lambda x: x[1], reverse=True):
            member = guild.get_member(int(uid)) if guild else None
            result.append({
                'user_id': uid,
                'name': member.display_name if member else f'User {uid}',
                'strikes': count,
                'last': g.get('last_strike', {}).get(uid, '')[:10],
            })
        return jsonify({'strikes': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/smartmod/clearstrikes/<user_id>', methods=['DELETE'])
@require_auth
def smartmod_clear_strikes(server_id, user_id):
    try:
        import json as _json
        if not os.path.exists(data_path('smartmod.json')):
            return jsonify({'error': 'No data'}), 404
        with open(data_path('smartmod.json')) as f:
            data = _json.load(f)
        g = data.get(str(server_id), {})
        g.get('strikes', {}).pop(str(user_id), None)
        g.get('last_strike', {}).pop(str(user_id), None)
        with open(data_path('smartmod.json'), 'w') as f:
            _json.dump(data, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== CHANNELGUARD API =====

@app.route('/api/server/<server_id>/channelguard/config', methods=['GET', 'POST'])
@require_auth
def channelguard_config(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('channelguard.json')):
            with open(data_path('channelguard.json')) as f:
                data = _json.load(f)
        if request.method == 'POST':
            body = request.json or {}
            g = data.setdefault(str(server_id), {})
            for k in ('enabled', 'auto_detect', 'log_channel'):
                if k in body: g[k] = body[k]
            with open(data_path('channelguard.json'), 'w') as f:
                _json.dump(data, f, indent=2)
            return jsonify({'success': True})
        return jsonify(data.get(str(server_id), {'enabled': False, 'auto_detect': True}))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/channelguard/scan')
@require_auth
def channelguard_scan(server_id):
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Guild not found'}), 404
        from cogs.channelguard import _detect_profile, PROFILES
        results = []
        for ch in guild.text_channels:
            p = _detect_profile(ch)
            if p:
                results.append({
                    'channel_id': str(ch.id),
                    'channel_name': ch.name,
                    'profile': p,
                    'hint': PROFILES[p]['hint'],
                })
        return jsonify({'channels': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/channelguard/set', methods=['POST'])
@require_auth
def channelguard_set(server_id):
    try:
        import json as _json
        body = request.json or {}
        channel_id = body.get('channel_id')
        profile = body.get('profile')
        if not channel_id or not profile:
            return jsonify({'error': 'channel_id and profile required'}), 400
        data = {}
        if os.path.exists(data_path('channelguard.json')):
            with open(data_path('channelguard.json')) as f:
                data = _json.load(f)
        g = data.setdefault(str(server_id), {'enabled': True, 'auto_detect': True})
        g.setdefault('channels', {})[str(channel_id)] = {'profile': profile}
        with open(data_path('channelguard.json'), 'w') as f:
            _json.dump(data, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/channelguard/remove/<channel_id>', methods=['DELETE'])
@require_auth
def channelguard_remove(server_id, channel_id):
    try:
        import json as _json
        if not os.path.exists(data_path('channelguard.json')):
            return jsonify({'error': 'No data'}), 404
        with open(data_path('channelguard.json')) as f:
            data = _json.load(f)
        g = data.get(str(server_id), {})
        g.get('channels', {}).pop(str(channel_id), None)
        with open(data_path('channelguard.json'), 'w') as f:
            _json.dump(data, f, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== JOIN/LEAVE API =====

@app.route('/api/server/<server_id>/joinleave/config', methods=['GET', 'POST'])
@require_auth
def joinleave_config(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('joinleave.json')):
            with open(data_path('joinleave.json')) as f: data = _json.load(f)
        if request.method == 'POST':
            body = request.json or {}
            data.setdefault(str(server_id), {}).update(body)
            with open(data_path('joinleave.json'), 'w') as f: _json.dump(data, f, indent=2)
            return jsonify({'success': True})
        return jsonify(data.get(str(server_id), {}))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== STARBOARD API =====

@app.route('/api/server/<server_id>/starboard/config', methods=['GET', 'POST'])
@require_auth
def starboard_config(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('starboard.json')):
            with open(data_path('starboard.json')) as f: data = _json.load(f)
        if request.method == 'POST':
            body = request.json or {}
            cfg = data.setdefault(str(server_id), {})
            for k in ('channel_id', 'threshold', 'enabled'):
                if k in body: cfg[k] = body[k]
            with open(data_path('starboard.json'), 'w') as f: _json.dump(data, f, indent=2)
            return jsonify({'success': True})
        cfg = data.get(str(server_id), {})
        return jsonify({k: v for k, v in cfg.items() if k != 'posted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== TIMED ACTIONS API =====

@app.route('/api/server/<server_id>/timedactions/list')
@require_auth
def timedactions_list(server_id):
    try:
        import json as _json
        data = {'timed_roles': [], 'timed_mutes': []}
        if os.path.exists(data_path('timedactions.json')):
            with open(data_path('timedactions.json')) as f: data = _json.load(f)
        guild = bot_instance.get_guild(int(server_id)) if bot_instance else None
        roles = []
        for e in data.get('timed_roles', []):
            if e.get('guild_id') != str(server_id): continue
            member = guild.get_member(int(e['user_id'])) if guild else None
            role = guild.get_role(int(e['role_id'])) if guild else None
            roles.append({**e, 'member_name': member.display_name if member else e['user_id'],
                          'role_name': role.name if role else e['role_id']})
        mutes = [e for e in data.get('timed_mutes', []) if e.get('guild_id') == str(server_id)]
        return jsonify({'timed_roles': roles, 'timed_mutes': mutes})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== EMBED BUILDER API =====

@app.route('/api/server/<server_id>/embeds', methods=['GET'])
@require_auth
def embeds_list(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('saved_embeds.json')):
            with open(data_path('saved_embeds.json')) as f: data = _json.load(f)
        templates = data.get(str(server_id), {})
        return jsonify({'templates': [{'name': k, **v} for k, v in templates.items()]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/embeds/post', methods=['POST'])
@require_auth
def embeds_post(server_id):
    try:
        body = request.json or {}
        channel_id = body.get('channel_id')
        embed_data = body.get('embed', {})
        if not channel_id or not bot_instance:
            return jsonify({'error': 'channel_id required or bot not ready'}), 400
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Guild not found'}), 404
        channel = guild.get_channel(int(channel_id))
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404

        from cogs.embedbuilder import _build_embed
        embed = _build_embed(embed_data)

        async def _send():
            await channel.send(embed=embed)

        future = asyncio.run_coroutine_threadsafe(_send(), bot_instance.loop)
        future.result(timeout=10)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== LOGGING CONFIG API =====

@app.route('/api/server/<server_id>/logging/config', methods=['GET', 'POST'])
@require_auth
def logging_config_api(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('logging_config.json')):
            with open(data_path('logging_config.json')) as f: data = _json.load(f)
        if request.method == 'POST':
            body = request.json or {}
            data.setdefault(str(server_id), {}).update(body)
            with open(data_path('logging_config.json'), 'w') as f: _json.dump(data, f, indent=2)
            return jsonify({'success': True})
        return jsonify(data.get(str(server_id), {}))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== COMMAND CENTER =====
@app.route('/api/server/<server_id>/command-center', methods=['POST'])
@require_auth
def command_center(server_id):
    """Execute moderation commands from dashboard"""
    try:
        body = request.json or {}
        action = body.get('action')
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild: return jsonify({'error': 'Server not found'}), 404

        async def _exec():
            if action == 'warn':
                member = guild.get_member(int(body['member_id']))
                if not member: return {'error': 'Member not found'}
                # Write warn case directly to modlog.json (ModLog cog has no add_case method)
                try:
                    import json as _json
                    _ml_path = data_path('modlog.json')
                    _ml_data = {}
                    if os.path.exists(_ml_path):
                        with open(_ml_path) as _f: _ml_data = _json.load(_f)
                    _cases = _ml_data.setdefault('cases', {}).setdefault(str(guild.id), [])
                    _cases.append({'id': len(_cases)+1, 'action': 'warn', 'mod_id': str(guild.me.id),
                                   'mod': str(guild.me), 'target_id': str(member.id), 'target': str(member),
                                   'reason': body.get('reason','No reason'),
                                   'timestamp': datetime.now(timezone.utc).isoformat()})
                    with open(_ml_path, 'w') as _f: _json.dump(_ml_data, _f, indent=2)
                except Exception: pass
                try:
                    await member.send(f"⚠️ You have been warned in **{guild.name}**: {body.get('reason','No reason')}")
                except: pass
                return {'success': True, 'msg': f'Warned {member.display_name}'}
            elif action == 'mute':
                import discord
                from datetime import timedelta
                member = guild.get_member(int(body['member_id']))
                if not member: return {'error': 'Member not found'}
                mins = int(body.get('duration', 10))
                await member.timeout(timedelta(minutes=mins), reason=body.get('reason','Dashboard mute'))
                return {'success': True, 'msg': f'Muted {member.display_name} for {mins}m'}
            elif action == 'purge':
                channel = guild.get_channel(int(body['channel_id']))
                if not channel: return {'error': 'Channel not found'}
                count = min(int(body.get('count', 10)), 100)
                deleted = await channel.purge(limit=count)
                return {'success': True, 'msg': f'Deleted {len(deleted)} messages'}
            elif action == 'dm':
                member = guild.get_member(int(body['member_id']))
                if not member: return {'error': 'Member not found'}
                await member.send(body.get('message',''))
                return {'success': True, 'msg': f'DM sent to {member.display_name}'}
            elif action == 'slowmode':
                channel = guild.get_channel(int(body['channel_id']))
                if not channel: return {'error': 'Channel not found'}
                secs = int(body.get('seconds', 0))
                await channel.edit(slowmode_delay=secs)
                return {'success': True, 'msg': f'Slowmode set to {secs}s'}
            elif action == 'lock':
                channel = guild.get_channel(int(body['channel_id']))
                if not channel: return {'error': 'Channel not found'}
                import discord
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = False if body.get('lock', True) else None
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                return {'success': True, 'msg': f'Channel {"locked" if body.get("lock",True) else "unlocked"}'}
            return {'error': 'Unknown action'}

        future = asyncio.run_coroutine_threadsafe(_exec(), bot_instance.loop)
        result = future.result(timeout=15)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== SERVER HEALTH SCORE =====
@app.route('/api/server/<server_id>/health')
@require_auth
def server_health(server_id):
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild: return jsonify({'error': 'Not found'}), 404

        score = 0
        factors = []

        # Bot online (20pts)
        score += 20
        factors.append({'name': 'Bot Online', 'pts': 20, 'max': 20, 'ok': True})

        # Online ratio (20pts)
        total = guild.member_count or 1
        online = sum(1 for m in guild.members if str(m.status) in ('online','idle','dnd'))
        ratio = online / total
        pts = round(ratio * 20)
        score += pts
        factors.append({'name': 'Active Members', 'pts': pts, 'max': 20, 'ok': ratio > 0.1, 'detail': f'{online}/{total} online'})

        # Boost level (20pts)
        bl = guild.premium_tier
        bpts = bl * 7
        score += min(bpts, 20)
        factors.append({'name': 'Boost Level', 'pts': min(bpts,20), 'max': 20, 'ok': bl > 0, 'detail': f'Level {bl}'})

        # Moderation activity (20pts) — read modlog.json directly
        mod_pts = 0
        try:
            modlog_path = data_path('modlog.json')
            if os.path.exists(modlog_path):
                with open(modlog_path) as _f:
                    _ml = json.load(_f)
                cases = _ml.get(str(server_id), {}).get('cases', [])
                mod_pts = min(len(cases) * 2, 20)
        except Exception:
            pass
        score += mod_pts
        factors.append({'name': 'Moderation Active', 'pts': mod_pts, 'max': 20, 'ok': mod_pts > 0})

        # Verification (10pts)
        vl = str(guild.verification_level)
        vpts = 10 if vl not in ('none','low') else 5
        score += vpts
        factors.append({'name': 'Verification', 'pts': vpts, 'max': 10, 'ok': vpts >= 10, 'detail': vl})

        # Channels configured (10pts)
        cpts = min(len(guild.text_channels) * 1, 10)
        score += cpts
        factors.append({'name': 'Server Setup', 'pts': cpts, 'max': 10, 'ok': cpts >= 5})

        return jsonify({'score': min(score, 100), 'factors': factors})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== MEMBER GROWTH (7/30 day) =====
@app.route('/api/server/<server_id>/growth')
@require_auth
def member_growth(server_id):
    """Return member join counts per day for last 30 days"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild: return jsonify({'error': 'Not found'}), 404
        from datetime import datetime, timezone, timedelta
        days = int(request.args.get('days', 7))
        now = datetime.now(timezone.utc)
        buckets = {}
        for i in range(days):
            d = (now - timedelta(days=days-1-i)).strftime('%m/%d')
            buckets[d] = 0
        for m in guild.members:
            if m.joined_at:
                diff = (now - m.joined_at).days
                if diff < days:
                    label = m.joined_at.strftime('%m/%d')
                    if label in buckets:
                        buckets[label] += 1
        labels = list(buckets.keys())
        data = list(buckets.values())
        # cumulative total per day
        total = guild.member_count
        return jsonify({'labels': labels, 'joins': data, 'total': total})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== TOP MEMBERS =====
@app.route('/api/server/<server_id>/top-members')
@require_auth
def top_members(server_id):
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        lvl_cog = bot_instance.get_cog('Leveling')
        guild = bot_instance.get_guild(int(server_id))
        if not guild: return jsonify({'error': 'Not found'}), 404
        top = []
        if lvl_cog:
            try:
                g = lvl_cog._guild(int(server_id))
                users = g.get('users', {})
                sorted_users = sorted(users.items(), key=lambda x: x[1].get('xp', 0), reverse=True)[:5]
                for uid, data in sorted_users:
                    m = guild.get_member(int(uid))
                    if m:
                        top.append({
                            'id': uid, 'name': m.display_name,
                            'avatar': str(m.display_avatar.url),
                            'xp': data.get('xp', 0), 'level': data.get('level', 0),
                            'messages': data.get('messages', 0)
                        })
            except: pass
        if not top:
            # fallback: just return first 5 non-bot members
            for m in list(guild.members)[:5]:
                if not m.bot:
                    top.append({'id': str(m.id), 'name': m.display_name,
                                'avatar': str(m.display_avatar.url), 'xp': 0, 'level': 0, 'messages': 0})
        return jsonify({'top': top})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== ROLE DISTRIBUTION =====
@app.route('/api/server/<server_id>/role-distribution')
@require_auth
def role_distribution(server_id):
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild: return jsonify({'error': 'Not found'}), 404
        dist = []
        for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
            if role.name == '@everyone': continue
            count = len([m for m in role.members if not m.bot])
            if count > 0:
                dist.append({'name': role.name, 'count': count,
                             'color': str(role.color) if str(role.color) != '#000000' else '#99aab5'})
        return jsonify({'roles': dist[:15]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== MESSAGE HEATMAP =====
@app.route('/api/server/<server_id>/heatmap')
@require_auth
def message_heatmap(server_id):
    """Return message activity heatmap data (day x hour)"""
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('activity_heatmap.json')):
            with open(data_path('activity_heatmap.json')) as f: data = _json.load(f)
        guild_data = data.get(str(server_id), {})
        # Build 7x24 grid
        days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
        grid = []
        max_val = 1
        for d_idx, day in enumerate(days):
            for h in range(24):
                val = guild_data.get(f'{d_idx}_{h}', 0)
                if val > max_val: max_val = val
                grid.append({'day': d_idx, 'hour': h, 'value': val})
        return jsonify({'grid': grid, 'days': days, 'max': max_val})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== NOTIFICATIONS =====
@app.route('/api/server/<server_id>/notifications')
@require_auth
def get_notifications(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('notifications.json')):
            with open(data_path('notifications.json')) as f: data = _json.load(f)
        notifs = data.get(str(server_id), [])
        return jsonify({'notifications': notifs[-30:][::-1]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/notifications/clear', methods=['POST'])
@require_auth
def clear_notifications(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('notifications.json')):
            with open(data_path('notifications.json')) as f: data = _json.load(f)
        data[str(server_id)] = []
        with open(data_path('notifications.json'), 'w') as f: _json.dump(data, f)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== EXPORT MEMBERS CSV =====
@app.route('/api/server/<server_id>/export/members')
@require_auth
def export_members_csv(server_id):
    try:
        import csv, io
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild: return jsonify({'error': 'Not found'}), 404
        lvl_cog = bot_instance.get_cog('Leveling')
        xp_data = {}
        if lvl_cog:
            try:
                g = lvl_cog._guild(int(server_id))
                xp_data = g.get('users', {})
            except: pass
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID','Username','Display Name','Bot','Status','Joined At','Account Created','Roles','XP','Level','Messages'])
        for m in guild.members:
            ud = xp_data.get(str(m.id), {})
            writer.writerow([
                m.id, m.name, m.display_name, m.bot, str(m.status),
                m.joined_at.isoformat() if m.joined_at else '',
                m.created_at.isoformat(),
                '|'.join(r.name for r in m.roles if r.name != '@everyone'),
                ud.get('xp', 0), ud.get('level', 0), ud.get('messages', 0)
            ])
        from flask import Response
        return Response(output.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': f'attachment; filename=members_{server_id}.csv'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== BOT PREFIX CONFIG =====
@app.route('/api/server/<server_id>/prefix', methods=['GET', 'POST'])
@require_auth
def prefix_config(server_id):
    try:
        import json as _json
        data = {}
        if os.path.exists(data_path('prefix_config.json')):
            with open(data_path('prefix_config.json')) as f: data = _json.load(f)
        if request.method == 'POST':
            prefix = (request.json or {}).get('prefix', '!')
            data[str(server_id)] = prefix
            with open(data_path('prefix_config.json'), 'w') as f: _json.dump(data, f)
            # Update bot if possible
            if bot_instance:
                try:
                    if hasattr(bot_instance, '_prefixes'):
                        bot_instance._prefixes[int(server_id)] = prefix
                except: pass
            return jsonify({'success': True, 'prefix': prefix})
        return jsonify({'prefix': data.get(str(server_id), '!')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== TEMP BAN =====
@app.route('/api/server/<server_id>/members/<member_id>/tempban', methods=['POST'])
@require_auth
def temp_ban_member(server_id, member_id):
    try:
        body = request.json or {}
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild: return jsonify({'error': 'Not found'}), 404
        member = guild.get_member(int(member_id))
        if not member: return jsonify({'error': 'Member not found'}), 404
        reason = body.get('reason', 'Temp ban via dashboard')
        hours = int(body.get('hours', 24))
        delete_days = int(body.get('delete_days', 0))

        async def _ban():
            await guild.ban(member, reason=reason, delete_message_days=delete_days)
            # Schedule unban
            import asyncio as _aio
            async def _unban():
                await _aio.sleep(hours * 3600)
                try: await guild.unban(member, reason='Temp ban expired')
                except: pass
            bot_instance.loop.create_task(_unban())
            return {'success': True, 'msg': f'Temp banned {member.display_name} for {hours}h'}

        future = asyncio.run_coroutine_threadsafe(_ban(), bot_instance.loop)
        return jsonify(future.result(timeout=10))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== BULK MODERATION =====
@app.route('/api/server/<server_id>/bulk-mod', methods=['POST'])
@require_auth
def bulk_mod(server_id):
    try:
        body = request.json or {}
        action = body.get('action')
        member_ids = body.get('member_ids', [])
        reason = body.get('reason', 'Bulk action via dashboard')
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild: return jsonify({'error': 'Not found'}), 404

        async def _bulk():
            results = []
            for mid in member_ids[:20]:  # cap at 20
                m = guild.get_member(int(mid))
                if not m: continue
                try:
                    if action == 'kick': await m.kick(reason=reason)
                    elif action == 'ban': await guild.ban(m, reason=reason)
                    elif action == 'timeout':
                        from datetime import timedelta
                        await m.timeout(timedelta(minutes=int(body.get('duration',10))), reason=reason)
                    results.append({'id': mid, 'name': m.display_name, 'ok': True})
                except Exception as e:
                    results.append({'id': mid, 'ok': False, 'error': str(e)})
            return {'success': True, 'results': results}

        future = asyncio.run_coroutine_threadsafe(_bulk(), bot_instance.loop)
        return jsonify(future.result(timeout=30))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════════
# WATCH PARTY — Synchronized video watching with live chat
# ═══════════════════════════════════════════════════════════════════════════════

# In-memory watch party rooms: {room_id: WatchRoom}
_watch_rooms: dict = {}

UPLOAD_FOLDER = os.path.join(os.getenv("DATA_DIR", "./data"), "watch_uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"}
MAX_UPLOAD_MB = 500


class WatchRoom:
    def __init__(self, room_id: str, guild_id: str, title: str,
                 video_url: str, host_id: str, host_name: str,
                 required_role_id: str = None):
        self.room_id        = room_id
        self.guild_id       = guild_id
        self.title          = title
        self.video_url      = video_url      # URL or /watch/stream/<room_id>
        self.host_id        = host_id
        self.host_name      = host_name
        self.required_role_id = required_role_id  # None = everyone
        self.created_at     = datetime.now(timezone.utc).isoformat()
        self.is_playing     = False
        self.current_time   = 0.0            # seconds
        self.last_sync      = _time.time()
        self.viewers: dict  = {}             # {session_id: {name, avatar, joined_at, user_id, role_level}}
        self.chat: list     = []             # [{user, msg, ts, user_id}]
        self.file_path: str = None           # set if uploaded file
        self.volume         = 1.0
        self.is_looping     = False

    def sync_time(self) -> float:
        """Return current playback position accounting for elapsed time."""
        if self.is_playing:
            return self.current_time + (_time.time() - self.last_sync)
        return self.current_time

    def to_dict(self):
        return {
            "room_id":    self.room_id,
            "guild_id":   self.guild_id,
            "title":      self.title,
            "video_url":  self.video_url,
            "host_id":    self.host_id,
            "host_name":  self.host_name,
            "is_playing": self.is_playing,
            "current_time": self.sync_time(),
            "viewer_count": len(self.viewers),
            "viewers":    list(self.viewers.values()),
            "created_at": self.created_at,
            "required_role_id": self.required_role_id,
            "volume": self.volume,
            "is_looping": self.is_looping,
        }


def _get_user_role_level(guild_id: int, user_id: int) -> int:
    """
    Determine user's role level in watch party.
    Returns: 0=Guest, 1=Member, 2=Mod, 3=Admin, 4=Owner
    """
    if not bot_instance or not bot_instance.is_ready():
        return 0
    
    guild = bot_instance.get_guild(guild_id)
    if not guild:
        return 0
    
    member = guild.get_member(user_id)
    if not member:
        return 0
    
    # Owner has highest level
    if member.id == guild.owner_id:
        return 4
    
    # Check for admin permissions
    if member.guild_permissions.administrator:
        return 3
    
    # Check for mod role (manage_messages or manage_guild)
    if member.guild_permissions.manage_messages or member.guild_permissions.manage_guild:
        return 2
    
    # Check if has any role (member vs guest)
    if len(member.roles) > 1:  # More than @everyone
        return 1
    
    return 0  # Guest

def _check_watch_access(room: WatchRoom) -> bool:
    """Check if current session user has access to this watch room."""
    if not room.required_role_id:
        return True
    if not bot_instance or not bot_instance.is_ready():
        return True
    user_id = session.get("user_id")
    if not user_id:
        return False
    guild = bot_instance.get_guild(int(room.guild_id))
    if not guild:
        return True
    member = guild.get_member(int(user_id))
    if not member:
        return False
    return any(str(r.id) == room.required_role_id for r in member.roles)


# ── REST endpoints ─────────────────────────────────────────────────────────────

@app.route("/api/server/<server_id>/watch/rooms")
@require_auth
def watch_list_rooms(server_id):
    """List all active watch rooms for a server."""
    rooms = [r.to_dict() for r in _watch_rooms.values()
             if r.guild_id == server_id]
    return jsonify({"rooms": rooms})


@app.route("/api/watch/resolve-url", methods=["POST"])
@require_auth
def watch_resolve_url():
    """Resolve a YouTube/external URL to a direct streamable URL using yt-dlp."""
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400

    # If it's already a direct video file, return as-is
    if any(url.lower().endswith(ext) for ext in (".mp4", ".webm", ".mkv", ".m3u8")):
        return jsonify({"stream_url": url, "title": url.split("/")[-1], "type": "direct"})

    try:
        import yt_dlp
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return jsonify({"error": "Could not extract video info"}), 400

            stream_url = info.get("url") or info.get("manifest_url")
            title = info.get("title", "Video")
            thumbnail = info.get("thumbnail", "")
            duration = info.get("duration", 0)

            if not stream_url:
                # Try formats list
                fmts = info.get("formats", [])
                for f in reversed(fmts):
                    if f.get("url") and f.get("vcodec") != "none":
                        stream_url = f["url"]
                        break

            if not stream_url:
                return jsonify({"error": "No streamable URL found"}), 400

            return jsonify({
                "stream_url": stream_url,
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration,
                "type": "resolved"
            })
    except Exception as e:
        logger.error(f"URL resolve error: {e}")
        return jsonify({"error": f"Could not resolve URL: {str(e)[:100]}"}), 400


@app.route("/api/server/<server_id>/watch/create", methods=["POST"])
@require_auth
def watch_create_room(server_id):
    """Create a new watch party room with a video URL."""
    data = request.json or {}
    video_url = data.get("video_url", "").strip()
    title     = data.get("title", "Watch Party").strip()[:100]
    role_id   = data.get("required_role_id") or None

    if not video_url:
        return jsonify({"error": "video_url is required"}), 400

    room_id = secrets.token_urlsafe(8)
    room = WatchRoom(
        room_id=room_id,
        guild_id=server_id,
        title=title,
        video_url=video_url,
        host_id=session.get("user_id", "unknown"),
        host_name=session.get("username", "Host"),
        required_role_id=role_id,
    )
    _watch_rooms[room_id] = room
    logger.info(f"Watch room created: {room_id} by {session.get('username')} in guild {server_id}")
    return jsonify({"room": room.to_dict(), "room_id": room_id})


@app.route("/api/server/<server_id>/watch/upload", methods=["POST"])
@require_auth
@limiter.limit("5 per hour")
def watch_upload_video(server_id):
    """Upload a video file and create a watch room with validation."""
    from watch_party_upload import UploadValidator
    from watch_party_db import WatchPartyDB
    
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Validate upload
    is_valid, validation_result = UploadValidator.validate_upload(f, f.filename)
    if not is_valid:
        errors = validation_result.get("errors", [])
        return jsonify({"error": errors[0] if errors else "Validation failed"}), 400

    # Get file info
    file_info = validation_result.get("file_info", {})
    ext = file_info.get("extension", ".mp4")
    
    # Save file
    room_id = secrets.token_urlsafe(8)
    safe_name = f"{room_id}{ext}"
    file_path = os.path.join(UPLOAD_FOLDER, safe_name)
    
    try:
        f.seek(0)
        f.save(file_path)
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        return jsonify({"error": "Failed to save file"}), 500

    # Create room
    title = request.form.get("title", f.filename[:80])
    role_id = request.form.get("required_role_id") or None

    room = WatchRoom(
        room_id=room_id,
        guild_id=server_id,
        title=title,
        video_url=f"/watch/stream/{room_id}",
        host_id=session.get("user_id", "unknown"),
        host_name=session.get("username", "Host"),
        required_role_id=role_id,
    )
    room.file_path = file_path
    _watch_rooms[room_id] = room
    
    # Save to database
    upload_info = {
        "room_id": room_id,
        "filename": f.filename,
        "size_bytes": file_info.get("size_bytes", 0),
        "title": title,
        "host_id": session.get("user_id"),
        "guild_id": server_id,
    }
    WatchPartyDB.save_upload_info(room_id, upload_info)
    WatchPartyDB.save_room_data(room_id, room.to_dict())
    
    logger.info(f"Watch upload: {room_id} ({file_info.get('size', 'unknown')}) by {session.get('username')}")

    # ── Fire Discord @everyone announcement + schedule poll ──────────────────
    try:
        from watch_party_upload_fixed import GuildUploadManager
        _upload_mgr = GuildUploadManager(bot_instance)
        uploader_name = session.get("username", "Unknown")
        file_size = file_info.get("size_bytes", 0)

        async def _announce():
            uid = await _upload_mgr.start_upload(
                guild_id=server_id,
                user_id=session.get("user_id", "unknown"),
                username=uploader_name,
                title=title,
                file_path=file_path,
                file_size=file_size,
            )
            if uid:
                await _upload_mgr.complete_upload(uid, room_id)

        import asyncio
        asyncio.run_coroutine_threadsafe(_announce(), bot_instance.loop)
    except Exception as _e:
        logger.warning(f"Could not fire upload announcement: {_e}")

    return jsonify({"room": room.to_dict(), "room_id": room_id})


@app.route("/watch/stream/<room_id>")
def watch_stream_file(room_id):
    """Stream an uploaded video file with range support."""
    if 'user_id' not in session:
        return redirect(url_for('login', next=request.url))
    room = _watch_rooms.get(room_id)
    if not room or not room.file_path or not os.path.exists(room.file_path):
        return jsonify({"error": "File not found"}), 404
    if not _check_watch_access(room):
        return jsonify({"error": "Access denied"}), 403

    ext = os.path.splitext(room.file_path)[1].lower()
    mime_map = {".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska",
                ".mov": "video/quicktime", ".avi": "video/x-msvideo", ".m4v": "video/mp4"}
    mime = mime_map.get(ext, "video/mp4")

    file_size = os.path.getsize(room.file_path)
    range_header = request.headers.get("Range")

    if range_header:
        # Byte-range streaming for seeking support
        byte_start, byte_end = 0, file_size - 1
        match = range_header.replace("bytes=", "").split("-")
        if match[0]:
            byte_start = int(match[0])
        if len(match) > 1 and match[1]:
            byte_end = int(match[1])
        length = byte_end - byte_start + 1

        def generate():
            with open(room.file_path, "rb") as fh:
                fh.seek(byte_start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        from flask import Response
        resp = Response(generate(), 206, mimetype=mime, direct_passthrough=True)
        resp.headers["Content-Range"] = f"bytes {byte_start}-{byte_end}/{file_size}"
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Content-Length"] = str(length)
        return resp

    return send_file(room.file_path, mimetype=mime)


@app.route("/api/watch/<room_id>")
@require_auth
def watch_get_room(room_id):
    """Get room state."""
    room = _watch_rooms.get(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if not _check_watch_access(room):
        return jsonify({"error": "Access denied — you need the required role"}), 403
    return jsonify(room.to_dict())


@app.route("/api/watch/<room_id>/close", methods=["POST"])
@require_auth
def watch_close_room(room_id):
    """Close a watch room (host only)."""
    room = _watch_rooms.get(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room.host_id != session.get("user_id"):
        return jsonify({"error": "Only the host can close the room"}), 403
    # Delete uploaded file if any
    if room.file_path and os.path.exists(room.file_path):
        try:
            os.remove(room.file_path)
        except Exception:
            pass
    del _watch_rooms[room_id]
    socketio.emit("room_closed", {"room_id": room_id}, room=f"watch_{room_id}")
    return jsonify({"success": True})


@app.route("/api/watch/movies/<server_id>")
@require_auth
def watch_list_movies(server_id):
    """List all uploaded movies for a server (persisted in DB)."""
    from watch_party_movies_db import MovieDatabase
    movies = MovieDatabase.get_guild_movies(str(server_id), active_only=True)
    # Also include in-memory rooms that have a file (uploaded this session)
    session_movies = []
    for room in _watch_rooms.values():
        if str(room.guild_id) == str(server_id) and getattr(room, "file_path", None):
            session_movies.append({
                "id": room.room_id,
                "title": room.title,
                "file_size": os.path.getsize(room.file_path) if os.path.exists(room.file_path) else 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "room_id": room.room_id,
            })
    # Merge, deduplicate by id
    all_ids = {m.get("id") or m.get("movie_id") for m in movies}
    for m in session_movies:
        if m["id"] not in all_ids:
            movies.append(m)
    return jsonify({"movies": movies})


@app.route("/api/watch/start/<server_id>/<movie_id>", methods=["POST"])
@require_auth
def watch_start_movie(server_id, movie_id):
    """Start a watch party for an existing movie."""
    from watch_party_movies_db import MovieDatabase
    # Check if room already exists for this movie
    for room in _watch_rooms.values():
        if str(room.guild_id) == str(server_id) and room.room_id == movie_id:
            return jsonify({"room_id": room.room_id, "room": room.to_dict()})
    # Look up movie in DB
    movie = MovieDatabase.get_movie(movie_id)
    if not movie:
        # Try in-memory rooms (uploaded this session)
        room = _watch_rooms.get(movie_id)
        if room:
            return jsonify({"room_id": room.room_id, "room": room.to_dict()})
        return jsonify({"error": "Movie not found"}), 404
    # Create a new room for this movie
    room_id = movie_id  # reuse movie_id as room_id for simplicity
    room = WatchRoom(
        room_id=room_id,
        guild_id=server_id,
        title=movie.get("title", "Movie"),
        video_url=f"/watch/stream/{room_id}",
        host_id=session.get("user_id", "unknown"),
        host_name=session.get("username", "Host"),
    )
    room.file_path = movie.get("file_path", "")
    _watch_rooms[room_id] = room
    MovieDatabase.update_movie_views(movie_id)
    return jsonify({"room_id": room_id, "room": room.to_dict()})


@app.route("/api/watch/delete/<server_id>/<movie_id>", methods=["DELETE", "POST"])
@require_auth
def watch_delete_movie(server_id, movie_id):
    """Delete a movie."""
    from watch_party_movies_db import MovieDatabase
    # Remove from in-memory rooms
    room = _watch_rooms.pop(movie_id, None)
    if room and room.file_path and os.path.exists(room.file_path):
        try:
            os.remove(room.file_path)
        except Exception:
            pass
    # Remove from DB
    MovieDatabase.delete_movie(movie_id)
    return jsonify({"success": True})


# ── Movie Schedule API (multiple time slots, loop support) ────────────────────
_movie_schedules: dict = {}  # {server_id: [schedule_entry, ...]}

@app.route("/api/server/<server_id>/watch/schedule", methods=["GET"])
@require_auth
def watch_get_schedule(server_id):
    """Get movie schedule for a server."""
    return jsonify({"schedule": _movie_schedules.get(server_id, [])})

@app.route("/api/server/<server_id>/watch/schedule", methods=["POST"])
@require_auth
def watch_save_schedule(server_id):
    """Save/replace movie schedule for a server."""
    data = request.json or {}
    schedule = data.get("schedule", [])
    _movie_schedules[server_id] = schedule
    return jsonify({"success": True, "count": len(schedule)})

@app.route("/api/server/<server_id>/watch/schedule/add", methods=["POST"])
@require_auth
def watch_add_schedule_entry(server_id):
    """Add a single schedule entry (supports multiple time slots)."""
    data = request.json or {}
    entry = {
        "id": secrets.token_hex(6),
        "title": str(data.get("title", ""))[:100],
        "date": data.get("date", ""),
        "slots": data.get("slots", []),  # list of time strings e.g. ["18:00","21:00"]
        "repeat": data.get("repeat", "none"),
        "room_id": data.get("room_id"),
        "role": data.get("role"),
        "is_looping": len(data.get("slots", [])) > 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": session.get("username", "unknown"),
    }
    if server_id not in _movie_schedules:
        _movie_schedules[server_id] = []
    _movie_schedules[server_id].append(entry)
    return jsonify({"success": True, "entry": entry})

@app.route("/api/server/<server_id>/watch/schedule/<entry_id>", methods=["DELETE"])
@require_auth
def watch_delete_schedule_entry(server_id, entry_id):
    """Delete a schedule entry."""
    if server_id in _movie_schedules:
        _movie_schedules[server_id] = [e for e in _movie_schedules[server_id] if e.get("id") != entry_id]
    return jsonify({"success": True})


@app.route("/watch/upload")
@require_auth
def watch_upload_page():
    """Serve watch party upload page"""
    return render_template("watch_party_upload.html")

@app.route("/watch/<room_id>")
def watch_party_page(room_id):
    """Serve the watch party page — no login required, room access check handles roles."""
    room = _watch_rooms.get(room_id)
    # If room not in memory (e.g. after restart), try to restore from DB
    if not room:
        try:
            from watch_party_movies_db import MovieDatabase
            movie = MovieDatabase.get_movie(room_id)
            if movie:
                room = WatchRoom(
                    room_id=room_id,
                    guild_id=str(movie.get("guild_id", "")),
                    title=movie.get("title", "Movie"),
                    video_url=f"/watch/stream/{room_id}",
                    host_id=movie.get("uploader_id", "unknown"),
                    host_name=movie.get("uploader_name", "Host"),
                )
                room.file_path = movie.get("file_path", "")
                _watch_rooms[room_id] = room
                MovieDatabase.update_movie_views(room_id)
        except Exception as _e:
            logger.warning(f"Could not restore room {room_id} from DB: {_e}")
    if not room:
        # Show a simple not-found page
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Watch Party Not Found</title>
        <style>body{{background:#05070f;color:#eef0ff;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px;}}
        h2{{font-size:24px;}}p{{color:#5a6080;}}a{{color:#7c6fff;text-decoration:none;}}</style></head>
        <body><div style="font-size:48px">🎬</div><h2>Watch Party Not Found</h2>
        <p>This watch party has ended or the link is no longer valid.</p>
        <a href="/">← Back to Dashboard</a></body></html>""", 404
    # Role-restricted rooms still require login
    if room.required_role_id and 'user_id' not in session:
        return redirect(url_for('login', next=request.url))
    if not _check_watch_access(room):
        return render_template("login.html", error="You need the required server role to join this watch party.")
    return render_template("watch_party.html",
                           room=room.to_dict(),
                           username=session.get("username", "Viewer"),
                           user_id=session.get("user_id", ""))


# ── SocketIO events for watch party ───────────────────────────────────────────

@socketio.on("watch_join")
def on_watch_join(data):
    room_id  = data.get("room_id")
    username = session.get("username", data.get("username", "Viewer"))
    user_id  = session.get("user_id", data.get("user_id", secrets.token_hex(4)))
    avatar   = session.get("avatar_url", "")

    room = _watch_rooms.get(room_id)
    if not room:
        emit("error", {"message": "Room not found"})
        return

    # Get user's role level
    try:
        guild_id = int(room.guild_id)
        user_id_int = int(user_id)
        role_level = _get_user_role_level(guild_id, user_id_int)
    except (ValueError, TypeError):
        role_level = 0

    join_room(f"watch_{room_id}")
    room.viewers[request.sid] = {
        "name": username, "user_id": user_id,
        "avatar": avatar, "joined_at": datetime.now(timezone.utc).isoformat(),
        "role_level": role_level,
    }

    # Send current state to the new viewer
    emit("watch_state", {
        "is_playing":    room.is_playing,
        "current_time":  room.sync_time(),
        "video_url":     room.video_url,
        "title":         room.title,
        "host_id":       room.host_id,
        "host_name":     room.host_name,
        "viewer_count":  len(room.viewers),
        "chat_history":  room.chat[-50:],
        "my_role_level": role_level,
        "volume":        room.volume,
        "is_looping":    room.is_looping,
    })

    # Notify others
    emit("viewer_joined", {
        "name": username, "viewer_count": len(room.viewers)
    }, room=f"watch_{room_id}", include_self=False)


@socketio.on("watch_leave")
def on_watch_leave(data):
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if room and request.sid in room.viewers:
        name = room.viewers.pop(request.sid, {}).get("name", "Someone")
        leave_room(f"watch_{room_id}")
        emit("viewer_left", {
            "name": name, "viewer_count": len(room.viewers)
        }, room=f"watch_{room_id}")


@socketio.on("watch_play")
def on_watch_play(data):
    """Host plays the video — sync all viewers."""
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if not room:
        return
    
    user_id = session.get("user_id", "")
    viewer = room.viewers.get(request.sid, {})
    role_level = viewer.get("role_level", 0)
    
    # Only host (role_level >= 2 = Mod+) or owner can control
    if user_id != room.host_id and role_level < 2:
        emit("error", {"message": "Only mods and above can control playback"})
        return
    
    room.current_time = float(data.get("current_time", room.sync_time()))
    room.is_playing   = True
    room.last_sync    = _time.time()
    emit("watch_sync", {
        "action": "play", "current_time": room.current_time,
        "is_playing": True
    }, room=f"watch_{room_id}")


@socketio.on("watch_pause")
def on_watch_pause(data):
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if not room:
        return
    
    user_id = session.get("user_id", "")
    viewer = room.viewers.get(request.sid, {})
    role_level = viewer.get("role_level", 0)
    
    # Only host or mods+ can control
    if user_id != room.host_id and role_level < 2:
        emit("error", {"message": "Only mods and above can control playback"})
        return
    
    room.current_time = float(data.get("current_time", room.sync_time()))
    room.is_playing   = False
    room.last_sync    = _time.time()
    emit("watch_sync", {
        "action": "pause", "current_time": room.current_time,
        "is_playing": False
    }, room=f"watch_{room_id}")


@socketio.on("watch_seek")
def on_watch_seek(data):
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if not room:
        return
    
    user_id = session.get("user_id", "")
    viewer = room.viewers.get(request.sid, {})
    role_level = viewer.get("role_level", 0)
    
    # Only host or mods+ can seek
    if user_id != room.host_id and role_level < 2:
        emit("error", {"message": "Only mods and above can skip/seek"})
        return
    
    room.current_time = float(data.get("current_time", 0))
    room.last_sync    = _time.time()
    emit("watch_sync", {
        "action": "seek", "current_time": room.current_time,
        "is_playing": room.is_playing
    }, room=f"watch_{room_id}")


@socketio.on("watch_chat")
def on_watch_chat(data):
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if not room:
        return
    
    username = session.get("username", data.get("username", "Viewer"))
    msg = str(data.get("message", "")).strip()[:500]
    if not msg:
        return
    
    # Everyone can chat — guests included
    avatar = session.get("avatar_url", "")
    entry = {
        "user":   username,
        "avatar": avatar,
        "msg":    msg,
        "ts":     datetime.now(timezone.utc).strftime("%H:%M"),
        "user_id": session.get("user_id", ""),
    }
    room.chat.append(entry)
    if len(room.chat) > 200:
        room.chat = room.chat[-200:]
    emit("watch_chat_msg", entry, room=f"watch_{room_id}")


@socketio.on("watch_request_sync")
def on_watch_request_sync(data):
    """Viewer requests current state (e.g. after reconnect)."""
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if not room:
        return
    emit("watch_sync", {
        "action": "sync",
        "current_time": room.sync_time(),
        "is_playing": room.is_playing,
    })


@socketio.on("watch_mood_react")
def on_watch_mood_react(data):
    """Mood reaction that affects the screen for everyone."""
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if not room:
        return
    emoji = data.get("emoji", "")
    username = session.get("username", "Someone")
    emit("mood_effect", {"emoji": emoji, "user": username},
         room=f"watch_{room_id}")


@socketio.on("watch_bookmark")
def on_watch_bookmark(data):
    """Drop a timestamp bookmark visible to everyone."""
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if not room:
        return
    if not hasattr(room, "bookmarks"):
        room.bookmarks = []
    bm = {
        "ts": data.get("current_time", 0),
        "label": str(data.get("label", "📍"))[:40],
        "user": session.get("username", "Someone"),
        "id": secrets.token_hex(4),
    }
    room.bookmarks.append(bm)
    emit("bookmark_added", bm, room=f"watch_{room_id}")


@socketio.on("watch_prediction_create")
def on_prediction_create(data):
    """Mod creates a prediction poll."""
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if not room:
        return
    viewer = room.viewers.get(request.sid, {})
    if viewer.get("role_level", 0) < 2:
        emit("error", {"message": "Only mods+ can create predictions"})
        return
    if not hasattr(room, "prediction"):
        room.prediction = None
    room.prediction = {
        "id": secrets.token_hex(4),
        "question": str(data.get("question", ""))[:100],
        "options": [str(o)[:50] for o in data.get("options", [])[:4]],
        "votes": {},
        "resolved": False,
        "winner": None,
        "created_by": session.get("username", "Mod"),
    }
    emit("prediction_started", room.prediction, room=f"watch_{room_id}")


@socketio.on("watch_prediction_vote")
def on_prediction_vote(data):
    """User votes on a prediction."""
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if not room or not hasattr(room, "prediction") or not room.prediction:
        return
    if room.prediction.get("resolved"):
        emit("error", {"message": "Prediction already resolved"})
        return
    user_id = session.get("user_id", request.sid)
    option = int(data.get("option", 0))
    room.prediction["votes"][user_id] = option
    # Broadcast updated vote counts (without revealing who voted what)
    counts = [0] * len(room.prediction["options"])
    for v in room.prediction["votes"].values():
        if 0 <= v < len(counts):
            counts[v] += 1
    emit("prediction_votes", {"counts": counts, "total": len(room.prediction["votes"])},
         room=f"watch_{room_id}")


@socketio.on("watch_prediction_resolve")
def on_prediction_resolve(data):
    """Mod resolves a prediction with the winning option."""
    room_id = data.get("room_id")
    room = _watch_rooms.get(room_id)
    if not room or not hasattr(room, "prediction") or not room.prediction:
        return
    viewer = room.viewers.get(request.sid, {})
    if viewer.get("role_level", 0) < 2:
        return
    winner_idx = int(data.get("winner", 0))
    room.prediction["resolved"] = True
    room.prediction["winner"] = winner_idx
    # Calculate who got it right
    correct = [uid for uid, v in room.prediction["votes"].items() if v == winner_idx]
    emit("prediction_resolved", {
        "prediction": room.prediction,
        "correct_count": len(correct),
        "correct_users": correct,
    }, room=f"watch_{room_id}")


@socketio.on("disconnect")
def on_watch_disconnect():
    # Clean up viewer from any watch rooms
    for room in list(_watch_rooms.values()):
        if request.sid in room.viewers:
            name = room.viewers.pop(request.sid, {}).get("name", "Someone")
            emit("viewer_left", {
                "name": name, "viewer_count": len(room.viewers)
            }, room=f"watch_{room.room_id}")
