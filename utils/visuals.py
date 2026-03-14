"""
Visual Enhancement Utilities
Rich graphics, progress bars, animations, and visual elements for Discord embeds
"""

import discord
from typing import Optional, List
import random

class ProgressBar:
    """Create beautiful progress bars"""
    
    @staticmethod
    def create(
        current: int,
        total: int,
        length: int = 10,
        fill: str = "█",
        empty: str = "░",
        show_percentage: bool = True
    ) -> str:
        """Create a progress bar"""
        if total == 0:
            percentage = 0
        else:
            percentage = min(100, int((current / total) * 100))
        
        filled = int((percentage / 100) * length)
        bar = fill * filled + empty * (length - filled)
        
        if show_percentage:
            return f"[{bar}] {percentage}%"
        return f"[{bar}]"
    
    @staticmethod
    def create_fancy(
        current: int,
        total: int,
        length: int = 15,
        show_numbers: bool = True
    ) -> str:
        """Create a fancy gradient progress bar"""
        if total == 0:
            percentage = 0
        else:
            percentage = min(100, int((current / total) * 100))
        
        filled = int((percentage / 100) * length)
        
        # Gradient bars
        if percentage >= 75:
            fill = "🟩"
        elif percentage >= 50:
            fill = "🟨"
        elif percentage >= 25:
            fill = "🟧"
        else:
            fill = "🟥"
        
        bar = fill * filled + "⬜" * (length - filled)
        
        if show_numbers:
            return f"{bar} {current}/{total} ({percentage}%)"
        return f"{bar} {percentage}%"
    
    @staticmethod
    def create_xp_bar(current_xp: int, needed_xp: int) -> str:
        """Create XP progress bar"""
        percentage = min(100, int((current_xp / needed_xp) * 100))
        filled = int(percentage / 10)
        
        bar = "▰" * filled + "▱" * (10 - filled)
        return f"{bar} {current_xp}/{needed_xp} XP"
    
    @staticmethod
    def create_health_bar(current: int, max_health: int) -> str:
        """Create health bar"""
        percentage = int((current / max_health) * 100)
        filled = int(percentage / 10)
        
        if percentage > 60:
            fill = "🟢"
        elif percentage > 30:
            fill = "🟡"
        else:
            fill = "🔴"
        
        bar = fill * filled + "⚫" * (10 - filled)
        return f"{bar} {current}/{max_health} HP"

class Emojis:
    """Emoji collections for visual enhancement"""
    
    # Status
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    LOADING = "⏳"
    
    # Actions
    ADD = "➕"
    REMOVE = "➖"
    EDIT = "✏️"
    DELETE = "🗑️"
    SAVE = "💾"
    
    # Arrows
    UP = "⬆️"
    DOWN = "⬇️"
    LEFT = "⬅️"
    RIGHT = "➡️"
    
    # Numbers (for rankings)
    NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    # Medals
    GOLD = "🥇"
    SILVER = "🥈"
    BRONZE = "🥉"
    
    # Stars
    STAR = "⭐"
    STAR_STRUCK = "🤩"
    SPARKLES = "✨"
    
    # Music
    MUSIC = "🎵"
    MUSICAL_NOTE = "🎶"
    MICROPHONE = "🎤"
    HEADPHONES = "🎧"
    
    # Gaming
    GAME = "🎮"
    TROPHY = "🏆"
    MEDAL = "🏅"
    TARGET = "🎯"
    
    # Social
    HEART = "❤️"
    FIRE = "🔥"
    PARTY = "🎉"
    GIFT = "🎁"
    
    # Time
    CLOCK = "🕐"
    HOURGLASS = "⏳"
    ALARM = "⏰"
    
    # Money
    COIN = "🪙"
    MONEY_BAG = "💰"
    DOLLAR = "💵"
    CHART = "📈"

