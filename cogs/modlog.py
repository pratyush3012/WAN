"""
Moderation Log — warn system with cases, strike thresholds, auto-actions, timed bans
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json, os, asyncio
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger('discord_bot.modlog')
MODLOG_FILE = 'modlog.json'


def _load():
    if os.path.exists(MODLOG_FILE):
        try:
            with open(MODLOG_FILE) as f: return json.load(f)
        except: pass
    return {'cases': {}, 'config': {}, 'tempbans': []}


def _save(d):
    with open(MODLOG_FILE, 'w') as f: json.dump(d, f, indent=2)


def _next_case(data, guild_id):
    gid = str(guild_id)
    cases = data['cases'].get(gid, [])
    return len(cases) + 1


def _add_case(data, guild_id, action, mod, target, reason, duration=None):
    gid = str(guild_id)
    cases = data['cases'].setdefault(gid, [])
    case = {
        'id': len(cases) + 1,
        'action': action,
        'mod_id': str(mod.id),
        'mod': str(mod),
        'target_id': str(target.id),
        'target': str(target),
        'reason': reason or 'No reason provided',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'duration': duration,
    }
    cases.append(case)
    _save(data)
    return case


def _case_embed(case, color=0xe74c3c):
    e = discord.Embed(title=f"Case #{case['id']} — {case['action'].upper()}", color=color)
    e.add_field(name="Target", value=f"{case['target']} (`{case['target_id']}`)", inline=True)
    e.add_field(name="Moderator", value=case['mod'], inline=True)
    e.add_field(name="Reason", value=case['reason'], inline=False)
    if case.get('duration'):
        e.add_field(name="Duration", value=case['duration'], inline=True)
    e.set_footer(text=f"Case #{case['id']} • {case['timestamp'][:10]}")
    return e


ACTION_COLORS = {
    'warn': 0xf39c12, 'kick': 0xe67e22, 'ban': 0xe74c3c,
    'tempban': 0xc0392b, 'timeout': 0x9b59b6, 'unban': 0x2ecc71,
    'note': 0x3498db,
}


class ModLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._tempban_check.start()

    def cog_unload(self):
        self._tempban_check.cancel()

    async def _log_to_channel(self, guild, case):
        data = _load()
        cfg = data['config'].get(str(guild.id), {})
        ch_id = cfg.get('log_channel')
        if not ch_id:
            return
        ch = guild.get_channel(int(ch_id))
        if ch:
            color = ACTION_COLORS.get(case['action'], 0xe74c3c)
            try:
                await ch.send(embed=_case_embed(case, color))
            except Exception as e:
                logger.warning(f"Could not log case: {e}")

    async def _check_thresholds(self, guild, target, data):
        """Auto-action on warn thresholds."""
        gid = str(guild.id)
        cfg = data['config'].get(gid, {})
        thresholds = cfg.get('thresholds', {})
        if not thresholds:
            return
        cases = data['cases'].get(gid, [])
        warn_count = sum(1 for c in cases
                         if c['target_id'] == str(target.id) and c['action'] == 'warn')
        action = thresholds.get(str(warn_count))
        if not action:
            return
        member = guild.get_member(target.id)
        if not member:
            return
        reason = f"Auto-action: {warn_count} warnings reached"
        if action == 'kick':
            await member.kick(reason=reason)
            case = _add_case(data, guild.id, 'kick', guild.me, target, reason)
            await self._log_to_channel(guild, case)
        elif action == 'ban':
            await member.ban(reason=reason)
            case = _add_case(data, guild.id, 'ban', guild.me, target, reason)
            await self._log_to_channel(guild, case)
        elif action == 'timeout':
            await member.timeout(timedelta(hours=1), reason=reason)
            case = _add_case(data, guild.id, 'timeout', guild.me, target, reason)
            await self._log_to_channel(guild, case)

    @tasks.loop(minutes=1)
    async def _tempban_check(self):
        data = _load()
        now = datetime.now(timezone.utc)
        remaining = []
        for tb in data.get('tempbans', []):
            expires = datetime.fromisoformat(tb['expires'])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if now >= expires:
                guild = self.bot.get_guild(int(tb['guild_id']))
                if guild:
                    try:
                        user = await self.bot.fetch_user(int(tb['user_id']))
                        await guild.unban(user, reason="Tempban expired")
                        case = _add_case(data, guild.id, 'unban', guild.me, user, "Tempban expired")
                        await self._log_to_channel(guild, case)
                    except Exception as e:
                        logger.warning(f"Tempban unban failed: {e}")
            else:
                remaining.append(tb)
        data['tempbans'] = remaining
        _save(data)

    @_tempban_check.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    # ── Commands ──────────────────────────────────────────────────────────

    async def warn(self, ctx, member: discord.Member, reason: str = None):
        data = _load()
        case = _add_case(data, ctx.guild.id, 'warn', ctx.author, member, reason)
        await self._log_to_channel(ctx.guild, case)
        await self._check_thresholds(ctx.guild, member, data)
        warns = sum(1 for c in data['cases'].get(str(ctx.guild.id), [])
                    if c['target_id'] == str(member.id) and c['action'] == 'warn')
        embed = _case_embed(case, ACTION_COLORS['warn'])
        embed.add_field(name="Total Warnings", value=str(warns), inline=True)
        try:
            await member.send(f"You were warned in **{ctx.guild.name}**: {reason or 'No reason'}")
        except: pass
        await ctx.send(embed=embed)

    async def warnings(self, ctx, member: discord.Member):
        data = _load()
        cases = [c for c in data['cases'].get(str(ctx.guild.id), [])
                 if c['target_id'] == str(member.id) and c['action'] == 'warn']
        embed = discord.Embed(title=f"Warnings for {member}", color=0xf39c12)
        if not cases:
            embed.description = "No warnings."
        else:
            for c in cases[-10:]:
                embed.add_field(name=f"Case #{c['id']} — {c['timestamp'][:10]}",
                                value=c['reason'], inline=False)
        embed.set_footer(text=f"Total: {len(cases)} warning(s)")
        await ctx.send(embed=embed)

    async def clearwarnings(self, ctx, member: discord.Member):
        data = _load()
        gid = str(ctx.guild.id)
        before = len([c for c in data['cases'].get(gid, [])
                      if c['target_id'] == str(member.id) and c['action'] == 'warn'])
        data['cases'][gid] = [c for c in data['cases'].get(gid, [])
                               if not (c['target_id'] == str(member.id) and c['action'] == 'warn')]
        _save(data)
        await ctx.send(f"Cleared {before} warning(s) for {member.mention}.")

    async def tempban(self, ctx, member: discord.Member,
                      duration: str, reason: str = None):
        units = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}
        try:
            secs = int(duration[:-1]) * units[duration[-1].lower()]
        except:
            return await ctx.send("Invalid duration. Use e.g. 1h, 7d")
        expires = datetime.now(timezone.utc) + timedelta(seconds=secs)
        data = _load()
        case = _add_case(data, ctx.guild.id, 'tempban', ctx.author, member, reason, duration)
        data.setdefault('tempbans', []).append({
            'guild_id': str(ctx.guild.id),
            'user_id': str(member.id),
            'expires': expires.isoformat(),
        })
        _save(data)
        try:
            await member.send(f"You were tempbanned from **{ctx.guild.name}** for {duration}: {reason or 'No reason'}")
        except: pass
        await member.ban(reason=f"Tempban ({duration}): {reason or 'No reason'}")
        await self._log_to_channel(ctx.guild, case)
        await ctx.send(embed=_case_embed(case, ACTION_COLORS['tempban']))

    async def case(self, ctx, case_id: int):
        data = _load()
        cases = data['cases'].get(str(ctx.guild.id), [])
        c = next((x for x in cases if x['id'] == case_id), None)
        if not c:
            return await ctx.send("Case not found.")
        color = ACTION_COLORS.get(c['action'], 0xe74c3c)
        await ctx.send(embed=_case_embed(c, color))

    async def modhistory(self, ctx, member: discord.Member):
        data = _load()
        cases = [c for c in data['cases'].get(str(ctx.guild.id), [])
                 if c['target_id'] == str(member.id)]
        embed = discord.Embed(title=f"Mod History — {member}", color=0x5865f2)
        embed.set_thumbnail(url=member.display_avatar.url)
        if not cases:
            embed.description = "No mod history."
        else:
            for c in cases[-15:]:
                color_dot = {'warn': '🟡', 'kick': '🟠', 'ban': '🔴', 'tempban': '🔴',
                             'timeout': '🟣', 'unban': '🟢', 'note': '🔵'}.get(c['action'], '⚪')
                embed.add_field(
                    name=f"{color_dot} Case #{c['id']} — {c['action'].upper()} ({c['timestamp'][:10]})",
                    value=f"By {c['mod']} • {c['reason']}", inline=False)
        embed.set_footer(text=f"Total cases: {len(cases)}")
        await ctx.send(embed=embed)

    async def note(self, ctx, member: discord.Member, note: str):
        data = _load()
        case = _add_case(data, ctx.guild.id, 'note', ctx.author, member, note)
        await ctx.send(f"Note added as Case #{case['id']}.")

    @app_commands.command(name="modlog-setup", description="📋 Set the mod log channel")
    @app_commands.describe(channel="Channel to send mod logs to")
    @app_commands.checks.has_permissions(administrator=True)
    async def modlog_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = _load()
        data['config'].setdefault(str(interaction.guild.id), {})['log_channel'] = str(channel.id)
        _save(data)
        await interaction.response.send_message(f"✅ Mod log channel set to {channel.mention}.", ephemeral=True)

    @app_commands.command(name="threshold-set", description="⚠️ Set auto-action on warn threshold")
    @app_commands.describe(warnings="Number of warnings to trigger action", action="Action: kick, ban, timeout")
    @app_commands.checks.has_permissions(administrator=True)
    async def threshold_set(self, interaction: discord.Interaction, warnings: int, action: str):
        data = _load()
        cfg = data['config'].setdefault(str(interaction.guild.id), {})
        cfg.setdefault('thresholds', {})[str(warnings)] = action
        _save(data)
        await interaction.response.send_message(f"✅ At **{warnings}** warnings → auto **{action}**.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ModLog(bot))
