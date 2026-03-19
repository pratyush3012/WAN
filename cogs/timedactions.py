"""
TimedActions — timed mute (timeout), timed roles, warn expiry
All actions persist across restarts and auto-expire.
"""
import discord
from discord.ext import commands, tasks
import json, os, logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord_bot.timedactions')
TA_FILE = 'timedactions.json'

UNITS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}


def _parse_duration(s: str) -> int | None:
    """Parse '10m', '2h', '7d' etc into seconds."""
    try:
        return int(s[:-1]) * UNITS[s[-1].lower()]
    except:
        return None


def _load():
    if os.path.exists(TA_FILE):
        try:
            with open(TA_FILE) as f: return json.load(f)
        except: pass
    return {'timed_roles': [], 'timed_mutes': []}

def _save(d):
    with open(TA_FILE, 'w') as f: json.dump(d, f, indent=2)


class TimedActions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._check.start()

    def cog_unload(self):
        self._check.cancel()

    @tasks.loop(minutes=1)
    async def _check(self):
        data = _load()
        now = datetime.now(timezone.utc)
        remaining_roles = []
        remaining_mutes = []

        for entry in data.get('timed_roles', []):
            expires = datetime.fromisoformat(entry['expires'])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if now >= expires:
                guild = self.bot.get_guild(int(entry['guild_id']))
                if guild:
                    member = guild.get_member(int(entry['user_id']))
                    role = guild.get_role(int(entry['role_id']))
                    if member and role:
                        try:
                            await member.remove_roles(role, reason='Timed role expired')
                            logger.info(f'Removed timed role {role.name} from {member}')
                        except Exception as e:
                            logger.warning(f'Timed role removal failed: {e}')
            else:
                remaining_roles.append(entry)

        for entry in data.get('timed_mutes', []):
            expires = datetime.fromisoformat(entry['expires'])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if now < expires:
                remaining_mutes.append(entry)

        data['timed_roles'] = remaining_roles
        data['timed_mutes'] = remaining_mutes
        _save(data)

    @_check.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    @commands.command(name='mute')
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: str, *, reason: str = 'No reason provided'):
        """Timeout a member: !mute @user <duration> [reason] (e.g. 10m, 2h, 1d)"""
        secs = _parse_duration(duration)
        if not secs:
            return await ctx.send('Invalid duration. Use e.g. `10m`, `2h`, `1d`, `7d`')
        if secs > 2419200:
            return await ctx.send('Max timeout is 28 days.')
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send('You cannot mute someone with equal or higher role.')

        expires = datetime.now(timezone.utc) + timedelta(seconds=secs)
        try:
            await member.timeout(timedelta(seconds=secs), reason=reason)
        except discord.Forbidden:
            return await ctx.send('Missing permissions to timeout this member.')

        data = _load()
        data.setdefault('timed_mutes', []).append({
            'guild_id': str(ctx.guild.id),
            'user_id': str(member.id),
            'expires': expires.isoformat(),
            'reason': reason,
            'mod_id': str(ctx.author.id),
        })
        _save(data)

        embed = discord.Embed(
            title='🔇 Member Muted',
            description=f'{member.mention} has been muted for **{duration}**.\n**Reason:** {reason}',
            color=0x9b59b6
        )
        embed.set_footer(text=f'Expires: {expires.strftime("%Y-%m-%d %H:%M UTC")}')
        await ctx.send(embed=embed)

        try:
            await member.send(f'You were muted in **{ctx.guild.name}** for {duration}. Reason: {reason}')
        except: pass

    @commands.command(name='unmute')
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        """Remove timeout from a member"""
        try:
            await member.timeout(None, reason=f'Unmuted by {ctx.author}')
            await ctx.send(f'✅ {member.mention} has been unmuted.')
        except discord.Forbidden:
            await ctx.send('Missing permissions.')

    @commands.command(name='role-add-timed')
    @commands.has_permissions(manage_roles=True)
    async def role_add_timed(self, ctx: commands.Context, member: discord.Member,
                              role: discord.Role, duration: str, *, reason: str = 'Timed role'):
        """Give a member a role for a set duration: !role-add-timed @user @role <duration>"""
        secs = _parse_duration(duration)
        if not secs:
            return await ctx.send('Invalid duration.')
        if role >= ctx.guild.me.top_role:
            return await ctx.send('I cannot assign that role (too high).')

        expires = datetime.now(timezone.utc) + timedelta(seconds=secs)
        try:
            await member.add_roles(role, reason=reason)
        except discord.Forbidden:
            return await ctx.send('Missing permissions to assign that role.')

        data = _load()
        data.setdefault('timed_roles', []).append({
            'guild_id': str(ctx.guild.id),
            'user_id': str(member.id),
            'role_id': str(role.id),
            'expires': expires.isoformat(),
            'reason': reason,
        })
        _save(data)

        embed = discord.Embed(
            title='⏱️ Timed Role Assigned',
            description=f'{member.mention} received **{role.name}** for **{duration}**.',
            color=role.color.value or 0x5865f2
        )
        embed.set_footer(text=f'Expires: {expires.strftime("%Y-%m-%d %H:%M UTC")}')
        await ctx.send(embed=embed)

    @commands.command(name='timed-roles-list')
    @commands.has_permissions(manage_roles=True)
    async def list_timed(self, ctx: commands.Context):
        """List active timed roles in this server"""
        data = _load()
        entries = [e for e in data.get('timed_roles', []) if e['guild_id'] == str(ctx.guild.id)]
        if not entries:
            return await ctx.send('No active timed roles.')
        embed = discord.Embed(title='Active Timed Roles', color=0x5865f2)
        for e in entries[:15]:
            member = ctx.guild.get_member(int(e['user_id']))
            role = ctx.guild.get_role(int(e['role_id']))
            embed.add_field(
                name=f'{member.display_name if member else e["user_id"]} → {role.name if role else e["role_id"]}',
                value=f'Expires: `{e["expires"][:16]}`',
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(name='softban')
    @commands.has_permissions(ban_members=True)
    async def softban(self, ctx: commands.Context, member: discord.Member, delete_days: int = 1, *, reason: str = 'Softban'):
        """Ban then immediately unban: !softban @user [delete_days] [reason]"""
        delete_days = max(1, min(7, delete_days))
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send('Cannot softban someone with equal or higher role.')
        try:
            await member.ban(reason=f'Softban: {reason}', delete_message_days=delete_days)
            await ctx.guild.unban(member, reason='Softban: immediate unban')
            embed = discord.Embed(
                title='🔨 Softban',
                description=f'{member.mention} was softbanned.\n**Reason:** {reason}\n**Messages deleted:** {delete_days} day(s)',
                color=0xe67e22
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send('Missing permissions.')

    @commands.command(name='massban')
    @commands.has_permissions(ban_members=True)
    async def massban(self, ctx: commands.Context, *, user_ids: str):
        """Ban multiple users by ID: !massban <id1> <id2> ..."""
        ids = [uid.strip() for uid in user_ids.split() if uid.strip().isdigit()]
        if not ids:
            return await ctx.send('No valid user IDs provided.')
        if len(ids) > 50:
            return await ctx.send('Max 50 users per massban.')

        msg = await ctx.send(f'Banning {len(ids)} users...')
        banned, failed = [], []
        for uid in ids:
            try:
                user = await self.bot.fetch_user(int(uid))
                await ctx.guild.ban(user, reason=f'Massban by {ctx.author}')
                banned.append(str(uid))
            except:
                failed.append(str(uid))

        embed = discord.Embed(title='🔨 Mass Ban', color=0xe74c3c)
        embed.add_field(name=f'Banned ({len(banned)})', value=', '.join(banned[:20]) or 'None', inline=False)
        if failed:
            embed.add_field(name=f'Failed ({len(failed)})', value=', '.join(failed[:20]), inline=False)
        await msg.edit(content=None, embed=embed)


async def setup(bot):
    await bot.add_cog(TimedActions(bot))
