import discord
from datetime import datetime

class EmbedFactory:
    @staticmethod
    def success(title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
    
    @staticmethod
    def error(title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
    
    @staticmethod
    def info(title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=f"ℹ️ {title}",
            description=description,
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
    
    @staticmethod
    def warning(title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=f"⚠️ {title}",
            description=description,
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
    
    @staticmethod
    def music(title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=f"🎵 {title}",
            description=description,
            color=discord.Color.purple(),
            timestamp=datetime.utcnow()
        )
