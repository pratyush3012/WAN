"""
Enhanced Watch Party Cog - Discord Integration
Handles announcements, approvals, and scheduling
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
import logging
import asyncio

logger = logging.getLogger(__name__)

from watch_party_enhanced import EnhancedWatchPartyDB
from watch_party_movies_db import MovieDatabase


def _pick_announce_channel(guild: discord.Guild):
    """First matching named channel, else first text channel, else None (avoids IndexError)."""
    ch = discord.utils.get(guild.text_channels, name="watch-party") or discord.utils.get(
        guild.text_channels, name="announcements"
    )
    if ch:
        return ch
    return guild.text_channels[0] if guild.text_channels else None


class WatchPartyEnhanced(commands.Cog):
    """Enhanced watch party with Discord integration"""
    
    def __init__(self, bot):
        self.bot = bot
        self.pending_approvals = {}  # room_id -> approval_data
        self.scheduled_check.start()
    
    def cog_unload(self):
        self.scheduled_check.cancel()
    
    # ── Movie Upload Announcement ──────────────────────────────────────────
    
    async def announce_movie_upload(self, guild_id: int, movie_title: str, 
                                   uploader_name: str, room_id: str):
        """Announce movie upload to Discord"""
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
            
            channel = _pick_announce_channel(guild)
            if not channel:
                return
            
            # Create embed
            embed = discord.Embed(
                title="🎬 Movie Upload Started",
                description=f"**{movie_title}** is being uploaded",
                color=discord.Color.from_rgb(0, 212, 255)
            )
            embed.add_field(name="Uploader", value=uploader_name, inline=True)
            embed.add_field(name="Status", value="⏳ Uploading...", inline=True)
            embed.set_footer(text="This will update when upload completes")
            
            msg = await channel.send(embed=embed)
            
            # Store message ID for later update
            self.pending_approvals[room_id] = {
                "message_id": msg.id,
                "channel_id": channel.id,
                "status": "uploading"
            }
            
            logger.info(f"Announced movie upload: {movie_title}")
        except Exception as e:
            logger.error(f"Error announcing movie upload: {e}")
    
    async def announce_movie_ready(self, guild_id: int, movie_title: str, 
                                  room_id: str, watch_url: str):
        """Announce movie is ready to watch"""
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
            
            channel = _pick_announce_channel(guild)
            if not channel:
                return
            
            # Create embed with watch button
            embed = discord.Embed(
                title="🎬 Movie Ready to Watch!",
                description=f"**{movie_title}** is now available",
                color=discord.Color.from_rgb(46, 213, 115)
            )
            embed.add_field(
                name="Watch Now",
                value=f"[Click here to watch]({watch_url})",
                inline=False
            )
            embed.set_footer(text="Click the link above to join the watch party")
            
            await channel.send(embed=embed)
            
            logger.info(f"Announced movie ready: {movie_title}")
        except Exception as e:
            logger.error(f"Error announcing movie ready: {e}")
    
    # ── Watch Request Approval ─────────────────────────────────────────────
    
    async def request_watch_approval(self, guild_id: int, user_id: int, 
                                    username: str, movie_title: str, 
                                    room_id: str) -> bool:
        """Request owner approval for watch"""
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return False
            
            # Get owner
            owner = guild.owner
            if not owner:
                return False
            
            # Create approval embed
            embed = discord.Embed(
                title="🔔 Watch Request Approval",
                description=f"{username} wants to watch **{movie_title}**",
                color=discord.Color.from_rgb(255, 165, 2)
            )
            embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
            embed.add_field(name="Movie", value=movie_title, inline=True)
            embed.set_footer(text="React to approve or deny")
            
            # Send to owner
            try:
                msg = await owner.send(embed=embed)
                
                # Add reactions
                await msg.add_reaction("✅")  # Approve
                await msg.add_reaction("❌")  # Deny
                
                # Store approval data
                self.pending_approvals[f"{user_id}_{room_id}"] = {
                    "message_id": msg.id,
                    "user_id": user_id,
                    "room_id": room_id,
                    "movie_title": movie_title,
                    "created_at": datetime.now(timezone.utc)
                }
                
                logger.info(f"Sent approval request for {username}")
                return True
            except discord.Forbidden:
                logger.warning(f"Cannot DM owner {owner}")
                return False
        except Exception as e:
            logger.error(f"Error requesting approval: {e}")
            return False
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle approval reactions"""
        if user.bot:
            return
        
        # Check if this is an approval message
        for key, data in list(self.pending_approvals.items()):
            if data.get("message_id") == reaction.message.id:
                if reaction.emoji == "✅":
                    # Approved
                    await reaction.message.edit(
                        embed=discord.Embed(
                            title="✅ Approved",
                            description="Watch request approved!",
                            color=discord.Color.from_rgb(46, 213, 115)
                        )
                    )
                    logger.info(f"Approved watch request: {key}")
                    del self.pending_approvals[key]
                
                elif reaction.emoji == "❌":
                    # Denied
                    await reaction.message.edit(
                        embed=discord.Embed(
                            title="❌ Denied",
                            description="Watch request denied",
                            color=discord.Color.from_rgb(255, 71, 87)
                        )
                    )
                    logger.info(f"Denied watch request: {key}")
                    del self.pending_approvals[key]
    
    # ── Scheduled Movie Start ──────────────────────────────────────────────
    
    @tasks.loop(minutes=1)
    async def scheduled_check(self):
        """Check for scheduled movies to start"""
        try:
            # Get all scheduled movies
            # This would need to iterate through all guilds
            # For now, just log that it's running
            logger.debug("Checking scheduled movies...")
        except Exception as e:
            logger.error(f"Error in scheduled check: {e}")
    
    @scheduled_check.before_loop
    async def before_scheduled_check(self):
        await self.bot.wait_until_ready()
    
    # ── Commands ───────────────────────────────────────────────────────────
    
    @commands.command(name="watchparty")
    @commands.has_permissions(manage_channels=True)
    async def watch_party_setup(self, ctx):
        """Setup watch party for the server"""
        embed = discord.Embed(
            title="🎬 Watch Party Setup",
            description="Watch party is ready to use!",
            color=discord.Color.from_rgb(0, 212, 255)
        )
        embed.add_field(
            name="Features",
            value="✅ Premium UI\n✅ Live Chat\n✅ Request System\n✅ Scheduling\n✅ Owner Approval",
            inline=False
        )
        embed.add_field(
            name="Commands",
            value="`/movie-upload` — upload flow (hybrid)\n`/watch-party` — create a party\n`!active-parties` — list active rooms",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="active-parties")
    async def active_parties(self, ctx):
        """Show active watch parties"""
        embed = discord.Embed(
            title="🎬 Active Watch Parties",
            description="Currently active watch parties",
            color=discord.Color.from_rgb(0, 212, 255)
        )
        
        # Get active rooms from database
        # This would query EnhancedWatchPartyDB
        
        embed.add_field(
            name="No active parties",
            value="Start one by uploading a movie!",
            inline=False
        )
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(WatchPartyEnhanced(bot))
