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
from datetime import datetime, timedelta, timezone
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

# Persistent data directory — set DATA_DIR env var on Render to a disk mount path
# Falls back to current directory for local dev
DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))

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
            # Always return JSON for /api/ routes
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'error': 'Authentication required', 'redirect': '/login'}), 401
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
        session['login_time'] = datetime.utcnow().isoformat()
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
        'timestamp': datetime.utcnow().isoformat()
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
        return jsonify({'bots': bots, 'total': len(bots), 'timestamp': datetime.utcnow().isoformat()})
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
            'timestamp': datetime.utcnow().isoformat()
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
            'linked_at': datetime.utcnow().isoformat(),
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
            'timestamp': datetime.utcnow().isoformat()
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
            'timestamp': datetime.utcnow().isoformat()
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
@app.route('/api/server/<server_id>/music/status')
@require_auth
def music_status(server_id):
    """Music status stub — returns not playing since music cog is not loaded."""
    return jsonify({'playing': False, 'current': None, 'track': None, 'queue': [], 'queue_size': 0, 'volume': 100})

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
        'expires': datetime.utcnow().timestamp() + 600,
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
    if datetime.utcnow().timestamp() > entry['expires']:
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
        'created_at': datetime.utcnow().isoformat(),
        'verified': True
    }
    _save_users(users)
    del _OTP_STORE[email]
    # Auto-login
    session.permanent = True
    session['user_id'] = pending['username']
    session['username'] = pending['username']
    session['login_time'] = datetime.utcnow().isoformat()
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
    entry['expires'] = datetime.utcnow().timestamp() + 600
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
        future = asyncio.run_coroutine_threadsafe(
            _dm_role_members(guild, role, roblox_cog), loop
        )
        result = future.result(timeout=30)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error(f"DM by role error: {e}")
        return jsonify({'error': str(e)}), 500

async def _dm_role_members(guild, role, roblox_cog):
    sent, failed, already_linked = 0, 0, 0
    for member in role.members:
        if member.bot:
            continue
        if member.id in roblox_cog.clan_members:
            already_linked += 1
            continue
        try:
            await roblox_cog._send_roblox_dm(member, guild)
            sent += 1
            await asyncio.sleep(0.5)
        except Exception:
            failed += 1
    return {'sent': sent, 'failed': failed, 'already_linked': already_linked, 'role': role.name}

@app.route('/api/server/<int:server_id>/roblox/dm-all', methods=['POST'])
@require_auth
def roblox_dm_all(server_id):
    """DM ALL unlinked members asking for their Roblox username"""
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

        async def _dm_all():
            sent = failed = already_linked = 0
            for member in guild.members:
                if member.bot:
                    continue
                if member.id in roblox_cog.clan_members:
                    already_linked += 1
                    continue
                try:
                    await roblox_cog._send_roblox_dm(member, guild)
                    sent += 1
                    await asyncio.sleep(0.6)
                except Exception:
                    failed += 1
            return {'sent': sent, 'failed': failed, 'already_linked': already_linked}

        result = asyncio.run_coroutine_threadsafe(_dm_all(), loop).result(timeout=120)
        return jsonify({'success': True, **result})
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
            cfg = welcome_cog._guild(int(server_id))
            return jsonify(cfg)

        data = request.json
        cfg = welcome_cog._guild(int(server_id))
        cfg.update({k: v for k, v in data.items() if v is not None and v != ''})
        welcome_cog._save()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Welcome config error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/welcome/test', methods=['POST'])
@require_auth
def test_welcome_message(server_id):
    """Send a test welcome/goodbye message"""
    try:
        msg_type = request.json.get('type', 'join')
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        guild = bot_instance.get_guild(int(server_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404

        welcome_cog = bot_instance.get_cog('Welcome')
        if not welcome_cog:
            return jsonify({'error': 'Welcome cog not loaded'}), 503

        event_map = {'join': 'welcome', 'leave': 'goodbye'}
        event = event_map.get(msg_type, 'welcome')
        member = guild.me

        async def _test():
            await welcome_cog._send_embed(member, welcome_cog._guild(int(server_id)), event)

        future = asyncio.run_coroutine_threadsafe(_test(), bot_instance.loop)
        future.result(timeout=10)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Welcome test error: {e}")
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
                    cfg = welcome_cog._guild(int(server_id))
                    cfg['verify_message_id'] = str(msg.id)
                    cfg['verify_role_id'] = str(role_id)
                    cfg['verify_channel_id'] = str(channel_id)
                    if data.get('unverify_role'):
                        cfg['unverify_role_id'] = str(data['unverify_role'])
                    welcome_cog._save()
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
                    cfg = welcome_cog._guild(int(server_id))
                    cfg['verify_question'] = question
                    cfg['verify_answer'] = answer
                    cfg['verify_role_id'] = str(role_id)
                    cfg['verify_channel_id'] = str(channel_id)
                    welcome_cog._save()
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
                'cur_xp': cur_xp,
                'needed': needed
            })
        entries.sort(key=lambda x: x['xp'], reverse=True)
        return jsonify({'leaderboard': entries[:20], 'total': len(entries)})
    except Exception as e:
        logger.error(f"XP leaderboard error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<server_id>/xp/config', methods=['POST'])
@require_auth
def xp_config(server_id):
    """Update XP config"""
    try:
        data = request.json
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        lvl_cog = bot_instance.get_cog('Leveling')
        if not lvl_cog:
            return jsonify({'error': 'Leveling cog not loaded'}), 503

        g = lvl_cog._guild(int(server_id))
        if data.get('channel_id'):
            g['config']['announce_channel'] = int(data['channel_id'])
        if data.get('multiplier'):
            g['config']['xp_multiplier'] = float(data['multiplier'])
        lvl_cog._save()
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
        if not level or not role_id:
            return jsonify({'error': 'level and role_id required'}), 400
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        lvl_cog = bot_instance.get_cog('Leveling')
        if not lvl_cog:
            return jsonify({'error': 'Leveling cog not loaded'}), 503

        g = lvl_cog._guild(int(server_id))
        g['config']['level_roles'][str(level)] = int(role_id)
        lvl_cog._save()
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
            'timestamp': datetime.utcnow().isoformat()
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

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
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
                                   'timestamp': datetime.utcnow().isoformat()})
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
