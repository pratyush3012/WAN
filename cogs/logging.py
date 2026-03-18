"""
Logging — comprehensive server event logging
Covers: messages, voice, members, roles, channels, invites, threads, nicknames
Config stored in logging_config.json — each event type can have its own channel.
"""
import discord
from discord.ext import commands, tasks
import json, os, logging
from datetime import datetime, timezone

logger = logging.getLogger('discord_bot.logging')
LOG_CFG_FILE = 'logging_config.json'

# Event categories
CATEGORIES = [
    'message_delete', 'message_edit', 'message_bulk_delete',
    'member_join', 'member_leave', 'member_ban', 'member_unban',
    'member_role_update', 'member_nickname',
    'voice_join', 'voice_leave', 'voice_move',
    'channel_create', 'channel_delete', 'channel_update',
    'role_create', 'role_delete', 'role_update',
    'invite_create', 'invite_delete',
    'thread_create', 'thread_delete',
    'guild_update',
]


def _load():
    if os.path.exists(LOG_CFG_FILE):
        try:
            with open(LOG_CFG_FILE) as f: return json.load(f)
        except: pass
    return {}

def _save(d):
    with open(LOG_CFG_FILE, 'w') as f: json.dump(d, f, indent=2)

def _cfg(guild_id):
    return _load().get(str(guild_id), {})


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._invite_cache = {}  # guild_id -> {code: uses}
        self._cache_invites.start()

    def cog_unload(self):
        self._cache_invites.cancel()

    @tasks.loop(minutes=10)
    async def _cache_invites(self):
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self._invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
            except: pass

    @_cache_invites.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    async def _log(self, guild_id: int, category: str, embed: discord.Embed):
        cfg = _cfg(guild_id)
        # Try category-specific channel first, then fallback to default
        ch_id = cfg.get(f'ch_{category}') or cfg.get('ch_default')
        if not ch_id:
            return
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        ch = guild.get_channel(int(ch_id))
        if ch:
            try:
                await ch.send(embed=embed)
            except: pass

    def _ts(self):
        return datetime.now(timezone.utc)

    # ── Message Events ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        embed = discord.Embed(title='🗑️ Message Deleted', color=0xe74c3c, timestamp=self._ts())
        embed.add_field(name='Author', value=f'{message.author.mention} (`{message.author.id}`)', inline=True)
        embed.add_field(name='Channel', value=message.channel.mention, inline=True)
        if message.content:
            embed.add_field(name='Content', value=message.content[:1000], inline=False)
        if message.attachments:
            embed.add_field(name='Attachments', value='\n'.join(a.url for a in message.attachments), inline=False)
        embed.set_footer(text=f'Message ID: {message.id}')
        await self._log(message.guild.id, 'message_delete', embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        embed = discord.Embed(title='✏️ Message Edited', color=0xf59e0b, timestamp=self._ts())
        embed.add_field(name='Author', value=f'{before.author.mention} (`{before.author.id}`)', inline=True)
        embed.add_field(name='Channel', value=before.channel.mention, inline=True)
        embed.add_field(name='Before', value=before.content[:500] or '*(empty)*', inline=False)
        embed.add_field(name='After', value=after.content[:500] or '*(empty)*', inline=False)
        embed.add_field(name='Jump', value=f'[Click here]({after.jump_url})', inline=True)
        embed.set_footer(text=f'Message ID: {before.id}')
        await self._log(before.guild.id, 'message_edit', embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages or not messages[0].guild:
            return
        guild = messages[0].guild
        embed = discord.Embed(title='🗑️ Bulk Message Delete', color=0xe74c3c, timestamp=self._ts())
        embed.add_field(name='Count', value=str(len(messages)), inline=True)
        embed.add_field(name='Channel', value=messages[0].channel.mention, inline=True)
        await self._log(guild.id, 'message_bulk_delete', embed)

    # ── Member Events ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = discord.Embed(title='📥 Member Joined', color=0x2ecc71, timestamp=self._ts())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name='Member', value=f'{member.mention} (`{member.id}`)', inline=True)
        embed.add_field(name='Account Age', value=f'<t:{int(member.created_at.timestamp())}:R>', inline=True)
        embed.add_field(name='Total Members', value=str(member.guild.member_count), inline=True)

        # Invite tracking
        try:
            new_invites = await member.guild.invites()
            old_cache = self._invite_cache.get(member.guild.id, {})
            for inv in new_invites:
                if old_cache.get(inv.code, 0) < inv.uses:
                    embed.add_field(name='Invited By', value=f'{inv.inviter.mention if inv.inviter else "Unknown"} (code: `{inv.code}`)', inline=False)
                    break
            self._invite_cache[member.guild.id] = {i.code: i.uses for i in new_invites}
        except: pass

        await self._log(member.guild.id, 'member_join', embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = discord.Embed(title='📤 Member Left', color=0xe74c3c, timestamp=self._ts())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name='Member', value=f'{member} (`{member.id}`)', inline=True)
        embed.add_field(name='Joined', value=f'<t:{int(member.joined_at.timestamp())}:R>' if member.joined_at else 'Unknown', inline=True)
        roles = [r.mention for r in member.roles if r.name != '@everyone']
        if roles:
            embed.add_field(name='Roles', value=' '.join(roles[:10]), inline=False)
        await self._log(member.guild.id, 'member_leave', embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(title='🔨 Member Banned', color=0xe74c3c, timestamp=self._ts())
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name='User', value=f'{user} (`{user.id}`)', inline=True)
        await self._log(guild.id, 'member_ban', embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(title='✅ Member Unbanned', color=0x2ecc71, timestamp=self._ts())
        embed.add_field(name='User', value=f'{user} (`{user.id}`)', inline=True)
        await self._log(guild.id, 'member_unban', embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Role changes
        if before.roles != after.roles:
            added = [r for r in after.roles if r not in before.roles]
            removed = [r for r in before.roles if r not in after.roles]
            if added or removed:
                embed = discord.Embed(title='🎭 Roles Updated', color=0x3498db, timestamp=self._ts())
                embed.add_field(name='Member', value=after.mention, inline=True)
                if added:
                    embed.add_field(name='Added', value=' '.join(r.mention for r in added), inline=True)
                if removed:
                    embed.add_field(name='Removed', value=' '.join(r.mention for r in removed), inline=True)
                await self._log(after.guild.id, 'member_role_update', embed)

        # Nickname changes
        if before.nick != after.nick:
            embed = discord.Embed(title='📝 Nickname Changed', color=0x9b59b6, timestamp=self._ts())
            embed.add_field(name='Member', value=after.mention, inline=True)
            embed.add_field(name='Before', value=before.nick or '*None*', inline=True)
            embed.add_field(name='After', value=after.nick or '*None*', inline=True)
            await self._log(after.guild.id, 'member_nickname', embed)

    # ── Voice Events ──────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                     before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        if after.channel and not before.channel:
            embed = discord.Embed(title='🔊 Voice Join', color=0x2ecc71, timestamp=self._ts())
            embed.add_field(name='Member', value=member.mention, inline=True)
            embed.add_field(name='Channel', value=after.channel.mention, inline=True)
            await self._log(member.guild.id, 'voice_join', embed)
        elif before.channel and not after.channel:
            embed = discord.Embed(title='🔇 Voice Leave', color=0xe74c3c, timestamp=self._ts())
            embed.add_field(name='Member', value=member.mention, inline=True)
            embed.add_field(name='Channel', value=before.channel.mention, inline=True)
            await self._log(member.guild.id, 'voice_leave', embed)
        elif before.channel and after.channel:
            embed = discord.Embed(title='🔀 Voice Move', color=0xf59e0b, timestamp=self._ts())
            embed.add_field(name='Member', value=member.mention, inline=True)
            embed.add_field(name='From', value=before.channel.mention, inline=True)
            embed.add_field(name='To', value=after.channel.mention, inline=True)
            await self._log(member.guild.id, 'voice_move', embed)

    # ── Channel Events ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(title='📝 Channel Created', color=0x2ecc71, timestamp=self._ts())
        embed.add_field(name='Channel', value=f'{channel.mention} (`{channel.name}`)', inline=True)
        embed.add_field(name='Type', value=str(channel.type), inline=True)
        await self._log(channel.guild.id, 'channel_create', embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(title='🗑️ Channel Deleted', color=0xe74c3c, timestamp=self._ts())
        embed.add_field(name='Channel', value=f'`#{channel.name}`', inline=True)
        embed.add_field(name='Type', value=str(channel.type), inline=True)
        await self._log(channel.guild.id, 'channel_delete', embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if before.name != after.name:
            embed = discord.Embed(title='✏️ Channel Renamed', color=0xf59e0b, timestamp=self._ts())
            embed.add_field(name='Before', value=f'`#{before.name}`', inline=True)
            embed.add_field(name='After', value=after.mention, inline=True)
            await self._log(after.guild.id, 'channel_update', embed)

    # ── Role Events ───────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = discord.Embed(title='✨ Role Created', color=role.color.value or 0x2ecc71, timestamp=self._ts())
        embed.add_field(name='Role', value=role.mention, inline=True)
        await self._log(role.guild.id, 'role_create', embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = discord.Embed(title='🗑️ Role Deleted', color=0xe74c3c, timestamp=self._ts())
        embed.add_field(name='Role', value=f'`{role.name}`', inline=True)
        await self._log(role.guild.id, 'role_delete', embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        changes = []
        if before.name != after.name:
            changes.append(f'Name: `{before.name}` → `{after.name}`')
        if before.color != after.color:
            changes.append(f'Color: `{before.color}` → `{after.color}`')
        if before.permissions != after.permissions:
            changes.append('Permissions changed')
        if not changes:
            return
        embed = discord.Embed(title='✏️ Role Updated', color=after.color.value or 0xf59e0b, timestamp=self._ts())
        embed.add_field(name='Role', value=after.mention, inline=True)
        embed.add_field(name='Changes', value='\n'.join(changes), inline=False)
        await self._log(after.guild.id, 'role_update', embed)

    # ── Invite Events ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        embed = discord.Embed(title='🔗 Invite Created', color=0x2ecc71, timestamp=self._ts())
        embed.add_field(name='Code', value=f'`{invite.code}`', inline=True)
        embed.add_field(name='Created By', value=invite.inviter.mention if invite.inviter else 'Unknown', inline=True)
        embed.add_field(name='Channel', value=invite.channel.mention if invite.channel else 'Unknown', inline=True)
        embed.add_field(name='Max Uses', value=str(invite.max_uses or '∞'), inline=True)
        embed.add_field(name='Expires', value=f'<t:{int(invite.expires_at.timestamp())}:R>' if invite.expires_at else 'Never', inline=True)
        await self._log(invite.guild.id, 'invite_create', embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        embed = discord.Embed(title='🔗 Invite Deleted', color=0xe74c3c, timestamp=self._ts())
        embed.add_field(name='Code', value=f'`{invite.code}`', inline=True)
        if invite.guild:
            await self._log(invite.guild.id, 'invite_delete', embed)

    # ── Thread Events ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        embed = discord.Embed(title='🧵 Thread Created', color=0x2ecc71, timestamp=self._ts())
        embed.add_field(name='Thread', value=thread.mention, inline=True)
        embed.add_field(name='Parent', value=thread.parent.mention if thread.parent else 'Unknown', inline=True)
        embed.add_field(name='Owner', value=thread.owner.mention if thread.owner else 'Unknown', inline=True)
        await self._log(thread.guild.id, 'thread_create', embed)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        embed = discord.Embed(title='🧵 Thread Deleted', color=0xe74c3c, timestamp=self._ts())
        embed.add_field(name='Thread', value=f'`{thread.name}`', inline=True)
        embed.add_field(name='Parent', value=thread.parent.mention if thread.parent else 'Unknown', inline=True)
        await self._log(thread.guild.id, 'thread_delete', embed)

    # ── Setup Commands ────────────────────────────────────────────────────────

    @discord.app_commands.command(name='log-set', description='Set a log channel for all or specific events')
    @discord.app_commands.describe(
        channel='Channel to send logs to',
        category='Specific event category (leave empty for default/all)'
    )
    @discord.app_commands.choices(category=[
        discord.app_commands.Choice(name=c.replace('_', ' ').title(), value=c)
        for c in CATEGORIES
    ])
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def log_set(self, interaction: discord.Interaction,
                      channel: discord.TextChannel,
                      category: discord.app_commands.Choice[str] = None):
        data = _load()
        cfg = data.setdefault(str(interaction.guild.id), {})
        if category:
            cfg[f'ch_{category.value}'] = str(channel.id)
            msg = f'Logs for **{category.name}** → {channel.mention}'
        else:
            cfg['ch_default'] = str(channel.id)
            msg = f'Default log channel → {channel.mention} (all events without a specific channel)'
        _save(data)
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.app_commands.command(name='log-status', description='View logging configuration')
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def log_status(self, interaction: discord.Interaction):
        cfg = _cfg(interaction.guild.id)
        embed = discord.Embed(title='Logging Configuration', color=0x5865f2)
        default_ch = interaction.guild.get_channel(int(cfg['ch_default'])) if cfg.get('ch_default') else None
        embed.add_field(name='Default Channel', value=default_ch.mention if default_ch else 'Not set', inline=False)
        overrides = []
        for cat in CATEGORIES:
            ch_id = cfg.get(f'ch_{cat}')
            if ch_id:
                ch = interaction.guild.get_channel(int(ch_id))
                overrides.append(f'`{cat}` → {ch.mention if ch else ch_id}')
        if overrides:
            embed.add_field(name='Category Overrides', value='\n'.join(overrides[:20]), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name='log-disable', description='Disable logging for a category or all')
    @discord.app_commands.choices(category=[
        discord.app_commands.Choice(name=c.replace('_', ' ').title(), value=c)
        for c in CATEGORIES + ['all']
    ])
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def log_disable(self, interaction: discord.Interaction,
                           category: discord.app_commands.Choice[str]):
        data = _load()
        cfg = data.get(str(interaction.guild.id), {})
        if category.value == 'all':
            data[str(interaction.guild.id)] = {}
            msg = 'All logging disabled.'
        else:
            cfg.pop(f'ch_{category.value}', None)
            msg = f'Logging for **{category.name}** disabled.'
        _save(data)
        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Logging(bot))
