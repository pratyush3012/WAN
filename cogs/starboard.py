import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.permissions import is_admin
from utils.database import Database

logger = logging.getLogger('discord_bot.starboard')

class Starboard(commands.Cog):
    """Starboard - Highlight best messages with stars"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.starboard_channels = {}  # {guild_id: channel_id}
        self.star_threshold = {}  # {guild_id: threshold}
        self.starred_messages = {}  # {message_id: starboard_message_id}
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle star reactions"""
        if payload.emoji.name != "⭐":
            return
        
        await self.update_starboard(payload)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle star reaction removal"""
        if payload.emoji.name != "⭐":
            return
        
        await self.update_starboard(payload)
    
    async def update_starboard(self, payload):
        """Update starboard message"""
        guild_id = payload.guild_id
        
        # Check if starboard is set up
        if guild_id not in self.starboard_channels:
            return
        
        try:
            # Get the message
            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                return
            
            message = await channel.fetch_message(payload.message_id)
            
            # Don't star bot messages or messages in starboard
            if message.author.bot or message.channel.id == self.starboard_channels[guild_id]:
                return
            
            # Count stars
            star_count = 0
            for reaction in message.reactions:
                if reaction.emoji == "⭐":
                    star_count = reaction.count
                    break
            
            # Get threshold
            threshold = self.star_threshold.get(guild_id, 3)
            
            # Get starboard channel
            starboard_channel = self.bot.get_channel(self.starboard_channels[guild_id])
            if not starboard_channel:
                return
            
            # Check if message is already on starboard
            if message.id in self.starred_messages:
                # Update existing starboard message
                try:
                    starboard_msg = await starboard_channel.fetch_message(
                        self.starred_messages[message.id]
                    )
                    
                    if star_count >= threshold:
                        # Update star count
                        embed = starboard_msg.embeds[0]
                        embed.title = f"⭐ {star_count} | #{message.channel.name}"
                        await starboard_msg.edit(embed=embed)
                    else:
                        # Remove from starboard if below threshold
                        await starboard_msg.delete()
                        del self.starred_messages[message.id]
                except:
                    pass
            
            elif star_count >= threshold:
                # Add to starboard
                embed = discord.Embed(
                    title=f"⭐ {star_count} | #{message.channel.name}",
                    description=message.content or "*[No text content]*",
                    color=discord.Color.gold(),
                    timestamp=message.created_at
                )
                
                embed.set_author(
                    name=message.author.display_name,
                    icon_url=message.author.display_avatar.url
                )
                
                # Add image if present
                if message.attachments:
                    embed.set_image(url=message.attachments[0].url)
                
                # Add jump link
                embed.add_field(
                    name="Source",
                    value=f"[Jump to message]({message.jump_url})",
                    inline=False
                )
                
                # Send to starboard
                starboard_msg = await starboard_channel.send(embed=embed)
                self.starred_messages[message.id] = starboard_msg.id
        
        except Exception as e:
            logger.error(f"Error updating starboard: {e}")
    
    @app_commands.command(name="starboard-setup", description="[Admin] Set up the starboard")
    @is_admin()
    async def setup_starboard(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        threshold: int = 3
    ):
        """Set up starboard channel and threshold"""
        
        if threshold < 1:
            return await interaction.response.send_message(
                "❌ Threshold must be at least 1!",
                ephemeral=True
            )
        
        self.starboard_channels[interaction.guild.id] = channel.id
        self.star_threshold[interaction.guild.id] = threshold
        
        embed = discord.Embed(
            title="⭐ Starboard Enabled",
            description=f"Messages with {threshold}+ ⭐ reactions will appear in {channel.mention}",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="How it works",
            value=f"1. React to messages with ⭐\n2. When a message gets {threshold}+ stars, it appears in starboard\n3. Star count updates in real-time",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="starboard-disable", description="[Admin] Disable the starboard")
    @is_admin()
    async def disable_starboard(self, interaction: discord.Interaction):
        """Disable starboard"""
        
        if interaction.guild.id not in self.starboard_channels:
            return await interaction.response.send_message(
                "❌ Starboard is not enabled!",
                ephemeral=True
            )
        
        del self.starboard_channels[interaction.guild.id]
        if interaction.guild.id in self.star_threshold:
            del self.star_threshold[interaction.guild.id]
        
        await interaction.response.send_message(
            "⭐ Starboard disabled",
            ephemeral=True
        )
    
    @app_commands.command(name="starboard-stats", description="View starboard statistics")
    async def starboard_stats(self, interaction: discord.Interaction):
        """Show starboard stats"""
        
        if interaction.guild.id not in self.starboard_channels:
            return await interaction.response.send_message(
                "❌ Starboard is not enabled!",
                ephemeral=True
            )
        
        # Count starred messages for this guild
        guild_starred = sum(
            1 for msg_id in self.starred_messages
            if msg_id in [m.id for m in interaction.guild.text_channels]
        )
        
        threshold = self.star_threshold.get(interaction.guild.id, 3)
        channel = self.bot.get_channel(self.starboard_channels[interaction.guild.id])
        
        embed = discord.Embed(
            title="⭐ Starboard Statistics",
            color=discord.Color.gold()
        )
        embed.add_field(name="Channel", value=channel.mention if channel else "Unknown", inline=True)
        embed.add_field(name="Threshold", value=f"{threshold} stars", inline=True)
        embed.add_field(name="Starred Messages", value=str(guild_starred), inline=True)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Starboard(bot))
