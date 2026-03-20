"""
SmartMod — toxicity detection with escalating punishments, appeal system.
- Shows exactly which word/sentence triggered the warning
- "Mind your language" public message
- Appeal button → DMs the guild owner to approve/deny timeout removal
"""
import discord
from discord.ext import commands
import json, os, re, logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord_bot.smartmod')
SMARTMOD_FILE = 'smartmod.json'

# ── Toxicity patterns with labels ─────────────────────────────────────────────
# Each entry: (pattern, friendly_category)
LABELED_PATTERNS = [
    # Racial slurs
    (r'n[i1!|]+[g9]+[a@e3]+[rz]?s?', 'racial slur'),
    (r'n[i1!]+g+[sz]',                'racial slur'),
    (r'nigg[ae]',                      'racial slur'),
    (r'n[i1]gg[a4@]',                  'racial slur'),
    (r'chink',                         'racial slur'),
    (r'sp[i1]c',                       'racial slur'),
    (r'k[i1]ke',                       'racial slur'),
    (r'g[o0]+[o0]+k',                  'racial slur'),
    (r'w[e3]tb[a@]ck',                 'racial slur'),
    (r'c[o0]{2}n',                     'racial slur'),
    (r'j[i1]gg?[a@b]b[o0]+',          'racial slur'),
    (r'p[a@]k[i1]',                    'racial slur'),
    (r'sand\s*n[i1]gg',               'racial slur'),
    (r'r[a@]gh[e3][a@]d',             'racial slur'),
    (r'z[i1]p\s*h[e3][a@]d',          'racial slur'),
    # Sexual / extreme profanity
    (r'm[o0]+th[e3]r\s*f+[uc]+k',     'extreme profanity'),
    (r'\bmf\b',                        'extreme profanity'),
    (r'f+[uc]+k\s*y[o0]+[uo]',        'extreme profanity'),
    (r'f[a@4]g+[o0]?t?',              'homophobic slur'),
    (r'c[uo][mn]t',                    'extreme profanity'),
    (r'wh[o0]+r[e3]',                  'sexual insult'),
    (r'sl[u]+t',                       'sexual insult'),
    (r'b[i1]+tch',                     'profanity'),
    (r'[a@]ssh[o0]+l[e3]',            'profanity'),
    (r'd[i1]+ck\s*h[e3][a@]d',        'profanity'),
    (r'sh[i1]+t',                      'profanity'),
    (r'b[a@]st[a@]rd',                'profanity'),
    (r'tw[a@]t',                       'profanity'),
    (r'c[o0]ck',                       'profanity'),
    # Hate / threats
    (r'k[i1]ll\s*y[o0]+[uo]rs[e3]lf', 'self-harm encouragement'),
    (r'\bkys\b',                       'self-harm encouragement'),
    (r'g[o0]\s*d[i1][e3]',            'death threat'),
    (r'h[i1]tl[e3]r',                 'hate speech'),
    (r'n[a@]z[i1]',                   'hate speech'),
    (r'h[a@][i1]l\s*h[i1]tl[e3]r',   'hate speech'),
    # Hindi/Urdu
    (r'bh[a@]nd',                      'Hindi profanity'),
    (r'm[a@]d[a@]rch[o0]d',           'Hindi profanity'),
    (r'b[e3]h[e3]nch[o0]d',           'Hindi profanity'),
    (r'ch[u]+tiy[a@]',                'Hindi profanity'),
    (r'g[a@]nd[u]+',                   'Hindi profanity'),
    (r'r[a@]nd[i1]',                   'Hindi profanity'),
    (r'h[a@]r[a@]mz[a@]d[a@]',       'Hindi profanity'),
    (r'k[a@]m[i1]n[a@]',              'Hindi profanity'),
    (r'ul[l]+[u]+',                    'Hindi profanity'),
    # Spanish
    (r'p[e3]nd[e3][j]+[o0]',          'Spanish profanity'),
    (r'c[a@]br[o0]n',                  'Spanish profanity'),
    (r'p[u]+t[a@]',                    'Spanish profanity'),
    (r'h[i1][j]+[o0]\s*d[e3]\s*p[u]+t[a@]', 'Spanish profanity'),
    (r'c[o0][j]+[o0]n[e3]s',          'Spanish profanity'),
    (r'm[a@]r[i1]c[o0]n',             'Spanish profanity'),
    # French
    (r'c[o0]nn[a@]rd',                'French profanity'),
    (r'p[u]+t[a@][i1]n',              'French profanity'),
    (r'enc[u]+l[e3]',                  'French profanity'),
    (r'b[a@]t[a@]rd',                 'French profanity'),
    # Arabic transliterated
    (r'ibn\s*[e3]l\s*sh[a@]rm[o0]+t[a@]', 'Arabic profanity'),
    (r'k[a@]ss\s*[o0]mm[a@]k',        'Arabic profanity'),
    (r'y[e3]bn\s*[e3]l\s*[a@]h[b]+[e3]', 'Arabic profanity'),
]

