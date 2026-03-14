"""
WAN Bot - Ultimate Web Dashboard
Complete server control from your browser!
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
import discord
from discord.ext import commands
import asyncio
import threading
import os
from datetime import datetime, timedelta
import json
import secrets
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global bot instance
bot_instance = None
bot_thread = None

# Dashboard data cache
dashboard_data = {
    'servers': {},
    'analytics': {},
    'logs': [],
    'active_users': 0,
    'bot_status': 'offline'
}

# Authentication (simple - enhance for production)
ADMIN_USERS = {}  # {user_id: {'username': '', 'password_hash': '', 'permissions': []}}

def require_auth(f):
    """Decorator for routes requiring authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        # Simple auth (enhance for production with proper hashing)
        if username == 'admin' and password == 'admin':  # Change this!
            session['user_id'] = 'admin'
            session['username'] = username
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'Invalid credentials'})
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/bot/status')
@require_auth
def bot_status():
    """Get bot status"""
    if bot_instance and bot_instance.is_ready():
        return jsonify({
            'status': 'online',
            'latency': round(bot_instance.latency * 1000),
            'servers': len(bot_instance.guilds),
            'users': sum(g.member_count for g in bot_instance.guilds),
            'uptime': str(datetime.utcnow() - bot_instance.start_time) if hasattr(bot_instance, 'start_time') else 'Unknown'
        })
    return jsonify({'status': 'offline'})

@app.route('/api/servers')
@require_auth
def get_servers():
    """Get all servers"""
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
            'created_at': guild.created_at.isoformat()
        })
    
    return jsonify({'servers': servers})

@app.route('/api/server/<int:server_id>')
@require_auth
def get_server_details(server_id):
    """Get detailed server information"""
    if not bot_instance or not bot_instance.is_ready():
        return jsonify({'error': 'Bot not ready'}), 503
    
    guild = bot_instance.get_guild(server_id)
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    # Detailed server info
    channels = {
        'text': [{'id': c.id, 'name': c.name, 'category': c.category.name if c.category else None} for c in guild.text_channels],
        'voice': [{'id': c.id, 'name': c.name, 'category': c.category.name if c.category else None} for c in guild.voice_channels],
        'categories': [{'id': c.id, 'name': c.name} for c in guild.categories]
    }
    
    roles = [{'id': r.id, 'name': r.name, 'color': str(r.color), 'members': len(r.members)} for r in guild.roles]
    
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
        'boost_count': guild.premium_subscription_count,
        'verification_level': str(guild.verification_level),
        'created_at': guild.created_at.isoformat()
    })

@app.route('/api/server/<int:server_id>/members')
@require_auth
def get_server_members(server_id):
    """Get server members"""
    if not bot_instance or not bot_instance.is_ready():
        return jsonify({'error': 'Bot not ready'}), 503
    
    guild = bot_instance.get_guild(server_id)
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    members = []
    for member in guild.members[:100]:  # Limit to 100 for performance
        members.append({
            'id': member.id,
            'name': str(member),
            'display_name': member.display_name,
            'avatar': str(member.display_avatar.url),
            'status': str(member.status),
            'bot': member.bot,
            'joined_at': member.joined_at.isoformat() if member.joined_at else None,
            'roles': [r.name for r in member.roles[1:]]  # Skip @everyone
        })
    
    return jsonify({'members': members, 'total': guild.member_count})

@app.route('/api/server/<int:server_id>/channels/<int:channel_id>/messages')
@require_auth
def get_channel_messages(server_id, channel_id):
    """Get channel messages"""
    if not bot_instance or not bot_instance.is_ready():
        return jsonify({'error': 'Bot not ready'}), 503
    
    guild = bot_instance.get_guild(server_id)
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    channel = guild.get_channel(channel_id)
    if not channel or not isinstance(channel, discord.TextChannel):
        return jsonify({'error': 'Channel not found'}), 404
    
    # Get recent messages
    messages = []
    async def fetch_messages():
        async for message in channel.history(limit=50):
            messages.append({
                'id': message.id,
                'author': {
                    'id': message.author.id,
                    'name': str(message.author),
                    'avatar': str(message.author.display_avatar.url)
                },
                'content': message.content,
                'timestamp': message.created_at.isoformat(),
                'attachments': [a.url for a in message.attachments],
                'embeds': len(message.embeds)
            })
    
    # Run async function
    asyncio.run_coroutine_threadsafe(fetch_messages(), bot_instance.loop).result()
    
    return jsonify({'messages': messages})

@app.route('/api/server/<int:server_id>/send_message', methods=['POST'])
@require_auth
def send_message(server_id):
    """Send message to channel"""
    if not bot_instance or not bot_instance.is_ready():
        return jsonify({'error': 'Bot not ready'}), 503
    
    data = request.json
    channel_id = data.get('channel_id')
    content = data.get('content')
    
    if not channel_id or not content:
        return jsonify({'error': 'Missing channel_id or content'}), 400
    
    guild = bot_instance.get_guild(server_id)
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    channel = guild.get_channel(channel_id)
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    async def send():
        await channel.send(content)
    
    asyncio.run_coroutine_threadsafe(send(), bot_instance.loop)
    
    return jsonify({'success': True})

