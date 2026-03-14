"""
WAN Bot - Server Management API Endpoints
Full control over Discord server from web dashboard
"""

from flask import jsonify, request
from functools import wraps
import discord
import asyncio
import logging

logger = logging.getLogger('dashboard')

def async_action(f):
    """Decorator to run async Discord actions"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        from web_dashboard_enhanced import bot_instance
        if not bot_instance or not bot_instance.is_ready():
            return jsonify({'error': 'Bot not ready'}), 503
        
        loop = bot_instance.loop
        if not loop or not loop.is_running():
            return jsonify({'error': 'Bot event loop not running'}), 503
        
        try:
            future = asyncio.run_coroutine_threadsafe(f(*args, **kwargs), loop)
            result = future.result(timeout=30)
            return result
        except TimeoutError:
            logger.error(f"Timeout in async action {f.__name__}")
            return jsonify({'error': 'Action timed out — try again'}), 504
        except Exception as e:
            logger.error(f"Error in async action {f.__name__}: {e}")
            return jsonify({'error': str(e)}), 500
    return wrapper

# ===== ROLE MANAGEMENT =====

@async_action
async def create_role_action(server_id, role_data):
    """Create a new role in the server"""
    from web_dashboard_enhanced import bot_instance
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    # Create role with specified properties
    role = await guild.create_role(
        name=role_data.get('name', 'New Role'),
        permissions=discord.Permissions(int(role_data.get('permissions', 0))),
        color=discord.Color(int(role_data.get('color', '0x99AAB5').replace('#', '0x'), 16)),
        hoist=role_data.get('hoist', False),
        mentionable=role_data.get('mentionable', False),
        reason=f"Created via dashboard by {request.remote_addr}"
    )
    
    return jsonify({
        'success': True,
        'role': {
            'id': str(role.id),
            'name': role.name,
            'color': str(role.color),
            'position': role.position
        }
    })

@async_action
async def edit_role_action(server_id, role_id, role_data):
    """Edit an existing role"""
    from web_dashboard_enhanced import bot_instance
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    role = guild.get_role(int(role_id))
    if not role:
        return jsonify({'error': 'Role not found'}), 404
    
    # Update role properties
    await role.edit(
        name=role_data.get('name', role.name),
        permissions=discord.Permissions(int(role_data.get('permissions', role.permissions.value))),
        color=discord.Color(int(role_data.get('color', str(role.color)).replace('#', '0x'), 16)),
        hoist=role_data.get('hoist', role.hoist),
        mentionable=role_data.get('mentionable', role.mentionable),
        reason=f"Edited via dashboard by {request.remote_addr}"
    )
    
    return jsonify({'success': True, 'message': f'Role {role.name} updated'})

@async_action
async def delete_role_action(server_id, role_id):
    """Delete a role"""
    from web_dashboard_enhanced import bot_instance
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    role = guild.get_role(int(role_id))
    if not role:
        return jsonify({'error': 'Role not found'}), 404
    
    await role.delete(reason=f"Deleted via dashboard by {request.remote_addr}")
    
    return jsonify({'success': True, 'message': f'Role deleted'})

@async_action
async def assign_role_action(server_id, member_id, role_id, action='add'):
    """Assign or remove role from member"""
    from web_dashboard_enhanced import bot_instance
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    member = guild.get_member(int(member_id))
    if not member:
        return jsonify({'error': 'Member not found'}), 404
    
    role = guild.get_role(int(role_id))
    if not role:
        return jsonify({'error': 'Role not found'}), 404
    
    if action == 'add':
        await member.add_roles(role, reason=f"Assigned via dashboard by {request.remote_addr}")
        message = f'Role {role.name} assigned to {member.name}'
    else:
        await member.remove_roles(role, reason=f"Removed via dashboard by {request.remote_addr}")
        message = f'Role {role.name} removed from {member.name}'
    
    return jsonify({'success': True, 'message': message})

# ===== CHANNEL MANAGEMENT =====

@async_action
async def create_channel_action(server_id, channel_data):
    """Create a new channel"""
    from web_dashboard_enhanced import bot_instance
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    channel_type = channel_data.get('type', 'text')
    category = None
    if channel_data.get('category_id'):
        category = guild.get_channel(int(channel_data['category_id']))
    
    if channel_type == 'text':
        channel = await guild.create_text_channel(
            name=channel_data.get('name', 'new-channel'),
            category=category,
            topic=channel_data.get('topic'),
            slowmode_delay=channel_data.get('slowmode', 0),
            nsfw=channel_data.get('nsfw', False),
            reason=f"Created via dashboard by {request.remote_addr}"
        )
    elif channel_type == 'voice':
        channel = await guild.create_voice_channel(
            name=channel_data.get('name', 'New Voice'),
            category=category,
            bitrate=channel_data.get('bitrate', 64000),
            user_limit=channel_data.get('user_limit', 0),
            reason=f"Created via dashboard by {request.remote_addr}"
        )
    elif channel_type == 'category':
        channel = await guild.create_category(
            name=channel_data.get('name', 'New Category'),
            reason=f"Created via dashboard by {request.remote_addr}"
        )
    else:
        return jsonify({'error': 'Invalid channel type'}), 400
    
    return jsonify({
        'success': True,
        'channel': {
            'id': str(channel.id),
            'name': channel.name,
            'type': str(channel.type)
        }
    })

@async_action
async def edit_channel_action(server_id, channel_id, channel_data):
    """Edit a channel"""
    from web_dashboard_enhanced import bot_instance
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    channel = guild.get_channel(int(channel_id))
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    # Update channel properties based on type
    if isinstance(channel, discord.TextChannel):
        await channel.edit(
            name=channel_data.get('name', channel.name),
            topic=channel_data.get('topic', channel.topic),
            slowmode_delay=channel_data.get('slowmode', channel.slowmode_delay),
            nsfw=channel_data.get('nsfw', channel.nsfw),
            reason=f"Edited via dashboard by {request.remote_addr}"
        )
    elif isinstance(channel, discord.VoiceChannel):
        await channel.edit(
            name=channel_data.get('name', channel.name),
            bitrate=channel_data.get('bitrate', channel.bitrate),
            user_limit=channel_data.get('user_limit', channel.user_limit),
            reason=f"Edited via dashboard by {request.remote_addr}"
        )
    
    return jsonify({'success': True, 'message': f'Channel {channel.name} updated'})

@async_action
async def delete_channel_action(server_id, channel_id):
    """Delete a channel"""
    from web_dashboard_enhanced import bot_instance
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    channel = guild.get_channel(int(channel_id))
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    await channel.delete(reason=f"Deleted via dashboard by {request.remote_addr}")
    
    return jsonify({'success': True, 'message': 'Channel deleted'})

# ===== SERVER DECORATION =====

@async_action
async def update_server_icon_action(server_id, icon_url):
    """Update server icon"""
    from web_dashboard_enhanced import bot_instance
    import aiohttp
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    # Download image
    async with aiohttp.ClientSession() as session:
        async with session.get(icon_url) as resp:
            if resp.status != 200:
                return jsonify({'error': 'Failed to download image'}), 400
            image_data = await resp.read()
    
    await guild.edit(icon=image_data, reason=f"Icon updated via dashboard by {request.remote_addr}")
    
    return jsonify({'success': True, 'message': 'Server icon updated'})

@async_action
async def update_server_banner_action(server_id, banner_url):
    """Update server banner"""
    from web_dashboard_enhanced import bot_instance
    import aiohttp
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    # Download image
    async with aiohttp.ClientSession() as session:
        async with session.get(banner_url) as resp:
            if resp.status != 200:
                return jsonify({'error': 'Failed to download image'}), 400
            image_data = await resp.read()
    
    await guild.edit(banner=image_data, reason=f"Banner updated via dashboard by {request.remote_addr}")
    
    return jsonify({'success': True, 'message': 'Server banner updated'})

@async_action
async def create_emoji_action(server_id, emoji_data):
    """Create custom emoji"""
    from web_dashboard_enhanced import bot_instance
    import aiohttp
    import base64
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    # Get image data
    if emoji_data.get('url'):
        async with aiohttp.ClientSession() as session:
            async with session.get(emoji_data['url']) as resp:
                if resp.status != 200:
                    return jsonify({'error': 'Failed to download image'}), 400
                image_data = await resp.read()
    elif emoji_data.get('base64'):
        image_data = base64.b64decode(emoji_data['base64'])
    else:
        return jsonify({'error': 'No image provided'}), 400
    
    emoji = await guild.create_custom_emoji(
        name=emoji_data.get('name', 'custom_emoji'),
        image=image_data,
        reason=f"Created via dashboard by {request.remote_addr}"
    )
    
    return jsonify({
        'success': True,
        'emoji': {
            'id': str(emoji.id),
            'name': emoji.name,
            'url': str(emoji.url)
        }
    })

# ===== MEMBER MANAGEMENT =====

@async_action
async def kick_member_action(server_id, member_id, reason=''):
    """Kick a member"""
    from web_dashboard_enhanced import bot_instance
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    member = guild.get_member(int(member_id))
    if not member:
        return jsonify({'error': 'Member not found'}), 404
    
    await member.kick(reason=f"{reason} (via dashboard by {request.remote_addr})")
    
    return jsonify({'success': True, 'message': f'{member.name} has been kicked'})

@async_action
async def ban_member_action(server_id, member_id, reason='', delete_days=0):
    """Ban a member"""
    from web_dashboard_enhanced import bot_instance
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    member = guild.get_member(int(member_id))
    if not member:
        return jsonify({'error': 'Member not found'}), 404
    
    await member.ban(
        reason=f"{reason} (via dashboard by {request.remote_addr})",
        delete_message_days=delete_days
    )
    
    return jsonify({'success': True, 'message': f'{member.name} has been banned'})

@async_action
async def timeout_member_action(server_id, member_id, duration, reason=''):
    """Timeout a member"""
    from web_dashboard_enhanced import bot_instance
    from datetime import timedelta
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    member = guild.get_member(int(member_id))
    if not member:
        return jsonify({'error': 'Member not found'}), 404
    
    await member.timeout(
        timedelta(minutes=duration),
        reason=f"{reason} (via dashboard by {request.remote_addr})"
    )
    
    return jsonify({'success': True, 'message': f'{member.name} has been timed out for {duration} minutes'})

# ===== BADGE MANAGEMENT =====

@async_action
async def assign_badge_action(server_id, member_id, badge_name):
    """Assign badge to member — creates role if needed"""
    from web_dashboard_enhanced import bot_instance

    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404

    member = guild.get_member(int(member_id))
    if not member:
        # Try fetching from API in case member isn't cached
        try:
            member = await guild.fetch_member(int(member_id))
        except Exception:
            return jsonify({'error': 'Member not found'}), 404

    # Badge emoji map
    badge_emojis = {
        'Owner': '👑', 'Admin': '⚡', 'Manager': '🛡️',
        'Moderator': '🔨', 'Helper': '💚', 'VIP': '⭐',
        'Booster': '💎', 'Member': '✅',
    }
    badge_colors = {
        'Owner': 0xFF0000, 'Admin': 0xFF4444, 'Manager': 0xFF8800,
        'Moderator': 0x00CC44, 'Helper': 0x00FFFF, 'VIP': 0xFFD700,
        'Booster': 0xFF69B4, 'Member': 0x0099FF,
    }

    emoji = badge_emojis.get(badge_name, '🏅')
    color = badge_colors.get(badge_name, 0xFFD700)
    role_name = f"{emoji} {badge_name}"

    # Find or create the badge role
    badge_role = discord.utils.get(guild.roles, name=role_name)
    if not badge_role:
        badge_role = await guild.create_role(
            name=role_name,
            color=discord.Color(color),
            hoist=True,
            mentionable=False,
            reason="Badge role created via dashboard"
        )

    if badge_role in member.roles:
        return jsonify({'success': True, 'message': f'{member.display_name} already has the {badge_name} badge'})

    await member.add_roles(badge_role, reason="Badge assigned via dashboard")
    return jsonify({'success': True, 'message': f'Badge {badge_name} assigned to {member.display_name}'})

# ===== SERVER SETTINGS =====

@async_action
async def update_server_settings_action(server_id, settings):
    """Update server settings"""
    from web_dashboard_enhanced import bot_instance
    
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Server not found'}), 404
    
    # Update various server settings
    await guild.edit(
        name=settings.get('name', guild.name),
        description=settings.get('description', guild.description),
        verification_level=discord.VerificationLevel[settings.get('verification_level', 'none')],
        default_notifications=discord.NotificationLevel[settings.get('notifications', 'all_messages')],
        explicit_content_filter=discord.ContentFilter[settings.get('content_filter', 'disabled')],
        reason=f"Settings updated via dashboard by {request.remote_addr}"
    )
    
    return jsonify({'success': True, 'message': 'Server settings updated'})
