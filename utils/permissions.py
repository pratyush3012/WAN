import discord
from discord import app_commands
from discord.ext import commands
from functools import wraps
import os

def is_owner():
    """Check if user is bot owner"""
    async def predicate(interaction: discord.Interaction) -> bool:
        owner_id = int(os.getenv('OWNER_ID', 0))
        if interaction.user.id != owner_id:
            await interaction.response.send_message(
                "❌ This command is only available to the bot owner.",
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)

def is_admin():
    """Check if user is admin (has Administrator permission)"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message(
            "❌ This command requires Administrator permission.",
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)

def is_moderator():
    """Check if user is moderator (has Manage Messages or Moderate Members permission)"""
    async def predicate(interaction: discord.Interaction) -> bool:
        perms = interaction.user.guild_permissions
        if perms.administrator or perms.manage_messages or perms.moderate_members:
            return True
        await interaction.response.send_message(
            "❌ This command requires Moderator permissions.",
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)

def is_member():
    """Check if user is a verified member (not a guest)"""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Check if user has been in server for at least 10 minutes
        if interaction.user.joined_at:
            from datetime import datetime, timedelta
            time_in_server = datetime.utcnow() - interaction.user.joined_at.replace(tzinfo=None)
            if time_in_server < timedelta(minutes=10):
                await interaction.response.send_message(
                    "❌ You must be in the server for at least 10 minutes to use this command.",
                    ephemeral=True
                )
                return False
        return True
    return app_commands.check(predicate)

def has_role(role_name: str):
    """Check if user has a specific role"""
    async def predicate(interaction: discord.Interaction) -> bool:
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role and role in interaction.user.roles:
            return True
        await interaction.response.send_message(
            f"❌ You need the **{role_name}** role to use this command.",
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)

def cooldown_by_role(guest_rate: int, member_rate: int, mod_rate: int):
    """Apply different cooldowns based on user role"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            perms = interaction.user.guild_permissions
            
            # Determine cooldown based on role
            if perms.administrator:
                cooldown = 0  # No cooldown for admins
            elif perms.manage_messages or perms.moderate_members:
                cooldown = mod_rate
            else:
                # Check if member or guest
                if interaction.user.joined_at:
                    from datetime import datetime, timedelta
                    time_in_server = datetime.utcnow() - interaction.user.joined_at.replace(tzinfo=None)
                    if time_in_server >= timedelta(minutes=10):
                        cooldown = member_rate
                    else:
                        cooldown = guest_rate
                else:
                    cooldown = guest_rate
            
            # Apply cooldown logic here if needed
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator

class PermissionLevel:
    """Permission levels for commands"""
    GUEST = 0
    MEMBER = 1
    MODERATOR = 2
    ADMIN = 3
    OWNER = 4

def get_permission_level(user: discord.Member) -> int:
    """Get user's permission level"""
    owner_id = int(os.getenv('OWNER_ID', 0))
    
    if user.id == owner_id:
        return PermissionLevel.OWNER
    
    if user.guild_permissions.administrator:
        return PermissionLevel.ADMIN
    
    if user.guild_permissions.manage_messages or user.guild_permissions.moderate_members:
        return PermissionLevel.MODERATOR
    
    # Check if member (in server for 10+ minutes)
    if user.joined_at:
        from datetime import datetime, timedelta
        time_in_server = datetime.utcnow() - user.joined_at.replace(tzinfo=None)
        if time_in_server >= timedelta(minutes=10):
            return PermissionLevel.MEMBER
    
    return PermissionLevel.GUEST

def get_permission_name(level: int) -> str:
    """Get permission level name"""
    names = {
        PermissionLevel.GUEST: "Guest",
        PermissionLevel.MEMBER: "Member",
        PermissionLevel.MODERATOR: "Moderator",
        PermissionLevel.ADMIN: "Admin",
        PermissionLevel.OWNER: "Owner"
    }
    return names.get(level, "Unknown")
