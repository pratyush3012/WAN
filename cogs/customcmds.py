import discord
from discord import app_commands
from discord.ext import commands
from collections import defaultdict
import logging
from utils.permissions import is_admin

logger = logging.getLogger('discord_bot.customcmds')

class CustomCommands(commands.Cog):
    """Custom Commands - User-created commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.custom_commands = defaultdict(dict)  # {guild_id: {name: response}}
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Check for custom commands"""
        if message.author.bot or not message.guild:
            return
        
        # Check if message starts with !
        if not message.content.startswith('!'):
            return
        
        # Extract command name
        parts = message.content[1:].split()
        if not parts:
            return
        
        cmd_name = parts[0].lower()
        guild_id = message.guild.id
        
        # Check if custom command exists
        if cmd_name in self.custom_commands[guild_id]:
            response = self.custom_commands[guild_id][cmd_name]
            
            # Replace variables
            response = response.replace('{user}', message.author.mention)
            response = response.replace('{server}', message.guild.name)
            response = response.replace('{channel}', message.channel.mention)
            response = response.replace('{members}', str(message.guild.member_count))
            
            await message.channel.send(response)
    
    @app_commands.command(name="customcmd-create", description="[Admin] Create a custom command")
    @is_admin()
    async def create_custom_cmd(
        self,
        interaction: discord.Interaction,
        name: str,
        response: str
    ):
        """Create a custom command"""
        
        name = name.lower()
        
        # Validate name
        if len(name) > 20:
            return await interaction.response.send_message(
                "❌ Command name must be 20 characters or less!",
                ephemeral=True
            )
        
        if not name.isalnum():
            return await interaction.response.send_message(
                "❌ Command name must be alphanumeric!",
                ephemeral=True
            )
        
        # Check if command already exists
        if name in self.custom_commands[interaction.guild.id]:
            return await interaction.response.send_message(
                f"❌ Command `!{name}` already exists!",
                ephemeral=True
            )
        
        # Create command
        self.custom_commands[interaction.guild.id][name] = response
        
        embed = discord.Embed(
            title="✅ Custom Command Created",
            description=f"Command `!{name}` has been created!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Usage",
            value=f"`!{name}`",
            inline=True
        )
        embed.add_field(
            name="Response",
            value=response[:100] + ("..." if len(response) > 100 else ""),
            inline=False
        )
        embed.add_field(
            name="Variables",
            value="`{user}` `{server}` `{channel}` `{members}`",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="customcmd-delete", description="[Admin] Delete a custom command")
    @is_admin()
    async def delete_custom_cmd(self, interaction: discord.Interaction, name: str):
        """Delete a custom command"""
        
        name = name.lower()
        guild_id = interaction.guild.id
        
        if name not in self.custom_commands[guild_id]:
            return await interaction.response.send_message(
                f"❌ Command `!{name}` doesn't exist!",
                ephemeral=True
            )
        
        del self.custom_commands[guild_id][name]
        
        await interaction.response.send_message(
            f"✅ Deleted command `!{name}`",
            ephemeral=True
        )
    
    @app_commands.command(name="customcmd-edit", description="[Admin] Edit a custom command")
    @is_admin()
    async def edit_custom_cmd(
        self,
        interaction: discord.Interaction,
        name: str,
        new_response: str
    ):
        """Edit a custom command"""
        
        name = name.lower()
        guild_id = interaction.guild.id
        
        if name not in self.custom_commands[guild_id]:
            return await interaction.response.send_message(
                f"❌ Command `!{name}` doesn't exist!",
                ephemeral=True
            )
        
        self.custom_commands[guild_id][name] = new_response
        
        embed = discord.Embed(
            title="✅ Custom Command Updated",
            description=f"Command `!{name}` has been updated!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="New Response",
            value=new_response[:200] + ("..." if len(new_response) > 200 else ""),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="customcmd-list", description="List all custom commands")
    async def list_custom_cmds(self, interaction: discord.Interaction):
        """List all custom commands"""
        
        guild_id = interaction.guild.id
        
        if not self.custom_commands[guild_id]:
            return await interaction.response.send_message(
                "❌ No custom commands created yet!",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="📝 Custom Commands",
            description=f"{len(self.custom_commands[guild_id])} custom commands",
            color=discord.Color.blue()
        )
        
        for name, response in list(self.custom_commands[guild_id].items())[:25]:
            embed.add_field(
                name=f"!{name}",
                value=response[:50] + ("..." if len(response) > 50 else ""),
                inline=False
            )
        
        if len(self.custom_commands[guild_id]) > 25:
            embed.set_footer(text=f"And {len(self.custom_commands[guild_id]) - 25} more...")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="customcmd-info", description="View info about a custom command")
    async def info_custom_cmd(self, interaction: discord.Interaction, name: str):
        """View custom command info"""
        
        name = name.lower()
        guild_id = interaction.guild.id
        
        if name not in self.custom_commands[guild_id]:
            return await interaction.response.send_message(
                f"❌ Command `!{name}` doesn't exist!",
                ephemeral=True
            )
        
        response = self.custom_commands[guild_id][name]
        
        embed = discord.Embed(
            title=f"📝 Command: !{name}",
            description=response,
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Usage",
            value=f"`!{name}`",
            inline=True
        )
        embed.add_field(
            name="Length",
            value=f"{len(response)} characters",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomCommands(bot))
