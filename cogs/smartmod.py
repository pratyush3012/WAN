"""
SmartMod — intelligent multi-language toxicity detection with escalating punishments.
Warn 1 → Warn 2 → Timeout 2h → Timeout 24h → Ban (configurable)
Detects: slurs, hate speech, profanity in English + common variants/leetspeak/unicode tricks.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, re, logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord_bot.smartmod')
SMARTMOD_FILE = 'smartmod.json'

# ── Toxicity word list ────────────────────────────────────────────────────────
# Covers direct words, common substitutions, and cross-language slurs.
# Uses regex patterns so l33tspeak / unicode tricks are caught.
RAW_PATTERNS = [
    # Racial slurs
    r'n[i1!|]+[g9]+[a@e3]+[rz]?s?',   # n*gger / n*gga variants
    r'n[i1!]+g+[sz]',
    r'nigg[ae]',
    r'n[i1]gg[a4@]',
    r'chink',
    r'sp[i1]c',
    r'k[i1]ke',
    r'g[o0]+[o0]+k',
    r'w[e3]tb[a@]ck',
    r'c[o0]{2}n',
    r'j[i1]gg?[a@b]b[o0]+',
    r'p[a@]k[i1]',
    r'sand\s*n[i1]gg',
    r'r[a@]gh[e3][a@]d',
    r'z[i1]p\s*h[e3][a@]d',
    # Sexual / extreme profanity
    r'm[o0]+th[e3]r\s*f+[uc]+k',       # motherfucker
    r'm\.?f\.?',                         # mf (standalone)
    r'\bmf\b',
    r'f+[uc]+k\s*y[o0]+[uo]',
    r'f[a@4]g+[o0]?t?',                 # f*ggot
    r'c[uo][mn]t',
    r'wh[o0]+r[e3]',
    r'sl[u]+t',
    r'b[i1]+tch',
    r'[a@]ssh[o0]+l[e3]',
    r'd[i1]+ck\s*h[e3][a@]d',
    r'sh[i1]+t',
    r'b[a@]st[a@]rd',
    r'tw[a@]t',
    r'c[o0]ck',
    r'p[e3]n[i1]s',
    r'v[a@]g[i1]n[a@]',
    r'[a@]n[a@]l',
    # Hate / threats
    r'k[i1]ll\s*y[o0]+[uo]rs[e3]lf',
    r'kys',
    r'g[o0]\s*d[i1][e3]',
    r'h[i1]tl[e3]r',
    r'n[a@]z[i1]',
    r'h[a@][i1]l\s*h[i1]tl[e3]r',
    # Hindi/Urdu slurs (transliterated)
    r'bh[a@]nd',
    r'm[a@]d[a@]rch[o0]d',
    r'b[e3]h[e3]nch[o0]d',
    r'ch[u]+tiy[a@]',
    r'g[a@]nd[u]+',
    r'r[a@]nd[i1]',
    r'h[a@]r[a@]mz[a@]d[a@]',
    r'k[a@]m[i1]n[a@]',
    r'ul[l]+[u]+',
    # Spanish slurs
    r'p[e3]nd[e3][j]+[o0]',
    r'c[a@]br[o0]n',
    r'p[u]+t[a@]',
    r'h[i1][j]+[o0]\s*d[e3]\s*p[u]+t[a@]',
    r'c[o0][j]+[o0]n[e3]s',
    r'm[a@]r[i1]c[o0]n',
    # French slurs
    r'c[o0]nn[a@]rd',
    r'p[u]+t[a@][i1]n',
    r'enc[u]+l[e3]',
    r'b[a@]t[a@]rd',
    # Arabic slurs (transliterated)
    r'ibn\s*[e3]l\s*sh[a@]rm[o0]+t[a@]',
    r'k[a@]ss\s*[o0]mm[a@]k',
    r'y[e3]bn\s*[e3]l\s*[a@]h[b]+[e3]',
]

# Compile all patterns once at module load
_COMPILED = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in RAW_PATTERNS]


def _is_toxic(text: str) -> bool:
    """Return True if text matches any toxicity pattern."""
    # Normalize: remove zero-width chars, collapse spaces
    clean = re.sub(r'[\u200b-\u200f\u202a-\u202e\uFEFF]', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    for pat in _COMPILED:
        if pat.search(clean):
            return True
    return False


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
        'strikes': {},          # user_id -> strike count
        'last_strike': {},      # user_id -> ISO timestamp
        'strike_decay_days': 30,
    })


# ── Escalation ladder ─────────────────────────────────────────────────────────
# strike 1 → warn DM + public notice
# strike 2 → warn DM + public notice
# strike 3 → timeout 2h
# strike 4 → timeout 24h
# strike 5+ → ban

ESCALATION = {
    1: ('warn',    None,              '⚠️ First warning'),
    2: ('warn',    None,              '⚠️ Final warning'),
    3: ('timeout', timedelta(hours=2),'⏱️ Timed out 2 hours'),
    4: ('timeout', timedelta(hours=24),'⏱️ Timed out 24 hours'),
}


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
        if not _is_toxic(message.content):
            return

        uid = str(message.author.id)

        # Strike decay — reset if last strike was > decay_days ago
        last_ts = g['last_strike'].get(uid)
        if last_ts:
            last_dt = datetime.fromisoformat(last_ts)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            decay_days = g.get('strike_decay_days', 30)
            if (datetime.now(timezone.utc) - last_dt).days >= decay_days:
                g['strikes'][uid] = 0

        # Increment strike
        g['strikes'][uid] = g['strikes'].get(uid, 0) + 1
        g['last_strike'][uid] = datetime.now(timezone.utc).isoformat()
        strike = g['strikes'][uid]
        _save(data)

        # Delete the message
        try:
            await message.delete()
        except: pass

        action, duration, label = ESCALATION.get(strike, ('ban', None, '🔨 Banned'))

        # Build public warning embed
        embed = discord.Embed(color=0xe74c3c, timestamp=datetime.now(timezone.utc))
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.title = f'{label} — Strike {strike}'
        embed.description = (
            f'{message.author.mention} your message was removed for violating community rules.\n'
            f'**Strike:** {strike}/5'
        )
        if action == 'timeout':
            embed.description += f'\n**Punishment:** Timeout for {duration}'
        elif action == 'ban':
            embed.description += '\n**Punishment:** Permanent ban'
        embed.set_footer(text='SmartMod • Toxicity Detection')

        # Send public notice (auto-delete after 15s)
        try:
            await message.channel.send(embed=embed, delete_after=15)
        except: pass

        # DM the user
        try:
            dm_embed = discord.Embed(
                title=f'You received Strike {strike} in {message.guild.name}',
                description=(
                    f'Your message was removed for containing prohibited language.\n\n'
                    f'**Strike {strike}/5** — {label}\n\n'
                    f'Continued violations will result in escalating punishments.'
                ),
                color=0xe74c3c
            )
            await message.author.send(embed=dm_embed)
        except: pass

        # Execute punishment
        try:
            if action == 'timeout' and duration:
                await message.author.timeout(duration, reason=f'SmartMod: strike {strike}')
            elif action == 'ban':
                await message.author.ban(reason=f'SmartMod: {strike} strikes — repeated toxicity')
        except Exception as e:
            logger.warning(f'SmartMod punishment failed: {e}')

        # Log to mod channel
        log_embed = discord.Embed(
            title=f'SmartMod Action — Strike {strike}',
            color=0xe74c3c,
            timestamp=datetime.now(timezone.utc)
        )
        log_embed.add_field(name='User', value=f'{message.author} (`{message.author.id}`)', inline=True)
        log_embed.add_field(name='Channel', value=message.channel.mention, inline=True)
        log_embed.add_field(name='Action', value=label, inline=True)
        log_embed.add_field(name='Message', value=f'||{message.content[:300]}||', inline=False)
        await self._log(message.guild, g, log_embed)

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name='smartmod-toggle', description='Enable or disable SmartMod toxicity detection')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle(self, interaction: discord.Interaction):
        data = _load()
        g = _guild(data, interaction.guild.id)
        g['enabled'] = not g['enabled']
        _save(data)
        state = 'enabled' if g['enabled'] else 'disabled'
        await interaction.response.send_message(f'SmartMod {state}.', ephemeral=True)

    @app_commands.command(name='smartmod-setlog', description='Set channel for SmartMod logs')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = _load()
        g = _guild(data, interaction.guild.id)
        g['log_channel'] = str(channel.id)
        _save(data)
        await interaction.response.send_message(f'SmartMod log channel set to {channel.mention}.', ephemeral=True)

    @app_commands.command(name='smartmod-strikes', description='View strikes for a member')
    @app_commands.checks.has_permissions(moderate_members=True)
    async def strikes(self, interaction: discord.Interaction, member: discord.Member):
        data = _load()
        g = _guild(data, interaction.guild.id)
        count = g['strikes'].get(str(member.id), 0)
        last = g['last_strike'].get(str(member.id), 'Never')
        if last != 'Never':
            last = last[:10]
        embed = discord.Embed(title=f'SmartMod Strikes — {member}', color=0xe74c3c)
        embed.add_field(name='Strikes', value=f'{count}/5', inline=True)
        embed.add_field(name='Last Strike', value=last, inline=True)
        next_action = ESCALATION.get(count + 1, ('ban', None, 'Ban'))[2]
        embed.add_field(name='Next Action', value=next_action, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='smartmod-clearstrikes', description='Clear strikes for a member')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def clearstrikes(self, interaction: discord.Interaction, member: discord.Member):
        data = _load()
        g = _guild(data, interaction.guild.id)
        uid = str(member.id)
        g['strikes'].pop(uid, None)
        g['last_strike'].pop(uid, None)
        _save(data)
        await interaction.response.send_message(f'Cleared strikes for {member.mention}.', ephemeral=True)

    @app_commands.command(name='smartmod-ignore-channel', description='Toggle channel ignore for SmartMod')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ignore_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = _load()
        g = _guild(data, interaction.guild.id)
        cid = str(channel.id)
        ignored = g.setdefault('ignored_channels', [])
        if cid in ignored:
            ignored.remove(cid)
            msg = f'SmartMod will now scan {channel.mention}.'
        else:
            ignored.append(cid)
            msg = f'SmartMod will ignore {channel.mention}.'
        _save(data)
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name='smartmod-ignore-role', description='Toggle role ignore for SmartMod')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ignore_role(self, interaction: discord.Interaction, role: discord.Role):
        data = _load()
        g = _guild(data, interaction.guild.id)
        rid = str(role.id)
        ignored = g.setdefault('ignored_roles', [])
        if rid in ignored:
            ignored.remove(rid)
            msg = f'SmartMod will now scan members with {role.mention}.'
        else:
            ignored.append(rid)
            msg = f'SmartMod will ignore members with {role.mention}.'
        _save(data)
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name='smartmod-status', description='View SmartMod configuration')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status(self, interaction: discord.Interaction):
        data = _load()
        g = _guild(data, interaction.guild.id)
        embed = discord.Embed(title='SmartMod Status', color=0x5865f2)
        embed.add_field(name='Status', value='✅ Enabled' if g['enabled'] else '❌ Disabled', inline=True)
        log_ch = interaction.guild.get_channel(int(g['log_channel'])) if g.get('log_channel') else None
        embed.add_field(name='Log Channel', value=log_ch.mention if log_ch else 'Not set', inline=True)
        embed.add_field(name='Strike Decay', value=f'{g.get("strike_decay_days", 30)} days', inline=True)
        embed.add_field(name='Escalation', value=(
            '1 strike → Warning\n'
            '2 strikes → Final Warning\n'
            '3 strikes → Timeout 2h\n'
            '4 strikes → Timeout 24h\n'
            '5+ strikes → Ban'
        ), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SmartMod(bot))
