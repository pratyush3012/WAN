import discord
from discord import app_commands
from discord.ext import commands
from utils.permissions import is_member
from utils.visuals import Emojis, VisualEffects, ProgressBar
import random
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('discord_bot.games')

class Games(commands.Cog):
    """Advanced Games - RPG, Casino, Battles, Tournaments, and More"""
    
    def __init__(self, bot):
        self.bot = bot
        self.player_stats = {}  # {user_id: stats}
        self.active_battles = {}  # {channel_id: battle_data}
        self.tournaments = {}  # {guild_id: tournament_data}
        self.casino_stats = {}  # {user_id: casino_stats}
        self.rpg_characters = {}  # {user_id: character_data}
        self.active_dungeons = {}  # {user_id: dungeon_data}
        self.guilds_system = {}  # {guild_id: guild_data}
    
    # RPG System
    @app_commands.command(name="rpg-create", description="[Member] Create your RPG character")
    @is_member()
    async def rpg_create(self, interaction: discord.Interaction, name: str, character_class: str):
        """Create RPG character"""
        
        user_id = interaction.user.id
        
        if user_id in self.rpg_characters:
            return await interaction.response.send_message(
                "❌ You already have an RPG character! Use `/rpg-profile` to view it.",
                ephemeral=True
            )
        
        classes = {
            "warrior": {"hp": 120, "attack": 15, "defense": 12, "magic": 5, "emoji": "⚔️"},
            "mage": {"hp": 80, "attack": 8, "defense": 6, "magic": 18, "emoji": "🔮"},
            "archer": {"hp": 100, "attack": 14, "defense": 8, "magic": 10, "emoji": "🏹"},
            "rogue": {"hp": 90, "attack": 16, "defense": 7, "magic": 8, "emoji": "🗡️"},
            "paladin": {"hp": 110, "attack": 12, "defense": 15, "magic": 12, "emoji": "🛡️"}
        }
        
        character_class = character_class.lower()
        if character_class not in classes:
            class_list = ", ".join(classes.keys())
            return await interaction.response.send_message(
                f"❌ Invalid class! Choose from: {class_list}",
                ephemeral=True
            )
        
        stats = classes[character_class]
        
        self.rpg_characters[user_id] = {
            "name": name,
            "class": character_class,
            "level": 1,
            "xp": 0,
            "hp": stats["hp"],
            "max_hp": stats["hp"],
            "attack": stats["attack"],
            "defense": stats["defense"],
            "magic": stats["magic"],
            "gold": 100,
            "inventory": ["Health Potion", "Rusty Sword"],
            "location": "Town Square",
            "quests_completed": 0,
            "battles_won": 0,
            "created_at": datetime.utcnow()
        }
        
        embed = discord.Embed(
            title=f"{stats['emoji']} Character Created!",
            description=f"Welcome, **{name}** the {character_class.title()}!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name=f"{Emojis.FIRE} Stats",
            value=f"```HP: {stats['hp']}\nAttack: {stats['attack']}\nDefense: {stats['defense']}\nMagic: {stats['magic']}```",
            inline=True
        )
        
        embed.add_field(
            name=f"{Emojis.COIN} Starting Items",
            value=f"```Gold: 100\nHealth Potion x1\nRusty Sword x1```",
            inline=True
        )
        
        embed.add_field(
            name=f"{Emojis.SPARKLES} Next Steps",
            value="• `/rpg-profile` - View character\n• `/rpg-adventure` - Go on adventures\n• `/rpg-battle @user` - Battle players\n• `/rpg-shop` - Buy equipment",
            inline=False
        )
        
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.FIRE} Your adventure begins now!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="rpg-profile", description="[Member] View your RPG character")
    @is_member()
    async def rpg_profile(self, interaction: discord.Interaction, user: discord.Member = None):
        """View RPG character profile"""
        
        target_user = user or interaction.user
        user_id = target_user.id
        
        if user_id not in self.rpg_characters:
            return await interaction.response.send_message(
                f"❌ {target_user.display_name} doesn't have an RPG character!",
                ephemeral=True
            )
        
        char = self.rpg_characters[user_id]
        
        # Class emojis
        class_emojis = {
            "warrior": "⚔️", "mage": "🔮", "archer": "🏹", 
            "rogue": "🗡️", "paladin": "🛡️"
        }
        
        embed = discord.Embed(
            title=f"{class_emojis.get(char['class'], '⚔️')} {char['name']}",
            description=f"**Level {char['level']} {char['class'].title()}**",
            color=discord.Color.purple()
        )
        
        # XP Progress
        xp_needed = char['level'] * 100
        xp_bar = ProgressBar.create_xp_bar(char['xp'], xp_needed)
        
        embed.add_field(
            name=f"{Emojis.STAR} Experience",
            value=xp_bar,
            inline=False
        )
        
        # HP Bar
        hp_bar = ProgressBar.create_health_bar(char['hp'], char['max_hp'])
        
        embed.add_field(
            name=f"{Emojis.HEART} Health",
            value=hp_bar,
            inline=False
        )
        
        # Stats
        embed.add_field(
            name=f"{Emojis.FIRE} Combat Stats",
            value=f"```Attack: {char['attack']}\nDefense: {char['defense']}\nMagic: {char['magic']}```",
            inline=True
        )
        
        embed.add_field(
            name=f"{Emojis.COIN} Resources",
            value=f"```Gold: {char['gold']}\nLocation: {char['location']}```",
            inline=True
        )
        
        embed.add_field(
            name=f"{Emojis.TROPHY} Achievements",
            value=f"```Quests: {char['quests_completed']}\nBattles Won: {char['battles_won']}\nDays Active: {(datetime.utcnow() - char['created_at']).days}```",
            inline=True
        )
        
        # Inventory preview
        inventory_preview = ", ".join(char['inventory'][:5])
        if len(char['inventory']) > 5:
            inventory_preview += f" (+{len(char['inventory']) - 5} more)"
        
        embed.add_field(
            name=f"{Emojis.GAME} Inventory",
            value=f"```{inventory_preview or 'Empty'}```",
            inline=False
        )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="rpg-adventure", description="[Member] Go on an adventure")
    @is_member()
    async def rpg_adventure(self, interaction: discord.Interaction):
        """Go on RPG adventure"""
        
        user_id = interaction.user.id
        
        if user_id not in self.rpg_characters:
            return await interaction.response.send_message(
                "❌ Create an RPG character first with `/rpg-create`!",
                ephemeral=True
            )
        
        char = self.rpg_characters[user_id]
        
        if char['hp'] <= 0:
            return await interaction.response.send_message(
                "❌ You need to heal before going on adventures! Use a Health Potion.",
                ephemeral=True
            )
        
        # Adventure scenarios
        adventures = [
            {
                "name": "Goblin Cave",
                "description": "You encounter a group of goblins!",
                "enemy": "Goblin",
                "difficulty": "Easy",
                "xp_reward": 25,
                "gold_reward": 15,
                "success_chance": 80
            },
            {
                "name": "Ancient Ruins",
                "description": "You explore mysterious ruins and find treasure!",
                "enemy": "Skeleton Warrior",
                "difficulty": "Medium",
                "xp_reward": 50,
                "gold_reward": 35,
                "success_chance": 60
            },
            {
                "name": "Dragon's Lair",
                "description": "You face a mighty dragon!",
                "enemy": "Young Dragon",
                "difficulty": "Hard",
                "xp_reward": 100,
                "gold_reward": 75,
                "success_chance": 40
            }
        ]
        
        adventure = random.choice(adventures)
        success = random.randint(1, 100) <= adventure['success_chance']
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Adventure: {adventure['name']}",
            description=adventure['description'],
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name=f"{Emojis.TARGET} Enemy",
            value=f"```{adventure['enemy']} ({adventure['difficulty']})```",
            inline=True
        )
        
        embed.add_field(
            name=f"{Emojis.CHART} Success Chance",
            value=f"```{adventure['success_chance']}%```",
            inline=True
        )
        
        if success:
            # Success!
            char['xp'] += adventure['xp_reward']
            char['gold'] += adventure['gold_reward']
            char['battles_won'] += 1
            
            # Level up check
            xp_needed = char['level'] * 100
            if char['xp'] >= xp_needed:
                char['level'] += 1
                char['xp'] -= xp_needed
                char['max_hp'] += 10
                char['hp'] = char['max_hp']  # Full heal on level up
                char['attack'] += 2
                char['defense'] += 1
                
                embed.add_field(
                    name=f"{Emojis.SPARKLES} LEVEL UP!",
                    value=f"```You reached level {char['level']}!\n+10 HP, +2 Attack, +1 Defense```",
                    inline=False
                )
            
            embed.add_field(
                name=f"{Emojis.SUCCESS} Victory!",
                value=f"```XP: +{adventure['xp_reward']}\nGold: +{adventure['gold_reward']}```",
                inline=False
            )
            embed.color = discord.Color.green()
            
        else:
            # Failure
            damage = random.randint(10, 25)
            char['hp'] = max(0, char['hp'] - damage)
            
            embed.add_field(
                name=f"{Emojis.ERROR} Defeat!",
                value=f"```You were defeated!\nHP: -{damage}```",
                inline=False
            )
            embed.color = discord.Color.red()
            
            if char['hp'] <= 0:
                embed.add_field(
                    name=f"{Emojis.WARNING} Knocked Out!",
                    value="You need to heal before your next adventure!",
                    inline=False
                )
        
        separator = VisualEffects.create_separator("arrows")
        embed.add_field(
            name=separator,
            value=f"{Emojis.FIRE} Ready for another adventure?",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    # Casino Games
    @app_commands.command(name="casino-slots", description="[Member] Play slot machine")
    @is_member()
    async def casino_slots(self, interaction: discord.Interaction, bet: int):
        """Play slot machine"""
        
        if bet < 10 or bet > 1000:
            return await interaction.response.send_message(
                "❌ Bet must be between 10 and 1000 coins!",
                ephemeral=True
            )
        
        # Slot symbols
        symbols = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
        weights = [30, 25, 20, 15, 7, 2, 1]  # Rarity weights
        
        # Spin the slots
        result = random.choices(symbols, weights=weights, k=3)
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Slot Machine",
            color=discord.Color.gold()
        )
        
        # Display slots
        slot_display = f"```\n┌─────────────┐\n│ {result[0]} │ {result[1]} │ {result[2]} │\n└─────────────┘```"
        
        embed.add_field(
            name=f"{Emojis.GAME} Spin Result",
            value=slot_display,
            inline=False
        )
        
        # Calculate winnings
        winnings = 0
        if result[0] == result[1] == result[2]:
            # Three of a kind
            multipliers = {"🍒": 5, "🍋": 8, "🍊": 10, "🍇": 15, "⭐": 25, "💎": 50, "7️⃣": 100}
            winnings = bet * multipliers.get(result[0], 5)
            
            embed.add_field(
                name=f"{Emojis.SUCCESS} JACKPOT!",
                value=f"```Three {result[0]}!\nWinnings: {winnings} coins```",
                inline=True
            )
            embed.color = discord.Color.green()
            
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            # Two of a kind
            winnings = bet * 2
            
            embed.add_field(
                name=f"{Emojis.FIRE} Match!",
                value=f"```Two matching symbols!\nWinnings: {winnings} coins```",
                inline=True
            )
            embed.color = discord.Color.blue()
            
        else:
            # No match
            embed.add_field(
                name=f"{Emojis.ERROR} No Match",
                value=f"```Better luck next time!\nLoss: -{bet} coins```",
                inline=True
            )
            embed.color = discord.Color.red()
        
        # Profit/Loss
        profit = winnings - bet
        embed.add_field(
            name=f"{Emojis.CHART} Result",
            value=f"```Bet: {bet}\nWon: {winnings}\nProfit: {profit:+d}```",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="casino-blackjack", description="[Member] Play blackjack")
    @is_member()
    async def casino_blackjack(self, interaction: discord.Interaction, bet: int):
        """Play blackjack"""
        
        if bet < 10 or bet > 1000:
            return await interaction.response.send_message(
                "❌ Bet must be between 10 and 1000 coins!",
                ephemeral=True
            )
        
        # Card deck
        suits = ["♠️", "♥️", "♦️", "♣️"]
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        
        def card_value(card):
            if card[0] in ["J", "Q", "K"]:
                return 10
            elif card[0] == "A":
                return 11  # Simplified - always 11 for demo
            else:
                return int(card[0])
        
        def draw_card():
            return random.choice(ranks) + random.choice(suits)
        
        # Deal initial cards
        player_cards = [draw_card(), draw_card()]
        dealer_cards = [draw_card(), draw_card()]
        
        player_total = sum(card_value(card) for card in player_cards)
        dealer_total = sum(card_value(card) for card in dealer_cards)
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Blackjack",
            description=f"Bet: {bet} coins",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name=f"{Emojis.FIRE} Your Cards ({player_total})",
            value=f"```{' '.join(player_cards)}```",
            inline=True
        )
        
        embed.add_field(
            name=f"{Emojis.TARGET} Dealer Cards",
            value=f"```{dealer_cards[0]} ??```",
            inline=True
        )
        
        # Determine winner (simplified)
        if player_total == 21:
            result = "BLACKJACK!"
            winnings = bet * 2.5
            color = discord.Color.green()
        elif player_total > 21:
            result = "BUST!"
            winnings = 0
            color = discord.Color.red()
        elif dealer_total > 21 or player_total > dealer_total:
            result = "WIN!"
            winnings = bet * 2
            color = discord.Color.green()
        elif player_total == dealer_total:
            result = "PUSH!"
            winnings = bet
            color = discord.Color.yellow()
        else:
            result = "LOSE!"
            winnings = 0
            color = discord.Color.red()
        
        embed.add_field(
            name=f"{Emojis.CHART} Result",
            value=f"```{result}\nWinnings: {winnings} coins\nProfit: {winnings - bet:+d}```",
            inline=False
        )
        
        embed.color = color
        
        await interaction.response.send_message(embed=embed)
    
    # Battle System
    @app_commands.command(name="battle", description="[Member] Challenge another player to battle")
    @is_member()
    async def battle(self, interaction: discord.Interaction, opponent: discord.Member):
        """Challenge player to battle"""
        
        if opponent.bot:
            return await interaction.response.send_message(
                "❌ You can't battle bots!",
                ephemeral=True
            )
        
        if opponent.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ You can't battle yourself!",
                ephemeral=True
            )
        
        # Check if both players have RPG characters
        if interaction.user.id not in self.rpg_characters:
            return await interaction.response.send_message(
                "❌ You need an RPG character! Use `/rpg-create` first.",
                ephemeral=True
            )
        
        if opponent.id not in self.rpg_characters:
            return await interaction.response.send_message(
                f"❌ {opponent.display_name} doesn't have an RPG character!",
                ephemeral=True
            )
        
        challenger = self.rpg_characters[interaction.user.id]
        defender = self.rpg_characters[opponent.id]
        
        # Battle simulation
        challenger_power = challenger['attack'] + challenger['magic'] + challenger['level'] * 5
        defender_power = defender['defense'] + defender['magic'] + defender['level'] * 5
        
        # Add randomness
        challenger_roll = random.randint(1, 20)
        defender_roll = random.randint(1, 20)
        
        challenger_total = challenger_power + challenger_roll
        defender_total = defender_power + defender_roll
        
        embed = discord.Embed(
            title=f"{Emojis.FIRE} Epic Battle!",
            description=f"**{challenger['name']}** vs **{defender['name']}**",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name=f"⚔️ {interaction.user.display_name}",
            value=f"```Level: {challenger['level']}\nPower: {challenger_power}\nRoll: {challenger_roll}\nTotal: {challenger_total}```",
            inline=True
        )
        
        embed.add_field(
            name=f"🛡️ {opponent.display_name}",
            value=f"```Level: {defender['level']}\nPower: {defender_power}\nRoll: {defender_roll}\nTotal: {defender_total}```",
            inline=True
        )
        
        # Determine winner
        if challenger_total > defender_total:
            winner = interaction.user
            winner_char = challenger
            loser_char = defender
            embed.color = discord.Color.green()
        else:
            winner = opponent
            winner_char = defender
            loser_char = challenger
            embed.color = discord.Color.blue()
        
        # Rewards
        xp_reward = 30
        gold_reward = 20
        
        winner_char['xp'] += xp_reward
        winner_char['gold'] += gold_reward
        winner_char['battles_won'] += 1
        
        embed.add_field(
            name=f"{Emojis.TROPHY} Victory!",
            value=f"**{winner.display_name}** wins!\n```XP: +{xp_reward}\nGold: +{gold_reward}```",
            inline=False
        )
        
        separator = VisualEffects.create_separator("swords")
        embed.add_field(
            name=separator,
            value=f"{Emojis.FIRE} Epic battle! Both warriors fought valiantly!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="game-stats", description="[Member] View your gaming statistics")
    @is_member()
    async def game_stats(self, interaction: discord.Interaction):
        """View gaming statistics"""
        
        user_id = interaction.user.id
        
        embed = discord.Embed(
            title=f"{Emojis.CHART} Gaming Statistics",
            description=f"**{interaction.user.display_name}'s** game data",
            color=discord.Color.purple()
        )
        
        # RPG Stats
        if user_id in self.rpg_characters:
            char = self.rpg_characters[user_id]
            embed.add_field(
                name=f"{Emojis.SPARKLES} RPG Character",
                value=f"```Name: {char['name']}\nLevel: {char['level']}\nClass: {char['class'].title()}\nBattles Won: {char['battles_won']}```",
                inline=True
            )
        else:
            embed.add_field(
                name=f"{Emojis.INFO} RPG Character",
                value="```No character created\nUse /rpg-create```",
                inline=True
            )
        
        # Casino Stats (simulated)
        casino_wins = random.randint(0, 50)
        casino_losses = random.randint(0, 30)
        total_bet = random.randint(1000, 10000)
        
        embed.add_field(
            name=f"{Emojis.COIN} Casino Stats",
            value=f"```Wins: {casino_wins}\nLosses: {casino_losses}\nTotal Bet: {total_bet}```",
            inline=True
        )
        
        # General Gaming
        games_played = casino_wins + casino_losses + (char['battles_won'] if user_id in self.rpg_characters else 0)
        
        embed.add_field(
            name=f"{Emojis.GAME} General Stats",
            value=f"```Games Played: {games_played}\nFavorite: RPG\nRank: Adventurer```",
            inline=True
        )
        
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.FIRE} Keep playing to unlock achievements!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Games(bot))