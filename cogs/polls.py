"""
Advanced Polls — button-based voting, timed polls, results
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger('discord_bot.polls')
POLLS_FILE = 'polls.json'


def _load() -> dict:
    if os.path.exists(POLLS_FILE):
        try:
            with open(POLLS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    with open(POLLS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _results_embed(p: dict, ended=False) -> discord.Embed:
    total = sum(len(v) for v in p['votes'].values())
    color = 0x5865f2 if not ended else 0x95a5a6
    embed = discord.Embed(title=f"{'📊' if not ended else '✅'} {p['question']}", color=color)

    for i, opt in enumerate(p['options']):
        voters = p['votes'].get(str(i), [])
        pct = (len(voters) / total * 100) if total > 0 else 0
        bar_len = int(pct / 10)
        bar = '█' * bar_len + '░' * (10 - bar_len)
        embed.add_field(
            name=f"{opt}",
            value=f"`{bar}` {pct:.1f}% ({len(voters)} votes)",
            inline=False
        )

    embed.set_footer(text=f"Total votes: {total}{' • Poll ended' if ended else ''}")
    if not ended and p.get('ends_at'):
        ends_at = datetime.fromisoformat(p['ends_at'])
        embed.add_field(name="Ends", value=f"<t:{int(ends_at.timestamp())}:R>", inline=False)
    return embed


class PollView(discord.ui.View):
    def __init__(self, options: list, msg_id: str = None):
        super().__init__(timeout=None)
        for i, opt in enumerate(options[:5]):
            btn = discord.ui.Button(
                label=opt[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"poll_{msg_id or 'x'}_{i}"
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _make_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            polls = _load()
            # find poll by message
            msg_id = str(interaction.message.id)
            p = polls.get(msg_id)
            if not p:
                return await interaction.response.send_message("Poll not found.", ephemeral=True)
            if p.get('ended'):
                return await interaction.response.send_message("This poll has ended.", ephemeral=True)

            uid = str(interaction.user.id)
            # Remove previous vote
            for votes in p['votes'].values():
                if uid in votes:
                    votes.remove(uid)

            p['votes'].setdefault(str(idx), []).append(uid)
            _save(polls)

            total = sum(len(v) for v in p['votes'].values())
            await interaction.response.send_message(
                f"Voted for **{p['options'][idx]}**! Total votes: {total}", ephemeral=True)
            # Update embed
            try:
                await interaction.message.edit(embed=_results_embed(p))
            except Exception:
                pass
        return callback


class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._check_polls.start()

    def cog_unload(self):
        self._check_polls.cancel()

    @tasks.loop(seconds=30)
    async def _check_polls(self):
        polls = _load()
        now = datetime.now(timezone.utc)
        changed = False
        for msg_id, p in list(polls.items()):
            if p.get('ended') or not p.get('ends_at'):
                continue
            ends_at = datetime.fromisoformat(p['ends_at'])
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
            if now >= ends_at:
                p['ended'] = True
                changed = True
                try:
                    guild = self.bot.get_guild(int(p['guild_id']))
                    ch = guild.get_channel(int(p['channel_id'])) if guild else None
                    if ch:
                        msg = await ch.fetch_message(int(msg_id))
                        await msg.edit(embed=_results_embed(p, ended=True), view=None)
                        await ch.send(f"📊 Poll ended: **{p['question']}**")
                except Exception as e:
                    logger.warning(f"Poll end error {msg_id}: {e}")
        if changed:
            _save(polls)

    @_check_polls.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="poll", description="Create a poll with up to 5 options")
    @app_commands.describe(
        question="The poll question",
        option1="Option 1", option2="Option 2",
        option3="Option 3 (optional)", option4="Option 4 (optional)", option5="Option 5 (optional)",
        duration="Optional duration e.g. 10m, 2h, 1d"
    )
    async def poll(self, interaction: discord.Interaction,
                   question: str, option1: str, option2: str,
                   option3: str = None, option4: str = None, option5: str = None,
                   duration: str = None):
        options = [o for o in [option1, option2, option3, option4, option5] if o]

        ends_at = None
        if duration:
            units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
            try:
                secs = int(duration[:-1]) * units[duration[-1].lower()]
                ends_at = (datetime.now(timezone.utc) + timedelta(seconds=secs)).isoformat()
            except Exception:
                return await interaction.response.send_message("Invalid duration format.", ephemeral=True)

        p = {
            'question': question,
            'options': options,
            'votes': {str(i): [] for i in range(len(options))},
            'guild_id': str(interaction.guild.id),
            'channel_id': str(interaction.channel.id),
            'host_id': str(interaction.user.id),
            'ends_at': ends_at,
            'ended': False,
        }

        view = PollView(options)
        await interaction.response.send_message(embed=_results_embed(p), view=view)
        msg = await interaction.original_response()

        # Re-create view with correct message ID for persistence
        view2 = PollView(options, str(msg.id))
        await msg.edit(view=view2)

        polls = _load()
        polls[str(msg.id)] = p
        _save(polls)

    @app_commands.command(name="poll-end", description="End a poll early")
    @app_commands.describe(message_id="Message ID of the poll")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def poll_end(self, interaction: discord.Interaction, message_id: str):
        polls = _load()
        p = polls.get(message_id)
        if not p:
            return await interaction.response.send_message("Poll not found.", ephemeral=True)
        p['ended'] = True
        _save(polls)
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
            await msg.edit(embed=_results_embed(p, ended=True), view=None)
        except Exception:
            pass
        await interaction.response.send_message("Poll ended.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Polls(bot))
