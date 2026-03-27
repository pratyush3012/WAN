import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import EmbedFactory
from utils.permissions import is_owner, is_admin, is_moderator
from utils.database import Database
import logging

logger = logging.getLogger('discord_bot.roles')

class RoleCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(name="slowmode", description="⏱️ Set slowmode for a channel")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)", channel="Channel (defaults to current)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int, channel: discord.TextChannel = None):
        channel = channel or interaction.channel
        if not 0 <= seconds <= 21600:
            return await interaction.response.send_message("❌ Must be 0–21600 seconds.", ephemeral=True)
        await channel.edit(slowmode_delay=seconds)
        msg = f"Slowmode disabled in {channel.mention}" if seconds == 0 else f"Slowmode set to **{seconds}s** in {channel.mention}"
        await interaction.response.send_message(embed=EmbedFactory.success("Slowmode", msg), ephemeral=True)

    @app_commands.command(name="nickname", description="✏️ Change a member's nickname")
    @app_commands.describe(member="Member to rename", nickname="New nickname (leave blank to reset)")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nickname(self, interaction: discord.Interaction, member: discord.Member, nickname: str = None):
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ Can't change nickname of someone with equal/higher role.", ephemeral=True)
        old = member.display_name
        await member.edit(nick=nickname)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Nickname Changed", f"{member.mention}: **{old}** → **{nickname or member.name}**"),
            ephemeral=True)

    # setup-roles removed to stay under 100 slash command limit


async def setup(bot):
    await bot.add_cog(RoleCommands(bot))