class AnimatedEmbed:
    """Create animated-looking embeds with visual effects"""
    
    @staticmethod
    def create_level_up(
        user: discord.Member,
        old_level: int,
        new_level: int,
        xp: int,
        next_level_xp: int
    ) -> discord.Embed:
        """Create beautiful level up embed"""
        embed = discord.Embed(
            title=f"🎉 LEVEL UP! 🎉",
            description=f"**{user.mention} reached Level {new_level}!**",
            color=discord.Color.gold()
        )
        
        # Progress visualization
        progress = ProgressBar.create_xp_bar(xp, next_level_xp)
        
        embed.add_field(
            name=f"Level {old_level} ➜ Level {new_level}",
            value=f"```diff\n+ Level Up!\n```",
            inline=False
        )
        
        embed.add_field(
            name="Progress to Next Level",
            value=progress,
            inline=False
        )
        
        # Add visual separator
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━━━━",
            value=f"Keep chatting to earn more XP! {Emojis.FIRE}",
            inline=False
        )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="🌟 Keep up the great work!")
        
        return embed
    
    @staticmethod
    def create_leaderboard(
        title: str,
        entries: List[tuple],
        guild: discord.Guild,
        description: str = ""
    ) -> discord.Embed:
        """Create beautiful leaderboard embed"""
        embed = discord.Embed(
            title=f"🏆 {title}",
            description=description,
            color=discord.Color.gold()
        )
        
        medals = [Emojis.GOLD, Emojis.SILVER, Emojis.BRONZE]
        
        leaderboard_text = []
        for i, (user_id, value) in enumerate(entries[:10], 1):
            member = guild.get_member(user_id)
            if not member:
                continue
            
            # Medal or number
            if i <= 3:
                prefix = medals[i-1]
            else:
                prefix = f"`{i:2d}.`"
            
            # Create bar for visual representation
            max_value = entries[0][1] if entries else 1
            bar_length = int((value / max_value) * 10) if max_value > 0 else 0
            bar = "▰" * bar_length + "▱" * (10 - bar_length)
            
            leaderboard_text.append(
                f"{prefix} **{member.display_name}**\n"
                f"    {bar} `{value:,}`"
            )
        
        embed.description = "\n\n".join(leaderboard_text)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text=f"📊 Total Entries: {len(entries)}")
        
        return embed
    
    @staticmethod
    def create_stats_card(
        user: discord.Member,
        stats: dict
    ) -> discord.Embed:
        """Create beautiful stats card"""
        embed = discord.Embed(
            title=f"📊 Stats for {user.display_name}",
            color=discord.Color.blue()
        )
        
        # Create visual stats
        for stat_name, stat_value in stats.items():
            if isinstance(stat_value, tuple):
                # Progress stat (current, max)
                current, maximum = stat_value
                bar = ProgressBar.create_fancy(current, maximum)
                embed.add_field(
                    name=stat_name,
                    value=bar,
                    inline=False
                )
            else:
                # Regular stat
                embed.add_field(
                    name=stat_name,
                    value=f"```{stat_value}```",
                    inline=True
                )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="✨ Keep being awesome!")
        
        return embed
    
    @staticmethod
    def create_achievement(
        user: discord.Member,
        achievement_name: str,
        achievement_desc: str,
        rarity: str = "common"
    ) -> discord.Embed:
        """Create achievement unlock embed"""
        colors = {
            "common": discord.Color.light_gray(),
            "rare": discord.Color.blue(),
            "epic": discord.Color.purple(),
            "legendary": discord.Color.gold()
        }
        
        emojis = {
            "common": "🎖️",
            "rare": "💎",
            "epic": "👑",
            "legendary": "🌟"
        }
        
        embed = discord.Embed(
            title=f"{emojis.get(rarity, '🏆')} Achievement Unlocked!",
            description=f"**{achievement_name}**\n{achievement_desc}",
            color=colors.get(rarity, discord.Color.gold())
        )
        
        embed.add_field(
            name="Rarity",
            value=f"```{rarity.upper()}```",
            inline=True
        )
        
        embed.add_field(
            name="Unlocked by",
            value=user.mention,
            inline=True
        )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="🎉 Congratulations!")
        
        return embed