@app.route('/api/server/<int:server_id>/moderation/kick', methods=['POST'])
@require_auth
def kick_member(server_id):
    """Kick member"""
    if not bot_instance or not bot_instance.is_ready():
        return jsonify({'error': 'Bot not ready'}), 503
    
    data = request.json
    member_id = data.get('member_id')
    reason = data.get('reason', 'Kicked via web dashboard')
    
    guild = bot_instance.get_guild(server_id)
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    member = guild.get_member(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404
    
    async def kick():
        await member.kick(reason=reason)
    
    asyncio.run_coroutine_threadsafe(kick(), bot_instance.loop)
    
    return jsonify({'success': True})

@app.route('/api/server/<int:server_id>/moderation/ban', methods=['POST'])
@require_auth
def ban_member(server_id):
    """Ban member"""
    if not bot_instance or not bot_instance.is_ready():
        return jsonify({'error': 'Bot not ready'}), 503
    
    data = request.json
    member_id = data.get('member_id')
    reason = data.get('reason', 'Banned via web dashboard')
    delete_days = data.get('delete_days', 0)
    
    guild = bot_instance.get_guild(server_id)
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    member = guild.get_member(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404
    
    async def ban():
        await member.ban(reason=reason, delete_message_days=delete_days)
    
    asyncio.run_coroutine_threadsafe(ban(), bot_instance.loop)
    
    return jsonify({'success': True})

@app.route('/api/server/<int:server_id>/analytics')
@require_auth
def get_server_analytics(server_id):
    """Get server analytics"""
    if not bot_instance or not bot_instance.is_ready():
        return jsonify({'error': 'Bot not ready'}), 503
    
    guild = bot_instance.get_guild(server_id)
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    # Generate analytics (simulated - enhance with real data)
    analytics = {
        'member_growth': {
            'current': guild.member_count,
            'change_24h': 5,
            'change_7d': 23,
            'change_30d': 87
        },
        'activity': {
            'messages_24h': 1234,
            'voice_minutes_24h': 567,
            'active_users_24h': 89
        },
        'engagement': {
            'reactions_24h': 456,
            'emoji_usage_24h': 234,
            'pins_total': 45
        },
        'moderation': {
            'warnings_7d': 3,
            'timeouts_7d': 1,
            'bans_7d': 0
        }
    }
    
    return jsonify(analytics)

@app.route('/api/server/<int:server_id>/settings', methods=['GET', 'POST'])
@require_auth
def server_settings(server_id):
    """Get or update server settings"""
    if not bot_instance or not bot_instance.is_ready():
        return jsonify({'error': 'Bot not ready'}), 503
    
    guild = bot_instance.get_guild(server_id)
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    if request.method == 'POST':
        # Update settings
        data = request.json
        # Implement settings update logic here
        return jsonify({'success': True})
    
    # Get current settings
    settings = {
        'prefix': '/',
        'language': 'en',
        'timezone': 'UTC',
        'welcome_channel': None,
        'log_channel': None,
        'auto_role': None,
        'xp_enabled': True,
        'moderation': {
            'auto_mod_enabled': True,
            'spam_detection': True,
            'link_filter': False
        }
    }
    
    return jsonify(settings)

@app.route('/api/logs')
@require_auth
def get_logs():
    """Get bot logs"""
    return jsonify({'logs': dashboard_data['logs'][-100:]})  # Last 100 logs

@app.route('/api/commands/execute', methods=['POST'])
@require_auth
def execute_command():
    """Execute bot command"""
    if not bot_instance or not bot_instance.is_ready():
        return jsonify({'error': 'Bot not ready'}), 503
    
    data = request.json
    server_id = data.get('server_id')
    command = data.get('command')
    
    # Execute command logic here
    return jsonify({'success': True, 'result': 'Command executed'})

# WebSocket events for real-time updates
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('connected', {'data': 'Connected to WAN Bot Dashboard'})

@socketio.on('subscribe_server')
def handle_subscribe(data):
    """Subscribe to server updates"""
    server_id = data.get('server_id')
    # Join room for server-specific updates
    from flask_socketio import join_room
    join_room(f'server_{server_id}')
    emit('subscribed', {'server_id': server_id})

def broadcast_update(event_type, data):
    """Broadcast update to all connected clients"""
    socketio.emit(event_type, data)

def start_web_dashboard(bot, host='0.0.0.0', port=5000):
    """Start the web dashboard"""
    global bot_instance
    bot_instance = bot
    
    print(f"🌐 Starting Web Dashboard on http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    print("⚠️  Run this through bot.py, not directly!")
    print("The web dashboard will start automatically with the bot.")
