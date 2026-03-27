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

    @app_commands.command(name="addrole", description="➕ Add a role to a member")
    @app_commands.describe(member="Member to add role to", role="Role to add")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def addrole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Error", "I cannot manage this role"), ephemeral=True)
        await member.add_roles(role)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Role Added", f"Added {role.mention} to {member.mention}"))

    @app_commands.command(name="removerole", description="➖ Remove a role from a member")
    @app_commands.describe(member="Member to remove role from", role="Role to remove")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def removerole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Permission Error", "I cannot manage this role"), ephemeral=True)
        await member.remove_roles(role)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Role Removed", f"Removed {role.mention} from {member.mention}"))

    @app_commands.command(name="setlogchannel", description="📋 Set the log channel")
    @app_commands.describe(channel="Channel to send logs to")
    @app_commands.checks.has_permissions(administrator=True)
    async def setlogchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.db.update_guild_config(interaction.guild.id, log_channel=channel.id)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Log Channel Set", f"Logs will be sent to {channel.mention}"), ephemeral=True)

    @app_commands.command(name="config", description="⚙️ Show server configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        config = await self.db.get_guild_config(interaction.guild.id)
        embed = discord.Embed(title=f"⚙️ {interaction.guild.name} Configuration", color=discord.Color.blue())
        embed.add_field(name="Welcome Channel", value=f"<#{config.welcome_channel}>" if config.welcome_channel else "Not set", inline=True)
        embed.add_field(name="Log Channel", value=f"<#{config.log_channel}>" if config.log_channel else "Not set", inline=True)
        embed.add_field(name="Auto Role", value=f"<@&{config.auto_role}>" if config.auto_role else "Not set", inline=True)
        embed.add_field(name="XP System", value="✅" if config.xp_enabled else "❌", inline=True)
        embed.add_field(name="Anti-Spam", value="✅" if config.anti_spam else "❌", inline=True)
        embed.add_field(name="Anti-Raid", value="✅" if config.anti_raid else "❌", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reload", description="🔄 Reload a cog (owner only)")
    @app_commands.describe(cog="Cog name to reload e.g. music")
    @app_commands.checks.has_permissions(administrator=True)
    async def reload(self, interaction: discord.Interaction, cog: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await interaction.response.send_message(
                embed=EmbedFactory.success("Cog Reloaded", f"Reloaded `{cog}`"), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                embed=EmbedFactory.error("Reload Failed", str(e)), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
