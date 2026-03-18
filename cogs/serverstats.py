"""
Server Stats — auto-updating voice channel counters (Dyno/MEE6 USP)
Channels update every 10 minutes to respect Discord rate limits.
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json, os, logging
from datetime import datetime, timezone

logger = logging.getLogger('discord_bot.serverstats')
STATS_FILE = 'serverstats.json'


def _load():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE) as f: return json.load(f)
        except: pass
    return {}


def _save(d):
    with open(STATS_FILE, 'w') as f: json.dump(d, f, indent=2)


STAT_TYPES = {
    'members': lambda g: f'Members: {g.member_count}',
    'online':  lambda g: f'Online: {sum(1 for m in g.members if m.status != discord.Status.offline)}',
    'bots':    lambda g: f'Bots: {sum(1 for m in g.members if m.bot)}',
    'humans':  lambda g: f'Humans: {sum(1 for m in g.members if not m.bot)}',
    'channels':lambda g: f'Channels: {len(g.channels)}',
    'roles':   lambda g: f'Roles: {len(g.roles)}',
    'boosts':  lambda g: f'Boosts: {g.premium_subscription_count or 0}',
}


class ServerStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._update_loop.start()

    def cog_unload(self):
        self._update_loop.cancel()

    @tasks.loop(minutes=10)
    async def _update_loop(self):
        data = _load()
        for gid, channels in data.items():
            guild = self.bot.get_guild(int(gid))
            if not guild:
                continue
            for ch_id, stat_type in list(channels.items()):
                ch = guild.get_channel(int(ch_id))
                if not ch:
                    continue
                try:
                    fn = STAT_TYPES.get(stat_type)
                    if fn:
                        await ch.edit(name=fn(guild), reason='Stats update')
                except Exception as e:
                    logger.warning(f'Stats update failed for {ch_id}: {e}')

    @_update_loop.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name='serverstats-setup', description='Create a stat voice channel')
    @app_commands.describe(
        stat='Which stat to display',
        category='Category to create the channel in (optional)'
    )
    @app_commands.choices(stat=[app_commands.Choice(name=k, value=k) for k in STAT_TYPES])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction,
                    stat: app_commands.Choice[str],
                    category: discord.CategoryChannel = None):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        fn = STAT_TYPES[stat.value]
        name = fn(guild)
        overwrites = {guild.default_role: discord.PermissionOverwrite(connect=False)}
        ch = await guild.create_voice_channel(name, category=category, overwrites=overwrites,
                                               reason='Server stats channel')
        data = _load()
        data.setdefault(str(guild.id), {})[str(ch.id)] = stat.value
        _save(data)
        await interaction.followup.send(f'Created stat channel {ch.mention} — updates every 10 min.')

    @app_commands.command(name='serverstats-remove', description='Remove a stat channel')
    @app_commands.describe(channel='The stat voice channel to remove')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        data = _load()
        gid = str(interaction.guild.id)
        cid = str(channel.id)
        if gid in data and cid in data[gid]:
            del data[gid][cid]
            _save(data)
            try:
                await channel.delete(reason='Stats channel removed')
            except: pass
            await interaction.response.send_message('Stat channel removed.', ephemeral=True)
        else:
            await interaction.response.send_message('That channel is not a stat channel.', ephemeral=True)

    @app_commands.command(name='serverstats-list', description='List all stat channels')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def list_stats(self, interaction: discord.Interaction):
        data = _load()
        channels = data.get(str(interaction.guild.id), {})
        if not channels:
            return await interaction.response.send_message('No stat channels configured.', ephemeral=True)
        lines = []
        for ch_id, stat in channels.items():
            ch = interaction.guild.get_channel(int(ch_id))
            lines.append(f'• {ch.mention if ch else ch_id} → `{stat}`')
        embed = discord.Embed(title='Server Stat Channels', description='\n'.join(lines), color=0x5865f2)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ServerStats(bot))
