import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.permissions import is_admin
from datetime import datetime

logger = logging.getLogger('discord_bot.suggestions')

class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.suggestion_channels = {}
        self.suggestion_counter = {}
    
    @app_commands.command(name="suggest", description="Submit a suggestion")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        """Submit a suggestion with beautiful visuals"""
        from utils.visuals import Emojis, VisualEffects

        guild_id = interaction.guild.id

        if guild_id not in self.suggestion_channels:
            return await interaction.response.send_message(
                "❌ Suggestion system not set up! Ask an admin to run `/suggest-setup`",
                ephemeral=True
            )

        if len(suggestion) < 10:
            return await interaction.response.send_message(
                "❌ Suggestion must be at least 10 characters!",
                ephemeral=True
            )

        if len(suggestion) > 1000:
            return await interaction.response.send_message(
                "❌ Suggestion must be 1000 characters or less!",
                ephemeral=True
            )

        # Increment counter
        self.suggestion_counter[guild_id] = self.suggestion_counter.get(guild_id, 0) + 1
        suggestion_num = self.suggestion_counter[guild_id]

        # Get suggestion channel
        channel = self.bot.get_channel(self.suggestion_channels[guild_id])
        if not channel:
            return await interaction.response.send_message(
                "❌ Suggestion channel not found!",
                ephemeral=True
            )

        # Create beautiful suggestion embed
        embed = discord.Embed(
            title=f"💡 Suggestion #{suggestion_num}",
            description=suggestion,
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        embed.set_author(
            name=f"Suggested by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )

        # Add visual voting section
        separator = VisualEffects.create_separator("arrows")
        embed.add_field(
            name=separator,
            value=f"👍 **Upvote** if you like this idea!\n👎 **Downvote** if you don't like it",
            inline=False
        )

        embed.add_field(
            name=f"{Emojis.INFO} Status",
            value=f"```🔵 Pending Review```",
            inline=True
        )

        embed.add_field(
            name=f"{Emojis.CHART} Votes",
            value=f"```👍 0 | 👎 0```",
            inline=True
        )

        embed.set_footer(text=f"Suggestion ID: {suggestion_num} • Vote with reactions below!")

        # Post suggestion
        msg = await channel.send(embed=embed)

        # Add voting reactions
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

        # Send confirmation with visual
        confirm_embed = discord.Embed(
            title=f"{Emojis.SUCCESS} Suggestion Submitted!",
            description=f"Your suggestion has been posted in {channel.mention}",
            color=discord.Color.green()
        )
        confirm_embed.add_field(
            name=f"{Emojis.TARGET} Suggestion #{suggestion_num}",
            value=f"```{suggestion[:100]}{'...' if len(suggestion) > 100 else ''}```",
            inline=False
        )
        confirm_embed.set_footer(text="💡 The community will vote on your suggestion!")

        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

    @app_commands.command(name="suggest-setup", description="[Admin] Set up the suggestion channel")
    @is_admin()
    async def suggest_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set up suggestion channel"""
        self.suggestion_channels[interaction.guild.id] = channel.id
        embed = discord.Embed(
            title="✅ Suggestion System Enabled",
            description=f"Suggestions will be posted in {channel.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="How to use", value="Members can use `/suggest <idea>` to submit suggestions.", inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Suggestions(bot))
