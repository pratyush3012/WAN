"""
Reminders — persistent reminders that survive restarts
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
import json
import os
import logging

logger = logging.getLogger('discord_bot.reminders')
REMINDERS_FILE = 'reminders.json'


def _load() -> list:
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save(data: list):
    with open(REMINDERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _parse_duration(s: str) -> int:
    s = s.strip().lower()
    units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    if s[-1] in units:
        try:
            return int(s[:-1]) * units[s[-1]]
        except ValueError:
            pass
    raise ValueError(f"Invalid duration: {s!r}. Use e.g. 30m, 2h, 1d")


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._check.start()

    def cog_unload(self):
        self._check.cancel()

    @tasks.loop(seconds=15)
    async def _check(self):
        reminders = _load()
        now = datetime.now(timezone.utc)
        remaining = []
        for r in reminders:
            due = datetime.fromisoformat(r['due'])
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if now >= due:
                try:
                    ch = self.bot.get_channel(int(r['channel_id']))
                    if ch:
                        await ch.send(
                            f"<@{r['user_id']}> ⏰ Reminder: **{r['message']}**"
                        )
                except Exception as e:
                    logger.warning(f"Reminder delivery failed: {e}")
            else:
                remaining.append(r)
        _save(remaining)

    @_check.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="remind", description="Set a reminder")
    @app_commands.describe(duration="When to remind you e.g. 30m, 2h, 1d", message="What to remind you about")
    async def remind(self, interaction: discord.Interaction, duration: str, message: str):
        try:
            secs = _parse_duration(duration)
        except ValueError as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

        due = (datetime.now(timezone.utc) + timedelta(seconds=secs)).isoformat()
        reminders = _load()
        reminders.append({
            'user_id': str(interaction.user.id),
            'channel_id': str(interaction.channel.id),
            'message': message,
            'due': due,
        })
        _save(reminders)

        due_dt = datetime.fromisoformat(due)
        await interaction.response.send_message(
            f"Reminder set! I'll remind you <t:{int(due_dt.timestamp())}:R>: **{message}**",
            ephemeral=True
        )

    @app_commands.command(name="reminders", description="List your active reminders")
    async def list_reminders(self, interaction: discord.Interaction):
        reminders = _load()
        mine = [r for r in reminders if r['user_id'] == str(interaction.user.id)]
        if not mine:
            return await interaction.response.send_message("You have no active reminders.", ephemeral=True)
        embed = discord.Embed(title="Your Reminders", color=0x5865f2)
        for r in mine[:10]:
            due = datetime.fromisoformat(r['due'])
            embed.add_field(
                name=r['message'][:50],
                value=f"<t:{int(due.timestamp())}:R>",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Reminders(bot))
