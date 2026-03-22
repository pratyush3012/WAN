import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.checks import is_mod, is_admin
from utils.embeds import EmbedFactory
from utils.database import Database, ModAction
from datetime import timedelta
from collections import defaultdict, deque
import asyncio
import time
import logging
import os

logger = logging.getLogger('discord_bot.moderation')

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        # Use deque with maxlen for automatic cleanup
        self.spam_tracker = defaultdict(lambda: deque(maxlen=10))
        self.spam_violations = defaultdict(int)
        # Start cleanup task
        self.cleanup_task.start()
    
    @tasks.loop(minutes=5)
    async def cleanup_task(self):
        """Cleanup old entries from spam tracker to prevent memory leaks"""
        now = time.time()
        to_remove = []
        
        for user_id, timestamps in list(self.spam_tracker.items()):
            # Remove if no activity in last 5 minutes
            if timestamps and now - timestamps[-1] > 300:
                to_remove.append(user_id)
        
        for user_id in to_remove:
            del self.spam_tracker[user_id]
            if user_id in self.spam_violations:
                del self.spam_violations[user_id]
        
        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} inactive spam tracker entries")
    
    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()
    
    def cog_unload(self):
        """Cancel cleanup task on cog unload"""
        self.cleanup_task.cancel()
        
    @app_commands.command(name="kick", description="Kick a member from the server")
    @is_mod()
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        # Check if bot has permission
        if not interaction.guild.me.guild_permissions.kick_members:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Missing Permission", "I don't have permission to kick members"),
                ephemeral=True
            )
        
        # Check if target is bot owner
        owner_id = int(os.getenv('OWNER_ID', 0))
        if member.id == owner_id:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Denied", "Cannot kick the bot owner"),
                ephemeral=True
            )
        
        # Check role hierarchy (user)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Denied", "You cannot kick someone with equal or higher role"),
                ephemeral=True
            )
        
        # Check role hierarchy (bot)
        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Denied", "I cannot kick someone with equal or higher role than me"),
                ephemeral=True
            )
        
        try:
            await member.kick(reason=reason)
            await interaction.response.send_message(
                embed=EmbedFactory.success("Member Kicked", f"{member.mention} has been kicked.\n**Reason:** {reason}")
            )
            await self._log_action(interaction.guild.id, member.id, interaction.user.id, "kick", reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=EmbedFactory.error("Error", "Failed to kick member - insufficient permissions"),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error kicking member {member.id}: {e}")
            await interaction.response.send_message(
                embed=EmbedFactory.error("Error", "An error occurred while kicking the member"),
                ephemeral=True
            )
    
    @app_commands.command(name="ban", description="Ban a member from the server")
    @is_mod()
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_days: int = 0):
        # Validate delete_days (Discord limit is 7)
        if delete_days < 0 or delete_days > 7:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid Parameter", "delete_days must be between 0 and 7"),
                ephemeral=True
            )
        
        # Check if bot has permission
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Missing Permission", "I don't have permission to ban members"),
                ephemeral=True
            )
        
        # Check if target is bot owner
        owner_id = int(os.getenv('OWNER_ID', 0))
        if member.id == owner_id:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Denied", "Cannot ban the bot owner"),
                ephemeral=True
            )
        
        # Check role hierarchy (user)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Denied", "You cannot ban someone with equal or higher role"),
                ephemeral=True
            )
        
        # Check role hierarchy (bot)
        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Denied", "I cannot ban someone with equal or higher role than me"),
                ephemeral=True
            )
        
        try:
            await member.ban(reason=reason, delete_message_days=delete_days)
            await interaction.response.send_message(
                embed=EmbedFactory.success("Member Banned", f"{member.mention} has been banned.\n**Reason:** {reason}")
            )
            await self._log_action(interaction.guild.id, member.id, interaction.user.id, "ban", reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=EmbedFactory.error("Error", "Failed to ban member - insufficient permissions"),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error banning member {member.id}: {e}")
            await interaction.response.send_message(
                embed=EmbedFactory.error("Error", "An error occurred while banning the member"),
                ephemeral=True
            )
    
    @app_commands.command(name="unban", description="Unban a user from the server")
    @is_mod()
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=reason)
            await interaction.response.send_message(
                embed=EmbedFactory.success("User Unbanned", f"{user.mention} has been unbanned.")
            )
        except:
            await interaction.response.send_message(
                embed=EmbedFactory.error("Error", "User not found or not banned"),
                ephemeral=True
            )
    
    @app_commands.command(name="timeout", description="Timeout a member")
    @is_mod()
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: int, unit: str, reason: str = "No reason provided"):
        units = {"m": 60, "h": 3600, "d": 86400}
        if unit not in units:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid Unit", "Use m (minutes), h (hours), or d (days)"),
                ephemeral=True
            )
        
        # Check if bot has permission
        if not interaction.guild.me.guild_permissions.moderate_members:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Missing Permission", "I don't have permission to timeout members"),
                ephemeral=True
            )
        
        # Check if target is bot owner
        owner_id = int(os.getenv('OWNER_ID', 0))
        if member.id == owner_id:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Denied", "Cannot timeout the bot owner"),
                ephemeral=True
            )
        
        # Check role hierarchy (user)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Denied", "You cannot timeout someone with equal or higher role"),
                ephemeral=True
            )
        
        # Check role hierarchy (bot)
        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Denied", "I cannot timeout someone with equal or higher role than me"),
                ephemeral=True
            )
        
        seconds = duration * units[unit]
        
        # Discord timeout limit is 28 days
        if seconds > 2419200:  # 28 days in seconds
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Duration Too Long", "Maximum timeout duration is 28 days"),
                ephemeral=True
            )
        
        try:
            await member.timeout(timedelta(seconds=seconds), reason=reason)
            await interaction.response.send_message(
                embed=EmbedFactory.success("Member Timed Out", f"{member.mention} has been timed out for {duration}{unit}.\n**Reason:** {reason}")
            )
            await self._log_action(interaction.guild.id, member.id, interaction.user.id, "timeout", reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=EmbedFactory.error("Error", "Failed to timeout member - insufficient permissions"),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error timing out member {member.id}: {e}")
            await interaction.response.send_message(
                embed=EmbedFactory.error("Error", "An error occurred while timing out the member"),
                ephemeral=True
            )
    
    @app_commands.command(name="purge", description="Delete multiple messages")
    @is_mod()
    async def purge(self, interaction: discord.Interaction, amount: int):
        if amount > 100:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Limit Exceeded", "Cannot delete more than 100 messages at once"),
                ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(
            embed=EmbedFactory.success("Messages Purged", f"Deleted {len(deleted)} messages"),
            ephemeral=True
        )

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        if not channel.permissions_for(ctx.guild.me).manage_permissions:
            return await ctx.send(f"❌ I don't have permission to manage permissions in {channel.mention}")
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=False)
            await ctx.send(f"🔒 {channel.mention} has been locked.")
        except discord.Forbidden:
            await ctx.send(f"❌ Failed to lock {channel.mention}")

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        if not channel.permissions_for(ctx.guild.me).manage_permissions:
            return await ctx.send(f"❌ I don't have permission to manage permissions in {channel.mention}")
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=None)
            await ctx.send(f"🔓 {channel.mention} has been unlocked.")
        except discord.Forbidden:
            await ctx.send(f"❌ Failed to unlock {channel.mention}")

    @commands.command(name="lockdown")
    @commands.has_permissions(administrator=True)
    async def lockdown(self, ctx):
        locked = 0
        for channel in ctx.guild.text_channels:
            try:
                await channel.set_permissions(ctx.guild.default_role, send_messages=False)
                locked += 1
            except Exception:
                pass
        await ctx.send(f"🔒 Server lockdown active — locked {locked} channels.")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        config = await self.db.get_guild_config(message.guild.id)
        if not config.anti_spam:
            return
        
        user_id = message.author.id
        now = message.created_at.timestamp()
        
        # Add timestamp to deque (automatically removes oldest if > 10)
        self.spam_tracker[user_id].append(now)
        
        # Check for spam (5 messages in 5 seconds)
        recent = [t for t in self.spam_tracker[user_id] if now - t < 5]
        
        if len(recent) >= 5:
            # Check if bot has permission to timeout
            if not message.guild.me.guild_permissions.moderate_members:
                logger.warning(f"Cannot timeout in guild {message.guild.id} - missing moderate_members permission")
                return
            
            # Check if target is moderator (don't timeout mods)
            if message.author.guild_permissions.manage_messages:
                return
            
            # Check if target role is higher than bot
            if message.author.top_role >= message.guild.me.top_role:
                return
            
            # Check if target is bot owner
            owner_id = int(os.getenv('OWNER_ID', 0))
            if message.author.id == owner_id:
                return
            
            try:
                self.spam_violations[user_id] += 1
                
                # Escalating timeout duration (5, 10, 15... up to 60 minutes)
                duration = min(5 * self.spam_violations[user_id], 60)
                
                await message.author.timeout(timedelta(minutes=duration), reason="Auto-mute: Spam detected")
                
                await message.channel.send(
                    embed=EmbedFactory.warning("Anti-Spam", f"{message.author.mention} has been muted for {duration} minutes due to spam."),
                    delete_after=10
                )
                
                # Clear tracker for this user
                self.spam_tracker[user_id].clear()
                
                logger.info(f"Auto-muted {message.author} ({message.author.id}) for {duration} minutes in guild {message.guild.id}")
            except discord.Forbidden:
                logger.warning(f"Cannot timeout {message.author} - insufficient permissions")
            except Exception as e:
                logger.error(f"Error in anti-spam for user {message.author.id}: {e}")
    
    async def _log_action(self, guild_id, user_id, mod_id, action_type, reason):
        async with self.db.async_session() as session:
            action = ModAction(
                guild_id=guild_id,
                user_id=user_id,
                moderator_id=mod_id,
                action_type=action_type,
                reason=reason
            )
            session.add(action)
            await session.commit()

async def setup(bot):
    await bot.add_cog(Moderation(bot))
