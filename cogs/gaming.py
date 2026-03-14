import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.embeds import EmbedFactory
from utils.database import Database, UserXP
from utils.permissions import is_member, is_moderator
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
import random
import asyncio
import datetime
import logging

logger = logging.getLogger('discord_bot.gaming')

class Gaming(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.voice_xp_task.start()
    
    def calculate_level(self, xp):
        return int((xp / 100) ** 0.5) + 1
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        config = await self.db.get_guild_config(message.guild.id)
        if not config.xp_enabled:
            return
        
        # Award XP (database handles cooldown)
        xp_gain = random.randint(15, 25)
        await self.add_xp(message.guild.id, message.author.id, xp_gain, message.channel)
    
    async def add_xp(self, guild_id, user_id, xp_amount, channel=None):
        """Add XP with atomic database operations to prevent race conditions"""
        try:
            async with self.db.async_session() as session:
                # Use SELECT FOR UPDATE to lock the row
                stmt = select(UserXP).where(
                    UserXP.guild_id == guild_id,
                    UserXP.user_id == user_id
                ).with_for_update()
                
                result = await session.execute(stmt)
                user_xp = result.scalar_one_or_none()
                
                now = datetime.datetime.utcnow()
                
                if not user_xp:
                    # Create new user XP record
                    user_xp = UserXP(
                        guild_id=guild_id,
                        user_id=user_id,
                        xp=xp_amount,
                        level=1,
                        last_xp_time=now
                    )
                    session.add(user_xp)
                    await session.commit()
                else:
                    # Check database-level cooldown (60 seconds)
                    if user_xp.last_xp_time:
                        time_diff = (now - user_xp.last_xp_time).total_seconds()
                        if time_diff < 60:
                            # Still on cooldown
                            return
                    
                    # Update XP
                    old_level = user_xp.level
                    user_xp.xp += xp_amount
                    user_xp.last_xp_time = now
                    new_level = self.calculate_level(user_xp.xp)
                    user_xp.level = new_level
                    
                    await session.commit()
                    
                    # Level up notification
                    if new_level > old_level and channel:
                        try:
                            embed = EmbedFactory.success(
                                "Level Up!",
                                f"<@{user_id}> reached level **{new_level}**! 🎉"
                            )
                            await channel.send(embed=embed, delete_after=10)
                        except Exception as e:
                            logger.debug(f"Could not send level up message: {e}")
        except Exception as e:
            logger.error(f"Error adding XP for user {user_id} in guild {guild_id}: {e}")
    
    @tasks.loop(minutes=5)  # Changed from 1 to 5 minutes to reduce farming
    async def voice_xp_task(self):
        """Award XP for voice activity (anti-farming measures)"""
        for guild in self.bot.guilds:
            try:
                config = await self.db.get_guild_config(guild.id)
                if not config.xp_enabled:
                    continue
                
                for channel in guild.voice_channels:
                    # Only award XP if there are at least 2 active people (prevent solo farming)
                    active_members = [
                        m for m in channel.members 
                        if not m.bot 
                        and not m.voice.self_deaf 
                        and not m.voice.deaf 
                        and not m.voice.afk
                        and not m.voice.self_mute
                    ]
                    
                    if len(active_members) < 2:
                        continue
                    
                    for member in active_members:
                        # Reduced XP gain from 5-10 to 3-7
                        xp_gain = random.randint(3, 7)
                        await self.add_xp(guild.id, member.id, xp_gain)
            except Exception as e:
                logger.error(f"Error in voice XP task for guild {guild.id}: {e}")
    
    @voice_xp_task.before_loop
    async def before_voice_xp(self):
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="rank", description="[Member] Check your rank and XP")
    @is_member()
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        
        async with self.db.async_session() as session:
            result = await session.execute(
                select(UserXP).where(
                    UserXP.guild_id == interaction.guild.id,
                    UserXP.user_id == member.id
                )
            )
            user_xp = result.scalar_one_or_none()
            
            if not user_xp:
                return await interaction.response.send_message(
                    embed=EmbedFactory.info("No Data", f"{member.mention} has no XP data yet"),
                    ephemeral=True
                )
            
            # Calculate rank
            all_users = await session.execute(
                select(UserXP).where(UserXP.guild_id == interaction.guild.id).order_by(UserXP.xp.desc())
            )
            all_users = all_users.scalars().all()
            rank = next((i + 1 for i, u in enumerate(all_users) if u.user_id == member.id), 0)
            total_users = len(all_users)
            
            # Import visual utilities
            from utils.visuals import CardGenerator
            
            # Create beautiful profile card with animations
            embed = CardGenerator.create_profile_card(
                member,
                user_xp.level,
                user_xp.xp,
                rank,
                total_users
            )
            
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="leaderboard", description="[Member] Show the server XP leaderboard")
    @is_member()
    async def leaderboard(self, interaction: discord.Interaction):
        async with self.db.async_session() as session:
            result = await session.execute(
                select(UserXP).where(UserXP.guild_id == interaction.guild.id).order_by(UserXP.xp.desc()).limit(10)
            )
            top_users = result.scalars().all()
            
            if not top_users:
                return await interaction.response.send_message(
                    embed=EmbedFactory.info("No Data", "No XP data available yet"),
                    ephemeral=True
                )
            
            embed = discord.Embed(
                title=f"🏆 {interaction.guild.name} Leaderboard",
                color=discord.Color.gold()
            )
            
            leaderboard_text = ""
            for i, user_xp in enumerate(top_users, 1):
                member = interaction.guild.get_member(user_xp.user_id)
                if member:
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
                    leaderboard_text += f"{medal} {member.mention} - Level {user_xp.level} ({user_xp.xp} XP)\n"
            
            embed.description = leaderboard_text
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="giveaway", description="[Moderator] Start a giveaway")
    @is_moderator()
    async def giveaway(self, interaction: discord.Interaction, duration: int, winners: int, prize: str):
        # Validate input
        if duration < 1 or duration > 10080:  # Max 1 week
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid Duration", "Duration must be between 1 minute and 1 week (10080 minutes)"),
                ephemeral=True
            )
        
        if winners < 1 or winners > 20:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid Winners", "Winners must be between 1 and 20"),
                ephemeral=True
            )
        
        if len(prize) > 256:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Prize Too Long", "Prize description must be 256 characters or less"),
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Duration:** {duration} minutes\n\nReact with 🎉 to enter!",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Hosted by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction("🎉")
        
        # Schedule giveaway end (non-blocking)
        asyncio.create_task(self._end_giveaway(message, winners, prize, duration))
    
    async def _end_giveaway(self, message, winners_count, prize, duration):
        """End giveaway after duration (non-blocking)"""
        try:
            await asyncio.sleep(duration * 60)
            
            # Refresh message
            channel = message.channel
            message = await channel.fetch_message(message.id)
            reaction = discord.utils.get(message.reactions, emoji="🎉")
            
            if not reaction or reaction.count <= 1:
                await channel.send(embed=EmbedFactory.info("Giveaway Ended", "No valid entries"))
                return
            
            # Get valid users (still in guild, not bots, account age > 7 days)
            users = []
            async for user in reaction.users():
                if user.bot:
                    continue
                
                member = channel.guild.get_member(user.id)
                if not member:
                    continue
                
                # Check account age (prevent alt abuse)
                account_age = (discord.utils.utcnow() - user.created_at).days
                if account_age < 7:
                    continue
                
                users.append(user)
            
            if not users:
                await channel.send(embed=EmbedFactory.info("Giveaway Ended", "No valid entries (accounts must be 7+ days old)"))
                return
            
            # Pick winners
            actual_winners = min(winners_count, len(users))
            winner_list = random.sample(users, actual_winners)
            winner_mentions = ", ".join([user.mention for user in winner_list])
            
            embed = EmbedFactory.success(
                "Giveaway Ended!",
                f"**Prize:** {prize}\n**Winners:** {winner_mentions}\n\nCongratulations! 🎉"
            )
            await channel.send(embed=embed)
            
            logger.info(f"Giveaway ended in guild {channel.guild.id}, winners: {[w.id for w in winner_list]}")
        except discord.NotFound:
            logger.warning(f"Giveaway message was deleted before completion")
        except Exception as e:
            logger.error(f"Error ending giveaway: {e}")

async def setup(bot):
    await bot.add_cog(Gaming(bot))
