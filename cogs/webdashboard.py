"""
WAN Bot - Web Dashboard Command Cog
Opens external web dashboard with role-based access
"""

import discord
from discord.ext import commands
from discord import app_commands
import secrets
import hashlib
from datetime import datetime, timedelta
import webbrowser
import os

class WebDashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.access_tokens = {}  # {token: {user_id, guild_id, role, expires}}
        self.dashboard_url = os.getenv('DASHBOARD_URL', 'http://localhost:5000')
    
    def generate_access_token(self, user_id: int, guild_id: int, role: str) -> str:
        """Generate secure access token for user"""
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=24)
        
        self.access_tokens[token] = {
            'user_id': user_id,
            'guild_id': guild_id,
            'role': role,
            'expires': expires,
            'created_at': datetime.utcnow()
        }
        
        return token
    
    def get_user_role(self, member: discord.Member) -> str:
        """Determine user's dashboard role based on Discord permissions"""
        if member.guild_permissions.administrator:
            return 'admin'
        elif member.guild_permissions.manage_guild:
            return 'manager'
        elif member.guild_permissions.moderate_members:
            return 'moderator'
        elif member.guild_permissions.manage_messages:
            return 'helper'
        else:
            return 'member'
    
    @app_commands.command(name="web", description="🌐 Open the ultimate web dashboard in your browser")
    async def web_dashboard(self, interaction: discord.Interaction):
        """Open web dashboard with personalized access"""
        
        # Get user's role
        role = self.get_user_role(interaction.user)
        
        # Generate secure access token
        token = self.generate_access_token(
            interaction.user.id,
            interaction.guild.id,
            role
        )
        
        # Create dashboard URL with token
        dashboard_url = f"{self.dashboard_url}/auth?token={token}"
        
        # Create beautiful embed
        embed = discord.Embed(
            title="🌐 WAN Bot Ultimate Dashboard",
            description="**Your personalized dashboard is ready!**",
            color=discord.Color.from_rgb(102, 126, 234)
        )
        
        # Role-specific features
        role_features = {
            'admin': [
                "✅ Full server control",
                "✅ All moderation tools",
                "✅ Analytics & insights",
                "✅ Bot configuration",
                "✅ User management",
                "✅ Security settings",
                "✅ Backup & restore",
                "✅ Advanced features"
            ],
            'manager': [
                "✅ Server management",
                "✅ Moderation tools",
                "✅ Analytics viewing",
                "✅ Member management",
                "✅ Channel control",
                "✅ Role management"
            ],
            'moderator': [
                "✅ Moderation tools",
                "✅ Member warnings",
                "✅ Message management",
                "✅ Basic analytics",
                "✅ Ticket handling"
            ],
            'helper': [
                "✅ View analytics",
                "✅ Ticket support",
                "✅ Message viewing",
                "✅ Member info"
            ],
            'member': [
                "✅ View profile",
                "✅ Check stats",
                "✅ View leaderboards",
                "✅ Manage settings"
            ]
        }
        
        features = role_features.get(role, role_features['member'])
        
        embed.add_field(
            name=f"🎭 Your Role: {role.title()}",
            value="\n".join(features[:4]),
            inline=False
        )
        
        if len(features) > 4:
            embed.add_field(
                name="✨ Additional Features",
                value="\n".join(features[4:]),
                inline=False
            )
        
        embed.add_field(
            name="🔗 Access Link",
            value=f"[Click here to open dashboard]({dashboard_url})",
            inline=False
        )
        
        embed.add_field(
            name="⏰ Session Duration",
            value="```24 hours```",
            inline=True
        )
        
        embed.add_field(
            name="🔒 Security",
            value="```Encrypted & Secure```",
            inline=True
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(
            text=f"Requested by {interaction.user.display_name} • Secure Token Generated",
            icon_url=interaction.user.display_avatar.url
        )
        embed.timestamp = datetime.utcnow()
        
        # Send ephemeral message (only visible to user)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Log access
        print(f"🌐 Dashboard access granted to {interaction.user} ({role}) in {interaction.guild.name}")
    
    @app_commands.command(name="backend", description="🖥️ Open the bot dashboard in your browser")
    async def backend(self, interaction: discord.Interaction):
        """Send a clickable link to the dashboard"""
        url = self.dashboard_url

        embed = discord.Embed(
            title="🖥️ WAN Bot Dashboard",
            description=f"Click the button below to open the dashboard.\n\n🔗 **[Open Dashboard]({url})**",
            color=discord.Color.from_rgb(102, 126, 234)
        )
        embed.add_field(name="📍 URL", value=f"`{url}`", inline=False)
        embed.set_footer(text="Only visible to you", icon_url=self.bot.user.display_avatar.url)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Open Dashboard", url=url, emoji="🖥️", style=discord.ButtonStyle.link))

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # web-status removed to stay under 100 command limit
    
    async def verify_token(self, token: str) -> dict:
        """Verify access token and return user info"""
        if token not in self.access_tokens:
            return None
        
        token_data = self.access_tokens[token]
        
        # Check if expired
        if token_data['expires'] < datetime.utcnow():
            del self.access_tokens[token]
            return None
        
        return token_data
    
    async def revoke_token(self, token: str):
        """Revoke access token"""
        if token in self.access_tokens:
            del self.access_tokens[token]

async def setup(bot):
    await bot.add_cog(WebDashboardCog(bot))
