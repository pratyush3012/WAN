"""
Fixed Watch Party Upload - Guild-specific uploads with Discord announcements and polls
"""

import os
import discord
from discord.ext import commands
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import json
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

from watch_party_upload import UploadValidator, UploadManager
from watch_party_notifications import WatchPartyNotifications
from watch_party_movies_db import MovieDatabase


class UploadConfig:
    """Upload configuration per guild"""
    
    CONFIG_DIR = Path("./data/watch_party")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE = CONFIG_DIR / "upload_config.json"
    
    @staticmethod
    def _ensure_config():
        """Ensure config file exists"""
        if not UploadConfig.CONFIG_FILE.exists():
            with open(UploadConfig.CONFIG_FILE, 'w') as f:
                json.dump({}, f)
    
    @staticmethod
    def set_upload_channel(guild_id: str, channel_id: str) -> bool:
        """Set upload announcement channel for guild"""
        try:
            UploadConfig._ensure_config()
            
            with open(UploadConfig.CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            if guild_id not in config:
                config[guild_id] = {}
            
            config[guild_id]["upload_channel_id"] = channel_id
            
            with open(UploadConfig.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"✅ Set upload channel {channel_id} for guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to set upload channel: {e}")
            return False
    
    @staticmethod
    def get_upload_channel(guild_id: str) -> Optional[str]:
        """Get upload announcement channel for guild"""
        try:
            UploadConfig._ensure_config()
            
            with open(UploadConfig.CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            return config.get(guild_id, {}).get("upload_channel_id")
        except Exception as e:
            logger.error(f"❌ Failed to get upload channel: {e}")
            return None


class GuildUploadManager:
    """Manage uploads per guild with announcements"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_uploads = {}  # {guild_id: upload_info}
    
    async def start_upload(self, guild_id: str, user_id: str, username: str, 
                          title: str, file_path: str, file_size: int) -> Optional[str]:
        """Start upload for specific guild"""
        try:
            # Store upload info
            upload_id = f"{guild_id}_{user_id}_{int(datetime.now(timezone.utc).timestamp())}"
            
            self.active_uploads[upload_id] = {
                "guild_id": guild_id,
                "user_id": user_id,
                "username": username,
                "title": title,
                "file_path": file_path,
                "file_size": file_size,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "uploading"
            }
            
            logger.info(f"✅ Started upload {upload_id} in guild {guild_id}")
            return upload_id
        
        except Exception as e:
            logger.error(f"❌ Failed to start upload: {e}")
            return None
    
    async def complete_upload(self, upload_id: str, movie_id: str) -> bool:
        """Complete upload and send announcements"""
        try:
            if upload_id not in self.active_uploads:
                logger.error(f"Upload {upload_id} not found")
                return False
            
            upload_info = self.active_uploads[upload_id]
            guild_id = int(upload_info["guild_id"])
            
            # Get guild
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.error(f"Guild {guild_id} not found")
                return False
            
            # Get upload channel
            channel_id = UploadConfig.get_upload_channel(str(guild_id))
            if not channel_id:
                logger.warning(f"No upload channel configured for guild {guild_id}")
                # Use first text channel as fallback
                channel = guild.text_channels[0] if guild.text_channels else None
            else:
                channel = guild.get_channel(int(channel_id))
            
            if not channel:
                logger.error(f"No channel found for announcements in guild {guild_id}")
                return False
            
            # Send @everyone announcement
            embed = discord.Embed(
                title="🎬 New Movie Uploaded!",
                description=f"**{upload_info['title']}** has been uploaded by {upload_info['username']}",
                color=discord.Color.from_rgb(0, 255, 200),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="📋 Vote for Watch Time",
                value="React with an emoji below to vote for when to watch this movie!",
                inline=False
            )
            embed.add_field(
                name="📊 File Info",
                value=f"Size: {upload_info['file_size'] / (1024**2):.1f}MB",
                inline=False
            )
            embed.set_footer(text="WAN Bot Watch Party")
            
            # Send announcement with @everyone mention
            msg = await channel.send(f"@everyone", embed=embed)
            
            # Add time voting reactions
            time_options = {
                "🕐": "6 PM",
                "🕑": "7 PM",
                "🕒": "8 PM",
                "🕓": "9 PM",
                "🕔": "10 PM",
                "🕕": "11 PM",
                "🕖": "12 AM",
                "🕗": "1 AM",
            }
            
            for emoji in time_options.keys():
                try:
                    await msg.add_reaction(emoji)
                except Exception as e:
                    logger.warning(f"Failed to add reaction {emoji}: {e}")
            
            # Store vote data
            WatchPartyNotifications._ensure_votes_file()
            from watch_party_notifications import VOTES_FILE
            
            with open(VOTES_FILE, 'r') as f:
                votes = json.load(f)
            
            votes[str(msg.id)] = {
                "movie_id": movie_id,
                "movie_title": upload_info["title"],
                "guild_id": guild_id,
                "channel_id": channel.id,
                "uploader": upload_info["username"],
                "uploader_id": upload_info["user_id"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "votes": {emoji: [] for emoji in time_options.keys()},
                "time_options": time_options,
                "message_id": msg.id
            }
            
            with open(VOTES_FILE, 'w') as f:
                json.dump(votes, f, indent=2)
            
            # Update upload status
            upload_info["status"] = "completed"
            upload_info["completed_at"] = datetime.now(timezone.utc).isoformat()
            upload_info["announcement_message_id"] = msg.id
            
            logger.info(f"✅ Upload completed: {upload_id}")
            logger.info(f"✅ Announcement sent to guild {guild_id}")
            logger.info(f"✅ Poll created with {len(time_options)} time options")
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to complete upload: {e}")
            return False
    
    async def send_owner_approval_request(self, guild_id: int, owner_id: int, 
                                         movie_title: str, uploader_name: str) -> Optional[int]:
        """Send approval request to owner"""
        try:
            user = self.bot.get_user(owner_id)
            if not user:
                logger.error(f"Owner {owner_id} not found")
                return None
            
            embed = discord.Embed(
                title="🎬 Movie Upload Approval",
                description=f"{uploader_name} uploaded **{movie_title}**",
                color=discord.Color.from_rgb(0, 255, 200),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="⚠️ Action Required",
                value="React with ✅ to approve or ❌ to deny this upload",
                inline=False
            )
            embed.add_field(
                name="📊 Server",
                value=f"Guild ID: {guild_id}",
                inline=False
            )
            embed.set_footer(text="WAN Bot Watch Party")
            
            msg = await user.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            
            logger.info(f"✅ Approval request sent to owner {owner_id}")
            return msg.id
        
        except Exception as e:
            logger.error(f"❌ Failed to send approval request: {e}")
            return None
    
    def get_active_uploads(self, guild_id: str) -> list:
        """Get active uploads for guild"""
        return [u for u in self.active_uploads.values() if u["guild_id"] == guild_id]
    
    def get_upload_info(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Get upload info"""
        return self.active_uploads.get(upload_id)


class UploadCog(commands.Cog):
    """Upload management commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.upload_manager = GuildUploadManager(bot)
    
    @commands.hybrid_command(name="set-upload-channel", description="Set upload announcement channel")
    @commands.has_permissions(administrator=True)
    async def set_upload_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel for upload announcements"""
        try:
            guild_id = str(ctx.guild.id)
            channel_id = str(channel.id)
            
            if UploadConfig.set_upload_channel(guild_id, channel_id):
                embed = discord.Embed(
                    title="✅ Upload Channel Set",
                    description=f"Movie uploads will be announced in {channel.mention}",
                    color=discord.Color.from_rgb(81, 207, 102),
                    timestamp=datetime.now(timezone.utc)
                )
                await ctx.send(embed=embed)
                logger.info(f"✅ Upload channel set for guild {guild_id}")
            else:
                await ctx.send("❌ Failed to set upload channel", ephemeral=True)
        
        except Exception as e:
            logger.error(f"❌ Error setting upload channel: {e}")
            await ctx.send("❌ An error occurred", ephemeral=True)
    
    @commands.hybrid_command(name="upload-status", description="Check upload status")
    async def upload_status(self, ctx):
        """Check active uploads for this guild"""
        try:
            guild_id = str(ctx.guild.id)
            uploads = self.upload_manager.get_active_uploads(guild_id)
            
            if not uploads:
                await ctx.send("No active uploads", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📊 Active Uploads",
                description=f"Total: {len(uploads)}",
                color=discord.Color.from_rgb(0, 255, 200),
                timestamp=datetime.now(timezone.utc)
            )
            
            for upload in uploads:
                embed.add_field(
                    name=upload["title"],
                    value=f"By: {upload['username']}\nStatus: {upload['status']}\nSize: {upload['file_size'] / (1024**2):.1f}MB",
                    inline=False
                )
            
            await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"❌ Error checking upload status: {e}")
            await ctx.send("❌ An error occurred", ephemeral=True)


async def setup(bot):
    await bot.add_cog(UploadCog(bot))
