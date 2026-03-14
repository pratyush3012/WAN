import discord
from discord import app_commands
from discord.ext import commands
import os

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        owner_id = int(os.getenv('OWNER_ID', 0))
        return interaction.user.id == owner_id
    return app_commands.check(predicate)

def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)

def is_mod():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        
        # Check if user is admin
        if interaction.user.guild_permissions.administrator:
            return True
        
        # Check if user has moderator permissions
        perms = interaction.user.guild_permissions
        return any([
            perms.kick_members,
            perms.ban_members,
            perms.manage_messages,
            perms.manage_roles
        ])
    return app_commands.check(predicate)

def has_dj_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        
        # Admins bypass DJ check
        if interaction.user.guild_permissions.administrator:
            return True
        
        # Check for DJ role from config
        from utils.database import Database
        db = Database()
        config = await db.get_guild_config(interaction.guild.id)
        
        if config.dj_role:
            dj_role = interaction.guild.get_role(config.dj_role)
            if dj_role and dj_role in interaction.user.roles:
                return True
        
        # If no DJ role set, allow users in voice channel
        if interaction.user.voice:
            return True
        
        return False
    return app_commands.check(predicate)
