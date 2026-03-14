import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, date
from collections import defaultdict
import asyncio
import logging
from utils.permissions import is_member, is_admin

logger = logging.getLogger('discord_bot.birthdays')

class Birthdays(commands.Cog):
    """Birthday System - Track and celebrate member birthdays"""
    
    def __init__(self, bot):
        self.bot = bot
        self.birthdays = defaultdict(dict)  # {guild_id: {user_id: date}}
        self.birthday_channels = {}  # {guild_id: channel_id}
        self.birthday_role = {}  # {guild_id: role_id}
        self.check_birthdays.start()
    
    def cog_unload(self):
        self.check_birthdays.cancel()
    
    @tasks.loop(hours=24)
    async def check_birthdays(self):
        """Check for birthdays daily"""
        today = date.today()
        
        for guild_id, users in self.birthdays.items():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            
            # Check each user's birthday
            for user_id, birthday in users.items():
                if birthday.month == today.month and birthday.day == today.day:
                    await self.celebrate_birthday(guild, user_id)
    
    @check_birthdays.before_loop
    async def before_check_birthdays(self):
        await self.bot.wait_until_ready()
    
    async def celebrate_birthday(self, guild, user_id):
        """Celebrate a user's birthday"""
        member = guild.get_member(user_id)
        if not member:
            return
        
        # Send birthday message
        if guild.id in self.birthday_channels:
            channel = self.bot.get_channel(self.birthday_channels[guild.id])
            if channel:
                embed = discord.Embed(
                    title="🎂 Happy Birthday!",
                    description=f"Happy Birthday {member.mention}! 🎉\n\nWishing you an amazing day!",
                    color=discord.Color.gold()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                
                try:
                    await channel.send(f"@everyone", embed=embed)
                except:
                    await channel.send(embed=embed)
        
        # Give birthday role
        if guild.id in self.birthday_role:
            role = guild.get_role(self.birthday_role[guild.id])
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Birthday!")
                    logger.info(f"Gave birthday role to {member}")
                    
                    # Remove role after 24 hours
                    await asyncio.sleep(86400)  # 24 hours
                    if role in member.roles:
                        await member.remove_roles(role, reason="Birthday ended")
                except Exception as e:
                    logger.error(f"Error managing birthday role: {e}")
    
    @app_commands.command(name="birthday-set", description="Set your birthday")
    @is_member()
    async def set_birthday(
        self,
        interaction: discord.Interaction,
        month: int,
        day: int
    ):
        """Set your birthday"""
        
        # Validate date
        try:
            birthday = date(2000, month, day)  # Use 2000 as dummy year
        except ValueError:
            return await interaction.response.send_message(
                "❌ Invalid date! Please use valid month (1-12) and day.",
                ephemeral=True
            )
        
        self.birthdays[interaction.guild.id][interaction.user.id] = birthday
        
        embed = discord.Embed(
            title="🎂 Birthday Set!",
            description=f"Your birthday is set to **{birthday.strftime('%B %d')}**",
            color=discord.Color.green()
        )
        embed.set_footer(text="We'll celebrate on your special day!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="birthday-remove", description="Remove your birthday")
    @is_member()
    async def remove_birthday(self, interaction: discord.Interaction):
        """Remove your birthday"""
        
        if interaction.user.id in self.birthdays[interaction.guild.id]:
            del self.birthdays[interaction.guild.id][interaction.user.id]
            await interaction.response.send_message(
                "✅ Your birthday has been removed",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ You don't have a birthday set!",
                ephemeral=True
            )
    
    @app_commands.command(name="birthday-list", description="View upcoming birthdays")
    @is_member()
    async def list_birthdays(self, interaction: discord.Interaction):
        """List upcoming birthdays"""
        
        guild_id = interaction.guild.id
        
        if not self.birthdays[guild_id]:
            return await interaction.response.send_message(
                "❌ No birthdays set yet!",
                ephemeral=True
            )
        
        today = date.today()
        upcoming = []
        
        for user_id, birthday in self.birthdays[guild_id].items():
            member = interaction.guild.get_member(user_id)
            if not member:
                continue
            
            # Calculate next birthday
            next_birthday = date(today.year, birthday.month, birthday.day)
            if next_birthday < today:
                next_birthday = date(today.year + 1, birthday.month, birthday.day)
            
            days_until = (next_birthday - today).days
            upcoming.append((member, birthday, days_until))
        
        # Sort by days until birthday
        upcoming.sort(key=lambda x: x[2])
        
        embed = discord.Embed(
            title="🎂 Upcoming Birthdays",
            color=discord.Color.gold()
        )
        
        for member, birthday, days in upcoming[:10]:
            if days == 0:
                status = "🎉 **TODAY!**"
            elif days == 1:
                status = "Tomorrow"
            else:
                status = f"In {days} days"
            
            embed.add_field(
                name=f"{member.display_name}",
                value=f"{birthday.strftime('%B %d')} - {status}",
                inline=False
            )
        
        if len(upcoming) > 10:
            embed.set_footer(text=f"And {len(upcoming) - 10} more...")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="birthday-setup", description="[Admin] Set up birthday announcements")
    @is_admin()
    async def setup_birthdays(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        birthday_role: discord.Role = None
    ):
        """Set up birthday system"""
        
        self.birthday_channels[interaction.guild.id] = channel.id
        
        if birthday_role:
            self.birthday_role[interaction.guild.id] = birthday_role.id
        
        embed = discord.Embed(
            title="🎂 Birthday System Enabled",
            description=f"Birthday announcements will be posted in {channel.mention}",
            color=discord.Color.green()
        )
        
        if birthday_role:
            embed.add_field(
                name="Birthday Role",
                value=f"{birthday_role.mention} will be given for 24 hours",
                inline=False
            )
        
        embed.add_field(
            name="How to use",
            value="Members can set their birthday with `/birthday-set <month> <day>`",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="birthday-today", description="Check today's birthdays")
    @is_member()
    async def today_birthdays(self, interaction: discord.Interaction):
        """Check today's birthdays"""
        
        guild_id = interaction.guild.id
        today = date.today()
        
        birthday_members = []
        for user_id, birthday in self.birthdays[guild_id].items():
            if birthday.month == today.month and birthday.day == today.day:
                member = interaction.guild.get_member(user_id)
                if member:
                    birthday_members.append(member)
        
        if not birthday_members:
            return await interaction.response.send_message(
                "🎂 No birthdays today!",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="🎂 Today's Birthdays!",
            description="\n".join(f"🎉 {m.mention}" for m in birthday_members),
            color=discord.Color.gold()
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Birthdays(bot))
