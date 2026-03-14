import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from collections import defaultdict
import logging
from utils.permissions import is_member

logger = logging.getLogger('discord_bot.voicestats')

class VoiceStats(commands.Cog):
    """Voice Stats - Track voice channel activity"""
    
    def __init__(self, bot):
        self.bot = bot
        self.voice_sessions = {}  # {user_id: join_time}
        self.voice_time = defaultdict(lambda: defaultdict(int))  # {guild_id: {user_id: seconds}}
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Track voice channel joins/leaves"""
        
        # User joined voice
        if not before.channel and after.channel:
            self.voice_sessions[member.id] = datetime.utcnow()
            logger.debug(f"{member} joined voice channel {after.channel.name}")
        
        # User left voice
        elif before.channel and not after.channel:
            if member.id in self.voice_sessions:
                join_time = self.voice_sessions[member.id]
                duration = (datetime.utcnow() - join_time).total_seconds()
                
                # Add to total time
                self.voice_time[member.guild.id][member.id] += int(duration)
                
                del self.voice_sessions[member.id]
                logger.debug(f"{member} left voice after {duration}s")
        
        # User switched channels
        elif before.channel and after.channel and before.channel != after.channel:
            # Update session time but keep tracking
            if member.id in self.voice_sessions:
                join_time = self.voice_sessions[member.id]
                duration = (datetime.utcnow() - join_time).total_seconds()
                self.voice_time[member.guild.id][member.id] += int(duration)
                
                # Reset join time for new channel
                self.voice_sessions[member.id] = datetime.utcnow()
    
    def format_time(self, seconds: int) -> str:
        """Format seconds into readable time"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    @app_commands.command(name="voicetime", description="Check voice channel time")
    @is_member()
    async def voicetime(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check voice time for a user"""
        
        target = user or interaction.user
        guild_id = interaction.guild.id
        
        total_seconds = self.voice_time[guild_id].get(target.id, 0)
        
        # Add current session if user is in voice
        if target.id in self.voice_sessions:
            join_time = self.voice_sessions[target.id]
            current_session = (datetime.utcnow() - join_time).total_seconds()
            total_seconds += int(current_session)
        
        embed = discord.Embed(
            title=f"🎤 Voice Time - {target.display_name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Total Time",
            value=self.format_time(total_seconds),
            inline=True
        )
        
        # Show current status
        if target.voice and target.voice.channel:
            embed.add_field(
                name="Current Channel",
                value=target.voice.channel.mention,
                inline=True
            )
            if target.id in self.voice_sessions:
                session_time = (datetime.utcnow() - self.voice_sessions[target.id]).total_seconds()
                embed.add_field(
                    name="Current Session",
                    value=self.format_time(int(session_time)),
                    inline=True
                )
        else:
            embed.add_field(
                name="Status",
                value="Not in voice",
                inline=True
            )
        
        embed.set_thumbnail(url=target.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="voiceleaderboard", description="View voice time leaderboard")
    @is_member()
    async def voiceleaderboard(self, interaction: discord.Interaction):
        """Show voice time leaderboard"""
        
        guild_id = interaction.guild.id
        
        if not self.voice_time[guild_id]:
            return await interaction.response.send_message(
                "❌ No voice activity recorded yet!",
                ephemeral=True
            )
        
        # Get top 10 users
        sorted_users = sorted(
            self.voice_time[guild_id].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        embed = discord.Embed(
            title="🎤 Voice Time Leaderboard",
            description="Top 10 most active voice users",
            color=discord.Color.gold()
        )
        
        for i, (user_id, seconds) in enumerate(sorted_users, 1):
            member = interaction.guild.get_member(user_id)
            if member:
                # Add current session if in voice
                total = seconds
                if user_id in self.voice_sessions:
                    session = (datetime.utcnow() - self.voice_sessions[user_id]).total_seconds()
                    total += int(session)
                
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                embed.add_field(
                    name=f"{medal} {member.display_name}",
                    value=self.format_time(total),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="voicestats", description="View server voice statistics")
    @is_member()
    async def voicestats(self, interaction: discord.Interaction):
        """Show server voice stats"""
        
        guild = interaction.guild
        
        # Count users in voice
        in_voice = sum(1 for m in guild.members if m.voice and m.voice.channel)
        
        # Total voice time
        total_seconds = sum(self.voice_time[guild.id].values())
        
        # Add current sessions
        for user_id in self.voice_sessions:
            if guild.get_member(user_id):
                session = (datetime.utcnow() - self.voice_sessions[user_id]).total_seconds()
                total_seconds += int(session)
        
        # Most active channel
        channel_activity = defaultdict(int)
        for member in guild.members:
            if member.voice and member.voice.channel:
                channel_activity[member.voice.channel.id] += 1
        
        most_active_channel = None
        if channel_activity:
            most_active_id = max(channel_activity, key=channel_activity.get)
            most_active_channel = guild.get_channel(most_active_id)
        
        embed = discord.Embed(
            title="🎤 Server Voice Statistics",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Currently in Voice",
            value=f"{in_voice} members",
            inline=True
        )
        
        embed.add_field(
            name="Total Voice Time",
            value=self.format_time(total_seconds),
            inline=True
        )
        
        embed.add_field(
            name="Tracked Users",
            value=f"{len(self.voice_time[guild.id])} members",
            inline=True
        )
        
        if most_active_channel:
            embed.add_field(
                name="Most Active Channel",
                value=f"{most_active_channel.mention} ({channel_activity[most_active_id]} users)",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(VoiceStats(bot))
