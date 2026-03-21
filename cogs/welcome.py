"""
WAN Bot - Welcome/Goodbye System
Randomized welcome messages (cool + flirty mix) so it never feels repetitive.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging, random
from datetime import datetime, timezone

logger = logging.getLogger('discord_bot.welcome')
DATA_FILE = 'welcome_data.json'

# ── Randomized welcome messages ───────────────────────────────────────────────
# Mix of cool, hype, and flirty — picked randomly each join so it never repeats
WELCOME_TITLES = [
    "✨ A new legend has arrived!",
    "🔥 Someone just walked in!",
    "💫 Look who just showed up!",
    "👑 Royalty has entered the chat!",
    "🎉 The squad just got bigger!",
    "😏 Well well well...",
    "🚀 New member incoming!",
    "💥 The server just leveled up!",
    "🌟 A star has joined us!",
    "🎊 Welcome to the family!",
]

WELCOME_MESSAGES = [
    "Hey {user}! We've been waiting for you 👀 Make yourself at home in **{server}**!",
    "Oh look who decided to show up 😏 Welcome, {user}! You're member **#{count}** — not bad.",
    "{user} just walked in and honestly? The vibe just improved. Welcome to **{server}**! 🔥",
    "Careful everyone, {user} just arrived and they look dangerous 😈 Welcome!",
    "The server was missing something... turns out it was you, {user}! Welcome to **{server}** 💫",
    "{user} has entered the chat. Everyone act cool 😎 Welcome to **{server}**!",
    "Plot twist: {user} just joined and now **{server}** is officially better 🎉",
    "We don't know who you are yet, {user}, but we already like you 😌 Welcome!",
    "{user} just dropped in! You're our **#{count}** member — make it count 👑",
    "Roses are red, the server is lit, {user} just joined and we love it 💕",
    "New member alert 🚨 {user} has arrived! Say hi before they think we're boring 😂",
    "{user} walked in like they own the place. Honestly? Respect. Welcome to **{server}**! 💪",
    "Hey {user}! Fair warning — we're a little chaotic here. You'll fit right in 😏",
    "The stars aligned and brought {user} to **{server}**. Coincidence? We think not ✨",
    "{user} just joined! Quick everyone, look busy 😅 Welcome to the crew!",
]

GOODBYE_MESSAGES = [
    "**{username}** has left the building 👋 We'll miss you (a little).",
    "**{username}** dipped. **{server}** has {count} members now.",
    "And just like that, **{username}** was gone 💨 Take care out there!",
    "**{username}** left. The vibe took a small hit ngl 😔",
    "**{username}** has logged off from **{server}**. Until next time! 👋",
]


def _fill(template: str, member: discord.Member) -> str:
    return (template
        .replace('{user}', member.mention)
        .replace('{username}', member.display_name)
        .replace('{server}', member.guild.name)
        .replace('{count}', str(member.guild.member_count))
        .replace('{id}', str(member.id))
    )


def _parse_color(raw, default: int) -> int:
    try:
        s = str(raw).strip()
        if s.startswith('#'):
            return int(s[1:], 16)
        elif s.lower().startswith('0x'):
            return int(s, 16)
        else:
            return int(s, 16)
    except Exception:
        return default


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data: dict = self._load()

    def _load(self) -> dict:
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save(self):
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump(self.data, f)
        except Exception as e:
            logger.error(f"Welcome save error: {e}")

    def _guild(self, gid: int) -> dict:
        key = str(gid)
        if key not in self.data:
            self.data[key] = {}
        return self.data[key]

    async def _send_embed(self, member: discord.Member, cfg: dict, event: str):
        ch_id = cfg.get(f'{event}_channel')
        if not ch_id:
            return
        ch = member.guild.get_channel(int(ch_id))
        if not ch:
            return

        # Use custom message if set, otherwise pick a random one
        if event == 'welcome':
            raw_title = cfg.get('welcome_title') or random.choice(WELCOME_TITLES)
            raw_desc  = cfg.get('welcome_message') or random.choice(WELCOME_MESSAGES)
            default_color = 0x57f287
        else:
            raw_title = cfg.get('goodbye_title') or '👋 See you around!'
            raw_desc  = cfg.get('goodbye_message') or random.choice(GOODBYE_MESSAGES)
            default_color = 0xef4444

        title = _fill(raw_title, member)
        desc  = _fill(raw_desc, member)
        color = _parse_color(cfg.get(f'{event}_color', default_color), default_color)

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"{member.guild.name} • {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
        try:
            await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"Welcome send error ({event}): {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = self._guild(member.guild.id)
        logger.info(f"Member join: {member} in {member.guild.name} — welcome_channel={cfg.get('welcome_channel')}")
        await self._send_embed(member, cfg, 'welcome')
        role_id = cfg.get('autorole')
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except Exception as e:
                    logger.warning(f"Auto-role error: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        cfg = self._guild(member.guild.id)
        await self._send_embed(member, cfg, 'goodbye')

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        cfg = self._guild(after.guild.id)
        promo_channel_id = cfg.get('promo_channel')
        promo_msg_template = cfg.get('promo_message', '🎉 Congratulations {user}! You\'ve been promoted to **{role}**! Well deserved! 🎊')
        watched_raw = cfg.get('promo_roles', '')
        if not promo_channel_id or not watched_raw:
            return
        watched = [r.strip().lower() for r in watched_raw.split(',') if r.strip()]
        new_roles = [r for r in after.roles if r not in before.roles]
        for role in new_roles:
            if role.name.lower() in watched:
                ch = after.guild.get_channel(int(promo_channel_id))
                if not ch:
                    return
                msg = promo_msg_template.replace('{user}', after.mention).replace('{username}', after.display_name).replace('{role}', role.name).replace('{server}', after.guild.name)
                embed = discord.Embed(description=msg, color=0xf59e0b)
                embed.set_thumbnail(url=after.display_avatar.url)
                embed.set_footer(text=f"{after.guild.name} • Promotion")
                try:
                    await ch.send(embed=embed)
                except Exception as e:
                    logger.warning(f"Promo send error: {e}")
                break

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(name="welcome-set", description="👋 Configure welcome messages (leave blank for random)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_set(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          message: str = "",
                          title: str = "",
                          color: str = "#57f287"):
        cfg = self._guild(interaction.guild.id)
        cfg.update({
            'welcome_channel': str(channel.id),
            'welcome_message': message,
            'welcome_title': title,
            'welcome_color': color,
        })
        self._save()
        note = "Random messages enabled (no custom message set)." if not message else f"Custom message saved."
        await interaction.response.send_message(
            f"✅ Welcome → {channel.mention}\n{note}\n"
            f"Variables: `{{user}}` `{{username}}` `{{server}}` `{{count}}` `{{id}}`",
            ephemeral=True)

    @app_commands.command(name="goodbye-set", description="👋 Configure goodbye messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_set(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          message: str = "",
                          title: str = ""):
        cfg = self._guild(interaction.guild.id)
        cfg.update({'goodbye_channel': str(channel.id), 'goodbye_message': message, 'goodbye_title': title})
        self._save()
        await interaction.response.send_message(f"✅ Goodbye → {channel.mention}", ephemeral=True)

    @app_commands.command(name="autorole", description="👋 Set a role to auto-assign when members join")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole(self, interaction: discord.Interaction, role: discord.Role = None):
        cfg = self._guild(interaction.guild.id)
        if role:
            cfg['autorole'] = str(role.id)
            self._save()
            await interaction.response.send_message(f"✅ New members will get **{role.name}** on join.", ephemeral=True)
        else:
            cfg.pop('autorole', None)
            self._save()
            await interaction.response.send_message("✅ Auto-role disabled.", ephemeral=True)

    @app_commands.command(name="welcome-test", description="👋 Test your welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_test(self, interaction: discord.Interaction):
        cfg = self._guild(interaction.guild.id)
        if not cfg.get('welcome_channel'):
            return await interaction.response.send_message("❌ No welcome channel set. Use `/welcome-set` first.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await self._send_embed(interaction.user, cfg, 'welcome')
        await interaction.followup.send("✅ Test welcome sent!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
