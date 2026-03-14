import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.permissions import is_admin
from utils.database import Database

logger = logging.getLogger('discord_bot.tempvoice')

class TempVoice(commands.Cog):
    """Temporary Voice Channels - Auto-create and delete voice channels"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.temp_channels = {}  # {channel_id: owner_id}
        self.creator_channels = {}  # {guild_id: creator_channel_id}
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice channel joins/leaves"""
        guild_id = member.guild.id
        
        # Check if user joined the creator channel
        if after.channel and guild_id in self.creator_channels:
            if after.channel.id == self.creator_channels[guild_id]:
                await self.create_temp_channel(member, after.channel)
        
        # Check if user left a temp channel
        if before.channel and before.channel.id in self.temp_channels:
            # If channel is empty, delete it
            if len(before.channel.members) == 0:
                await self.delete_temp_channel(before.channel)
    
    async def create_temp_channel(self, member, creator_channel):
        """Create a temporary voice channel for the user"""
        try:
            # Create new channel
            channel = await creator_channel.category.create_voice_channel(
                name=f"{member.display_name}'s Channel",
                user_limit=creator_channel.user_limit if creator_channel.user_limit > 0 else None,
                bitrate=creator_channel.bitrate,
                reason=f"Temporary channel for {member}"
            )
            
            # Move user to new channel
            await member.move_to(channel)
            
            # Track this channel
            self.temp_channels[channel.id] = member.id
            
            # Give owner permissions
            await channel.set_permissions(
                member,
                manage_channels=True,
                move_members=True,
                mute_members=True,
                deafen_members=True
            )
            
            logger.info(f"Created temp channel {channel.name} for {member}")
            
        except Exception as e:
            logger.error(f"Error creating temp channel: {e}")
    
    async def delete_temp_channel(self, channel):
        """Delete a temporary voice channel"""
        try:
            if channel.id in self.temp_channels:
                await channel.delete(reason="Temporary channel empty")
                del self.temp_channels[channel.id]
                logger.info(f"Deleted temp channel {channel.name}")
        except Exception as e:
            logger.error(f"Error deleting temp channel: {e}")
    
    @app_commands.command(name="tempvoice-setup", description="[Admin] Set up temporary voice channels")
    @is_admin()
    async def setup_tempvoice(self, interaction: discord.Interaction, category: discord.CategoryChannel = None):
        """Set up the temp voice system"""
        
        # Use current category or create new one
        if not category:
            category = await interaction.guild.create_category("Voice Channels")
        
        # Create the creator channel
        creator = await category.create_voice_channel(
            name="➕ Create Channel",
            user_limit=1
        )
        
        # Store in memory and database
        self.creator_channels[interaction.guild.id] = creator.id
        
        embed = discord.Embed(
            title="✅ Temporary Voice Channels Enabled",
            description=f"Users can now join {creator.mention} to create their own temporary voice channel!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="How it works",
            value="1. Join the 'Create Channel' voice channel\n2. Bot creates a new channel for you\n3. You get moved to your new channel\n4. Channel auto-deletes when empty",
            inline=False
        )
        embed.add_field(
            name="Channel Owner Permissions",
            value="• Rename channel\n• Set user limit\n• Move members\n• Mute/deafen members",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="voice-lock", description="Lock your temporary voice channel")
    async def lock_voice(self, interaction: discord.Interaction):
        """Lock your temp voice channel"""
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ You must be in a voice channel!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if channel.id not in self.temp_channels:
            return await interaction.response.send_message(
                "❌ This is not a temporary voice channel!",
                ephemeral=True
            )
        
        if self.temp_channels[channel.id] != interaction.user.id:
            return await interaction.response.send_message(
                "❌ You don't own this channel!",
                ephemeral=True
            )
        
        # Lock channel
        await channel.set_permissions(
            interaction.guild.default_role,
            connect=False
        )
        
        await interaction.response.send_message(
            f"🔒 Locked {channel.mention}",
            ephemeral=True
        )
    
    @app_commands.command(name="voice-unlock", description="Unlock your temporary voice channel")
    async def unlock_voice(self, interaction: discord.Interaction):
        """Unlock your temp voice channel"""
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ You must be in a voice channel!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if channel.id not in self.temp_channels:
            return await interaction.response.send_message(
                "❌ This is not a temporary voice channel!",
                ephemeral=True
            )
        
        if self.temp_channels[channel.id] != interaction.user.id:
            return await interaction.response.send_message(
                "❌ You don't own this channel!",
                ephemeral=True
            )
        
        # Unlock channel
        await channel.set_permissions(
            interaction.guild.default_role,
            connect=None
        )
        
        await interaction.response.send_message(
            f"🔓 Unlocked {channel.mention}",
            ephemeral=True
        )
    
    @app_commands.command(name="voice-limit", description="Set user limit for your temporary voice channel")
    async def limit_voice(self, interaction: discord.Interaction, limit: int):
        """Set user limit for temp voice channel"""
        
        if not 0 <= limit <= 99:
            return await interaction.response.send_message(
                "❌ Limit must be between 0 (unlimited) and 99!",
                ephemeral=True
            )
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ You must be in a voice channel!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if channel.id not in self.temp_channels:
            return await interaction.response.send_message(
                "❌ This is not a temporary voice channel!",
                ephemeral=True
            )
        
        if self.temp_channels[channel.id] != interaction.user.id:
            return await interaction.response.send_message(
                "❌ You don't own this channel!",
                ephemeral=True
            )
        
        # Set limit
        await channel.edit(user_limit=limit if limit > 0 else None)
        
        limit_text = f"{limit} users" if limit > 0 else "unlimited"
        await interaction.response.send_message(
            f"👥 Set user limit to {limit_text}",
            ephemeral=True
        )
    
    @app_commands.command(name="voice-rename", description="Rename your temporary voice channel")
    async def rename_voice(self, interaction: discord.Interaction, name: str):
        """Rename temp voice channel"""
        
        if len(name) > 100:
            return await interaction.response.send_message(
                "❌ Name must be 100 characters or less!",
                ephemeral=True
            )
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ You must be in a voice channel!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if channel.id not in self.temp_channels:
            return await interaction.response.send_message(
                "❌ This is not a temporary voice channel!",
                ephemeral=True
            )
        
        if self.temp_channels[channel.id] != interaction.user.id:
            return await interaction.response.send_message(
                "❌ You don't own this channel!",
                ephemeral=True
            )
        
        # Rename channel
        old_name = channel.name
        await channel.edit(name=name)
        
        await interaction.response.send_message(
            f"✏️ Renamed channel from '{old_name}' to '{name}'",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(TempVoice(bot))
