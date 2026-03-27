import discord
from discord import app_commands
from discord.ext import commands
from utils.database import Database

class Automation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(name="announce", description="📢 Send an announcement to a channel")
    @app_commands.describe(channel="Channel to announce in", title="Announcement title", message="Announcement content")
    @app_commands.checks.has_permissions(administrator=True)
    async def announce(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
        embed = discord.Embed(title=f"📢 {title}", description=message, color=discord.Color.blue())
        embed.set_footer(text=f"Announced by {interaction.user.display_name}")
        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Announcement sent to {channel.mention}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Automation(bot))
