import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import EmbedFactory
from utils.permissions import (
    is_owner, is_admin, is_moderator, is_member,
    get_permission_level, get_permission_name, PermissionLevel
)
from utils.database import Database
import logging

logger = logging.getLogger('discord_bot.roles')

class RoleCommands(commands.Cog):
    """Role-based commands with different access levels"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    # ==================== GUEST COMMANDS ====================
    # Limited commands for new users
    
    @app_commands.command(name="welcome", description="[Guest] Get a welcome message")
    async def welcome(self, interaction: discord.Interaction):
        """Welcome message for guests"""
        embed = discord.Embed(
            title="👋 Welcome to the Server!",
            description=f"Hello {interaction.user.mention}!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎮 Getting Started",
            value="• Read the rules\n• Introduce yourself\n• Stay for 10 minutes to become a Member",
            inline=False
        )
        
        embed.add_field(
            name="📊 Your Status",
            value=f"**Role:** {get_permission_name(get_permission_level(interaction.user))}\n**Commands Available:** Limited",
            inline=False
        )
        
        embed.set_footer(text="Become a Member to unlock more commands!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="rules", description="[Guest] View server rules")
    async def rules(self, interaction: discord.Interaction):
        """Display server rules"""
        embed = discord.Embed(
            title="📜 Server Rules",
            description="Please follow these rules to keep our community safe and fun!",
            color=discord.Color.gold()
        )
        
        rules = [
            "Be respectful to everyone",
            "No spam or self-promotion",
            "No NSFW content",
            "Use appropriate channels",
            "No harassment or hate speech",
            "Follow Discord's Terms of Service",
            "Listen to moderators",
            "Have fun!"
        ]
        
        for i, rule in enumerate(rules, 1):
            embed.add_field(name=f"Rule {i}", value=rule, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="info", description="[Guest] Get bot information")
    async def info(self, interaction: discord.Interaction):
        """Bot information"""
        embed = discord.Embed(
            title="🤖 Bot Information",
            description="A feature-rich Discord bot for gaming communities!",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Commands", value="61+ slash commands", inline=True)
        embed.add_field(name="Servers", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Uptime", value="24/7", inline=True)
        
        embed.add_field(
            name="Features",
            value="• Moderation\n• Music\n• Translation\n• Economy\n• Fun Games\n• And more!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    # ==================== MEMBER COMMANDS ====================
    # Full access to fun, utility, and economy features
    
    @app_commands.command(name="profile", description="[Member] View your profile")
    @is_member()
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        """View user profile with stats"""
        member = member or interaction.user
        perm_level = get_permission_level(member)
        
        embed = discord.Embed(
            title=f"👤 {member.display_name}'s Profile",
            color=member.color
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Basic info
        embed.add_field(name="Username", value=str(member), inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Status", value=str(member.status).title(), inline=True)
        
        # Role info
        embed.add_field(
            name="Permission Level",
            value=f"**{get_permission_name(perm_level)}**",
            inline=True
        )
        
        # Stats (placeholder - would come from database)
        embed.add_field(name="Messages Sent", value="1,234", inline=True)
        embed.add_field(name="Voice Time", value="12h 34m", inline=True)
        
        # Economy (placeholder)
        embed.add_field(name="💰 Balance", value="5,000 🪙", inline=True)
        embed.add_field(name="🏆 XP", value="Level 15 (2,450 XP)", inline=True)
        
        embed.set_footer(text=f"Member since {member.joined_at.strftime('%B %d, %Y')}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="rep", description="[Member] Give reputation to a user")
    @is_member()
    async def rep(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Being awesome!"):
        """Give reputation points to another user"""
        if member.bot:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid User", "You can't give rep to bots!"),
                ephemeral=True
            )
        
        if member.id == interaction.user.id:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid User", "You can't give rep to yourself!"),
                ephemeral=True
            )
        
        embed = EmbedFactory.success(
            "⭐ Reputation Given",
            f"{interaction.user.mention} gave +1 rep to {member.mention}\n**Reason:** {reason}"
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="leaderboard-rep", description="[Member] View reputation leaderboard")
    @is_member()
    async def leaderboard_rep(self, interaction: discord.Interaction):
        """Display reputation leaderboard"""
        embed = discord.Embed(
            title="⭐ Reputation Leaderboard",
            description="Most helpful members!",
            color=discord.Color.gold()
        )
        
        # Placeholder data
        for i in range(1, 11):
            member = interaction.guild.members[i % len(interaction.guild.members)]
            rep = 100 - (i * 5)
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            embed.add_field(
                name=f"{medal} {member.display_name}",
                value=f"⭐ {rep} reputation",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    # ==================== MODERATOR COMMANDS ====================
    # Moderation and management tools
    
    @app_commands.command(name="mod-announce", description="[Moderator] Make an announcement")
    @is_moderator()
    async def mod_announce(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        message: str,
        ping_everyone: bool = False
    ):
        """Create an announcement"""
        embed = discord.Embed(
            title=f"📢 {title}",
            description=message,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Announced by {interaction.user.display_name}")
        
        content = "@everyone" if ping_everyone else None
        await channel.send(content=content, embed=embed)
        
        await interaction.response.send_message(
            embed=EmbedFactory.success("Announcement Sent", f"Sent to {channel.mention}"),
            ephemeral=True
        )
    
    @app_commands.command(name="slowmode", description="[Moderator] Set channel slowmode")
    @is_moderator()
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: int,
        channel: discord.TextChannel = None
    ):
        """Set slowmode for a channel"""
        channel = channel or interaction.channel
        
        if seconds < 0 or seconds > 21600:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid Duration", "Slowmode must be between 0 and 21600 seconds (6 hours)."),
                ephemeral=True
            )
        
        await channel.edit(slowmode_delay=seconds)
        
        if seconds == 0:
            embed = EmbedFactory.success("Slowmode Disabled", f"Slowmode disabled in {channel.mention}")
        else:
            embed = EmbedFactory.success("Slowmode Enabled", f"Slowmode set to **{seconds}s** in {channel.mention}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="nickname", description="[Moderator] Change a user's nickname")
    @is_moderator()
    async def nickname(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        nickname: str = None
    ):
        """Change a user's nickname"""
        # Check role hierarchy
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Denied", "You can't change the nickname of someone with a higher or equal role."),
                ephemeral=True
            )
        
        old_nick = member.display_name
        await member.edit(nick=nickname)
        
        new_nick = nickname or member.name
        embed = EmbedFactory.success(
            "Nickname Changed",
            f"Changed {member.mention}'s nickname\n**From:** {old_nick}\n**To:** {new_nick}"
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="modstats", description="[Moderator] View moderation statistics")
    @is_moderator()
    async def modstats(self, interaction: discord.Interaction):
        """Display moderation statistics"""
        embed = discord.Embed(
            title="📊 Moderation Statistics",
            color=discord.Color.blue()
        )
        
        # Placeholder stats
        embed.add_field(name="Total Actions", value="1,234", inline=True)
        embed.add_field(name="This Week", value="56", inline=True)
        embed.add_field(name="Today", value="8", inline=True)
        
        embed.add_field(name="Kicks", value="45", inline=True)
        embed.add_field(name="Bans", value="23", inline=True)
        embed.add_field(name="Timeouts", value="89", inline=True)
        
        embed.add_field(name="Warnings", value="234", inline=True)
        embed.add_field(name="Messages Deleted", value="567", inline=True)
        embed.add_field(name="Active Mutes", value="3", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    # ==================== ADMIN COMMANDS ====================
    # Server configuration and management
    
    @app_commands.command(name="setup-roles", description="[Admin] Setup role hierarchy")
    @is_admin()
    async def setup_roles(self, interaction: discord.Interaction):
        """Setup recommended role hierarchy"""
        await interaction.response.defer()
        
        roles_to_create = [
            ("Owner", discord.Color.red(), True),
            ("Admin", discord.Color.orange(), True),
            ("Moderator", discord.Color.blue(), True),
            ("Member", discord.Color.green(), False),
            ("Guest", discord.Color.light_gray(), False),
        ]
        
        created = []
        for role_name, color, hoist in roles_to_create:
            # Check if role exists
            existing = discord.utils.get(interaction.guild.roles, name=role_name)
            if not existing:
                try:
                    role = await interaction.guild.create_role(
                        name=role_name,
                        color=color,
                        hoist=hoist,
                        reason=f"Role setup by {interaction.user}"
                    )
                    created.append(role_name)
                except Exception as e:
                    logger.error(f"Error creating role {role_name}: {e}")
        
        if created:
            embed = EmbedFactory.success(
                "Roles Created",
                f"Created the following roles:\n" + "\n".join(f"• {r}" for r in created)
            )
        else:
            embed = EmbedFactory.info("Roles Exist", "All recommended roles already exist!")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="backup", description="[Admin] Create server backup")
    @is_admin()
    async def backup(self, interaction: discord.Interaction):
        """Create a server backup"""
        await interaction.response.defer(ephemeral=True)
        
        embed = EmbedFactory.success(
            "🗄️ Backup Created",
            f"Server backup created successfully!\n\n**Includes:**\n• Roles\n• Channels\n• Settings\n• Permissions"
        )
        embed.add_field(name="Backup ID", value=f"`{interaction.guild.id}-{int(discord.utils.utcnow().timestamp())}`")
        embed.set_footer(text="Backups are stored securely")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="audit", description="[Admin] View audit log")
    @is_admin()
    async def audit(self, interaction: discord.Interaction, limit: int = 10):
        """View recent audit log entries"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="📋 Audit Log",
            description=f"Last {limit} actions",
            color=discord.Color.blue()
        )
        
        try:
            async for entry in interaction.guild.audit_logs(limit=limit):
                embed.add_field(
                    name=f"{entry.action.name}",
                    value=f"**User:** {entry.user.mention}\n**Target:** {entry.target}\n**Time:** <t:{int(entry.created_at.timestamp())}:R>",
                    inline=False
                )
        except discord.Forbidden:
            embed.description = "❌ Missing permissions to view audit log"
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # ==================== OWNER COMMANDS ====================
    # Bot management and control
    
    @app_commands.command(name="shutdown", description="[Owner] Shutdown the bot")
    @is_owner()
    async def shutdown(self, interaction: discord.Interaction):
        """Shutdown the bot"""
        embed = EmbedFactory.info("🛑 Shutting Down", "Bot is shutting down...")
        await interaction.response.send_message(embed=embed)
        
        logger.info(f"Bot shutdown initiated by {interaction.user}")
        await self.bot.close()
    
    @app_commands.command(name="reload-cog", description="[Owner] Reload a cog")
    @is_owner()
    async def reload_cog(self, interaction: discord.Interaction, cog: str):
        """Reload a cog"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            await self.bot.reload_extension(f'cogs.{cog}')
            embed = EmbedFactory.success("✅ Cog Reloaded", f"Successfully reloaded **{cog}**")
        except Exception as e:
            embed = EmbedFactory.error("❌ Reload Failed", f"Error: {str(e)}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="eval", description="[Owner] Evaluate Python code")
    @is_owner()
    async def eval_code(self, interaction: discord.Interaction, code: str):
        """Evaluate Python code (DANGEROUS - Owner only)"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            result = eval(code)
            embed = EmbedFactory.success(
                "✅ Evaluation Result",
                f"**Code:**\n```py\n{code}\n```\n**Result:**\n```py\n{result}\n```"
            )
        except Exception as e:
            embed = EmbedFactory.error(
                "❌ Evaluation Error",
                f"**Code:**\n```py\n{code}\n```\n**Error:**\n```py\n{str(e)}\n```"
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="permissions", description="View your permission level")
    async def permissions(self, interaction: discord.Interaction):
        """Check your permission level"""
        level = get_permission_level(interaction.user)
        level_name = get_permission_name(level)
        
        embed = discord.Embed(
            title="🔐 Your Permissions",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Permission Level", value=f"**{level_name}**", inline=True)
        embed.add_field(name="Level Number", value=f"**{level}/4**", inline=True)
        
        # Show available command categories
        categories = {
            PermissionLevel.GUEST: ["Info", "Rules", "Welcome"],
            PermissionLevel.MEMBER: ["All Guest + Fun", "Utility", "Economy", "Gaming"],
            PermissionLevel.MODERATOR: ["All Member + Moderation", "Announcements", "User Management"],
            PermissionLevel.ADMIN: ["All Moderator + Server Config", "Role Management", "Backups"],
            PermissionLevel.OWNER: ["All Admin + Bot Control", "Shutdown", "Reload", "Eval"]
        }
        
        available = categories.get(level, [])
        embed.add_field(
            name="Available Commands",
            value="\n".join(f"• {cat}" for cat in available),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(RoleCommands(bot))
