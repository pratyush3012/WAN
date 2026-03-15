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
    
    # ==================== MODERATOR COMMANDS ====================
    # Moderation and management tools
    
    # mod-announce removed — use /announce from dashboard or cogs/announce
    
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
    
    # modstats removed — use dashboard analytics instead
    
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
    
    # backup removed — placeholder only, no real functionality
    
    # audit removed — use dashboard audit log instead
    
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
    
    # reload-cog removed — use /reload in admin.py instead
    
    # eval removed — security risk
    
    # permissions removed — low value, covered by Discord's own UI

async def setup(bot):
    await bot.add_cog(RoleCommands(bot))
