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
    
    @app_commands.command(name="marry", description="[Member] Propose marriage to someone")
    @is_member()
    async def marry(self, interaction: discord.Interaction, partner: discord.Member):
        """Propose marriage"""
        if partner.id == interaction.user.id:
            return await interaction.response.send_message("❌ You can't marry yourself!", ephemeral=True)
        
        if partner.bot:
            return await interaction.response.send_message("❌ You can't marry a bot!", ephemeral=True)
        
        # Create proposal embed
        embed = discord.Embed(
            title="💍 Marriage Proposal",
            color=discord.Color.from_rgb(255, 192, 203)
        )
        
        proposal_box = f"""
```
╔═══════════════════════════════════════════════╗
║                                               ║
║  💕 {interaction.user.display_name} is proposing to        ║
║     {partner.display_name}!                              ║
║                                               ║
║  💍 Will you marry them? 💍                   ║
║                                               ║
╚═══════════════════════════════════════════════╝
```
"""
        embed.add_field(name="", value=proposal_box, inline=False)
        
        # Create accept/decline buttons
        view = MarriageView(interaction.user, partner)
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="divorce", description="[Member] Divorce your partner")
    @is_member()
    async def divorce(self, interaction: discord.Interaction):
        """Divorce your partner"""
        embed = discord.Embed(
            title="💔 Divorce",
            description="```\nYou are now divorced.\n```",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="adopt", description="[Member] Adopt a pet")
    @is_member()
    async def adopt(self, interaction: discord.Interaction):
        """Show pet adoption menu with beautiful visuals"""
        from utils.visuals import Emojis, VisualEffects

        embed = discord.Embed(
            title="🐾 Pet Adoption Center",
            description="Welcome to the WAN Bot Pet Adoption Center!\nChoose your perfect companion!",
            color=discord.Color.green()
        )

        # Group pets by price
        budget_pets = []
        premium_pets = []
        legendary_pets = []

        for pet_id, pet_data in self.pets.items():
            if pet_data['cost'] <= 2000:
                budget_pets.append(f"{pet_data['emoji']} **{pet_data['name']}** - {pet_data['cost']:,} {Emojis.COIN}")
            elif pet_data['cost'] <= 5000:
                premium_pets.append(f"{pet_data['emoji']} **{pet_data['name']}** - {pet_data['cost']:,} {Emojis.COIN}")
            else:
                legendary_pets.append(f"{pet_data['emoji']} **{pet_data['name']}** - {pet_data['cost']:,} {Emojis.COIN}")

        if budget_pets:
            embed.add_field(
                name="🥉 Common Pets",
                value="\n".join(budget_pets),
                inline=False
            )

        if premium_pets:
            embed.add_field(
                name="🥈 Rare Pets",
                value="\n".join(premium_pets),
                inline=False
            )

        if legendary_pets:
            embed.add_field(
                name="💎 Legendary Pets",
                value="\n".join(legendary_pets),
                inline=False
            )

        # Add visual separator
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} Use `/buy-pet <pet_name>` to adopt a pet!",
            inline=False
        )

        embed.add_field(
            name="✨ Pet Features",
            value="• Feed and play with your pet\n• Level up your pet\n• Earn rewards from pet activities\n• Show off your pet to friends!",
            inline=False
        )

        embed.set_footer(text="💡 Pets require daily care to stay happy!")

        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="buy-pet", description="[Member] Buy a pet")
    @is_member()
    async def buy_pet(self, interaction: discord.Interaction, pet_type: str):
        """Buy a pet"""
        pet_type = pet_type.lower()
        
        if pet_type not in self.pets:
            return await interaction.response.send_message("❌ Invalid pet type!", ephemeral=True)
        
        pet = self.pets[pet_type]
        
        embed = discord.Embed(
            title=f"🎉 Pet Adopted!",
            description=f"You adopted a {pet['emoji']} **{pet['name']}**!",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="pet", description="[Member] View your pet")
    @is_member()
    async def view_pet(self, interaction: discord.Interaction):
        """View your pet with beautiful visuals"""
        from utils.visuals import ProgressBar, Emojis, VisualEffects

        # Simulate pet data (in production, fetch from database)
        pet_name = "Fluffy"
        pet_type = "🐱 Cat"
        pet_level = 5
        pet_happiness = 85
        pet_hunger = 60
        pet_xp = 450
        next_level_xp = 500

        embed = discord.Embed(
            title=f"🐾 Your Pet: {pet_name}",
            description=f"**{pet_type}** • Level {pet_level}",
            color=discord.Color.blue()
        )

        # XP Progress
        xp_bar = ProgressBar.create_xp_bar(pet_xp, next_level_xp)
        embed.add_field(
            name=f"{Emojis.STAR} Experience",
            value=xp_bar,
            inline=False
        )

        # Happiness bar
        happy_bar = ProgressBar.create_fancy(pet_happiness, 100, length=15)
        embed.add_field(
            name=f"{Emojis.HEART} Happiness",
            value=happy_bar,
            inline=False
        )

        # Hunger bar
        hunger_bar = ProgressBar.create_fancy(pet_hunger, 100, length=15)
        embed.add_field(
            name=f"{Emojis.FIRE} Hunger",
            value=hunger_bar,
            inline=False
        )

        # Pet stats
        embed.add_field(
            name="📊 Stats",
            value=f"```Level: {pet_level}\nXP: {pet_xp}/{next_level_xp}\nHappiness: {pet_happiness}%\nHunger: {pet_hunger}%```",
            inline=True
        )

        # Pet activities
        embed.add_field(
            name="🎮 Activities",
            value=f"{Emojis.GAME} `/feed-pet` - Feed your pet\n{Emojis.PARTY} `/play-pet` - Play together\n{Emojis.TARGET} `/train-pet` - Train skills",
            inline=True
        )

        # Add visual separator
        separator = VisualEffects.create_separator("dots")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} Keep your pet happy and fed to earn bonuses!",
            inline=False
        )

        # Status message
        if pet_happiness < 30:
            status = f"{Emojis.WARNING} Your pet is sad! Play with them!"
        elif pet_hunger > 80:
            status = f"{Emojis.WARNING} Your pet is hungry! Feed them!"
        else:
            status = f"{Emojis.SUCCESS} Your pet is doing great!"

        embed.add_field(
            name="💭 Status",
            value=status,
            inline=False
        )

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="💡 Interact with your pet daily for rewards!")

        await interaction.response.send_message(embed=embed)
    
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
