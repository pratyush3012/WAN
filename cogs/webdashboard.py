"""
WAN Bot - Web Dashboard Command Cog
Generates signed auth tokens that work on Render (cross-process).
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import os
import logging

from utils.discord_interaction import send_response

logger = logging.getLogger(__name__)

DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'http://localhost:5000').rstrip('/')
if not os.getenv('DASHBOARD_URL'):
    logger.warning(
        "DASHBOARD_URL is not set — /web links default to localhost. "
        "Set DASHBOARD_URL=https://wan-ujtv.onrender.com on Render."
    )
SECRET_KEY    = os.getenv('DASHBOARD_SECRET_KEY', 'wan-bot-dashboard-secret-key-change-me-in-env')


def _make_token(user_id: str, guild_id: str, username: str, role: str) -> str:
    """Build a signed token without importing web_dashboard_enhanced (avoids circular import)."""
    from itsdangerous import URLSafeTimedSerializer
    s = URLSafeTimedSerializer(SECRET_KEY, salt='discord-auth')
    return s.dumps({'uid': user_id, 'gid': guild_id, 'un': username, 'role': role})


class WebDashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_role(self, member: discord.Member) -> str:
        if member.guild_permissions.administrator:
            return 'admin'
        elif member.guild_permissions.manage_guild:
            return 'manager'
        elif member.guild_permissions.moderate_members:
            return 'moderator'
        elif member.guild_permissions.manage_messages:
            return 'helper'
        return 'member'

    @app_commands.command(name="web", description="🌐 Open the WAN Bot dashboard")
    @app_commands.guild_only()
    async def web_dashboard(self, interaction: discord.Interaction):
        # interaction.user always works; interaction.member may be None
        user = interaction.user
        guild = interaction.guild

        # Determine role from permissions
        try:
            member = guild.get_member(user.id) if guild else None
            role = self.get_user_role(member) if member else 'member'
        except Exception:
            role = 'member'

        try:
            token = _make_token(
                user_id=str(user.id),
                guild_id=str(guild.id) if guild else '0',
                username=user.display_name,
                role=role,
            )
            link = f"{DASHBOARD_URL}/auth?token={token}"
        except Exception as e:
            logger.error(f"/web token error: {e}")
            link = f"{DASHBOARD_URL}/login"

        role_icons = {'admin':'⚙️','manager':'🔧','moderator':'🛡️','helper':'🤝','member':'👤'}
        embed = discord.Embed(
            title="🌐 WAN Bot Dashboard",
            description=f"Your dashboard is ready, {user.mention}!",
            color=discord.Color.from_rgb(102, 126, 234)
        )
        embed.add_field(name="Role", value=f"{role_icons.get(role,'👤')} {role.title()}", inline=True)
        embed.add_field(name="Expires", value="24 hours", inline=True)
        embed.add_field(name="🔗 Open Dashboard", value=f"[Click here]({link})", inline=False)
        embed.set_footer(text="This link is personal — don't share it",
                         icon_url=user.display_avatar.url)
        embed.timestamp = datetime.now(timezone.utc)
        await send_response(interaction, embed=embed, ephemeral=True)

    async def verify_token(self, token: str):
        return None  # legacy — no longer used


async def setup(bot):
    await bot.add_cog(WebDashboardCog(bot))
