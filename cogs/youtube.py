import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.checks import is_admin
from utils.embeds import EmbedFactory
from utils.database import Database
import feedparser
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('discord_bot.youtube')

class YouTube(commands.Cog):
    """YouTube notifications using free RSS feeds (no API key needed)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.check_uploads.start()
        self.last_video_ids = {}
        logger.info("YouTube cog initialized (using free RSS feeds)")
    
    @app_commands.command(name="addyoutube", description="Add a YouTube channel to track (no API key needed!)")
    @is_admin()
    async def addyoutube(
        self, 
        interaction: discord.Interaction, 
        channel_id: str, 
        notification_channel: discord.TextChannel
    ):
        """
        Add a YouTube channel to track new uploads
        
        Args:
            channel_id: YouTube channel ID (e.g., UCxxxxxx or @username)
            notification_channel: Discord channel for notifications
        """
        await interaction.response.defer()
        
        # Validate channel exists by checking RSS feed
        try:
            # Support both channel IDs and usernames
            if channel_id.startswith('@'):
                # For usernames, we'll store as-is and handle in RSS URL
                feed_url = f"https://www.youtube.com/feeds/videos.xml?user={channel_id[1:]}"
            else:
                feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            
            # Test the feed
            feed = await self.bot.loop.run_in_executor(None, feedparser.parse, feed_url)
            
            if not feed.entries:
                return await interaction.followup.send(
                    embed=EmbedFactory.error(
                        "Invalid Channel", 
                        "Could not find this YouTube channel. Make sure the channel ID or @username is correct."
                    )
                )
            
            # Get channel info from feed
            channel_title = feed.feed.get('title', 'Unknown Channel')
            
            config = await self.db.get_guild_config(interaction.guild.id)
            youtube_channels = config.youtube_channels or []
            
            # Check if already tracking
            if any(ch['channel_id'] == channel_id for ch in youtube_channels):
                return await interaction.followup.send(
                    embed=EmbedFactory.error("Already Tracking", "This channel is already being tracked.")
                )
            
            youtube_channels.append({
                'channel_id': channel_id,
                'notification_channel': notification_channel.id
            })
            
            await self.db.update_guild_config(interaction.guild.id, youtube_channels=youtube_channels)
            
            embed = EmbedFactory.success(
                "YouTube Channel Added", 
                f"Now tracking **{channel_title}**\nNotifications will be sent to {notification_channel.mention}"
            )
            embed.add_field(name="Channel ID", value=channel_id, inline=False)
            embed.set_footer(text="✨ Using free RSS feeds - no API key needed!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error adding YouTube channel: {e}")
            await interaction.followup.send(
                embed=EmbedFactory.error(
                    "Error", 
                    "Could not add this channel. Please check the channel ID and try again."
                )
            )
    
    @app_commands.command(name="removeyoutube", description="Remove a YouTube channel from tracking")
    @is_admin()
    async def removeyoutube(self, interaction: discord.Interaction, channel_id: str):
        """Remove a YouTube channel from tracking"""
        config = await self.db.get_guild_config(interaction.guild.id)
        youtube_channels = config.youtube_channels or []
        
        # Find and remove the channel
        original_count = len(youtube_channels)
        youtube_channels = [ch for ch in youtube_channels if ch['channel_id'] != channel_id]
        
        if len(youtube_channels) == original_count:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Not Found", "This channel is not being tracked.")
            )
        
        await self.db.update_guild_config(interaction.guild.id, youtube_channels=youtube_channels)
        await interaction.response.send_message(
            embed=EmbedFactory.success("YouTube Channel Removed", "Channel removed from tracking")
        )
    
    @app_commands.command(name="listyoutube", description="List all tracked YouTube channels")
    @is_admin()
    async def listyoutube(self, interaction: discord.Interaction):
        """List all tracked YouTube channels"""
        config = await self.db.get_guild_config(interaction.guild.id)
        youtube_channels = config.youtube_channels or []
        
        if not youtube_channels:
            return await interaction.response.send_message(
                embed=EmbedFactory.info("No Channels", "No YouTube channels are being tracked.")
            )
        
        embed = EmbedFactory.info("Tracked YouTube Channels", f"Tracking {len(youtube_channels)} channel(s)")
        
        for ch in youtube_channels:
            channel = interaction.guild.get_channel(ch['notification_channel'])
            channel_mention = channel.mention if channel else "Unknown Channel"
            embed.add_field(
                name=ch['channel_id'], 
                value=f"Notifications: {channel_mention}", 
                inline=False
            )
        
        embed.set_footer(text="✨ Using free RSS feeds - no API key needed!")
        await interaction.response.send_message(embed=embed)
    
    @tasks.loop(minutes=15)
    async def check_uploads(self):
        """Check for new YouTube uploads using RSS feeds (free!)"""
        try:
            for guild in self.bot.guilds:
                config = await self.db.get_guild_config(guild.id)
                if not config.youtube_channels:
                    continue
                
                for yt_channel in config.youtube_channels:
                    try:
                        await self.check_channel_uploads(guild, yt_channel)
                    except Exception as e:
                        logger.error(f"Error checking YouTube channel {yt_channel.get('channel_id')}: {e}")
        except Exception as e:
            logger.error(f"Error in check_uploads loop: {e}")
    
    async def check_channel_uploads(self, guild, yt_channel):
        """Check a single YouTube channel for new uploads using RSS"""
        channel_id = yt_channel['channel_id']
        notification_channel_id = yt_channel['notification_channel']
        
        # Build RSS feed URL
        if channel_id.startswith('@'):
            feed_url = f"https://www.youtube.com/feeds/videos.xml?user={channel_id[1:]}"
        else:
            feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        
        # Parse RSS feed (run in executor to avoid blocking)
        feed = await self.bot.loop.run_in_executor(None, feedparser.parse, feed_url)
        
        if not feed.entries:
            logger.warning(f"No entries found for YouTube channel {channel_id}")
            return
        
        # Get the latest video
        latest_video = feed.entries[0]
        video_id = latest_video.yt_videoid if hasattr(latest_video, 'yt_videoid') else latest_video.id.split(':')[-1]
        
        # Check if this is a new video
        cache_key = f"{guild.id}_{channel_id}"
        
        # Skip if we've already notified about this video
        if cache_key in self.last_video_ids and self.last_video_ids[cache_key] == video_id:
            return
        
        # Check if video is recent (within last 24 hours) to avoid spam on first run
        published = latest_video.published_parsed
        video_date = datetime(*published[:6])
        if datetime.now() - video_date > timedelta(hours=24) and cache_key not in self.last_video_ids:
            # First time checking this channel, just cache the video ID without notifying
            self.last_video_ids[cache_key] = video_id
            logger.info(f"Initialized tracking for {channel_id}, skipping old video")
            return
        
        # Update cache
        self.last_video_ids[cache_key] = video_id
        
        # Send notification
        notification_channel = guild.get_channel(notification_channel_id)
        if not notification_channel:
            logger.warning(f"Notification channel {notification_channel_id} not found")
            return
        
        try:
            # Extract video info from RSS feed
            title = latest_video.title
            author = latest_video.author
            description = latest_video.summary if hasattr(latest_video, 'summary') else ""
            thumbnail = latest_video.media_thumbnail[0]['url'] if hasattr(latest_video, 'media_thumbnail') else None
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Create embed
            embed = discord.Embed(
                title="🎥 New YouTube Upload!",
                description=f"**{title}**\n\n{description[:200]}..." if description else f"**{title}**",
                color=discord.Color.red(),
                url=video_url
            )
            
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)
            
            embed.add_field(name="Channel", value=author, inline=True)
            embed.add_field(name="Watch", value=f"[Click here]({video_url})", inline=True)
            embed.set_footer(text="✨ Free RSS notifications")
            embed.timestamp = video_date
            
            await notification_channel.send(
                content=f"@everyone New video from **{author}**!",
                embed=embed
            )
            
            logger.info(f"Sent notification for new video: {title}")
            
        except Exception as e:
            logger.error(f"Error sending YouTube notification: {e}")
    
    @check_uploads.before_loop
    async def before_check_uploads(self):
        """Wait for bot to be ready before starting the loop"""
        await self.bot.wait_until_ready()
        logger.info("YouTube upload checker started")
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.check_uploads.cancel()
        logger.info("YouTube cog unloaded")

async def setup(bot):
    await bot.add_cog(YouTube(bot))
