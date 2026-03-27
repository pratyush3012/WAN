"""
Voice XP — earn XP for time spent in voice channels (Arcane USP)
Tracks voice time, awards XP per minute, supports double XP events.
"""
import discord
from discord.ext import commands, tasks
import json, os, logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord_bot.voicexp')
VXP_FILE = 'voicexp.json'
XP_PER_MINUTE = 2
DOUBLE_XP_FILE = 'voicexp_event.json'


def _load():
    if os.path.exists(VXP_FILE):
        try:
            with open(VXP_FILE) as f: return json.load(f)
        except: pass
    return {}


def _save(d):
    with open(VXP_FILE, 'w') as f: json.dump(d, f, indent=2)


def _load_event():
    if os.path.exists(DOUBLE_XP_FILE):
        try:
            with open(DOUBLE_XP_FILE) as f: return json.load(f)
        except: pass
    return {}


def _save_event(d):
    with open(DOUBLE_XP_FILE, 'w') as f: json.dump(d, f, indent=2)


def _level_from_xp(xp):
    level = 0
    while xp >= (level + 1) * 100:
        xp -= (level + 1) * 100
        level += 1
    return level, xp, (level + 1) * 100


class VoiceXP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._sessions = {}  # (guild_id, user_id) -> join_datetime
        self._tick.start()

    def cog_unload(self):
        self._tick.cancel()

    def _is_double_xp(self, guild_id):
        event = _load_event()
        e = event.get(str(guild_id))
        if not e:
            return False
        expires = datetime.fromisoformat(e['expires'])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < expires

    @tasks.loop(minutes=1)
    async def _tick(self):
        """Award XP every minute to users in voice."""
        data = _load()
        now = datetime.now(timezone.utc)
        for (gid, uid), joined in list(self._sessions.items()):
            minutes = max(1, int((now - joined).total_seconds() / 60))
            multiplier = 2 if self._is_double_xp(gid) else 1
            xp_gain = XP_PER_MINUTE * multiplier
            g = data.setdefault(str(gid), {})
            u = g.setdefault(str(uid), {'xp': 0, 'minutes': 0})
            u['xp'] += xp_gain
            u['minutes'] = u.get('minutes', 0) + 1
            self._sessions[(gid, uid)] = now
        _save(data)

    @_tick.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                     before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        key = (member.guild.id, member.id)
        if after.channel and not before.channel:
            self._sessions[key] = datetime.now(timezone.utc)
        elif before.channel and not after.channel:
            self._sessions.pop(key, None)

    @commands.command(name='voicexp-rank')
    async def rank(self, ctx: commands.Context, member: discord.Member = None):
        """Check your voice XP rank"""
        member = member or ctx.author
        data = _load()
        u = data.get(str(ctx.guild.id), {}).get(str(member.id), {'xp': 0, 'minutes': 0})
        level, cur_xp, needed = _level_from_xp(u['xp'])
        hours = u.get('minutes', 0) // 60
        mins = u.get('minutes', 0) % 60
        embed = discord.Embed(title=f'Voice XP — {member.display_name}', color=0x9b59b6)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name='Level', value=str(level), inline=True)
        embed.add_field(name='XP', value=f'{cur_xp}/{needed}', inline=True)
        embed.add_field(name='Time in Voice', value=f'{hours}h {mins}m', inline=True)
        double = '🔥 Double XP active!' if self._is_double_xp(ctx.guild.id) else ''
        if double:
            embed.set_footer(text=double)
        await ctx.send(embed=embed)

    @commands.command(name='voicexp-leaderboard')
    async def leaderboard(self, ctx: commands.Context):
        """Top voice XP members"""
        data = _load()
        users = data.get(str(ctx.guild.id), {})
        entries = sorted(users.items(), key=lambda x: x[1].get('xp', 0), reverse=True)[:10]
        embed = discord.Embed(title=f'Voice XP Leaderboard — {ctx.guild.name}', color=0x9b59b6)
        medals = ['🥇', '🥈', '🥉']
        lines = []
        for i, (uid, u) in enumerate(entries):
            member = ctx.guild.get_member(int(uid))
            name = member.display_name if member else f'User {uid}'
            level, _, _ = _level_from_xp(u.get('xp', 0))
            medal = medals[i] if i < 3 else f'{i+1}.'
            lines.append(f'{medal} **{name}** — Level {level} ({u.get("xp", 0)} XP)')
        embed.description = '\n'.join(lines) or 'No data yet.'
        await ctx.send(embed=embed)

    @commands.command(name='voicexp-double-xp')
    @commands.has_permissions(manage_guild=True)
    async def double_xp(self, ctx: commands.Context, duration: str):
        """Start a double XP event: !voicexp-double-xp <duration> (e.g. 1h, 2h, 1d)"""
        units = {'m': 60, 'h': 3600, 'd': 86400}
        try:
            secs = int(duration[:-1]) * units[duration[-1].lower()]
        except (ValueError, KeyError):
            return await ctx.send('Invalid duration. Use e.g. 1h, 2h, 1d')
        expires = datetime.now(timezone.utc) + timedelta(seconds=secs)
        event = _load_event()
        event[str(ctx.guild.id)] = {'expires': expires.isoformat()}
        _save_event(event)
        await ctx.send(f'🔥 Double XP event started for {duration}!')

    @commands.command(name='voicexp-reset')
    @commands.has_permissions(manage_guild=True)
    async def reset(self, ctx: commands.Context, member: discord.Member):
        """Reset voice XP for a member"""
        data = _load()
        gid = str(ctx.guild.id)
        if gid in data and str(member.id) in data[gid]:
            del data[gid][str(member.id)]
            _save(data)
        await ctx.send(f'Reset voice XP for {member.mention}.')


async def setup(bot):
    await bot.add_cog(VoiceXP(bot))
