"""
Server Stats — auto-updating voice channel counters (Dyno/MEE6 USP)
Channels update every 10 minutes to respect Discord rate limits.
"""
import discord
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

    @commands.command(name='serverstats-setup')
    @commands.has_permissions(manage_guild=True)
    async def setup(self, ctx: commands.Context, stat: str, category: discord.CategoryChannel = None):
        """Create a stat voice channel: !serverstats-setup <stat> [category]
        Stats: members, online, bots, humans, channels, roles, boosts"""
        if stat not in STAT_TYPES:
            return await ctx.send(f'Invalid stat. Choose from: {", ".join(STAT_TYPES.keys())}')
        guild = ctx.guild
        fn = STAT_TYPES[stat]
        name = fn(guild)
        overwrites = {guild.default_role: discord.PermissionOverwrite(connect=False)}
        ch = await guild.create_voice_channel(name, category=category, overwrites=overwrites,
                                               reason='Server stats channel')
        data = _load()
        data.setdefault(str(guild.id), {})[str(ch.id)] = stat
        _save(data)
        await ctx.send(f'Created stat channel {ch.mention} — updates every 10 min.')

    @commands.command(name='serverstats-remove')
    @commands.has_permissions(manage_guild=True)
    async def remove(self, ctx: commands.Context, channel: discord.VoiceChannel):
        """Remove a stat channel"""
        data = _load()
        gid = str(ctx.guild.id)
        cid = str(channel.id)
        if gid in data and cid in data[gid]:
            del data[gid][cid]
            _save(data)
            try:
                await channel.delete(reason='Stats channel removed')
            except: pass
            await ctx.send('Stat channel removed.')
        else:
            await ctx.send('That channel is not a stat channel.')

    @commands.command(name='serverstats-list')
    @commands.has_permissions(manage_guild=True)
    async def list_stats(self, ctx: commands.Context):
        """List all stat channels"""
        data = _load()
        channels = data.get(str(ctx.guild.id), {})
        if not channels:
            return await ctx.send('No stat channels configured.')
        lines = []
        for ch_id, stat in channels.items():
            ch = ctx.guild.get_channel(int(ch_id))
            lines.append(f'• {ch.mention if ch else ch_id} → `{stat}`')
        embed = discord.Embed(title='Server Stat Channels', description='\n'.join(lines), color=0x5865f2)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ServerStats(bot))
