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

    # uptime removed — visible in dashboard stats bar


async def setup(bot):
    await bot.add_cog(Utility(bot))