_COMPILED = [(re.compile(p, re.IGNORECASE | re.UNICODE), cat) for p, cat in LABELED_PATTERNS]


def _detect(text: str):
    """Return (matched_word, category) or (None, None) if clean."""
    clean = re.sub(r'[\u200b-\u200f\u202a-\u202e\uFEFF]', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    for pat, cat in _COMPILED:
        m = pat.search(clean)
        if m:
            return m.group(0), cat
    return None, None


# ── Persistence ───────────────────────────────────────────────────────────────

def _load():
    if os.path.exists(SMARTMOD_FILE):
        try:
            with open(SMARTMOD_FILE) as f: return json.load(f)
        except: pass
    return {}

def _save(d):
    with open(SMARTMOD_FILE, 'w') as f: json.dump(d, f, indent=2)

def _guild(data, guild_id):
    return data.setdefault(str(guild_id), {
        'enabled': True,
        'log_channel': None,
        'ignored_roles': [],
        'ignored_channels': [],
        'strikes': {},
        'last_strike': {},
        'strike_decay_days': 30,
    })


# ── Escalation ladder ─────────────────────────────────────────────────────────
ESCALATION = {
    1: ('warn',    None,               '⚠️ First warning'),
    2: ('warn',    None,               '⚠️ Final warning'),
    3: ('timeout', timedelta(hours=2), '⏱️ Timed out 2 hours'),
    4: ('timeout', timedelta(hours=24),'⏱️ Timed out 24 hours'),
}


# ── Appeal View ───────────────────────────────────────────────────────────────

class AppealView(discord.ui.View):
    """Sent to the user — has a single Appeal button."""

    def __init__(self, guild_id: int, user_id: int, strike: int,
                 offending_word: str, category: str, sentence: str,
                 action: str, owner_id: int):
        super().__init__(timeout=86400)  # 24h
        self.guild_id = guild_id
        self.user_id = user_id
        self.strike = strike
        self.offending_word = offending_word
        self.category = category
        self.sentence = sentence
        self.action = action
        self.owner_id = owner_id
        self.appealed = False

    @discord.ui.button(label='📩 Appeal Punishment', style=discord.ButtonStyle.primary)
    async def appeal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message('This is not your appeal.', ephemeral=True)
        if self.appealed:
            return await interaction.response.send_message('You already submitted an appeal.', ephemeral=True)

        self.appealed = True
        button.disabled = True
        button.label = '✅ Appeal Submitted'
        await interaction.response.edit_message(view=self)

        # DM the owner
        try:
            owner = await interaction.client.fetch_user(self.owner_id)
            owner_view = OwnerAppealView(
                guild_id=self.guild_id,
                user_id=self.user_id,
                strike=self.strike,
                action=self.action,
            )
            owner_embed = discord.Embed(
                title='📩 Punishment Appeal Request',
                color=0xf59e0b,
                timestamp=datetime.now(timezone.utc)
            )
            owner_embed.add_field(name='User', value=f'<@{self.user_id}> (`{self.user_id}`)', inline=True)
            owner_embed.add_field(name='Strike', value=f'{self.strike}/5', inline=True)
            owner_embed.add_field(name='Punishment', value=self.action, inline=True)
            owner_embed.add_field(name='Flagged Word', value=f'`{self.offending_word}`', inline=True)
            owner_embed.add_field(name='Category', value=self.category, inline=True)
            owner_embed.add_field(name='Original Message', value=f'||{self.sentence[:300]}||', inline=False)
            owner_embed.set_footer(text='Approve to remove the punishment • Deny to keep it')
            await owner.send(embed=owner_embed, view=owner_view)
        except Exception as e:
            logger.warning(f'Could not DM owner for appeal: {e}')
            await interaction.followup.send(
                '⚠️ Could not reach the server owner. Please contact them directly.', ephemeral=True
            )


class OwnerAppealView(discord.ui.View):
    """Sent to the owner — Approve / Deny buttons."""

    def __init__(self, guild_id: int, user_id: int, strike: int, action: str):
        super().__init__(timeout=172800)  # 48h
        self.guild_id = guild_id
        self.user_id = user_id
        self.strike = strike
        self.action = action
        self.resolved = False

    async def _resolve(self, interaction: discord.Interaction, approved: bool):
        if self.resolved:
            return await interaction.response.send_message('Already resolved.', ephemeral=True)
        self.resolved = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        guild = interaction.client.get_guild(self.guild_id)
        member = guild.get_member(self.user_id) if guild else None

        if approved:
            # Remove timeout if active
            if member:
                try:
                    await member.timeout(None, reason='Appeal approved by owner')
                except Exception as e:
                    logger.warning(f'Could not remove timeout: {e}')
            # Notify user
            try:
                user = await interaction.client.fetch_user(self.user_id)
                embed = discord.Embed(
                    title='✅ Appeal Approved',
                    description=(
                        f'Your appeal in **{guild.name if guild else "the server"}** was **approved** by the owner.\n'
                        f'Your punishment has been removed. Please follow the rules going forward.'
                    ),
                    color=0x10b981
                )
                await user.send(embed=embed)
            except: pass
            await interaction.followup.send(f'✅ Appeal approved — timeout removed for <@{self.user_id}>.', ephemeral=True)
        else:
            # Notify user of denial
            try:
                user = await interaction.client.fetch_user(self.user_id)
                embed = discord.Embed(
                    title='❌ Appeal Denied',
                    description=(
                        f'Your appeal in **{guild.name if guild else "the server"}** was **denied** by the owner.\n'
                        f'Your punishment remains in place. Please respect the community rules.'
                    ),
                    color=0xe74c3c
                )
                await user.send(embed=embed)
            except: pass
            await interaction.followup.send(f'❌ Appeal denied — punishment kept for <@{self.user_id}>.', ephemeral=True)

    @discord.ui.button(label='✅ Approve — Remove Punishment', style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, approved=True)

    @discord.ui.button(label='❌ Deny — Keep Punishment', style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, approved=False)


# ── Cog ───────────────────────────────────────────────────────────────────────

class SmartMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _is_ignored(self, message: discord.Message, g: dict) -> bool:
        if message.author.guild_permissions.administrator:
            return True
        if str(message.channel.id) in g.get('ignored_channels', []):
            return True
        user_role_ids = {str(r.id) for r in message.author.roles}
        if user_role_ids & set(g.get('ignored_roles', [])):
            return True
        return False

    async def _log(self, guild: discord.Guild, g: dict, embed: discord.Embed):
        ch_id = g.get('log_channel')
        if not ch_id:
            return
        ch = guild.get_channel(int(ch_id))
        if ch:
            try:
                await ch.send(embed=embed)
            except: pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        data = _load()
        g = _guild(data, message.guild.id)
        if not g['enabled']:
            return
        if self._is_ignored(message, g):
            return

        offending_word, category = _detect(message.content)
        if not offending_word:
            return

        uid = str(message.author.id)
        original_sentence = message.content

        # Strike decay
        last_ts = g['last_strike'].get(uid)
        if last_ts:
            last_dt = datetime.fromisoformat(last_ts)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - last_dt).days >= g.get('strike_decay_days', 30):
                g['strikes'][uid] = 0

        # Increment strike
        g['strikes'][uid] = g['strikes'].get(uid, 0) + 1
        g['last_strike'][uid] = datetime.now(timezone.utc).isoformat()
        strike = g['strikes'][uid]
        _save(data)

        # Delete message
        try:
            await message.delete()
        except: pass

        action, duration, label = ESCALATION.get(strike, ('ban', None, '🔨 Banned'))

        # ── Public channel warning ────────────────────────────────────────────
        pub_embed = discord.Embed(
            title='🚫 Mind Your Language!',
            color=0xe74c3c,
            timestamp=datetime.now(timezone.utc)
        )
        pub_embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        pub_embed.description = (
            f'{message.author.mention} your message was removed.\n\n'
            f'**Reason:** Contains {category}\n'
            f'**Flagged word:** `{offending_word}`\n'
            f'**Strike:** {strike}/5 — {label}'
        )
        if action == 'timeout' and duration:
            pub_embed.description += f'\n**Punishment:** Timed out for {duration}'
        elif action == 'ban':
            pub_embed.description += '\n**Punishment:** Permanent ban'
        pub_embed.set_footer(text='SmartMod • Check your DMs to appeal')

        try:
            await message.channel.send(embed=pub_embed, delete_after=20)
        except: pass

        # ── DM the user with full details + appeal button ─────────────────────
        owner_id = message.guild.owner_id
        dm_embed = discord.Embed(
            title=f'⚠️ Warning — Strike {strike}/5 in {message.guild.name}',
            color=0xe74c3c,
            timestamp=datetime.now(timezone.utc)
        )
        dm_embed.description = (
            f'**Mind your language!** Your message was removed.\n\n'
            f'**Server:** {message.guild.name}\n'
            f'**Channel:** #{message.channel.name}\n'
            f'**Reason:** Contains {category}\n'
            f'**Flagged word:** `{offending_word}`\n'
            f'**Your message:** ||{original_sentence[:300]}||\n\n'
            f'**Strike:** {strike}/5 — {label}'
        )
        if action == 'timeout' and duration:
            dm_embed.description += f'\n**Punishment:** Timed out for {duration}'
            dm_embed.add_field(
                name='💡 What to do',
                value='If you believe this was a mistake, click the Appeal button below.\nThe server owner will review your case.',
                inline=False
            )
        elif action == 'ban':
            dm_embed.description += '\n**Punishment:** Permanent ban'
        elif action == 'warn':
            dm_embed.add_field(
                name='💡 Note',
                value='This is a warning. Further violations will result in a timeout.\nYou may appeal if you believe this was a mistake.',
                inline=False
            )
        dm_embed.set_footer(text=f'{message.guild.name} • SmartMod')

        # Only show appeal button if there's an actual punishment (warn or timeout)
        appeal_view = AppealView(
            guild_id=message.guild.id,
            user_id=message.author.id,
            strike=strike,
            offending_word=offending_word,
            category=category,
            sentence=original_sentence,
            action=label,
            owner_id=owner_id,
        )

        try:
            await message.author.send(embed=dm_embed, view=appeal_view)
        except Exception as e:
            logger.warning(f'Could not DM user {message.author}: {e}')

        # ── Execute punishment ────────────────────────────────────────────────
        try:
            if action == 'timeout' and duration:
                await message.author.timeout(duration, reason=f'SmartMod: {category} (strike {strike})')
            elif action == 'ban':
                await message.author.ban(reason=f'SmartMod: {strike} strikes — repeated {category}')
        except Exception as e:
            logger.warning(f'SmartMod punishment failed: {e}')

        # ── Log to mod channel ────────────────────────────────────────────────
        log_embed = discord.Embed(
            title=f'SmartMod — Strike {strike} | {label}',
            color=0xe74c3c,
            timestamp=datetime.now(timezone.utc)
        )
        log_embed.add_field(name='User', value=f'{message.author} (`{message.author.id}`)', inline=True)
        log_embed.add_field(name='Channel', value=message.channel.mention, inline=True)
        log_embed.add_field(name='Category', value=category, inline=True)
        log_embed.add_field(name='Flagged Word', value=f'`{offending_word}`', inline=True)
        log_embed.add_field(name='Action', value=label, inline=True)
        log_embed.add_field(name='Message', value=f'||{original_sentence[:300]}||', inline=False)
        await self._log(message.guild, g, log_embed)

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.command(name='smartmod-toggle')
    @commands.has_permissions(manage_guild=True)
    async def toggle(self, ctx: commands.Context):
        """Enable or disable SmartMod"""
        data = _load()
        g = _guild(data, ctx.guild.id)
        g['enabled'] = not g['enabled']
        _save(data)
        await ctx.send(f'SmartMod {"enabled" if g["enabled"] else "disabled"}.')

    @commands.command(name='smartmod-setlog')
    @commands.has_permissions(manage_guild=True)
    async def setlog(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set SmartMod log channel"""
        data = _load()
        g = _guild(data, ctx.guild.id)
        g['log_channel'] = str(channel.id)
        _save(data)
        await ctx.send(f'SmartMod log channel set to {channel.mention}.')

    @commands.command(name='smartmod-strikes')
    @commands.has_permissions(moderate_members=True)
    async def strikes(self, ctx: commands.Context, member: discord.Member):
        """View strikes for a member"""
        data = _load()
        g = _guild(data, ctx.guild.id)
        count = g['strikes'].get(str(member.id), 0)
        last = g['last_strike'].get(str(member.id), 'Never')[:10] if g['last_strike'].get(str(member.id)) else 'Never'
        embed = discord.Embed(title=f'SmartMod Strikes — {member}', color=0xe74c3c)
        embed.add_field(name='Strikes', value=f'{count}/5', inline=True)
        embed.add_field(name='Last Strike', value=last, inline=True)
        embed.add_field(name='Next Action', value=ESCALATION.get(count + 1, ('ban', None, '🔨 Ban'))[2], inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='smartmod-clearstrikes')
    @commands.has_permissions(manage_guild=True)
    async def clearstrikes(self, ctx: commands.Context, member: discord.Member):
        """Clear strikes for a member"""
        data = _load()
        g = _guild(data, ctx.guild.id)
        uid = str(member.id)
        g['strikes'].pop(uid, None)
        g['last_strike'].pop(uid, None)
        _save(data)
        await ctx.send(f'Cleared strikes for {member.mention}.')

    @commands.command(name='smartmod-ignore-channel')
    @commands.has_permissions(manage_guild=True)
    async def ignore_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Toggle channel ignore for SmartMod"""
        data = _load()
        g = _guild(data, ctx.guild.id)
        cid = str(channel.id)
        ignored = g.setdefault('ignored_channels', [])
        if cid in ignored:
            ignored.remove(cid)
            msg = f'SmartMod will now scan {channel.mention}.'
        else:
            ignored.append(cid)
            msg = f'SmartMod will ignore {channel.mention}.'
        _save(data)
        await ctx.send(msg)

    @commands.command(name='smartmod-ignore-role')
    @commands.has_permissions(manage_guild=True)
    async def ignore_role(self, ctx: commands.Context, role: discord.Role):
        """Toggle role ignore for SmartMod"""
        data = _load()
        g = _guild(data, ctx.guild.id)
        rid = str(role.id)
        ignored = g.setdefault('ignored_roles', [])
        if rid in ignored:
            ignored.remove(rid)
            msg = f'SmartMod will now scan members with {role.mention}.'
        else:
            ignored.append(rid)
            msg = f'SmartMod will ignore members with {role.mention}.'
        _save(data)
        await ctx.send(msg)

    @commands.command(name='smartmod-status')
    @commands.has_permissions(manage_guild=True)
    async def status(self, ctx: commands.Context):
        """View SmartMod configuration"""
        data = _load()
        g = _guild(data, ctx.guild.id)
        embed = discord.Embed(title='SmartMod Status', color=0x5865f2)
        embed.add_field(name='Status', value='✅ Enabled' if g['enabled'] else '❌ Disabled', inline=True)
        log_ch = ctx.guild.get_channel(int(g['log_channel'])) if g.get('log_channel') else None
        embed.add_field(name='Log Channel', value=log_ch.mention if log_ch else 'Not set', inline=True)
        embed.add_field(name='Strike Decay', value=f'{g.get("strike_decay_days", 30)} days', inline=True)
        embed.add_field(name='Escalation', value=(
            '1 strike → Warning\n2 strikes → Final Warning\n'
            '3 strikes → Timeout 2h\n4 strikes → Timeout 24h\n5+ strikes → Ban'
        ), inline=False)
        embed.add_field(name='Appeal System', value='✅ Active — users can appeal via DM button', inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(SmartMod(bot))
