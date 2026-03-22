"""
Utility — just uptime (other commands moved to info.py, afk.py, reminders.py)
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import logging

logger = logging.getLogger('discord_bot.utility')


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="uptime")
    async def uptime(self, ctx):
        now = datetime.now(timezone.utc)
        start = self.bot.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        delta = now - start
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        mins, secs = divmod(rem, 60)
        embed = discord.Embed(
            title="Bot Uptime",
            description=f"**{days}d {hours}h {mins}m {secs}s**",
            color=0x5865f2
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Utility(bot))
