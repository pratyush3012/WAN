"""
WAN Bot - Badge System
Per-server configurable badges with branding & marketing links.
Default brand: VAMP clan. Each server can override via /badge-setup.
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
from typing import Optional
import asyncio
import json
import os
import logging

logger = logging.getLogger("discord_bot.badges")

# ── Default brand config (VAMP clan) ────────────────────────────────────────
DEFAULT_BRAND = {
    "name": "VAMP",
    "url": os.getenv("CLAN_URL", "https://discord.gg/vamp"),   # set in .env
    "color": 0x8B0000,   # deep red
}

# Badge definitions — emoji, label, color, priority (lower = higher rank)
# Role names are kept SHORT so they display as compact tags next to usernames
BADGE_DEFS = {
    "owner":     {"emoji": "👑", "label": "Owner",     "color": 0xE74C3C, "priority": 0, "tag": "👑"},
    "admin":     {"emoji": "⚔️", "label": "Admin",     "color": 0xE67E22, "priority": 1, "tag": "⚔️"},
    "manager":   {"emoji": "🛡️", "label": "Manager",   "color": 0xF1C40F, "priority": 2, "tag": "🛡️"},
    "moderator": {"emoji": "🔨", "label": "Mod",       "color": 0x2ECC71, "priority": 3, "tag": "🔨"},
    "helper":    {"emoji": "💚", "label": "Helper",    "color": 0x1ABC9C, "priority": 4, "tag": "💚"},
    "vip":       {"emoji": "⭐", "label": "VIP",       "color": 0xFFD700, "priority": 5, "tag": "⭐"},
    "booster":   {"emoji": "💎", "label": "Booster",   "color": 0xFF69B4, "priority": 6, "tag": "💎"},
    "member":    {"emoji": "✅", "label": "Member",    "color": 0x3498DB, "priority": 7, "tag": "✅"},
}

ROLE_KEYWORDS = {
    "owner":     ["owner", "founder"],
    "admin":     ["admin", "administrator"],
    "manager":   ["manager", "management"],
    "moderator": ["mod", "moderator"],
    "helper":    ["helper", "support", "staff"],
    "vip":       ["vip", "premium", "elite"],
    "booster":   ["booster", "boost"],
}

CONFIG_FILE = "badge_config.json"

def load_configs() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_configs(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


class BadgeSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.configs = load_configs()   # {guild_id: {name, url, color}}
        self.auto_sync.start()

    def cog_unload(self):
        self.auto_sync.cancel()

    # ── Config helpers ───────────────────────────────────────────────────────

    def get_brand(self, guild_id: int) -> dict:
        return self.configs.get(str(guild_id), DEFAULT_BRAND)

    def role_name(self, guild_id: int, badge_type: str) -> str:
        """Short clan tag role — e.g. ⚔️ VAMP, 🛡️ VAMP, 👑 VAMP"""
        brand = self.get_brand(guild_id)
        info = BADGE_DEFS[badge_type]
        return f"{info['tag']} {brand['name']}"

    def all_badge_role_names(self, guild_id: int) -> set:
        return {self.role_name(guild_id, k) for k in BADGE_DEFS}

    # ── Badge detection ──────────────────────────────────────────────────────

    def get_badge_type(self, member: discord.Member) -> Optional[str]:
        if member.bot:
            return None
        if member.id == member.guild.owner_id:
            return "owner"
        perms = member.guild_permissions
        if perms.administrator:
            return "admin"
        if perms.manage_guild:
            return "manager"
        if perms.moderate_members or perms.kick_members:
            return "moderator"
        if perms.manage_messages:
            return "helper"
        if member.premium_since:
            return "booster"
        role_names_lower = [r.name.lower() for r in member.roles]
        for bt, keywords in ROLE_KEYWORDS.items():
            if any(kw in rn for kw in keywords for rn in role_names_lower):
                return bt
        if len(member.roles) > 1:
            return "member"
        return None

    # ── Role management ──────────────────────────────────────────────────────

    async def ensure_badge_roles(self, guild: discord.Guild):
        """Create all badge roles for this guild if missing."""
        for bt in BADGE_DEFS:
            rname = self.role_name(guild.id, bt)
            if not discord.utils.get(guild.roles, name=rname):
                try:
                    await guild.create_role(
                        name=rname,
                        color=discord.Color(BADGE_DEFS[bt]["color"]),
                        hoist=True,
                        mentionable=False,
                        reason="WAN Bot badge role"
                    )
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"[badges] Could not create {rname}: {e}")

    async def assign_badge(self, member: discord.Member):
        """Assign the correct badge role, remove stale ones."""
        if member.bot:
            return
        bt = self.get_badge_type(member)
        all_badge_names = self.all_badge_role_names(member.guild.id)

        # Remove stale badge roles
        stale = [r for r in member.roles if r.name in all_badge_names]
        if stale:
            try:
                await member.remove_roles(*stale, reason="Badge update")
                await asyncio.sleep(0.3)
            except Exception:
                pass

        if not bt:
            return

        target_name = self.role_name(member.guild.id, bt)
        role = discord.utils.get(member.guild.roles, name=target_name)
        if not role:
            await self.ensure_badge_roles(member.guild)
            role = discord.utils.get(member.guild.roles, name=target_name)
        if role:
            try:
                await member.add_roles(role, reason="Badge assigned")
            except Exception as e:
                print(f"[badges] Could not assign {target_name} to {member}: {e}")

    # ── Events ───────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.assign_badge(member)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles or before.premium_since != after.premium_since:
            await self.assign_badge(after)

    # ── Background sync every 30 min ─────────────────────────────────────────

    @tasks.loop(hours=2)
    async def auto_sync(self):
        """
        Rate-limit-safe badge sync — runs every 2 hours.
        Only touches members whose badge is actually wrong.
        10s between API calls, 60s between guilds.
        """
        for guild in self.bot.guilds:
            try:
                await self.ensure_badge_roles(guild)
                await asyncio.sleep(2)
                all_badge_names = self.all_badge_role_names(guild.id)
                for member in guild.members:
                    if member.bot:
                        continue
                    bt = self.get_badge_type(member)
                    current_badges = [r for r in member.roles if r.name in all_badge_names]
                    expected_name = self.role_name(guild.id, bt) if bt else None
                    # Skip if already correct — no API call needed
                    if expected_name:
                        if len(current_badges) == 1 and current_badges[0].name == expected_name:
                            continue
                    elif not current_badges:
                        continue
                    await self.assign_badge(member)
                    await asyncio.sleep(10)  # 10s between role changes
            except Exception as e:
                logger.warning(f"[badges] auto_sync error for {guild.name}: {e}")
            await asyncio.sleep(60)  # 60s between guilds

    @auto_sync.before_loop
    async def before_sync(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(120)  # wait 2 min after startup before first sync

    # ── Commands ─────────────────────────────────────────────────────────────

    @app_commands.command(name="badge", description="View your badge or another member's badge")
    async def view_badge(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        bt = self.get_badge_type(target)
        info = BADGE_DEFS.get(bt)
        brand = self.get_brand(interaction.guild.id)

        color = discord.Color(info["color"]) if info else discord.Color.greyple()
        embed = discord.Embed(
            title=f"{info['emoji'] if info else '👤'} {brand['name']} Badge",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        if info:
            embed.description = (
                f"## {info['emoji']} {brand['name']} {info['label']}\n"
                f"**{target.display_name}** is a verified **{brand['name']} {info['label']}**"
            )
            embed.add_field(
                name="🔗 Join the Clan",
                value=f"[Click here to join **{brand['name']}**]({brand['url']})",
                inline=False
            )
        else:
            embed.description = f"**{target.display_name}** has no badge yet.\nJoin the server and get a role!"
            embed.add_field(
                name="🔗 Join the Clan",
                value=f"[Click here to join **{brand['name']}**]({brand['url']})",
                inline=False
            )

        roles = [r.mention for r in target.roles[1:] if not any(r.name.startswith(BADGE_DEFS[k]["emoji"]) for k in BADGE_DEFS)]
        if roles:
            embed.add_field(name="Roles", value=" ".join(roles[:8]), inline=False)

        embed.set_footer(text=f"{brand['name']} • Powered by WAN Bot")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="sync-badges", description="[Admin] Assign badges to every member now")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync_badges(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.ensure_badge_roles(interaction.guild)
        count = 0
        for member in interaction.guild.members:
            await self.assign_badge(member)
            await asyncio.sleep(1.0)
            count += 1
        brand = self.get_brand(interaction.guild.id)
        await interaction.followup.send(
            f"✅ **{brand['name']}** badges synced for **{count}** members!",
            ephemeral=True
        )

    @app_commands.command(name="badge-stats", description="Badge distribution across the server")
    async def badge_stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        brand = self.get_brand(interaction.guild.id)
        counts = {k: 0 for k in BADGE_DEFS}
        guests = 0
        for m in interaction.guild.members:
            if m.bot:
                continue
            bt = self.get_badge_type(m)
            if bt:
                counts[bt] += 1
            else:
                guests += 1

        embed = discord.Embed(
            title=f"📊 {brand['name']} Badge Statistics",
            color=discord.Color(DEFAULT_BRAND["color"]),
            timestamp=datetime.utcnow()
        )
        lines = []
        total = sum(counts.values()) + guests
        for bt, info in BADGE_DEFS.items():
            n = counts[bt]
            if n:
                bar = "█" * int((n / max(total, 1)) * 20)
                lines.append(f"{info['emoji']} **{brand['name']} {info['label']}** — {n}\n`{bar}`")
        if guests:
            lines.append(f"👤 **No Badge** — {guests}")
        embed.description = "\n\n".join(lines) or "No data yet."
        embed.set_footer(text=f"Total: {total} members • {brand['name']}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="badge-setup", description="[Admin] Configure badge branding for this server")
    @app_commands.describe(
        clan_name="Your clan/community name (e.g. VAMP)",
        clan_url="Invite or website URL shown when badge is clicked",
        brand_color="Hex color for your brand (e.g. 8B0000)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def badge_setup(self, interaction: discord.Interaction, clan_name: str, clan_url: str, brand_color: str = "8B0000"):
        try:
            color = int(brand_color.lstrip("#"), 16)
        except ValueError:
            color = 0x8B0000

        self.configs[str(interaction.guild.id)] = {
            "name": clan_name,
            "url": clan_url,
            "color": color
        }
        save_configs(self.configs)

        # Recreate badge roles with new name
        await self.ensure_badge_roles(interaction.guild)

        embed = discord.Embed(
            title="✅ Badge Branding Updated",
            color=discord.Color(color),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Clan Name", value=clan_name, inline=True)
        embed.add_field(name="Clan URL", value=clan_url, inline=True)
        embed.add_field(name="Note", value="Run `/sync-badges` to apply new names to all members.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BadgeSystem(bot))
