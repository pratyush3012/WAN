"""
AFK System — auto-reply when mentioned, auto-remove on message
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import logging

logger = logging.getLogger('discord_bot.afk')


class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._afk: dict = {}  # user_id -> {reason, since}

    @app_commands.command(name="afk", description="💤 Set your AFK status")
    @app_commands.describe(reason="Reason for being AFK")
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK"):
        self._afk[interaction.user.id] = {
            'reason': reason,
            'since': datetime.now(timezone.utc).isoformat()
        }
        await interaction.response.send_message(
            f"💤 You're now AFK: **{reason}**\nI'll let people know when they mention you.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        uid = message.author.id

        # Remove AFK if user sends a message
        if uid in self._afk:
            afk_data = self._afk.pop(uid)
            since = datetime.fromisoformat(afk_data['since'])
            elapsed = datetime.now(timezone.utc) - since
            mins = int(elapsed.total_seconds() / 60)
            try:
                await message.reply(
                    f"Welcome back! You were AFK for **{mins} minute(s)**.",
                    delete_after=10
                )
            except Exception:
                pass
            return

        # Notify if a mentioned user is AFK
        for mentioned in message.mentions:
            if mentioned.id in self._afk and mentioned.id != uid:
                afk_data = self._afk[mentioned.id]
                since = datetime.fromisoformat(afk_data['since'])
                elapsed = datetime.now(timezone.utc) - since
                mins = int(elapsed.total_seconds() / 60)
                try:
                    await message.reply(
                        f"{mentioned.display_name} is AFK: **{afk_data['reason']}** "
                        f"(since {mins} minute(s) ago)",
                        delete_after=15
                    )
                except Exception:
                    pass


async def setup(bot):
    await bot.add_cog(AFK(bot))
