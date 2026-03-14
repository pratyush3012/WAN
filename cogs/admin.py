import discord
from discord import app_commands
from discord.ext import commands
from utils.checks import is_admin, is_owner
from utils.embeds import EmbedFactory
from utils.database import Database

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    @app_commands.command(name="addrole", description="Give a role to a member")
    @is_admin()
    async def addrole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Error", "I cannot manage this role (it's higher than my highest role)"),
                ephemeral=True
            )
        
        await member.add_roles(role)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Role Added", f"Added {role.mention} to {member.mention}")
        )
    
    @app_commands.command(name="removerole", description="Remove a role from a member")
    @is_admin()
    async def removerole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Error", "I cannot manage this role"),
                ephemeral=True
            )
        
        await member.remove_roles(role)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Role Removed", f"Removed {role.mention} from {member.mention}")
        )
    
    @app_commands.command(name="setlogchannel", description="Set the logging channel")
    @is_admin()
    async def setlogchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.db.update_guild_config(interaction.guild.id, log_channel=channel.id)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Log Channel Set", f"Logs will be sent to {channel.mention}")
        )
    
    @app_commands.command(name="setdjrole", description="Set the DJ role for music commands")
    @is_admin()
    async def setdjrole(self, interaction: discord.Interaction, role: discord.Role):
        await self.db.update_guild_config(interaction.guild.id, dj_role=role.id)
        await interaction.response.send_message(
            embed=EmbedFactory.success("DJ Role Set", f"DJ role set to {role.mention}")
        )
    
    @app_commands.command(name="togglemodule", description="Enable or disable a bot module")
    @is_admin()
    async def togglemodule(self, interaction: discord.Interaction, module: str):
        config = await self.db.get_guild_config(interaction.guild.id)
        disabled = config.disabled_modules or []
        
        if module in disabled:
            disabled.remove(module)
            status = "enabled"
        else:
            disabled.append(module)
            status = "disabled"
        
        await self.db.update_guild_config(interaction.guild.id, disabled_modules=disabled)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Module Toggled", f"Module `{module}` has been {status}")
        )
    
    @app_commands.command(name="config", description="View server configuration")
    @is_admin()
    async def config(self, interaction: discord.Interaction):
        await interaction.response.defer()
        config = await self.db.get_guild_config(interaction.guild.id)
        
        embed = discord.Embed(
            title=f"⚙️ {interaction.guild.name} Configuration",
            color=discord.Color.blue()
        )
        
        welcome_ch = f"<#{config.welcome_channel}>" if config.welcome_channel else "Not set"
        log_ch = f"<#{config.log_channel}>" if config.log_channel else "Not set"
        dj_role = f"<@&{config.dj_role}>" if config.dj_role else "Not set"
        auto_role = f"<@&{config.auto_role}>" if config.auto_role else "Not set"
        
        embed.add_field(name="Welcome Channel", value=welcome_ch, inline=True)
        embed.add_field(name="Log Channel", value=log_ch, inline=True)
        embed.add_field(name="DJ Role", value=dj_role, inline=True)
        embed.add_field(name="Auto Role", value=auto_role, inline=True)
        embed.add_field(name="Music Volume", value=f"{config.music_volume}%", inline=True)
        embed.add_field(name="Translation", value="✅" if config.translation_enabled else "❌", inline=True)
        embed.add_field(name="XP System", value="✅" if config.xp_enabled else "❌", inline=True)
        embed.add_field(name="Anti-Spam", value="✅" if config.anti_spam else "❌", inline=True)
        embed.add_field(name="Anti-Raid", value="✅" if config.anti_raid else "❌", inline=True)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="reload", description="Reload a cog (Owner only)")
    @is_owner()
    async def reload(self, interaction: discord.Interaction, cog: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await interaction.response.send_message(
                embed=EmbedFactory.success("Cog Reloaded", f"Successfully reloaded `{cog}`"),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=EmbedFactory.error("Reload Failed", f"Error: {str(e)}"),
                ephemeral=True
            )
    
    @app_commands.command(name="sync-commands", description="Fix duplicate commands by clearing guild-specific syncs (Owner only)")
    @is_owner()
    async def sync_commands(self, interaction: discord.Interaction):
        """Clear guild-specific commands and sync globally only"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Clear guild-specific commands for all guilds
            cleared_guilds = []
            for guild in self.bot.guilds:
                try:
                    self.bot.tree.clear_commands(guild=guild)
                    await self.bot.tree.sync(guild=guild)
                    cleared_guilds.append(guild.name)
                except Exception as e:
                    pass
            
            # Sync globally
            synced = await self.bot.tree.sync()
            
            embed = discord.Embed(
                title="✅ Commands Synced",
                description=f"Successfully cleared duplicate commands and synced {len(synced)} commands globally.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Cleared Guild Commands",
                value=f"Removed duplicates from {len(cleared_guilds)} guilds",
                inline=False
            )
            embed.add_field(
                name="⚠️ Note",
                value="Global commands may take up to 1 hour to appear. Restart Discord if you still see duplicates.",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                embed=EmbedFactory.error("Sync Failed", f"Error: {str(e)}"),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Admin(bot))
