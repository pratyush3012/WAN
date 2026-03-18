"""
Giveaway System — Carl-bot style
Features: timed giveaways, winner selection, reroll, multiple winners, requirements
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import random
import json
import os
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger('discord_bot.giveaways')
GIVEAWAY_FILE = 'giveaways.json'


def _load() -> dict:
    if os.path.exists(GIVEAWAY_FILE):
        try:
            with open(GIVEAWAY_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    with open(GIVEAWAY_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _parse_duration(s: str) -> int:
    """Parse '10m', '2h', '1d' → seconds."""
    s = s.strip().lower()
    units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    if s[-1] in units:
        try:
            return int(s[:-1]) * units[s[-1]]
        except ValueError:
            pass
    raise ValueError(f"Invalid duration: {s!r}. Use format like 10m, 2h, 1d")


def _giveaway_embed(g: dict, ended=False) -> discord.Embed:
    ends_at = datetime.fromisoformat(g['ends_at'])
    color = 0x2ecc71 if not ended else 0x95a5a6
    embed = discord.Embed(
        title=f"{'🎉' if not ended else '🎊'} {g['prize']}",
        color=color
    )
    embed.add_field(name="Winners", value=str(g['winners']), inline=True)
    embed.add_field(name="Hosted by", value=f"<@{g['host_id']}>", inline=True)
    if not ended:
        embed.add_field(name="Ends", value=f"<t:{int(ends_at.timestamp())}:R>", inline=True)
        embed.set_footer(text="React with 🎉 to enter!")
    else:
        winners = g.get('winner_ids', [])
        if winners:
            embed.add_field(name="Winners", value=" ".join(f"<@{w}>" for w in winners), inline=False)
        else:
            embed.add_field(name="Winners", value="No valid entries", inline=False)
        embed.set_footer(text="Giveaway ended")
    embed.timestamp = ends_at
    return embed


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎉 Enter", style=discord.ButtonStyle.green, custom_id="giveaway_enter")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog('Giveaways')
        if not cog:
            return await interaction.response.send_message("Giveaway system unavailable.", ephemeral=True)

        msg_id = str(interaction.message.id)
        giveaways = _load()
        g = giveaways.get(msg_id)
        if not g:
            return await interaction.response.send_message("This giveaway no longer exists.", ephemeral=True)
        if g.get('ended'):
            return await interaction.response.send_message("This giveaway has ended.", ephemeral=True)

        uid = str(interaction.user.id)
        entries = g.setdefault('entries', [])
        if uid in entries:
            entries.remove(uid)
            _save(giveaways)
            await interaction.response.send_message("You left the giveaway.", ephemeral=True)
        else:
            entries.append(uid)
            _save(giveaways)
            await interaction.response.send_message(
                f"You entered! Total entries: **{len(entries)}**", ephemeral=True)


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(GiveawayView())  # re-register persistent view
        self._check_giveaways.start()

    def cog_unload(self):
        self._check_giveaways.cancel()

    @tasks.loop(seconds=15)
    async def _check_giveaways(self):
        giveaways = _load()
        now = datetime.now(timezone.utc)
        changed = False
        for msg_id, g in list(giveaways.items()):
            if g.get('ended'):
                continue
            ends_at = datetime.fromisoformat(g['ends_at'])
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
            if now >= ends_at:
                await self._end_giveaway(msg_id, g, giveaways)
                changed = True
        if changed:
            _save(giveaways)

    @_check_giveaways.before_loop
    async def _before_check(self):
        await self.bot.wait_until_ready()

    async def _end_giveaway(self, msg_id: str, g: dict, giveaways: dict):
        g['ended'] = True
        entries = g.get('entries', [])
        num_winners = min(g['winners'], len(entries))
        winner_ids = random.sample(entries, num_winners) if entries else []
        g['winner_ids'] = winner_ids

        try:
            guild = self.bot.get_guild(int(g['guild_id']))
            channel = guild.get_channel(int(g['channel_id'])) if guild else None
            if channel:
                msg = await channel.fetch_message(int(msg_id))
                await msg.edit(embed=_giveaway_embed(g, ended=True), view=None)
                if winner_ids:
                    mentions = " ".join(f"<@{w}>" for w in winner_ids)
                    await channel.send(
                        f"🎊 Congratulations {mentions}! You won **{g['prize']}**!\n"
                        f"[Jump to giveaway]({msg.jump_url})"
                    )
                else:
                    await channel.send(f"No valid entries for **{g['prize']}**.")
        except Exception as e:
            logger.warning(f"Could not end giveaway {msg_id}: {e}")

    g = app_commands.Group(name="giveaway", description="Giveaway management")

    @g.command(name="start", description="Start a giveaway")
    @app_commands.describe(
        duration="Duration e.g. 10m, 2h, 1d",
        winners="Number of winners",
        prize="What are you giving away?",
        channel="Channel to post in (defaults to current)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_start(self, interaction: discord.Interaction,
                              duration: str, winners: int, prize: str,
                              channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=True)
        try:
            secs = _parse_duration(duration)
        except ValueError as e:
            return await interaction.followup.send(str(e), ephemeral=True)

        if winners < 1 or winners > 20:
            return await interaction.followup.send("Winners must be between 1 and 20.", ephemeral=True)

        ch = channel or interaction.channel
        ends_at = datetime.now(timezone.utc) + timedelta(seconds=secs)

        g_data = {
            'prize': prize,
            'winners': winners,
            'host_id': str(interaction.user.id),
            'guild_id': str(interaction.guild.id),
            'channel_id': str(ch.id),
            'ends_at': ends_at.isoformat(),
            'entries': [],
            'ended': False,
        }

        msg = await ch.send(embed=_giveaway_embed(g_data), view=GiveawayView())
        giveaways = _load()
        giveaways[str(msg.id)] = g_data
        _save(giveaways)
        await interaction.followup.send(f"Giveaway started in {ch.mention}!", ephemeral=True)

    @g.command(name="end", description="End a giveaway early")
    @app_commands.describe(message_id="Message ID of the giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_end(self, interaction: discord.Interaction, message_id: str):
        giveaways = _load()
        g = giveaways.get(message_id)
        if not g:
            return await interaction.response.send_message("Giveaway not found.", ephemeral=True)
        if g.get('ended'):
            return await interaction.response.send_message("Already ended.", ephemeral=True)
        await self._end_giveaway(message_id, g, giveaways)
        _save(giveaways)
        await interaction.response.send_message("Giveaway ended.", ephemeral=True)

    @g.command(name="reroll", description="Reroll winners for an ended giveaway")
    @app_commands.describe(message_id="Message ID of the giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_reroll(self, interaction: discord.Interaction, message_id: str):
        giveaways = _load()
        g = giveaways.get(message_id)
        if not g or not g.get('ended'):
            return await interaction.response.send_message("Giveaway not found or not ended.", ephemeral=True)
        entries = g.get('entries', [])
        if not entries:
            return await interaction.response.send_message("No entries to reroll.", ephemeral=True)
        num = min(g['winners'], len(entries))
        new_winners = random.sample(entries, num)
        g['winner_ids'] = new_winners
        _save(giveaways)
        mentions = " ".join(f"<@{w}>" for w in new_winners)
        await interaction.response.send_message(
            f"🎊 New winners for **{g['prize']}**: {mentions}")

    @g.command(name="list", description="List active giveaways in this server")
    async def giveaway_list(self, interaction: discord.Interaction):
        giveaways = _load()
        active = [g for g in giveaways.values()
                  if g.get('guild_id') == str(interaction.guild.id) and not g.get('ended')]
        if not active:
            return await interaction.response.send_message("No active giveaways.", ephemeral=True)
        embed = discord.Embed(title="Active Giveaways", color=0x2ecc71)
        for g in active[:10]:
            ends_at = datetime.fromisoformat(g['ends_at'])
            embed.add_field(
                name=g['prize'],
                value=f"Winners: {g['winners']} | Ends: <t:{int(ends_at.timestamp())}:R> | Entries: {len(g.get('entries', []))}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Giveaways(bot))
