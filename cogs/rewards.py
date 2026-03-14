import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.permissions import is_admin, is_member
from utils.database import Database

logger = logging.getLogger('discord_bot.rewards')

class Rewards(commands.Cog):
    """Leveling Rewards - Auto-assign roles and rewards based on XP level"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.level_rewards = {}  # {guild_id: {level: role_id}}
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Check for level ups and assign rewards"""
        if message.author.bot or not message.guild:
            return
        
        # This will be called after XP is added in gaming.py
        # We check if user leveled up and assign rewards
        await self.check_and_assign_rewards(message.guild, message.author)
    
    async def check_and_assign_rewards(self, guild, member):
        """Check if user has rewards to claim"""
        if guild.id not in self.level_rewards:
            return
        
        # Get user's current level
        async with self.db.async_session() as session:
            from utils.database import UserXP
            from sqlalchemy import select
            
            stmt = select(UserXP).where(
                UserXP.guild_id == guild.id,
                UserXP.user_id == member.id
            )
            result = await session.execute(stmt)
            user_xp = result.scalar_one_or_none()
            
            if not user_xp:
                return
            
            current_level = user_xp.level
        
        # Check for rewards at this level
        rewards = self.level_rewards[guild.id]
        
        for level, role_id in rewards.items():
            if current_level >= level:
                role = guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason=f"Level {level} reward")
                        logger.info(f"Assigned {role.name} to {member} for reaching level {level}")
                    except Exception as e:
                        logger.error(f"Failed to assign reward role: {e}")
    
    @app_commands.command(name="reward-add", description="[Admin] Add a level reward")
    @is_admin()
    async def add_reward(
        self,
        interaction: discord.Interaction,
        level: int,
        role: discord.Role
    ):
        """Add a role reward for reaching a level"""
        
        if level < 1:
            return await interaction.response.send_message(
                "❌ Level must be at least 1!",
                ephemeral=True
            )
        
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "❌ I cannot manage that role (it's higher than my highest role)!",
                ephemeral=True
            )
        
        if interaction.guild.id not in self.level_rewards:
            self.level_rewards[interaction.guild.id] = {}
        
        self.level_rewards[interaction.guild.id][level] = role.id
        
        embed = discord.Embed(
            title="✅ Reward Added",
            description=f"Users will receive {role.mention} when they reach level **{level}**",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="reward-remove", description="[Admin] Remove a level reward")
    @is_admin()
    async def remove_reward(self, interaction: discord.Interaction, level: int):
        """Remove a level reward"""
        
        if interaction.guild.id not in self.level_rewards:
            return await interaction.response.send_message(
                "❌ No rewards configured!",
                ephemeral=True
            )
        
        if level not in self.level_rewards[interaction.guild.id]:
            return await interaction.response.send_message(
                f"❌ No reward configured for level {level}!",
                ephemeral=True
            )
        
        del self.level_rewards[interaction.guild.id][level]
        
        await interaction.response.send_message(
            f"✅ Removed reward for level {level}",
            ephemeral=True
        )
    
    @app_commands.command(name="rewards", description="View all level rewards")
    @is_member()
    async def view_rewards(self, interaction: discord.Interaction):
        """View all configured rewards"""
        
        if interaction.guild.id not in self.level_rewards or not self.level_rewards[interaction.guild.id]:
            return await interaction.response.send_message(
                "❌ No rewards configured yet!",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="🎁 Level Rewards",
            description="Earn these roles by leveling up!",
            color=discord.Color.gold()
        )
        
        rewards = self.level_rewards[interaction.guild.id]
        sorted_rewards = sorted(rewards.items())
        
        for level, role_id in sorted_rewards:
            role = interaction.guild.get_role(role_id)
            if role:
                embed.add_field(
                    name=f"Level {level}",
                    value=role.mention,
                    inline=True
                )
        
        # Show user's progress
        async with self.db.async_session() as session:
            from utils.database import UserXP
            from sqlalchemy import select
            
            stmt = select(UserXP).where(
                UserXP.guild_id == interaction.guild.id,
                UserXP.user_id == interaction.user.id
            )
            result = await session.execute(stmt)
            user_xp = result.scalar_one_or_none()
            
            if user_xp:
                embed.set_footer(text=f"Your current level: {user_xp.level}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="reward-sync", description="[Admin] Sync rewards for all members")
    @is_admin()
    async def sync_rewards(self, interaction: discord.Interaction):
        """Sync rewards for all members (useful after adding new rewards)"""
        
        await interaction.response.defer()
        
        if interaction.guild.id not in self.level_rewards:
            return await interaction.followup.send(
                "❌ No rewards configured!",
                ephemeral=True
            )
        
        synced = 0
        
        for member in interaction.guild.members:
            if not member.bot:
                await self.check_and_assign_rewards(interaction.guild, member)
                synced += 1
        
        await interaction.followup.send(
            f"✅ Synced rewards for {synced} members!",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Rewards(bot))
