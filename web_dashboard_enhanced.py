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
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only in production
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
            import asyncio
            loop = bot_instance.loop or asyncio.get_event_loop()
            token_data = loop.run_until_complete(webdashboard_cog.verify_token(token))
            
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
@cache.cached(timeout=10, key_prefix='bot_status')
def bot_status():
    """Get bot status with caching"""
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
@cache.cached(timeout=60, key_prefix='servers_list')
def get_servers():
    """Get all servers with caching"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        
        servers = []
        for guild in bot_instance.guilds:
            servers.append({
                'id': guild.id,
                'name': guild.name,
                'icon': str(guild.icon.url) if guild.icon else None,
                'member_count': guild.member_count,
                'owner': str(guild.owner),
                'owner_id': guild.owner_id,
                'created_at': guild.created_at.isoformat(),
                'boost_level': guild.premium_tier,
                'boost_count': guild.premium_subscription_count or 0
            })
        
        return jsonify({'servers': servers, 'total': len(servers)})
    except Exception as e:
        logger.error(f"Error getting servers: {e}")
        return jsonify({'error': 'Failed to get servers'}), 500

@app.route('/api/server/<int:server_id>')
@require_auth
def get_server_details(server_id):
    """Get detailed server information"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        
        guild = bot_instance.get_guild(server_id)
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        # Detailed server info
        channels = {
            'text': [{'id': c.id, 'name': c.name, 'category': c.category.name if c.category else None} 
                     for c in guild.text_channels],
            'voice': [{'id': c.id, 'name': c.name, 'category': c.category.name if c.category else None} 
                      for c in guild.voice_channels],
            'categories': [{'id': c.id, 'name': c.name} for c in guild.categories]
        }
        
        roles = [{'id': r.id, 'name': r.name, 'color': str(r.color), 'members': len(r.members), 
                  'position': r.position} for r in guild.roles]
        
        members = {
            'total': guild.member_count,
            'online': len([m for m in guild.members if m.status != discord.Status.offline]),
            'bots': len([m for m in guild.members if m.bot]),
            'humans': len([m for m in guild.members if not m.bot])
        }
        
        return jsonify({
            'id': guild.id,
            'name': guild.name,
            'icon': str(guild.icon.url) if guild.icon else None,
            'banner': str(guild.banner.url) if guild.banner else None,
            'description': guild.description,
            'owner': {'id': guild.owner.id, 'name': str(guild.owner)},
            'channels': channels,
            'roles': roles,
            'members': members,
            'boost_level': guild.premium_tier,
            'boost_count': guild.premium_subscription_count or 0,
            'verification_level': str(guild.verification_level),
            'created_at': guild.created_at.isoformat(),
            'features': guild.features
        })
    except Exception as e:
        logger.error(f"Error getting server details: {e}")
        return jsonify({'error': 'Failed to get server details'}), 500

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
                        'id': g.id,
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

