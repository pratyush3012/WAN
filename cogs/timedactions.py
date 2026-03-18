"""
TimedActions — timed mute (timeout), timed roles, warn expiry
All actions persist across restarts and auto-expire.
"""
import discord
from discord import app_commands
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

        # Expire timed roles
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

        # Expire timed mutes (Discord handles timeout expiry natively, but we track for logging)
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

    # ── Timed Mute ────────────────────────────────────────────────────────────

    @app_commands.command(name='mute', description='Timeout a member for a duration')
    @app_commands.describe(member='Member to mute', duration='Duration e.g. 10m, 2h, 1d', reason='Reason')
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member,
                   duration: str, reason: str = 'No reason provided'):
        secs = _parse_duration(duration)
        if not secs:
            return await interaction.response.send_message(
                'Invalid duration. Use e.g. `10m`, `2h`, `1d`, `7d`', ephemeral=True)
        if secs > 2419200:  # Discord max 28 days
            return await interaction.response.send_message('Max timeout is 28 days.', ephemeral=True)
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message('You cannot mute someone with equal or higher role.', ephemeral=True)

        expires = datetime.now(timezone.utc) + timedelta(seconds=secs)
        try:
            await member.timeout(timedelta(seconds=secs), reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message('Missing permissions to timeout this member.', ephemeral=True)

        data = _load()
        data.setdefault('timed_mutes', []).append({
            'guild_id': str(interaction.guild.id),
            'user_id': str(member.id),
            'expires': expires.isoformat(),
            'reason': reason,
            'mod_id': str(interaction.user.id),
        })
        _save(data)

        embed = discord.Embed(
            title='🔇 Member Muted',
            description=f'{member.mention} has been muted for **{duration}**.\n**Reason:** {reason}',
            color=0x9b59b6
        )
        embed.set_footer(text=f'Expires: {expires.strftime("%Y-%m-%d %H:%M UTC")}')
        await interaction.response.send_message(embed=embed)

        try:
            await member.send(f'You were muted in **{interaction.guild.name}** for {duration}. Reason: {reason}')
        except: pass

    @app_commands.command(name='unmute', description='Remove timeout from a member')
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        try:
            await member.timeout(None, reason=f'Unmuted by {interaction.user}')
            await interaction.response.send_message(f'✅ {member.mention} has been unmuted.')
        except discord.Forbidden:
            await interaction.response.send_message('Missing permissions.', ephemeral=True)

    # ── Timed Roles ───────────────────────────────────────────────────────────

    @app_commands.command(name='role-add-timed', description='Give a member a role for a set duration')
    @app_commands.describe(member='Member', role='Role to assign', duration='Duration e.g. 1h, 7d', reason='Reason')
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role_add_timed(self, interaction: discord.Interaction, member: discord.Member,
                              role: discord.Role, duration: str, reason: str = 'Timed role'):
        secs = _parse_duration(duration)
        if not secs:
            return await interaction.response.send_message('Invalid duration.', ephemeral=True)
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message('I cannot assign that role (too high).', ephemeral=True)

        expires = datetime.now(timezone.utc) + timedelta(seconds=secs)
        try:
            await member.add_roles(role, reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message('Missing permissions to assign that role.', ephemeral=True)

        data = _load()
        data.setdefault('timed_roles', []).append({
            'guild_id': str(interaction.guild.id),
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
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='timed-roles-list', description='List active timed roles in this server')
    @app_commands.checks.has_permissions(manage_roles=True)
    async def list_timed(self, interaction: discord.Interaction):
        data = _load()
        entries = [e for e in data.get('timed_roles', []) if e['guild_id'] == str(interaction.guild.id)]
        if not entries:
            return await interaction.response.send_message('No active timed roles.', ephemeral=True)
        embed = discord.Embed(title='Active Timed Roles', color=0x5865f2)
        for e in entries[:15]:
            member = interaction.guild.get_member(int(e['user_id']))
            role = interaction.guild.get_role(int(e['role_id']))
            embed.add_field(
                name=f'{member.display_name if member else e["user_id"]} → {role.name if role else e["role_id"]}',
                value=f'Expires: `{e["expires"][:16]}`',
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Softban ───────────────────────────────────────────────────────────────

    @app_commands.command(name='softban', description='Ban then immediately unban (clears messages, no permanent ban)')
    @app_commands.describe(member='Member to softban', reason='Reason', delete_days='Days of messages to delete (1-7)')
    @app_commands.checks.has_permissions(ban_members=True)
    async def softban(self, interaction: discord.Interaction, member: discord.Member,
                      reason: str = 'Softban', delete_days: int = 1):
        delete_days = max(1, min(7, delete_days))
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message('Cannot softban someone with equal or higher role.', ephemeral=True)
        try:
            await member.ban(reason=f'Softban: {reason}', delete_message_days=delete_days)
            await interaction.guild.unban(member, reason='Softban: immediate unban')
            embed = discord.Embed(
                title='🔨 Softban',
                description=f'{member.mention} was softbanned.\n**Reason:** {reason}\n**Messages deleted:** {delete_days} day(s)',
                color=0xe67e22
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message('Missing permissions.', ephemeral=True)

    # ── Massban ───────────────────────────────────────────────────────────────

    @app_commands.command(name='massban', description='Ban multiple users by ID (space-separated)')
    @app_commands.describe(user_ids='Space-separated user IDs', reason='Reason for mass ban')
    @app_commands.checks.has_permissions(ban_members=True)
    async def massban(self, interaction: discord.Interaction, user_ids: str, reason: str = 'Mass ban'):
        await interaction.response.defer()
        ids = [uid.strip() for uid in user_ids.split() if uid.strip().isdigit()]
        if not ids:
            return await interaction.followup.send('No valid user IDs provided.', ephemeral=True)
        if len(ids) > 50:
            return await interaction.followup.send('Max 50 users per massban.', ephemeral=True)

        banned, failed = [], []
        for uid in ids:
            try:
                user = await self.bot.fetch_user(int(uid))
                await interaction.guild.ban(user, reason=f'Massban by {interaction.user}: {reason}')
                banned.append(str(uid))
            except:
                failed.append(str(uid))

        embed = discord.Embed(title='🔨 Mass Ban', color=0xe74c3c)
        embed.add_field(name=f'Banned ({len(banned)})', value=', '.join(banned[:20]) or 'None', inline=False)
        if failed:
            embed.add_field(name=f'Failed ({len(failed)})', value=', '.join(failed[:20]), inline=False)
        embed.add_field(name='Reason', value=reason, inline=False)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TimedActions(bot))
