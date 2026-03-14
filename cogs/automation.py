import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.checks import is_admin
from utils.embeds import EmbedFactory
from utils.database import Database
import json

class Automation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = await self.db.get_guild_config(member.guild.id)
        
        # Auto-role
        if config.auto_role:
            role = member.guild.get_role(config.auto_role)
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass
        
        # Welcome message
        if config.welcome_channel:
            channel = member.guild.get_channel(config.welcome_channel)
            if channel:
                embed = discord.Embed(
                    title="👋 Welcome!",
                    description=f"Welcome to **{member.guild.name}**, {member.mention}!\n\nWe're glad to have you here. Make sure to read the rules and have fun!",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"Member #{member.guild.member_count}")
                await channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        config = await self.db.get_guild_config(member.guild.id)
        
        if config.welcome_channel:
            channel = member.guild.get_channel(config.welcome_channel)
            if channel:
                embed = discord.Embed(
                    title="👋 Goodbye",
                    description=f"**{member.name}** has left the server.",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed)
    
    @app_commands.command(name="setwelcome", description="Set the welcome channel")
    @is_admin()
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.db.update_guild_config(interaction.guild.id, welcome_channel=channel.id)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Welcome Channel Set", f"Welcome messages will be sent to {channel.mention}")
        )
    
    @app_commands.command(name="setautorole", description="Set role to give new members automatically")
    @is_admin()
    async def setautorole(self, interaction: discord.Interaction, role: discord.Role):
        await self.db.update_guild_config(interaction.guild.id, auto_role=role.id)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Auto-Role Set", f"New members will automatically receive {role.mention}")
        )
    
    @app_commands.command(name="announce", description="Send an announcement to a channel")
    @is_admin()
    async def announce(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
        embed = discord.Embed(
            title=f"📢 {title}",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Announced by {interaction.user.display_name}")
        
        await channel.send(embed=embed)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Announcement Sent", f"Announcement sent to {channel.mention}"),
            ephemeral=True
        )
    
    @app_commands.command(name="reactionrole", description="Create a reaction role message")
    @is_admin()
    async def reactionrole(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, description: str):
        embed = discord.Embed(
            title=title,
            description=description + "\n\nReact below to get roles!",
            color=discord.Color.purple()
        )
        
        message = await channel.send(embed=embed)
        await interaction.response.send_message(
            embed=EmbedFactory.success("Reaction Role Created", f"Message ID: {message.id}\nUse `/addreactionrole` to add role mappings"),
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Automation(bot))