@app.route('/api/roblox/leaderboard/<category>')
@require_auth
@cache.cached(timeout=60, key_prefix='roblox_leaderboard')
def get_roblox_leaderboard(category):
    """Get Roblox leaderboard by category"""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if not roblox_cog:
            return jsonify({'error': 'Roblox integration not loaded'}), 503
        
        # Collect all player data
        all_stats = []
        for discord_id, member_info in roblox_cog.clan_members.items():
            player_data = roblox_cog.player_cache.get(discord_id)
            if player_data:
                all_stats.append(player_data)
        
        # Sort by category
        sort_keys = {
            'playtime': lambda x: x['stats']['playtime'],
            'coins': lambda x: x['stats']['coins_collected'],
            'kills': lambda x: x['stats']['kills'],
            'level': lambda x: x['stats']['level'],
            'kd': lambda x: x['stats']['kills'] / max(x['stats']['deaths'], 1)
        }
        
        sort_key = sort_keys.get(category, sort_keys['playtime'])
        all_stats.sort(key=sort_key, reverse=True)
        
        # Return top 20
        leaderboard = []
        for i, player in enumerate(all_stats[:20]):
            entry = {
                'rank': i + 1,
                'discord_id': player['discord_id'],
                'roblox_username': player['roblox_username'],
                'display_name': player['display_name'],
                'is_online': player['is_online'],
                'stats': player['stats']
            }
            
            if category == 'kd':
                entry['value'] = player['stats']['kills'] / max(player['stats']['deaths'], 1)
            else:
                entry['value'] = player['stats'].get(category if category != 'coins' else 'coins_collected', 0)
            
            leaderboard.append(entry)
        
        return jsonify({
            'category': category,
            'leaderboard': leaderboard,
            'total_players': len(all_stats),
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

# ── Commands Manager ─────────────────────────────────────────────────────────

# Persisted disabled commands set
_DISABLED_COMMANDS_FILE = 'disabled_commands.json'
_disabled_commands: set = set()

def _load_disabled_commands():
    global _disabled_commands
    try:
        if os.path.exists(_DISABLED_COMMANDS_FILE):
            with open(_DISABLED_COMMANDS_FILE) as f:
                _disabled_commands = set(json.load(f))
    except Exception:
        _disabled_commands = set()

def _save_disabled_commands():
    try:
        with open(_DISABLED_COMMANDS_FILE, 'w') as f:
            json.dump(list(_disabled_commands), f)
    except Exception:
        pass

_load_disabled_commands()

# Custom commands storage
_CUSTOM_COMMANDS_FILE = 'custom_commands_dashboard.json'
_custom_commands: list = []

def _load_custom_commands():
    global _custom_commands
    try:
        if os.path.exists(_CUSTOM_COMMANDS_FILE):
            with open(_CUSTOM_COMMANDS_FILE) as f:
                _custom_commands = json.load(f)
    except Exception:
        _custom_commands = []

def _save_custom_commands():
    try:
        with open(_CUSTOM_COMMANDS_FILE, 'w') as f:
            json.dump(_custom_commands, f, indent=2)
    except Exception:
        pass

_load_custom_commands()

# Map of response types to generated code templates
_RESPONSE_TEMPLATES = {
    'text': '''    @app_commands.command(name="{name}", description="{description}")
    async def {func_name}(self, interaction: discord.Interaction):
        await interaction.response.send_message("{response}")''',

    'embed': '''    @app_commands.command(name="{name}", description="{description}")
    async def {func_name}(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="{name}",
            description="{response}",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed)''',

    'dm': '''    @app_commands.command(name="{name}", description="{description}")
    async def {func_name}(self, interaction: discord.Interaction):
        try:
            await interaction.user.send("{response}")
            await interaction.response.send_message("✅ Sent you a DM!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Could not DM you.", ephemeral=True)''',

    'ephemeral': '''    @app_commands.command(name="{name}", description="{description}")
    async def {func_name}(self, interaction: discord.Interaction):
        await interaction.response.send_message("{response}", ephemeral=True)''',
}

def _generate_cog_file(commands: list) -> str:
    """Generate a full cog Python file from a list of custom command dicts."""
    methods = []
    for cmd in commands:
        name = cmd['name'].lower().replace(' ', '_').replace('-', '_')
        tmpl = _RESPONSE_TEMPLATES.get(cmd.get('response_type', 'text'), _RESPONSE_TEMPLATES['text'])
        methods.append(tmpl.format(
            name=cmd['name'],
            func_name=name,
            description=cmd.get('description', 'Custom command'),
            response=cmd.get('response', '').replace('"', '\\"'),
        ))

    body = '\n\n'.join(methods) if methods else '    pass'
    return f'''"""Auto-generated custom commands from WAN Bot Dashboard"""
import discord
from discord import app_commands
from discord.ext import commands


class DashboardCustomCommands(commands.Cog):
    """Custom commands created via the web dashboard."""

    def __init__(self, bot):
        self.bot = bot

{body}


async def setup(bot):
    await bot.add_cog(DashboardCustomCommands(bot))
'''

@app.route('/api/commands')
@require_auth
def get_all_commands():
    """Return all registered slash commands grouped by cog."""
    try:
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        groups: dict = {}
        for cmd in bot_instance.tree.get_commands():
            cog_name = 'Uncategorized'
            # Find which cog owns this command
            for cog in bot_instance.cogs.values():
                for c in cog.get_app_commands():
                    if c.name == cmd.name:
                        cog_name = type(cog).__name__
                        break
            groups.setdefault(cog_name, []).append({
                'name': cmd.name,
                'description': cmd.description,
                'enabled': cmd.name not in _disabled_commands,
            })

        return jsonify({
            'groups': groups,
            'total': sum(len(v) for v in groups.values()),
            'disabled_count': len(_disabled_commands),
        })
    except Exception as e:
        logger.error(f"get_all_commands error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/commands/toggle', methods=['POST'])
@require_auth
def toggle_command():
    """Enable or disable a slash command by name."""
    try:
        data = request.get_json()
        name = (data or {}).get('name', '').strip()
        enabled = (data or {}).get('enabled', True)
        if not name:
            return jsonify({'error': 'name required'}), 400

        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503

        if enabled:
            _disabled_commands.discard(name)
        else:
            _disabled_commands.add(name)
        _save_disabled_commands()

        # Apply to the command tree at runtime
        loop = bot_instance.loop
        async def _apply():
            for cmd in bot_instance.tree.get_commands():
                if cmd.name == name:
                    # discord.py doesn't have a built-in disable, so we patch the callback
                    if not enabled:
                        async def _disabled_handler(interaction: discord.Interaction, **_):
                            await interaction.response.send_message(
                                f"❌ The `/{name}` command is currently disabled.", ephemeral=True)
                        cmd._callback = _disabled_handler
                    else:
                        # Reload the cog to restore original callback
                        for cog in list(bot_instance.cogs.values()):
                            for c in cog.get_app_commands():
                                if c.name == name:
                                    # Re-add cog to restore
                                    cog_class = type(cog)
                                    cog_name = cog_class.__name__
                                    await bot_instance.remove_cog(cog_name)
                                    await bot_instance.add_cog(cog_class(bot_instance))
                                    return
        asyncio.run_coroutine_threadsafe(_apply(), loop).result(timeout=10)

        return jsonify({'success': True, 'name': name, 'enabled': enabled})
    except Exception as e:
        logger.error(f"toggle_command error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/commands/custom', methods=['GET'])
@require_auth
def get_custom_commands():
    return jsonify({'commands': _custom_commands})


@app.route('/api/commands/custom', methods=['POST'])
@require_auth
def create_custom_command():
    """Create a new custom command and hot-reload it into the bot."""
    try:
        data = request.get_json() or {}
        name = data.get('name', '').strip().lower().replace(' ', '-')
        description = data.get('description', '').strip()
        response = data.get('response', '').strip()
        response_type = data.get('response_type', 'text')

        if not name or not response:
            return jsonify({'error': 'name and response are required'}), 400
        if len(name) > 32:
            return jsonify({'error': 'name must be 32 chars or less'}), 400
        if any(c['name'] == name for c in _custom_commands):
            return jsonify({'error': f'Command /{name} already exists'}), 409

        cmd_entry = {
            'name': name,
            'description': description or f'Custom command: {name}',
            'response': response,
            'response_type': response_type,
            'created_at': datetime.utcnow().isoformat(),
        }
        _custom_commands.append(cmd_entry)
        _save_custom_commands()

        # Write and reload the cog
        cog_path = os.path.join(os.path.dirname(__file__), 'cogs', 'dashboard_custom.py')
        with open(cog_path, 'w') as f:
            f.write(_generate_cog_file(_custom_commands))

        if bot_instance and bot_instance.is_ready():
            loop = bot_instance.loop
            async def _reload():
                if 'DashboardCustomCommands' in bot_instance.cogs:
                    await bot_instance.remove_cog('DashboardCustomCommands')
                await bot_instance.load_extension('cogs.dashboard_custom')
                await bot_instance.tree.sync()
            asyncio.run_coroutine_threadsafe(_reload(), loop).result(timeout=15)

        return jsonify({'success': True, 'command': cmd_entry}), 201
    except Exception as e:
        logger.error(f"create_custom_command error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/commands/custom/<name>', methods=['DELETE'])
@require_auth
def delete_custom_command(name: str):
    """Delete a custom command and reload the cog."""
    try:
        global _custom_commands
        before = len(_custom_commands)
        _custom_commands = [c for c in _custom_commands if c['name'] != name]
        if len(_custom_commands) == before:
            return jsonify({'error': 'Command not found'}), 404
        _save_custom_commands()

        cog_path = os.path.join(os.path.dirname(__file__), 'cogs', 'dashboard_custom.py')
        with open(cog_path, 'w') as f:
            f.write(_generate_cog_file(_custom_commands))

        if bot_instance and bot_instance.is_ready():
            loop = bot_instance.loop
            async def _reload():
                if 'DashboardCustomCommands' in bot_instance.cogs:
                    await bot_instance.remove_cog('DashboardCustomCommands')
                if _custom_commands:
                    await bot_instance.load_extension('cogs.dashboard_custom')
                await bot_instance.tree.sync()
            asyncio.run_coroutine_threadsafe(_reload(), loop).result(timeout=15)

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"delete_custom_command error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/commands/custom/<name>/code', methods=['GET'])
@require_auth
def get_custom_command_code(name: str):
    """Return the generated Python code for a custom command."""
    cmd = next((c for c in _custom_commands if c['name'] == name), None)
    if not cmd:
        return jsonify({'error': 'Not found'}), 404
    tmpl = _RESPONSE_TEMPLATES.get(cmd.get('response_type', 'text'), _RESPONSE_TEMPLATES['text'])
    func_name = name.replace('-', '_')
    code = tmpl.format(
        name=cmd['name'], func_name=func_name,
        description=cmd.get('description', ''), response=cmd.get('response', '').replace('"', '\\"')
    )
    return jsonify({'code': code})


def broadcast_update(event_type: str, data: dict, room: str = None):
    """Broadcast update to all connected clients or specific room"""
    try:
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
