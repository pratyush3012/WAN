"""
Complete Watch Party System - Integrates uploads, notifications, scheduling, and permissions
"""

import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, timezone
from user_auth_db import UserAuthDB
from watch_party_notifications import WatchPartyNotifications
from watch_party_enhanced import EnhancedWatchPartyDB

logger = logging.getLogger(__name__)


class WatchPartyComplete(commands.Cog):
    """Complete watch party system with auto-registration and notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self._schedule_due_logged: set = set()
        self.check_scheduled_movies.start()
    
    def cog_unload(self):
        self.check_scheduled_movies.cancel()
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Auto-register users when they get mod/admin roles"""
        try:
            # Check if roles changed
            before_roles = set(before.roles)
            after_roles = set(after.roles)
            
            new_roles = after_roles - before_roles
            
            for role in new_roles:
                # Check if it's a mod/admin role
                role_name = role.name.lower()
                
                if any(keyword in role_name for keyword in ['mod', 'admin', 'staff', 'owner']):
                    # Determine role level
                    if 'owner' in role_name:
                        user_role = "owner"
                    elif 'admin' in role_name:
                        user_role = "admin"
                    elif 'mod' in role_name:
                        user_role = "moderator"
                    else:
                        user_role = "member"
                    
                    # Register user
                    user_data = UserAuthDB.register_user(
                        user_id=str(after.id),
                        username=after.name,
                        guild_id=str(after.guild.id),
                        role=user_role
                    )
                    
                    if user_data:
                        # Send DM with account info
                        embed = discord.Embed(
                            title="🎉 Welcome to WAN Bot Dashboard!",
                            description=f"You've been promoted to **{user_role.upper()}**",
                            color=discord.Color.from_rgb(0, 255, 200),
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.add_field(
                            name="👤 Your Account",
                            value=f"**Username:** {after.name}\n**Primary ID:** {after.name}",
                            inline=False
                        )
                        embed.add_field(
                            name="🔐 Set Your Password",
                            value="Use `/set-password` command to set your dashboard password",
                            inline=False
                        )
                        embed.add_field(
                            name="📊 Dashboard Access",
                            value="You now have access to the WAN Bot dashboard with full controls!",
                            inline=False
                        )
                        embed.set_footer(text="WAN Bot • Keep your password safe!")
                        
                        try:
                            await after.send(embed=embed)
                            logger.info(f"✅ Sent account info to {after.name}")
                        except:
                            logger.warning(f"⚠️ Could not DM {after.name}")
        
        except Exception as e:
            logger.error(f"❌ Error in on_member_update: {e}")
    
    @commands.hybrid_command(name="set-password", description="Set your dashboard password")
    async def set_password(self, ctx, password: str):
        """Set password for dashboard access"""
        try:
            user_id = str(ctx.author.id)
            
            # Check if user is registered
            user = UserAuthDB.get_user(user_id)
            if not user:
                await ctx.send("❌ You are not registered. Contact an admin.", ephemeral=True)
                return
            
            # Validate password strength
            if len(password) < 8:
                await ctx.send("❌ Password must be at least 8 characters", ephemeral=True)
                return
            
            # Set password
            if UserAuthDB.set_password(user_id, password):
                embed = discord.Embed(
                    title="✅ Password Set!",
                    description="Your dashboard password has been updated",
                    color=discord.Color.from_rgb(81, 207, 102),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(
                    name="🔐 Login Info",
                    value=f"**Username:** {ctx.author.name}\n**Password:** ••••••••",
                    inline=False
                )
                embed.add_field(
                    name="📊 Dashboard",
                    value="You can now log in to the WAN Bot dashboard!",
                    inline=False
                )
                await ctx.send(embed=embed, ephemeral=True)
                logger.info(f"✅ Password set for {ctx.author.name}")
            else:
                await ctx.send("❌ Failed to set password", ephemeral=True)
        
        except Exception as e:
            logger.error(f"❌ Error setting password: {e}")
            await ctx.send("❌ An error occurred", ephemeral=True)
    
    @commands.hybrid_command(name="movie-upload", description="Upload a new movie")
    async def movie_upload(self, ctx):
        """Start movie upload process"""
        try:
            # Check permissions
            if not UserAuthDB.has_permission(str(ctx.author.id), "upload"):
                await ctx.send("❌ You don't have permission to upload movies", ephemeral=True)
                return
            
            # Send upload form
            embed = discord.Embed(
                title="🎬 Movie Upload",
                description="Upload a new movie to the watch party",
                color=discord.Color.from_rgb(0, 255, 200),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="📋 Steps",
                value="1. Go to the dashboard\n2. Click 'Upload Movie'\n3. Select your file\n4. Wait for processing",
                inline=False
            )
            embed.add_field(
                name="📊 Supported Formats",
                value="MP4, MKV, AVI, MOV",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Announce to channel
            guild_id = ctx.guild.id
            channel = ctx.channel
            
            await WatchPartyNotifications.announce_movie_upload(
                self.bot,
                guild_id=guild_id,
                movie_title="[New Movie Uploading...]",
                uploader_name=ctx.author.name,
                upload_channel_id=channel.id,
                movie_id="pending"
            )
            
            logger.info(f"✅ Movie upload initiated by {ctx.author.name}")
        
        except Exception as e:
            logger.error(f"❌ Error in movie_upload: {e}")
            await ctx.send("❌ An error occurred", ephemeral=True)
    
    @commands.hybrid_command(name="watch-party", description="Create a watch party")
    async def watch_party(self, ctx):
        """Create a new watch party"""
        try:
            embed = discord.Embed(
                title="🎬 Create Watch Party",
                description="Start watching a movie with your community",
                color=discord.Color.from_rgb(0, 255, 200),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="📋 Available Movies",
                value="Use `/list-movies` to see available movies",
                inline=False
            )
            embed.add_field(
                name="🎮 Features",
                value="• Live chat\n• Play/Pause requests\n• Schedule voting\n• Viewer list",
                inline=False
            )
            
            await ctx.send(embed=embed)
            logger.info(f"✅ Watch party info sent to {ctx.author.name}")
        
        except Exception as e:
            logger.error(f"❌ Error in watch_party: {e}")
            await ctx.send("❌ An error occurred", ephemeral=True)
    
    @commands.hybrid_command(name="list-movies", description="List available movies")
    async def list_movies(self, ctx):
        """List all available movies"""
        try:
            from watch_party_movies_db import MovieDatabase
            
            movies = MovieDatabase.get_guild_movies(str(ctx.guild.id))
            
            if not movies:
                await ctx.send("❌ No movies available", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🎬 Available Movies",
                description=f"Total: {len(movies)} movies",
                color=discord.Color.from_rgb(0, 255, 200),
                timestamp=datetime.now(timezone.utc)
            )
            
            for movie in movies[:10]:  # Show first 10
                embed.add_field(
                    name=movie.get("title", "Unknown"),
                    value=f"Uploaded by: {movie.get('uploader_name', 'Unknown')}\nViews: {movie.get('views', 0)}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            logger.info(f"✅ Movie list sent to {ctx.author.name}")
        
        except Exception as e:
            logger.error(f"❌ Error listing movies: {e}")
            await ctx.send("❌ An error occurred", ephemeral=True)
    
    @tasks.loop(minutes=1)
    async def check_scheduled_movies(self):
        """Notify once when a scheduled watch party start time is reached (rooms stay in DB)."""
        try:
            for guild in self.bot.guilds:
                for room in EnhancedWatchPartyDB.get_scheduled_movies(str(guild.id)):
                    rid = room.get("id")
                    start_s = room.get("scheduled_start")
                    if not rid or not start_s:
                        continue
                    try:
                        start_dt = datetime.fromisoformat(start_s.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) < start_dt:
                        continue
                    key = f"{guild.id}:{rid}"
                    if key in self._schedule_due_logged:
                        continue
                    self._schedule_due_logged.add(key)
                    title = room.get("title", "Unknown")
                    logger.info(
                        f"⏰ Scheduled watch party due: guild={guild.id} room={rid} title={title!r}"
                    )
        except Exception as e:
            logger.error(f"❌ Error checking scheduled movies: {e}")
    
    @check_scheduled_movies.before_loop
    async def before_check_scheduled_movies(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(WatchPartyComplete(bot))
