"""
Watch Party Notifications - Handles movie upload announcements and schedule voting
"""

import discord
from discord.ext import commands
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# Database for schedule votes
VOTES_DIR = Path("./data/watch_party")
VOTES_DIR.mkdir(parents=True, exist_ok=True)
VOTES_FILE = VOTES_DIR / "schedule_votes.json"


class WatchPartyNotifications:
    """Handle movie upload notifications and schedule voting"""
    
    @staticmethod
    def _ensure_votes_file():
        """Ensure votes file exists"""
        if not VOTES_FILE.exists():
            with open(VOTES_FILE, 'w') as f:
                json.dump({}, f)
    
    @staticmethod
    async def announce_movie_upload(bot, guild_id: int, movie_title: str, uploader_name: str, 
                                    upload_channel_id: int, movie_id: str):
        """Announce movie upload to Discord and ask for schedule"""
        try:
            guild = bot.get_guild(guild_id)
            if not guild:
                logger.error(f"Guild {guild_id} not found")
                return
            
            channel = guild.get_channel(upload_channel_id)
            if not channel:
                logger.error(f"Channel {upload_channel_id} not found")
                return
            
            # Create upload announcement embed
            embed = discord.Embed(
                title="🎬 New Movie Uploaded!",
                description=f"**{movie_title}** has been uploaded by {uploader_name}",
                color=discord.Color.from_rgb(0, 255, 200),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="📋 What's Next?",
                value="React with a time below to vote for when to watch this movie!",
                inline=False
            )
            embed.set_footer(text="WAN Bot Watch Party")
            
            # Send announcement
            msg = await channel.send(embed=embed)
            
            # Add time reaction options
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
                await msg.add_reaction(emoji)
            
            # Store vote data
            WatchPartyNotifications._ensure_votes_file()
            with open(VOTES_FILE, 'r') as f:
                votes = json.load(f)
            
            votes[str(msg.id)] = {
                "movie_id": movie_id,
                "movie_title": movie_title,
                "guild_id": guild_id,
                "channel_id": upload_channel_id,
                "uploader": uploader_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "votes": {emoji: [] for emoji in time_options.keys()},
                "time_options": time_options
            }
            
            with open(VOTES_FILE, 'w') as f:
                json.dump(votes, f, indent=2)
            
            logger.info(f"✅ Movie upload announced: {movie_title}")
            
        except Exception as e:
            logger.error(f"❌ Failed to announce movie upload: {e}")
    
    @staticmethod
    async def handle_schedule_vote(bot, payload: discord.RawReactionActionEvent):
        """Handle schedule voting reactions"""
        try:
            WatchPartyNotifications._ensure_votes_file()
            
            with open(VOTES_FILE, 'r') as f:
                votes = json.load(f)
            
            msg_id = str(payload.message_id)
            if msg_id not in votes:
                return
            
            vote_data = votes[msg_id]
            emoji = str(payload.emoji)
            
            if emoji not in vote_data["votes"]:
                return
            
            user_id = str(payload.user_id)
            
            # Add vote
            if user_id not in vote_data["votes"][emoji]:
                vote_data["votes"][emoji].append(user_id)
            
            # Save updated votes
            with open(VOTES_FILE, 'w') as f:
                json.dump(votes, f, indent=2)
            
            logger.info(f"✅ Vote recorded for {vote_data['movie_title']}: {emoji}")
            
        except Exception as e:
            logger.error(f"❌ Failed to handle schedule vote: {e}")
    
    @staticmethod
    def get_winning_time(msg_id: str) -> Optional[str]:
        """Get the winning time from votes"""
        try:
            WatchPartyNotifications._ensure_votes_file()
            
            with open(VOTES_FILE, 'r') as f:
                votes = json.load(f)
            
            if str(msg_id) not in votes:
                return None
            
            vote_data = votes[str(msg_id)]
            
            # Find emoji with most votes
            max_votes = 0
            winning_emoji = None
            
            for emoji, voters in vote_data["votes"].items():
                if len(voters) > max_votes:
                    max_votes = len(voters)
                    winning_emoji = emoji
            
            if winning_emoji:
                return vote_data["time_options"].get(winning_emoji)
            
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get winning time: {e}")
            return None
    
    @staticmethod
    async def send_schedule_confirmation(bot, guild_id: int, movie_title: str, 
                                        scheduled_time: str, owner_id: int):
        """Send schedule confirmation to owner"""
        try:
            user = bot.get_user(owner_id)
            if not user:
                logger.error(f"User {owner_id} not found")
                return
            
            embed = discord.Embed(
                title="✅ Movie Scheduled!",
                description=f"**{movie_title}** has been scheduled",
                color=discord.Color.from_rgb(81, 207, 102),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="⏰ Scheduled Time",
                value=scheduled_time,
                inline=False
            )
            embed.add_field(
                name="📊 Community Vote",
                value="This time was chosen by community voting!",
                inline=False
            )
            embed.set_footer(text="WAN Bot Watch Party")
            
            await user.send(embed=embed)
            logger.info(f"✅ Schedule confirmation sent to owner {owner_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send schedule confirmation: {e}")
    
    @staticmethod
    async def send_permission_request(bot, guild_id: int, owner_id: int, 
                                     movie_title: str, uploader_name: str):
        """Send permission request to owner via DM"""
        try:
            user = bot.get_user(owner_id)
            if not user:
                logger.error(f"User {owner_id} not found")
                return
            
            embed = discord.Embed(
                title="🎬 Watch Permission Request",
                description=f"{uploader_name} wants to upload **{movie_title}**",
                color=discord.Color.from_rgb(0, 255, 200),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="📋 Action Required",
                value="React with ✅ to approve or ❌ to deny",
                inline=False
            )
            embed.set_footer(text="WAN Bot Watch Party")
            
            msg = await user.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            
            logger.info(f"✅ Permission request sent to owner {owner_id}")
            return msg.id
            
        except Exception as e:
            logger.error(f"❌ Failed to send permission request: {e}")
            return None
