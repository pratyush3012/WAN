"""
WAN Bot - Server Analytics (replaces Statbot)
Tracks member growth, message activity, peak hours.
/analytics, /server-stats, /activity
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict

logger = logging.getLogger('discord_bot.analytics')
DATA_FILE = 'analytics_data.json'


class Analytics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data: dict = self._load()

    def _load(self) -> dict:
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save(self):
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump(self.data, f)
        except Exception as e:
            logger.error(f"Analytics save error: {e}")

    def _guild(self, gid: int) -> dict:
        key = str(gid)
        if key not in self.data:
            self.data[key] = {
                'member_snapshots': [],   # [{date, count}]
                'daily_messages': {},     # {date: count}
                'hourly_messages': {},    # {hour: count}
                'channel_messages': {},   # {channel_id: count}
                'top_users': {},          # {user_id: count}
            }
        return self.data[key]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        g = self._guild(message.guild.id)
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        hour = str(datetime.now(timezone.utc).hour)
        g['daily_messages'][today] = g['daily_messages'].get(today, 0) + 1
        g['hourly_messages'][hour] = g['hourly_messages'].get(hour, 0) + 1
        ch_key = str(message.channel.id)
        g['channel_messages'][ch_key] = g['channel_messages'].get(ch_key, 0) + 1
        uid = str(message.author.id)
        g['top_users'][uid] = g['top_users'].get(uid, 0) + 1
        # Save every 50 messages to avoid too many writes
        total = sum(g['daily_messages'].values())
        if total % 50 == 0:
            self._save()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        g = self._guild(member.guild.id)
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        snapshots = g['member_snapshots']
        if not snapshots or snapshots[-1]['date'] != today:
            snapshots.append({'date': today, 'count': member.guild.member_count})
        else:
            snapshots[-1]['count'] = member.guild.member_count
        # Keep last 90 days
        g['member_snapshots'] = snapshots[-90:]
        self._save()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        g = self._guild(member.guild.id)
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        snapshots = g['member_snapshots']
        if not snapshots or snapshots[-1]['date'] != today:
            snapshots.append({'date': today, 'count': member.guild.member_count})
        else:
            snapshots[-1]['count'] = member.guild.member_count
        g['member_snapshots'] = snapshots[-90:]
        self._save()

    @app_commands.command(name="analytics", description="📊 Show server analytics")
    async def analytics(self, interaction: discord.Interaction):
        g = self._guild(interaction.guild.id)
        guild = interaction.guild

        # Last 7 days messages
        today = datetime.now(timezone.utc)
        week_msgs = sum(
            g['daily_messages'].get((today - timedelta(days=i)).strftime('%Y-%m-%d'), 0)
            for i in range(7)
        )
        today_msgs = g['daily_messages'].get(today.strftime('%Y-%m-%d'), 0)

        # Peak hour
        hourly = g['hourly_messages']
        peak_hour = max(hourly, key=hourly.get, default='N/A')
        peak_count = hourly.get(peak_hour, 0)

        # Top channel
        ch_msgs = g['channel_messages']
        top_ch_id = max(ch_msgs, key=ch_msgs.get, default=None)
        top_ch = guild.get_channel(int(top_ch_id)) if top_ch_id else None

        # Member growth (last 7 snapshots)
        snapshots = g['member_snapshots'][-7:]
        growth = 0
        if len(snapshots) >= 2:
            growth = snapshots[-1]['count'] - snapshots[0]['count']

        embed = discord.Embed(title=f"📊 {guild.name} Analytics", color=0x6366f1)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="👥 Members", value=f"{guild.member_count:,}", inline=True)
        embed.add_field(name="📈 7-day Growth", value=f"{'+' if growth >= 0 else ''}{growth}", inline=True)
        embed.add_field(name="💬 Today's Messages", value=str(today_msgs), inline=True)
        embed.add_field(name="📅 7-day Messages", value=str(week_msgs), inline=True)
        embed.add_field(name="⏰ Peak Hour", value=f"{peak_hour}:00 UTC ({peak_count} msgs)", inline=True)
        embed.add_field(name="🔥 Most Active Channel", value=top_ch.mention if top_ch else "N/A", inline=True)

        # Top 5 users
        top_users = sorted(g['top_users'].items(), key=lambda x: x[1], reverse=True)[:5]
        if top_users:
            lines = []
            for uid, count in top_users:
                m = guild.get_member(int(uid))
                name = m.display_name if m else f"User {uid}"
                lines.append(f"**{name}** — {count} messages")
            embed.add_field(name="🏆 Top Members", value="\n".join(lines), inline=False)

        embed.set_footer(text=f"Data collected since bot joined • {today.strftime('%Y-%m-%d')}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="server-stats", description="📊 Quick server statistics")
    async def server_stats(self, interaction: discord.Interaction):
        guild = interaction.guild
        bots = sum(1 for m in guild.members if m.bot)
        humans = guild.member_count - bots
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)
        embed = discord.Embed(title=f"📊 {guild.name}", color=0x6366f1)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="👥 Total Members", value=f"{guild.member_count:,}", inline=True)
        embed.add_field(name="🟢 Online", value=str(online), inline=True)
        embed.add_field(name="🤖 Bots", value=str(bots), inline=True)
        embed.add_field(name="💬 Text Channels", value=str(len(guild.text_channels)), inline=True)
        embed.add_field(name="🔊 Voice Channels", value=str(len(guild.voice_channels)), inline=True)
        embed.add_field(name="🎭 Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="🚀 Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        embed.add_field(name="📅 Created", value=guild.created_at.strftime('%b %d, %Y'), inline=True)
        embed.add_field(name="👑 Owner", value=str(guild.owner) if guild.owner else "Unknown", inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Analytics(bot))
