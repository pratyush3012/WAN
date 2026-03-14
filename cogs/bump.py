import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
import logging
from utils.permissions import is_admin

logger = logging.getLogger('discord_bot.bump')

class BumpReminder(commands.Cog):
    """Bump Reminder - Remind to bump server on listing sites"""
    
    def __init__(self, bot):
        self.bot = bot
        self.bump_channels = {}  # {guild_id: channel_id}
        self.last_bump = {}  # {guild_id: datetime}
        self.bump_role = {}  # {guild_id: role_id}
        self.check_bumps.start()
    
    def cog_unload(self):
        self.check_bumps.cancel()
    
    @tasks.loop(minutes=5)
    async def check_bumps(self):
        """Check if it's time to remind about bumping"""
        now = datetime.utcnow()
        
        for guild_id, last_bump_time in list(self.last_bump.items()):
            # Disboard bump cooldown is 2 hours
            if now - last_bump_time >= timedelta(hours=2):
                await self.send_bump_reminder(guild_id)
                # Remove from tracking until next bump
                del self.last_bump[guild_id]
    
    @check_bumps.before_loop
    async def before_check_bumps(self):
        await self.bot.wait_until_ready()
    
    async def send_bump_reminder(self, guild_id):
        """Send bump reminder"""
        if guild_id not in self.bump_channels:
            return
        
        channel = self.bot.get_channel(self.bump_channels[guild_id])
        if not channel:
            return
        
        embed = discord.Embed(
            title="⏰ Bump Reminder!",
            description="It's time to bump the server!\n\nUse `/bump` to bump on Disboard!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Bumping helps grow our community!")
        
        # Mention bump role if configured
        mention = ""
        if guild_id in self.bump_role:
            role = channel.guild.get_role(self.bump_role[guild_id])
            if role:
                mention = role.mention
        
        try:
            await channel.send(mention, embed=embed)
        except:
            await channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Detect bump commands"""
        if message.author.bot and message.author.id == 302050872383242240:  # Disboard bot
            # Check if it's a bump success message
            if message.embeds and "Bump done" in message.embeds[0].description:
                guild_id = message.guild.id
                self.last_bump[guild_id] = datetime.utcnow()
                
                # Thank the bumper
                if message.interaction:
                    bumper = message.interaction.user
                    
                    embed = discord.Embed(
                        title="✅ Thanks for bumping!",
                        description=f"Thank you {bumper.mention} for bumping the server!\n\nNext bump available in 2 hours.",
                        color=discord.Color.green()
                    )
                    
                    await message.channel.send(embed=embed, delete_after=10)
    
    @app_commands.command(name="bump-setup", description="[Admin] Set up bump reminders")
    @is_admin()
    async def setup_bump(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        reminder_role: discord.Role = None
    ):
        """Set up bump reminder system"""
        
        self.bump_channels[interaction.guild.id] = channel.id
        
        if reminder_role:
            self.bump_role[interaction.guild.id] = reminder_role.id
        
        embed = discord.Embed(
            title="⏰ Bump Reminders Enabled",
            description=f"Bump reminders will be sent to {channel.mention}",
            color=discord.Color.green()
        )
        
        if reminder_role:
            embed.add_field(
                name="Reminder Role",
                value=f"{reminder_role.mention} will be pinged",
                inline=False
            )
        
        embed.add_field(
            name="How it works",
            value="1. Someone bumps with `/bump`\n2. Bot detects the bump\n3. Reminder sent after 2 hours\n4. Repeat!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="bump-disable", description="[Admin] Disable bump reminders")
    @is_admin()
    async def disable_bump(self, interaction: discord.Interaction):
        """Disable bump reminders"""
        
        if interaction.guild.id in self.bump_channels:
            del self.bump_channels[interaction.guild.id]
        
        if interaction.guild.id in self.bump_role:
            del self.bump_role[interaction.guild.id]
        
        await interaction.response.send_message(
            "✅ Bump reminders disabled",
            ephemeral=True
        )
    
    @app_commands.command(name="bump-status", description="Check bump status")
    async def bump_status(self, interaction: discord.Interaction):
        """Check when next bump is available"""
        
        guild_id = interaction.guild.id
        
        if guild_id not in self.last_bump:
            return await interaction.response.send_message(
                "❌ No recent bumps recorded! Use `/bump` to bump the server.",
                ephemeral=True
            )
        
        last_bump_time = self.last_bump[guild_id]
        next_bump_time = last_bump_time + timedelta(hours=2)
        now = datetime.utcnow()
        
        if now >= next_bump_time:
            status = "✅ **Available now!**"
            color = discord.Color.green()
        else:
            time_left = next_bump_time - now
            minutes = int(time_left.total_seconds() / 60)
            status = f"⏰ Available in **{minutes} minutes**"
            color = discord.Color.blue()
        
        embed = discord.Embed(
            title="⏰ Bump Status",
            description=status,
            color=color
        )
        embed.add_field(
            name="Last Bump",
            value=f"<t:{int(last_bump_time.timestamp())}:R>",
            inline=True
        )
        embed.add_field(
            name="Next Bump",
            value=f"<t:{int(next_bump_time.timestamp())}:R>",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(BumpReminder(bot))