class VisualEffects:
    """Visual effects and decorations"""
    
    @staticmethod
    def create_separator(style: str = "default") -> str:
        """Create visual separators"""
        separators = {
            "default": "━━━━━━━━━━━━━━━━━━━━",
            "dots": "• • • • • • • • • • • • • • • •",
            "stars": "✦ ✦ ✦ ✦ ✦ ✦ ✦ ✦ ✦ ✦",
            "arrows": "➤ ➤ ➤ ➤ ➤ ➤ ➤ ➤ ➤ ➤",
            "fancy": "═══════════════════════",
            "wave": "～～～～～～～～～～～～～～～～～～～～"
        }
        return separators.get(style, separators["default"])
    
    @staticmethod
    def create_box(text: str, style: str = "default") -> str:
        """Create text box"""
        styles = {
            "default": ("╔", "═", "╗", "║", "╚", "╝"),
            "round": ("╭", "─", "╮", "│", "╰", "╯"),
            "double": ("╔", "═", "╗", "║", "╚", "╝"),
            "bold": ("┏", "━", "┓", "┃", "┗", "┛")
        }
        
        tl, h, tr, v, bl, br = styles.get(style, styles["default"])
        width = len(text) + 2
        
        return f"{tl}{h * width}{tr}\n{v} {text} {v}\n{bl}{h * width}{br}"
    
    @staticmethod
    def create_badge(text: str, color: str = "blue") -> str:
        """Create badge-style text"""
        colors = {
            "blue": "🔵",
            "green": "🟢",
            "red": "🔴",
            "yellow": "🟡",
            "purple": "🟣",
            "orange": "🟠"
        }
        
        emoji = colors.get(color, "⚪")
        return f"{emoji} **{text}**"
    
    @staticmethod
    def create_percentage_visual(percentage: int) -> str:
        """Create visual percentage representation"""
        if percentage >= 90:
            return f"🟢 {percentage}% (Excellent)"
        elif percentage >= 70:
            return f"🟡 {percentage}% (Good)"
        elif percentage >= 50:
            return f"🟠 {percentage}% (Average)"
        else:
            return f"🔴 {percentage}% (Low)"

class CardGenerator:
    """Generate beautiful card-style embeds"""
    
    @staticmethod
    def create_profile_card(
        user: discord.Member,
        level: int,
        xp: int,
        rank: int,
        total_users: int
    ) -> discord.Embed:
        """Create beautiful profile card"""
        # Calculate XP for next level
        next_level_xp = (level + 1) ** 2 * 100
        current_level_xp = level ** 2 * 100
        xp_in_level = xp - current_level_xp
        xp_needed = next_level_xp - current_level_xp
        
        embed = discord.Embed(
            title=f"✨ {user.display_name}'s Profile",
            color=discord.Color.from_rgb(random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
        )
        
        # Level and XP
        xp_bar = ProgressBar.create_xp_bar(xp_in_level, xp_needed)
        embed.add_field(
            name=f"📊 Level {level}",
            value=xp_bar,
            inline=False
        )
        
        # Rank
        rank_percentage = int((rank / total_users) * 100)
        rank_bar = ProgressBar.create_fancy(total_users - rank, total_users, length=10, show_numbers=False)
        embed.add_field(
            name=f"🏆 Rank #{rank}",
            value=f"{rank_bar}\nTop {rank_percentage}% of server",
            inline=False
        )
        
        # Stats
        embed.add_field(
            name="📈 Total XP",
            value=f"```{xp:,}```",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Messages",
            value=f"```{xp // 20:,}```",
            inline=True
        )
        
        embed.add_field(
            name="⭐ Status",
            value="```Active```",
            inline=True
        )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="🌟 Keep leveling up!")
        
        return embed

# Export all classes
__all__ = [
    'ProgressBar',
    'Emojis',
    'AnimatedEmbed',
    'VisualEffects',
    'CardGenerator'
]
