"""
WAN Bot - Dashboard Custom Commands
Auto-generated and hot-reloaded by the web dashboard.
"""
import discord
from discord import app_commands
from discord.ext import commands


class DashboardCustomCommands(commands.Cog):
    """Holds custom slash commands created via the web dashboard."""

    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(DashboardCustomCommands(bot))
