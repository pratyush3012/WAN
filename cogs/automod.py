"""
AutoMod — spam, caps, links, mentions, emoji flood, invite filter, slowmode automation
Persistent config stored in automod.json
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json, os, re, logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord_bot.automod')
AUTOMOD_FILE = 'automod.json'

DEFAULT_CFG = {
    'spam_enabled': True,
    'spam_threshold': 5,
    'spam_window': 5,
    'link_filter_enabled': False,
    'invite_filter_enabled': False,
    'bad_words_enabled': False,
    'bad_words': [],
    'caps_filter_enabled': False,
    'caps_threshold': 70,
    'mention_spam_enabled': True,
    'mention_threshold': 5,
    'emoji_flood_enabled': False,
    'emoji_threshold': 10,
    'raid_protection_enabled': True,
    'raid_threshold': 10,
    'raid_window': 10,
    'slowmode_auto': False,
    'slowmode_threshold': 10,
    'slowmode_window': 5,
    'slowmode_seconds': 5,
    'log_channel': None,
    'ignored_roles': [],
    'ignored_channels': [],
}


def _load():
    if os.path.exists(AUTOMOD_FILE):
        try:
            with open(AUTOMOD_FILE) as f: return json.load(f)
        except: pass
    return {}


def _save(d):
    with open(AUTOMOD_FILE, 'w') as f: json.dump(d, f, indent=2)


def _cfg(guild_id):
    data = _load()
    return {**DEFAULT_CFG, **data.get(str(guild_id), {})}


def _save_cfg(guild_id, cfg):
    data = _load()
    data[str(guild_id)] = cfg
    _save(data)


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._msg_history = defaultdict(list)   # user_id -> [datetime]
        self._join_history = defaultdict(list)  # guild_id -> [datetime]
        self._ch_history = defaultdict(list)    # channel_id -> [datetime]
        self._slowmode_active = set()           # channel_ids with auto-slowmode

    def _is_ignored(self, message: discord.Message, cfg: dict) -> bool:
        if message.author.guild_permissions.administrator:
            return True
        if str(message.channel.id) in cfg.get('ignored_channels', []):
            return True
        user_role_ids = [str(r.id) for r in message.author.roles]
        if any(r in cfg.get('ignored_roles', []) for r in user_role_ids):
            return True
        return False

    async def _log(self, guild, action: str, user: discord.Member, reason: str, cfg: dict):
        ch_id = cfg.get('log_channel')
        if not ch_id:
            return
        ch = guild.get_channel(int(ch_id))
        if not ch:
            return
        embed = discord.Embed(
            title=f'AutoMod — {action}',
            description=f'**User:** {user.mention} (`{user}`)\n**Reason:** {reason}',
            color=0xe74c3c,
            timestamp=datetime.now(timezone.utc)
        )
        try:
            await ch.send(embed=embed)
        except: pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        cfg = _cfg(message.guild.id)
        if self._is_ignored(message, cfg):
            return

        if cfg['spam_enabled'] and await self._check_spam(message, cfg): return
        if cfg['link_filter_enabled'] and await self._check_links(message, cfg): return
        if cfg['invite_filter_enabled'] and await self._check_invites(message, cfg): return
        if cfg['bad_words_enabled'] and await self._check_bad_words(message, cfg): return
        if cfg['caps_filter_enabled'] and await self._check_caps(message, cfg): return
        if cfg['mention_spam_enabled'] and await self._check_mentions(message, cfg): return
        if cfg['emoji_flood_enabled'] and await self._check_emoji(message, cfg): return
        if cfg['slowmode_auto']: await self._check_slowmode(message, cfg)

    async def _check_spam(self, message, cfg):
        uid = message.author.id
        now = datetime.now(timezone.utc)
        self._msg_history[uid].append(now)
        self._msg_history[uid] = [t for t in self._msg_history[uid]
                                   if (now - t).total_seconds() < cfg['spam_window']]
        if len(self._msg_history[uid]) > cfg['spam_threshold']:
            try:
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} Slow down! (spam)', delete_after=5)
                await message.author.timeout(timedelta(minutes=1), reason='AutoMod: spam')
                await self._log(message.guild, 'Spam', message.author, f'{len(self._msg_history[uid])} msgs/{cfg["spam_window"]}s', cfg)
            except: pass
            return True
        return False

    async def _check_links(self, message, cfg):
        if re.search(r'https?://', message.content):
            try:
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} Links are not allowed here.', delete_after=5)
                await self._log(message.guild, 'Link Blocked', message.author, message.content[:100], cfg)
            except: pass
            return True
        return False

    async def _check_invites(self, message, cfg):
        if re.search(r'discord\.gg/|discord\.com/invite/', message.content, re.IGNORECASE):
            try:
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} Discord invites are not allowed.', delete_after=5)
                await self._log(message.guild, 'Invite Blocked', message.author, message.content[:100], cfg)
            except: pass
            return True
        return False

    async def _check_bad_words(self, message, cfg):
        content_lower = message.content.lower()
        for word in cfg.get('bad_words', []):
            if word.lower() in content_lower:
                try:
                    await message.delete()
                    await message.channel.send(f'⚠️ {message.author.mention} Watch your language!', delete_after=5)
                    await self._log(message.guild, 'Bad Word', message.author, f'Matched: {word}', cfg)
                except: pass
                return True
        return False

    async def _check_caps(self, message, cfg):
        text = message.content
        if len(text) < 10:
            return False
        caps = sum(1 for c in text if c.isupper())
        if (caps / len(text)) * 100 > cfg['caps_threshold']:
            try:
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} Excessive caps!', delete_after=5)
                await self._log(message.guild, 'Caps Filter', message.author, f'{int(caps/len(text)*100)}% caps', cfg)
            except: pass
            return True
        return False

    async def _check_mentions(self, message, cfg):
        if len(message.mentions) + len(message.role_mentions) > cfg['mention_threshold']:
            try:
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} Too many mentions!', delete_after=5)
                await message.author.timeout(timedelta(minutes=5), reason='AutoMod: mention spam')
                await self._log(message.guild, 'Mention Spam', message.author, f'{len(message.mentions)} mentions', cfg)
            except: pass
            return True
        return False

    async def _check_emoji(self, message, cfg):
        emoji_count = len(re.findall(r'<a?:\w+:\d+>|[\U0001F300-\U0001FAFF]', message.content))
        if emoji_count > cfg['emoji_threshold']:
            try:
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} Too many emojis!', delete_after=5)
                await self._log(message.guild, 'Emoji Flood', message.author, f'{emoji_count} emojis', cfg)
            except: pass
            return True
        return False

    async def _check_slowmode(self, message, cfg):
        ch_id = message.channel.id
        now = datetime.now(timezone.utc)
        self._ch_history[ch_id].append(now)
        self._ch_history[ch_id] = [t for t in self._ch_history[ch_id]
                                    if (now - t).total_seconds() < cfg['slowmode_window']]
        if len(self._ch_history[ch_id]) > cfg['slowmode_threshold']:
            if ch_id not in self._slowmode_active:
                self._slowmode_active.add(ch_id)
                try:
                    await message.channel.edit(slowmode_delay=cfg['slowmode_seconds'],
                                               reason='AutoMod: high message rate')
                    await message.channel.send(
                        f'🐢 Slowmode enabled ({cfg["slowmode_seconds"]}s) due to high activity.',
                        delete_after=30)
                    # Auto-remove after 2 minutes
                    async def _remove_slowmode():
                        await __import__('asyncio').sleep(120)
                        try:
                            await message.channel.edit(slowmode_delay=0, reason='AutoMod: slowmode expired')
                            self._slowmode_active.discard(ch_id)
                        except: pass
                    self.bot.loop.create_task(_remove_slowmode())
                except: pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = _cfg(member.guild.id)
        if not cfg['raid_protection_enabled']:
            return
        now = datetime.now(timezone.utc)
        gid = member.guild.id
        self._join_history[gid].append(now)
        self._join_history[gid] = [t for t in self._join_history[gid]
                                    if (now - t).total_seconds() < cfg['raid_window']]
        if len(self._join_history[gid]) >= cfg['raid_threshold']:
            ch_id = cfg.get('log_channel')
            if ch_id:
                ch = member.guild.get_channel(int(ch_id))
                if ch:
                    try:
                        await ch.send(
                            f'🚨 **RAID ALERT** — {cfg["raid_threshold"]}+ joins in {cfg["raid_window"]}s! '
                            f'Use `/antiraid-unlock` to lift lockdown after securing the server.')
                    except: pass

    # ── Commands ──────────────────────────────────────────────────────────

    @app_commands.command(name='automod-config', description='View automod configuration')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config(self, interaction: discord.Interaction):
        cfg = _cfg(interaction.guild.id)
        embed = discord.Embed(title='AutoMod Configuration', color=0x5865f2)
        checks = [
            ('Spam', cfg['spam_enabled'], f'{cfg["spam_threshold"]} msgs/{cfg["spam_window"]}s'),
            ('Link Filter', cfg['link_filter_enabled'], ''),
            ('Invite Filter', cfg['invite_filter_enabled'], ''),
            ('Bad Words', cfg['bad_words_enabled'], f'{len(cfg.get("bad_words", []))} words'),
            ('Caps Filter', cfg['caps_filter_enabled'], f'>{cfg["caps_threshold"]}%'),
            ('Mention Spam', cfg['mention_spam_enabled'], f'>{cfg["mention_threshold"]} mentions'),
            ('Emoji Flood', cfg['emoji_flood_enabled'], f'>{cfg["emoji_threshold"]} emojis'),
            ('Raid Protection', cfg['raid_protection_enabled'], f'{cfg["raid_threshold"]} joins/{cfg["raid_window"]}s'),
            ('Auto Slowmode', cfg['slowmode_auto'], f'>{cfg["slowmode_threshold"]} msgs/{cfg["slowmode_window"]}s → {cfg["slowmode_seconds"]}s'),
        ]
        for name, enabled, detail in checks:
            val = ('✅ ' if enabled else '❌ ') + (detail if detail else '')
            embed.add_field(name=name, value=val, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='automod-toggle', description='Toggle an automod feature')
    @app_commands.choices(feature=[
        app_commands.Choice(name=n, value=v) for n, v in [
            ('Spam', 'spam_enabled'), ('Link Filter', 'link_filter_enabled'),
            ('Invite Filter', 'invite_filter_enabled'), ('Bad Words', 'bad_words_enabled'),
            ('Caps Filter', 'caps_filter_enabled'), ('Mention Spam', 'mention_spam_enabled'),
            ('Emoji Flood', 'emoji_flood_enabled'), ('Raid Protection', 'raid_protection_enabled'),
            ('Auto Slowmode', 'slowmode_auto'),
        ]
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle(self, interaction: discord.Interaction, feature: app_commands.Choice[str]):
        cfg = _cfg(interaction.guild.id)
        cfg[feature.value] = not cfg[feature.value]
        _save_cfg(interaction.guild.id, cfg)
        state = 'enabled' if cfg[feature.value] else 'disabled'
        await interaction.response.send_message(f'{feature.name} {state}.', ephemeral=True)

    @app_commands.command(name='automod-badword-add', description='Add a word to the filter')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def badword_add(self, interaction: discord.Interaction, word: str):
        cfg = _cfg(interaction.guild.id)
        words = cfg.setdefault('bad_words', [])
        if word.lower() not in words:
            words.append(word.lower())
        _save_cfg(interaction.guild.id, cfg)
        await interaction.response.send_message(f'Added `{word}` to filter.', ephemeral=True)

    @app_commands.command(name='automod-badword-remove', description='Remove a word from the filter')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def badword_remove(self, interaction: discord.Interaction, word: str):
        cfg = _cfg(interaction.guild.id)
        words = cfg.get('bad_words', [])
        if word.lower() in words:
            words.remove(word.lower())
            _save_cfg(interaction.guild.id, cfg)
            await interaction.response.send_message(f'Removed `{word}` from filter.', ephemeral=True)
        else:
            await interaction.response.send_message('Word not in filter.', ephemeral=True)

    @app_commands.command(name='automod-set-log', description='Set the automod log channel')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        cfg = _cfg(interaction.guild.id)
        cfg['log_channel'] = str(channel.id)
        _save_cfg(interaction.guild.id, cfg)
        await interaction.response.send_message(f'AutoMod log channel set to {channel.mention}.', ephemeral=True)

    @app_commands.command(name='automod-ignore-channel', description='Ignore a channel from automod')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ignore_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        cfg = _cfg(interaction.guild.id)
        ignored = cfg.setdefault('ignored_channels', [])
        cid = str(channel.id)
        if cid in ignored:
            ignored.remove(cid)
            msg = f'Removed {channel.mention} from ignored channels.'
        else:
            ignored.append(cid)
            msg = f'Added {channel.mention} to ignored channels.'
        _save_cfg(interaction.guild.id, cfg)
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name='automod-ignore-role', description='Ignore a role from automod')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ignore_role(self, interaction: discord.Interaction, role: discord.Role):
        cfg = _cfg(interaction.guild.id)
        ignored = cfg.setdefault('ignored_roles', [])
        rid = str(role.id)
        if rid in ignored:
            ignored.remove(rid)
            msg = f'Removed {role.mention} from ignored roles.'
        else:
            ignored.append(rid)
            msg = f'Added {role.mention} to ignored roles.'
        _save_cfg(interaction.guild.id, cfg)
        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
