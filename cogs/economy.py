import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import EmbedFactory
from utils.database import Database
from utils.permissions import is_member
import random
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('discord_bot.economy')

class Economy(commands.Cog):
    """Economy system with currency, shop, and inventory - Members only"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.daily_cooldowns = {}
        self.work_cooldowns = {}
        
        # Shop items
        self.shop_items = {
            "coffee": {"name": "☕ Coffee", "price": 50, "description": "A nice cup of coffee"},
            "pizza": {"name": "🍕 Pizza", "price": 100, "description": "Delicious pizza slice"},
            "trophy": {"name": "🏆 Trophy", "price": 500, "description": "A shiny trophy"},
            "crown": {"name": "👑 Crown", "price": 1000, "description": "Royal crown"},
            "gem": {"name": "💎 Gem", "price": 2500, "description": "Rare gem"},
            "rocket": {"name": "🚀 Rocket", "price": 5000, "description": "To the moon!"},
        }
    
    @app_commands.command(name="balance", description="[Member] Check your balance")
    @is_member()
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        """Check balance with beautiful visual card"""
        member = member or interaction.user

        # Import visual utilities
        from utils.visuals import CardGenerator, ProgressBar, Emojis, VisualEffects

        # Placeholder balance (in production, fetch from database)
        balance = random.randint(0, 10000)
        bank = random.randint(0, 50000)
        total = balance + bank

        # Calculate wealth level
        if total >= 100000:
            wealth_level = "💎 Diamond"
            color = discord.Color.from_rgb(185, 242, 255)
        elif total >= 50000:
            wealth_level = "🏆 Gold"
            color = discord.Color.gold()
        elif total >= 10000:
            wealth_level = "🥈 Silver"
            color = discord.Color.from_rgb(192, 192, 192)
        else:
            wealth_level = "🥉 Bronze"
            color = discord.Color.from_rgb(205, 127, 50)

        embed = discord.Embed(
            title=f"💰 {member.display_name}'s Wallet",
            color=color
        )

        # Wallet display with visual bars
        wallet_bar = ProgressBar.create_fancy(balance, max(balance, 10000), length=15, show_numbers=False)
        bank_bar = ProgressBar.create_fancy(bank, max(bank, 50000), length=15, show_numbers=False)

        embed.add_field(
            name=f"{Emojis.COIN} Wallet",
            value=f"{wallet_bar}\n```{balance:,} coins```",
            inline=False
        )

        embed.add_field(
            name=f"{Emojis.MONEY_BAG} Bank",
            value=f"{bank_bar}\n```{bank:,} coins```",
            inline=False
        )

        embed.add_field(
            name=f"{Emojis.CHART} Total Wealth",
            value=f"```{total:,} coins```",
            inline=True
        )

        embed.add_field(
            name="🏅 Wealth Level",
            value=f"```{wealth_level}```",
            inline=True
        )

        # Add visual separator
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.FIRE} Keep earning to reach the next level!",
            inline=False
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="💡 Use /daily and /work to earn more coins!")

        await interaction.response.send_message(embed=embed)
    
    async def update_balance(self, user_id: int, amount: int):
        """Update user's balance"""
        # Placeholder for database update
        pass
    
    @app_commands.command(name="daily", description="[Member] Claim your daily reward")
    @is_member()
    async def daily(self, interaction: discord.Interaction):
        """Claim daily reward with animated visuals"""
        from utils.visuals import Emojis, ProgressBar, VisualEffects

        user_id = interaction.user.id
        now = datetime.utcnow()

        # Check cooldown
        if user_id in self.daily_cooldowns:
            last_claim = self.daily_cooldowns[user_id]
            time_diff = now - last_claim

            if time_diff < timedelta(hours=24):
                remaining = timedelta(hours=24) - time_diff
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60

                # Create cooldown embed with visual timer
                embed = discord.Embed(
                    title=f"{Emojis.HOURGLASS} Daily Cooldown",
                    description=f"You already claimed your daily reward!",
                    color=discord.Color.orange()
                )

                # Visual countdown
                total_seconds = 24 * 3600
                elapsed_seconds = time_diff.total_seconds()
                progress_bar = ProgressBar.create_fancy(
                    int(elapsed_seconds),
                    total_seconds,
                    length=15,
                    show_numbers=False
                )

                embed.add_field(
                    name="⏰ Time Until Next Claim",
                    value=f"{progress_bar}\n```{hours}h {minutes}m remaining```",
                    inline=False
                )

                embed.set_footer(text="💡 Come back tomorrow for your reward!")

                return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Give reward
        reward = random.randint(100, 500)
        streak = random.randint(1, 30)  # In production, fetch from database
        bonus = streak * 10 if streak >= 7 else 0
        total_reward = reward + bonus

        self.daily_cooldowns[user_id] = now

        # Create beautiful reward embed
        embed = discord.Embed(
            title=f"{Emojis.GIFT} Daily Reward Claimed!",
            description=f"**{interaction.user.mention} received their daily reward!**",
            color=discord.Color.green()
        )

        # Reward breakdown
        embed.add_field(
            name=f"{Emojis.COIN} Base Reward",
            value=f"```+{reward} coins```",
            inline=True
        )

        if bonus > 0:
            embed.add_field(
                name=f"{Emojis.FIRE} Streak Bonus",
                value=f"```+{bonus} coins```",
                inline=True
            )

        embed.add_field(
            name=f"{Emojis.MONEY_BAG} Total Earned",
            value=f"```{total_reward} coins```",
            inline=True
        )

        # Streak visualization
        streak_display = f"{Emojis.FIRE} " * min(streak, 10)
        embed.add_field(
            name=f"🔥 Current Streak: {streak} Days",
            value=streak_display,
            inline=False
        )

        # Next claim time
        next_claim = now + timedelta(hours=24)
        embed.add_field(
            name="⏰ Next Claim",
            value=f"<t:{int(next_claim.timestamp())}:R>",
            inline=False
        )

        # Milestones
        if streak == 7:
            embed.add_field(
                name=f"{Emojis.TROPHY} Milestone Reached!",
                value="🎉 7-day streak! Keep it up!",
                inline=False
            )
        elif streak == 30:
            embed.add_field(
                name=f"{Emojis.STAR} LEGENDARY STREAK!",
                value="🌟 30-day streak! You're amazing!",
                inline=False
            )

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="💡 Claim daily to build your streak and earn bonus coins!")

        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="work", description="[Member] Work to earn coins")
    @is_member()
    async def work(self, interaction: discord.Interaction):
        """Work for coins"""
        user_id = interaction.user.id
        now = datetime.utcnow()
        
        # Check cooldown (1 hour)
        if user_id in self.work_cooldowns:
            last_work = self.work_cooldowns[user_id]
            time_diff = now - last_work
            
            if time_diff < timedelta(hours=1):
                remaining = timedelta(hours=1) - time_diff
                minutes = remaining.seconds // 60
                
                return await interaction.response.send_message(
                    embed=EmbedFactory.error(
                        "⏰ Cooldown",
                        f"You're tired! Rest for **{minutes}m** before working again."
                    ),
                    ephemeral=True
                )
        
        # Work jobs
        jobs = [
            ("streamed on Twitch", 50, 150),
            ("made YouTube videos", 75, 200),
            ("coded a Discord bot", 100, 250),
            ("played games", 40, 120),
            ("moderated the server", 60, 180),
            ("created memes", 30, 100),
        ]
        
        job, min_earn, max_earn = random.choice(jobs)
        earned = random.randint(min_earn, max_earn)
        self.work_cooldowns[user_id] = now
        
        embed = EmbedFactory.success(
            "💼 Work",
            f"You {job} and earned **{earned} 🪙**!"
        )
        embed.set_footer(text="You can work again in 1 hour")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="shop", description="[Member] View the shop")
    @is_member()
    async def shop(self, interaction: discord.Interaction):
            """Display shop with beautiful visuals"""
            from utils.visuals import Emojis, VisualEffects

            embed = discord.Embed(
                title=f"{Emojis.MONEY_BAG} WAN Bot Shop",
                description="Buy items with your hard-earned coins!",
                color=discord.Color.blue()
            )

            # Group items by price range
            cheap_items = []
            medium_items = []
            expensive_items = []

            for item_id, item in self.shop_items.items():
                item_display = f"{item['name']} - **{item['price']:,}** {Emojis.COIN}"
                if item['price'] < 500:
                    cheap_items.append(item_display)
                elif item['price'] < 2500:
                    medium_items.append(item_display)
                else:
                    expensive_items.append(item_display)

            if cheap_items:
                embed.add_field(
                    name="🥉 Budget Items (< 500 coins)",
                    value="\n".join(cheap_items),
                    inline=False
                )

            if medium_items:
                embed.add_field(
                    name="🥈 Premium Items (500-2,500 coins)",
                    value="\n".join(medium_items),
                    inline=False
                )

            if expensive_items:
                embed.add_field(
                    name="💎 Luxury Items (2,500+ coins)",
                    value="\n".join(expensive_items),
                    inline=False
                )

            # Add visual separator
            separator = VisualEffects.create_separator("stars")
            embed.add_field(
                name=separator,
                value=f"{Emojis.INFO} Use `/buy <item>` to purchase items!",
                inline=False
            )

            embed.set_footer(text="💡 Earn coins with /daily and /work!")

            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="buy", description="[Member] Buy an item from the shop")
    @is_member()
    async def buy(self, interaction: discord.Interaction, item: str):
        """Buy an item"""
        item = item.lower()
        
        if item not in self.shop_items:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Item Not Found", "That item doesn't exist in the shop!"),
                ephemeral=True
            )
        
        shop_item = self.shop_items[item]
        
        # Check balance (placeholder)
        balance = random.randint(0, 10000)
        
        if balance < shop_item['price']:
            return await interaction.response.send_message(
                embed=EmbedFactory.error(
                    "Insufficient Funds",
                    f"You need **{shop_item['price']} 🪙** but only have **{balance} 🪙**"
                ),
                ephemeral=True
            )
        
        embed = EmbedFactory.success(
            "✅ Purchase Successful",
            f"You bought {shop_item['name']} for **{shop_item['price']} 🪙**!"
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="inventory", description="[Member] View your inventory")
    @is_member()
    async def inventory(self, interaction: discord.Interaction):
        """Display inventory"""
        # Placeholder inventory
        items = ["☕ Coffee x2", "🍕 Pizza x1", "🏆 Trophy x1"]
        
        embed = discord.Embed(
            title=f"🎒 {interaction.user.display_name}'s Inventory",
            description="\n".join(items) if items else "Your inventory is empty!",
            color=discord.Color.purple()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="give", description="[Member] Give coins to another user")
    @is_member()
    async def give(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        """Give coins to another user"""
        if member.bot:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid User", "You can't give coins to bots!"),
                ephemeral=True
            )
        
        if member.id == interaction.user.id:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid User", "You can't give coins to yourself!"),
                ephemeral=True
            )
        
        if amount < 1:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid Amount", "Amount must be at least 1 coin!"),
                ephemeral=True
            )
        
        embed = EmbedFactory.success(
            "💸 Transfer Complete",
            f"You gave **{amount} 🪙** to {member.mention}!"
        )
        
        await interaction.response.send_message(embed=embed)
    
    # leaderboard-coins and gamble removed to stay under 100 command limit

async def setup(bot):
    await bot.add_cog(Economy(bot))
