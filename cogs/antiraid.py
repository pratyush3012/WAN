"""
Anti-Raid — mass-join detection, auto-lockdown, alt account detection (Wick USP)
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict

logger = logging.getLogger('discord_bot.antiraid')
RAID_FILE = 'antiraid.json'


def _load():
    if os.path.exists(RAID_FILE):
        try:
            with open(RAID_FILE) as f: return json.load(f)
        except: pass
    return {}


def _save(d):
    with open(RAID_FILE, 'w') as f: json.dump(d, f, indent=2)


DEFAULT_CFG = {
    'enabled': True,
    'join_threshold': 8,       # joins in window to trigger
    'join_window': 10,         # seconds
    'action': 'kick',          # kick | ban | timeout
    'alt_min_age_days': 7,     # accounts newer than this = alt
    'alt_action': 'kick',      # kick | ban | none
    'log_channel': None,
    'lockdown_active': False,
}


class AntiRaid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._join_history = defaultdict(list)  # guild_id -> [datetime]

    def _cfg(self, guild_id):
        data = _load()
        cfg = data.get(str(guild_id), {})
        return {**DEFAULT_CFG, **cfg}

    def _save_cfg(self, guild_id, cfg):
        data = _load()
        data[str(guild_id)] = cfg
        _save(data)

    async def _log(self, guild, msg, color=0xe74c3c):
        cfg = self._cfg(guild.id)
        ch_id = cfg.get('log_channel')
        if not ch_id:
            return
        ch = guild.get_channel(int(ch_id))
        if ch:
            embed = discord.Embed(description=msg, color=color, timestamp=datetime.now(timezone.utc))
            embed.set_author(name='Anti-Raid')
            try:
                await ch.send(embed=embed)
            except: pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = self._cfg(member.guild.id)
        if not cfg['enabled']:
            return

        now = datetime.now(timezone.utc)
        gid = member.guild.id

        # Alt detection
        account_age = (now - member.created_at).days
        if account_age < cfg['alt_min_age_days'] and cfg['alt_action'] != 'none':
            try:
                reason = f'Alt account detected (account age: {account_age}d)'
                if cfg['alt_action'] == 'kick':
                    await member.kick(reason=reason)
                elif cfg['alt_action'] == 'ban':
                    await member.ban(reason=reason)
                await self._log(member.guild, f'🔍 Alt detected: {member} (age {account_age}d) → {cfg["alt_action"]}')
            except Exception as e:
                logger.warning(f'Alt action failed: {e}')
            return

        # Raid detection
        self._join_history[gid].append(now)
        self._join_history[gid] = [
            t for t in self._join_history[gid]
            if (now - t).total_seconds() < cfg['join_window']
        ]

        if len(self._join_history[gid]) >= cfg['join_threshold']:
            await self._trigger_raid(member.guild, cfg)

    async def _trigger_raid(self, guild: discord.Guild, cfg: dict):
        if cfg.get('lockdown_active'):
            return  # already locked
        cfg['lockdown_active'] = True
        self._save_cfg(guild.id, cfg)

        await self._log(guild, f'🚨 **RAID DETECTED** — {cfg["join_threshold"]}+ joins in {cfg["join_window"]}s. Auto-lockdown activated.')

        # Lock all text channels
        for ch in guild.text_channels:
            try:
                overwrite = ch.overwrites_for(guild.default_role)
                overwrite.send_messages = False
                await ch.set_permissions(guild.default_role, overwrite=overwrite, reason='Anti-raid lockdown')
            except: pass

        # Kick/ban recent joiners
        now = datetime.now(timezone.utc)
        for member in guild.members:
            if member.bot:
                continue
            joined = member.joined_at
            if joined and (now - joined).total_seconds() < cfg['join_window'] * 2:
                try:
                    if cfg['action'] == 'kick':
                        await member.kick(reason='Anti-raid: mass join')
                    elif cfg['action'] == 'ban':
                        await member.ban(reason='Anti-raid: mass join')
                    elif cfg['action'] == 'timeout':
                        await member.timeout(timedelta(hours=1), reason='Anti-raid: mass join')
                except: pass

    @commands.command(name="antiraid-config")
    async def config(self, ctx,
                     join_threshold: int = None,
                     join_window: int = None,
                     action: app_commands.Choice[str] = None,
                     alt_min_age_days: int = None,
                     alt_action: app_commands.Choice[str] = None,
                     log_channel: discord.TextChannel = None):
        cfg = self._cfg(ctx.guild.id)
        if join_threshold is not None: cfg['join_threshold'] = join_threshold
        if join_window is not None: cfg['join_window'] = join_window
        if action: cfg['action'] = action.value
        if alt_min_age_days is not None: cfg['alt_min_age_days'] = alt_min_age_days
        if alt_action: cfg['alt_action'] = alt_action.value
        if log_channel: cfg['log_channel'] = str(log_channel.id)
        self._save_cfg(ctx.guild.id, cfg)
        await ctx.send('Anti-raid config updated.')

    @commands.command(name="antiraid-toggle")
    async def toggle(self, ctx):
        cfg = self._cfg(ctx.guild.id)
        cfg['enabled'] = not cfg['enabled']
        self._save_cfg(ctx.guild.id, cfg)
        state = 'enabled' if cfg['enabled'] else 'disabled'
        await ctx.send(f'Anti-raid {state}.')

    @commands.command(name="antiraid-unlock")
    async def unlock(self, ctx):
        await ctx.defer()
        cfg = self._cfg(ctx.guild.id)
        cfg['lockdown_active'] = False
        self._save_cfg(ctx.guild.id, cfg)
        for ch in ctx.guild.text_channels:
            try:
                overwrite = ch.overwrites_for(ctx.guild.default_role)
                overwrite.send_messages = None
                await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason='Raid lockdown lifted')
            except: pass
        await ctx.send('Lockdown lifted. All channels unlocked.')

    @commands.command(name="antiraid-status")
    async def status(self, ctx):
        cfg = self._cfg(ctx.guild.id)
        embed = discord.Embed(title='Anti-Raid Status', color=0xe74c3c if cfg['enabled'] else 0x95a5a6)
        embed.add_field(name='Status', value='✅ Enabled' if cfg['enabled'] else '❌ Disabled', inline=True)
        embed.add_field(name='Lockdown', value='🔒 Active' if cfg.get('lockdown_active') else '🔓 Inactive', inline=True)
        embed.add_field(name='Trigger', value=f'{cfg["join_threshold"]} joins / {cfg["join_window"]}s', inline=True)
        embed.add_field(name='Raider Action', value=cfg['action'], inline=True)
        embed.add_field(name='Alt Detection', value=f'< {cfg["alt_min_age_days"]}d → {cfg["alt_action"]}', inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AntiRaid(bot))
