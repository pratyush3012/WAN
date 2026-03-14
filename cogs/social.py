import discord
from discord import app_commands
from discord.ext import commands
from utils.permissions import is_member
from utils.database import Database
import random
from datetime import datetime, timedelta

class Social(commands.Cog):
    """Social features - Marriage, Pets, Achievements, Streaks"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        
        # Pet types with emojis
        self.pets = {
            "dog": {"emoji": "🐕", "cost": 1000, "name": "Dog"},
            "cat": {"emoji": "🐱", "cost": 1000, "name": "Cat"},
            "dragon": {"emoji": "🐉", "cost": 5000, "name": "Dragon"},
            "unicorn": {"emoji": "🦄", "cost": 5000, "name": "Unicorn"},
            "phoenix": {"emoji": "🔥", "cost": 10000, "name": "Phoenix"},
            "wolf": {"emoji": "🐺", "cost": 2000, "name": "Wolf"},
            "panda": {"emoji": "🐼", "cost": 3000, "name": "Panda"},
            "lion": {"emoji": "🦁", "cost": 4000, "name": "Lion"}
        }
    
    @app_commands.command(name="achievements", description="[Member] View your achievements")
    @is_member()
    async def achievements(self, interaction: discord.Interaction):
        """View achievements"""
        embed = discord.Embed(
            title="🏆 Your Achievements",
            color=discord.Color.gold()
        )
        
        achievements_display = """
```ansi
[2;33m╔════════════════════════════════════════╗[0m
[2;33m║[0m  [1;36m🏆 ACHIEVEMENTS UNLOCKED[0m            [2;33m║[0m
[2;33m╠════════════════════════════════════════╣[0m
[2;33m║[0m                                        [2;33m║[0m
[2;33m║[0m  [1;32m✓[0m First Steps                       [2;33m║[0m
[2;33m║[0m    ╰→ Join the server                [2;33m║[0m
[2;33m║[0m                                        [2;33m║[0m
[2;33m║[0m  [1;32m✓[0m Chatterbox                        [2;33m║[0m
[2;33m║[0m    ╰→ Send 100 messages              [2;33m║[0m
[2;33m║[0m                                        [2;33m║[0m
[2;33m║[0m  [1;32m✓[0m Money Maker                       [2;33m║[0m
[2;33m║[0m    ╰→ Earn 10,000 coins              [2;33m║[0m
[2;33m║[0m                                        [2;33m║[0m
[2;33m║[0m  [1;30m✗[0m Legendary                         [2;33m║[0m
[2;33m║[0m    ╰→ Reach level 50                 [2;33m║[0m
[2;33m║[0m                                        [2;33m║[0m
[2;33m║[0m  [1;30m✗[0m Millionaire                       [2;33m║[0m
[2;33m║[0m    ╰→ Earn 1,000,000 coins           [2;33m║[0m
[2;33m║[0m                                        [2;33m║[0m
[2;33m╚════════════════════════════════════════╝[0m
```
"""
        
        embed.add_field(name="", value=achievements_display, inline=False)
        embed.set_footer(text="Complete tasks to unlock more achievements!")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="streak", description="[Member] View your daily streak")
    @is_member()
    async def streak(self, interaction: discord.Interaction):
            """View daily streak with beautiful visuals"""
            from utils.visuals import ProgressBar, Emojis, VisualEffects

            # Simulate streak data (in production, fetch from database)
            current_streak = 7
            longest_streak = 15
            next_milestone = 30

            embed = discord.Embed(
                title=f"{Emojis.FIRE} Daily Streak",
                description="Keep your streak alive by claiming `/daily` every day!",
                color=discord.Color.orange()
            )

            # Streak visualization
            streak_display = f"{Emojis.FIRE} " * min(current_streak, 15)
            if current_streak > 15:
                streak_display += f" +{current_streak - 15}"

            embed.add_field(
                name=f"🔥 Current Streak: {current_streak} Days",
                value=streak_display,
                inline=False
            )

            # Progress to next milestone
            milestone_progress = ProgressBar.create_fancy(current_streak, next_milestone, length=15)
            embed.add_field(
                name=f"{Emojis.TARGET} Progress to {next_milestone}-Day Milestone",
                value=milestone_progress,
                inline=False
            )

            # Stats
            embed.add_field(
                name="📊 Streak Stats",
                value=f"```Current: {current_streak} days\nLongest: {longest_streak} days\nNext Goal: {next_milestone} days```",
                inline=True
            )

            # Rewards
            rewards_text = f"{Emojis.COIN} **7 days:** +500 bonus coins\n{Emojis.MONEY_BAG} **30 days:** +2,000 bonus coins\n{Emojis.TROPHY} **100 days:** Special Badge"
            embed.add_field(
                name="🎁 Streak Rewards",
                value=rewards_text,
                inline=True
            )

            # Add visual separator
            separator = VisualEffects.create_separator("stars")
            embed.add_field(
                name=separator,
                value=f"{Emojis.INFO} Don't break your streak! Claim `/daily` every 24 hours!",
                inline=False
            )

            # Milestone achievements
            if current_streak >= 7:
                embed.add_field(
                    name=f"{Emojis.TROPHY} Achievements Unlocked",
                    value=f"{Emojis.SUCCESS} 7-Day Warrior\n{Emojis.FIRE} Streak Master",
                    inline=False
                )

            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.set_footer(text="💡 Longer streaks = bigger rewards!")

            await interaction.response.send_message(embed=embed)


class MarriageView(discord.ui.View):
    """View for marriage proposal"""
    
    def __init__(self, proposer: discord.Member, partner: discord.Member):
        super().__init__(timeout=60)
        self.proposer = proposer
        self.partner = partner
    
    @discord.ui.button(label="💍 Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.partner.id:
            return await interaction.response.send_message("❌ Only the proposed person can respond!", ephemeral=True)
        
        embed = discord.Embed(
            title="💕 Married!",
            description=f"🎉 {self.proposer.mention} and {self.partner.mention} are now married! 💍",
            color=discord.Color.from_rgb(255, 192, 203)
        )
        
        celebration = """
```
╔═══════════════════════════════════════════════╗
║                                               ║
║          🎊 CONGRATULATIONS! 🎊               ║
║                                               ║
║              💕 💍 💕 💍 💕                    ║
║                                               ║
║        May your love last forever!            ║
║                                               ║
╚═══════════════════════════════════════════════╝
```
"""
        embed.add_field(name="", value=celebration, inline=False)
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="💔 Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.partner.id:
            return await interaction.response.send_message("❌ Only the proposed person can respond!", ephemeral=True)
        
        embed = discord.Embed(
            title="💔 Proposal Declined",
            description=f"{self.partner.mention} declined the proposal.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


async def setup(bot):
    await bot.add_cog(Social(bot))
