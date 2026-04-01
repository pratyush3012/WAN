"""
WAN Bot - Web Dashboard Command Cog
Generates signed auth tokens that work on Render (cross-process).
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import os
import sys

# Add project root to path so we can import the token helper
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'http://localhost:5000').rstrip('/')


def _get_token_maker():
    """Lazy-import _make_auth_token from web_dashboard_enhanced to avoid circular imports."""
    try:
        from web_dashboard_enhanced import _make_auth_token
        return _make_auth_token
    except Exception:
        return None


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
    async def web_dashboard(self, interaction: discord.Interaction):
        role = self.get_user_role(interaction.user)

        # Build signed token (works on Render — no shared memory needed)
        make_token = _get_token_maker()
        if make_token:
            token = make_token(
                user_id=str(interaction.user.id),
                guild_id=str(interaction.guild.id),
                username=interaction.user.display_name,
                role=role,
            )
            link = f"{DASHBOARD_URL}/auth?token={token}"
        else:
            # Fallback: direct login page
            link = f"{DASHBOARD_URL}/login"

        role_icons = {'admin':'⚙️','manager':'🔧','moderator':'🛡️','helper':'🤝','member':'👤'}
        embed = discord.Embed(
            title="🌐 WAN Bot Dashboard",
            description=f"Your personalized dashboard is ready, {interaction.user.mention}!",
            color=discord.Color.from_rgb(102, 126, 234)
        )
        embed.add_field(name="🎭 Role", value=f"{role_icons.get(role,'👤')} {role.title()}", inline=True)
        embed.add_field(name="⏰ Expires", value="24 hours", inline=True)
        embed.add_field(name="🔗 Open Dashboard", value=f"[Click here]({link})", inline=False)
        embed.set_footer(text="Link is personal — don't share it", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Keep verify_token for legacy fallback in /auth route
    async def verify_token(self, token: str):
        return None  # legacy tokens no longer issued


async def setup(bot):
    await bot.add_cog(WebDashboardCog(bot))
