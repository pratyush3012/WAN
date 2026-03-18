"""
ChannelGuard — enforces channel purpose automatically.
Analyzes channel name + topic to determine what's allowed.
Off-topic messages are deleted with a polite notice.
Admins can also manually set rules per channel.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, re, logging
from datetime import datetime, timezone

logger = logging.getLogger('discord_bot.channelguard')
GUARD_FILE = 'channelguard.json'

# ── Channel purpose profiles ──────────────────────────────────────────────────
# Each profile defines:
#   keywords  — channel name/topic keywords that trigger this profile
#   allowed   — regex patterns that are ALLOWED (if set, everything else is deleted)
#   blocked   — regex patterns that are always blocked regardless
#   hint      — message shown to user when their message is deleted

PROFILES = {
    'voting': {
        'keywords': ['vote', 'voting', 'poll', 'election', 'ballot'],
        'allowed': [
            r'^[✅❌👍👎🔴🟢🟡⬆️⬇️1️⃣2️⃣3️⃣4️⃣5️⃣]',   # emoji votes
            r'^\d+$',                                          # number votes
            r'^(yes|no|yep|nope|agree|disagree|for|against)$',
        ],
        'blocked': [],
        'hint': 'This channel is for voting only. Use reactions or vote with ✅/❌.',
        'allow_bots': True,
        'allow_images': False,
    },
    'announcements': {
        'keywords': ['announcement', 'announcements', 'news', 'updates', 'update'],
        'allowed': [],   # empty = only staff can post (enforced via Discord perms, we just delete non-staff)
        'blocked': [],
        'hint': 'This channel is for announcements only. Only staff can post here.',
        'allow_bots': True,
        'allow_images': True,
        'staff_only': True,
    },
    'rules': {
        'keywords': ['rules', 'rule', 'guidelines', 'tos', 'terms'],
        'allowed': [],
        'blocked': [],
        'hint': 'This channel is read-only. Please follow the rules!',
        'allow_bots': True,
        'allow_images': True,
        'staff_only': True,
    },
    'media': {
        'keywords': ['media', 'memes', 'meme', 'images', 'photos', 'pics', 'art', 'showcase', 'gallery'],
        'allowed': [],
        'blocked': [r'^[a-zA-Z\s]{10,}$'],   # pure text walls with no media
        'hint': 'This channel is for media/images only. Please attach an image or video.',
        'allow_bots': True,
        'allow_images': True,
        'require_attachment': True,
    },
    'introductions': {
        'keywords': ['intro', 'introduction', 'introductions', 'introduce', 'welcome-yourself'],
        'allowed': [],
        'blocked': [],
        'hint': 'This channel is for introductions. Please introduce yourself!',
        'allow_bots': True,
        'allow_images': True,
        'one_per_user': True,   # only one message per user
    },
    'bot_commands': {
        'keywords': ['bot', 'bots', 'commands', 'cmd', 'bot-commands', 'bot-spam', 'botspam'],
        'allowed': [r'^[/!?.]'],   # slash/prefix commands
        'blocked': [],
        'hint': 'This channel is for bot commands only. Please use bot commands here.',
        'allow_bots': True,
        'allow_images': False,
        'bot_commands_only': True,
    },
    'music': {
        'keywords': ['music', 'songs', 'playlist', 'jukebox', 'radio'],
        'allowed': [r'^[/!?.]'],
        'blocked': [],
        'hint': 'This channel is for music commands only.',
        'allow_bots': True,
        'allow_images': False,
        'bot_commands_only': True,
    },
    'lfg': {
        'keywords': ['lfg', 'looking-for-group', 'looking_for_group', 'party', 'recruitment'],
        'allowed': [],
        'blocked': [],
        'hint': 'This channel is for LFG posts. Keep it relevant to finding groups.',
        'allow_bots': True,
        'allow_images': True,
    },
    'logs': {
        'keywords': ['log', 'logs', 'audit', 'mod-log', 'modlog', 'audit-log'],
        'allowed': [],
        'blocked': [],
        'hint': 'This is a log channel. No messages allowed.',
        'allow_bots': True,
        'allow_images': False,
        'staff_only': True,
    },
}


def _detect_profile(channel: discord.TextChannel) -> str | None:
    """Auto-detect channel purpose from name and topic."""
    text = (channel.name + ' ' + (channel.topic or '')).lower()
    text = re.sub(r'[-_]', ' ', text)
    for profile_name, profile in PROFILES.items():
        for kw in profile['keywords']:
            if kw in text:
                return profile_name
    return None


def _load():
    if os.path.exists(GUARD_FILE):
        try:
            with open(GUARD_FILE) as f: return json.load(f)
        except: pass
    return {}


def _save(d):
    with open(GUARD_FILE, 'w') as f: json.dump(d, f, indent=2)


def _is_staff(member: discord.Member) -> bool:
    return (member.guild_permissions.manage_messages or
            member.guild_permissions.manage_guild or
            member.guild_permissions.administrator)


class ChannelGuard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._intro_seen = {}  # (guild_id, channel_id, user_id) -> True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.id == self.bot.user.id:
            return

        data = _load()
        gid = str(message.guild.id)
        cid = str(message.channel.id)

        # Check if this guild has channelguard enabled
        guild_cfg = data.get(gid, {})
        if not guild_cfg.get('enabled', False):
            return

        # Get channel rule — manual override takes priority, then auto-detect
        channel_rules = guild_cfg.get('channels', {})
        rule = channel_rules.get(cid)

        if rule is None:
            # Auto-detect if auto_detect is on
            if not guild_cfg.get('auto_detect', True):
                return
            profile_name = _detect_profile(message.channel)
            if not profile_name:
                return
            rule = {'profile': profile_name, 'auto': True}

        profile_name = rule.get('profile')
        profile = PROFILES.get(profile_name, {})
        if not profile:
            return

        # Staff always allowed (unless explicitly blocked)
        if _is_staff(message.author):
            return

        # Bots allowed?
        if message.author.bot and profile.get('allow_bots', True):
            return

        reason = None

        # Staff-only channel
        if profile.get('staff_only'):
            reason = profile['hint']

        # Require attachment (media channels)
        elif profile.get('require_attachment') and not message.attachments:
            reason = profile['hint']

        # Bot commands only
        elif profile.get('bot_commands_only'):
            if not re.match(r'^[/!?.]', message.content):
                reason = profile['hint']

        # One message per user (introductions)
        elif profile.get('one_per_user'):
            key = (message.guild.id, message.channel.id, message.author.id)
            if key in self._intro_seen:
                reason = 'You already posted an introduction here!'
            else:
                self._intro_seen[key] = True

        # Allowed patterns whitelist
        elif profile.get('allowed'):
            matched = any(re.match(p, message.content.strip(), re.IGNORECASE)
                          for p in profile['allowed'])
            if not matched:
                reason = profile['hint']

        # Blocked patterns blacklist
        elif profile.get('blocked'):
            for p in profile['blocked']:
                if re.search(p, message.content, re.IGNORECASE):
                    reason = profile['hint']
                    break

        if reason:
            try:
                await message.delete()
            except: pass
            try:
                notice = await message.channel.send(
                    f'🚫 {message.author.mention} — {reason}',
                    delete_after=8
                )
            except: pass
            # Log it
            log_ch_id = guild_cfg.get('log_channel')
            if log_ch_id:
                log_ch = message.guild.get_channel(int(log_ch_id))
                if log_ch:
                    embed = discord.Embed(
                        title='ChannelGuard — Off-topic deleted',
                        color=0xf59e0b,
                        timestamp=datetime.now(timezone.utc)
                    )
                    embed.add_field(name='User', value=f'{message.author} (`{message.author.id}`)', inline=True)
                    embed.add_field(name='Channel', value=message.channel.mention, inline=True)
                    embed.add_field(name='Profile', value=profile_name, inline=True)
                    embed.add_field(name='Message', value=message.content[:300] or '[no text]', inline=False)
                    try:
                        await log_ch.send(embed=embed)
                    except: pass

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name='channelguard-enable', description='Enable ChannelGuard for this server')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def enable(self, interaction: discord.Interaction):
        data = _load()
        g = data.setdefault(str(interaction.guild.id), {})
        g['enabled'] = True
        g.setdefault('auto_detect', True)
        _save(data)
        await interaction.response.send_message(
            '✅ ChannelGuard enabled. Auto-detection is **on** — channels are analyzed by name/topic automatically.\n'
            'Use `/channelguard-set` to manually assign profiles to specific channels.',
            ephemeral=True)

    @app_commands.command(name='channelguard-disable', description='Disable ChannelGuard for this server')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def disable(self, interaction: discord.Interaction):
        data = _load()
        data.setdefault(str(interaction.guild.id), {})['enabled'] = False
        _save(data)
        await interaction.response.send_message('ChannelGuard disabled.', ephemeral=True)

    @app_commands.command(name='channelguard-set', description='Manually assign a purpose profile to a channel')
    @app_commands.describe(channel='Channel to configure', profile='Purpose profile')
    @app_commands.choices(profile=[
        app_commands.Choice(name=k, value=k) for k in PROFILES
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_profile(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          profile: app_commands.Choice[str]):
        data = _load()
        g = data.setdefault(str(interaction.guild.id), {'enabled': True, 'auto_detect': True})
        g.setdefault('channels', {})[str(channel.id)] = {'profile': profile.value}
        _save(data)
        p = PROFILES[profile.value]
        await interaction.response.send_message(
            f'Set {channel.mention} to profile **{profile.value}**.\n> {p["hint"]}',
            ephemeral=True)

    @app_commands.command(name='channelguard-remove', description='Remove channel guard from a channel')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_profile(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = _load()
        g = data.get(str(interaction.guild.id), {})
        channels = g.get('channels', {})
        if str(channel.id) in channels:
            del channels[str(channel.id)]
            _save(data)
            await interaction.response.send_message(f'Removed guard from {channel.mention}.', ephemeral=True)
        else:
            await interaction.response.send_message('No manual rule set for that channel.', ephemeral=True)

    @app_commands.command(name='channelguard-setlog', description='Set log channel for ChannelGuard')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = _load()
        data.setdefault(str(interaction.guild.id), {})['log_channel'] = str(channel.id)
        _save(data)
        await interaction.response.send_message(f'ChannelGuard log channel set to {channel.mention}.', ephemeral=True)

    @app_commands.command(name='channelguard-status', description='View ChannelGuard configuration')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status(self, interaction: discord.Interaction):
        data = _load()
        g = data.get(str(interaction.guild.id), {})
        embed = discord.Embed(title='ChannelGuard Status', color=0xf59e0b)
        embed.add_field(name='Status', value='✅ Enabled' if g.get('enabled') else '❌ Disabled', inline=True)
        embed.add_field(name='Auto-detect', value='✅ On' if g.get('auto_detect', True) else '❌ Off', inline=True)
        log_ch = interaction.guild.get_channel(int(g['log_channel'])) if g.get('log_channel') else None
        embed.add_field(name='Log Channel', value=log_ch.mention if log_ch else 'Not set', inline=True)

        manual = g.get('channels', {})
        if manual:
            lines = []
            for ch_id, rule in manual.items():
                ch = interaction.guild.get_channel(int(ch_id))
                lines.append(f'{ch.mention if ch else ch_id} → `{rule["profile"]}`')
            embed.add_field(name='Manual Rules', value='\n'.join(lines[:15]), inline=False)

        # Show auto-detected channels
        auto_lines = []
        for ch in interaction.guild.text_channels:
            if str(ch.id) not in manual:
                p = _detect_profile(ch)
                if p:
                    auto_lines.append(f'{ch.mention} → `{p}` (auto)')
        if auto_lines:
            embed.add_field(name='Auto-detected', value='\n'.join(auto_lines[:15]), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='channelguard-scan', description='Scan all channels and show detected profiles')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def scan(self, interaction: discord.Interaction):
        """Preview what ChannelGuard would auto-detect without enabling it."""
        lines = []
        for ch in interaction.guild.text_channels:
            p = _detect_profile(ch)
            if p:
                profile = PROFILES[p]
                lines.append(f'{ch.mention} → **{p}**\n  _{profile["hint"]}_')
        if not lines:
            return await interaction.response.send_message(
                'No channels matched any profile. Use `/channelguard-set` to manually assign profiles.',
                ephemeral=True)
        embed = discord.Embed(
            title='ChannelGuard Scan Results',
            description='\n\n'.join(lines[:20]),
            color=0xf59e0b
        )
        embed.set_footer(text='Use /channelguard-enable to activate auto-detection')
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ChannelGuard(bot))
