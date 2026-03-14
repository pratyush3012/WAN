import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
from utils.embeds import EmbedFactory
from utils.database import Database
import time
import logging
from collections import deque, defaultdict
import asyncio

logger = logging.getLogger('discord_bot.translation')

class TranslationView(discord.ui.View):
    def __init__(self, original_message, cog, timeout=180):
        super().__init__(timeout=timeout)
        self.original_message = original_message
        self.cog = cog
        self.languages = {
            "🇺🇸": ("en", "English"),
            "🇯🇵": ("ja", "Japanese"),
            "🇪🇸": ("es", "Spanish"),
            "🇫🇷": ("fr", "French"),
            "🇩🇪": ("de", "German"),
            "🇰🇷": ("ko", "Korean"),
            "🇷🇺": ("ru", "Russian"),
            "🇮🇳": ("hi", "Hindi")
        }
        
        for emoji, (code, name) in self.languages.items():
            button = discord.ui.Button(emoji=emoji, label=name, style=discord.ButtonStyle.secondary)
            button.callback = self.create_callback(code, name)
            self.add_item(button)
    
    def create_callback(self, lang_code, lang_name):
        async def callback(interaction: discord.Interaction):
            # Check per-user rate limit
            if not await self.cog.check_user_rate_limit(interaction.user.id):
                return await interaction.response.send_message(
                    embed=EmbedFactory.error("Rate Limited", "Please wait before translating again (10s cooldown per user)"),
                    ephemeral=True
                )
            
            # Check global API rate limit
            if not await self.cog.check_api_rate_limit():
                return await interaction.response.send_message(
                    embed=EmbedFactory.error("Service Busy", "Translation service is temporarily busy. Please try again in a minute."),
                    ephemeral=True
                )
            
            try:
                # Use free deep-translator library (no API key needed!)
                translator = GoogleTranslator(source='auto', target=lang_code)
                # Run translation in executor to avoid blocking
                loop = asyncio.get_event_loop()
                translated = await loop.run_in_executor(
                    None, 
                    translator.translate, 
                    self.original_message.content
                )
                
                embed = EmbedFactory.info(f"Translation to {lang_name}", translated)
                embed.add_field(name="Original", value=self.original_message.content[:1024], inline=False)
                embed.set_footer(text=f"Translated by {interaction.user.display_name} • ✨ Free translation")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                logger.error(f"Translation error: {e}")
                await interaction.response.send_message(
                    embed=EmbedFactory.error("Translation Error", "Could not translate this message. Please try again later."),
                    ephemeral=True
                )
        return callback

class Translation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        
        # Per-user rate limiting (10 second cooldown)
        self.user_cooldowns = {}
        
        # Global API rate limiting (60 calls per minute)
        self.api_calls = deque(maxlen=100)
        self.max_calls_per_minute = 60
        
        # Per-guild reaction cooldown (5 seconds)
        self.guild_reaction_cooldown = {}
    
    async def check_user_rate_limit(self, user_id: int) -> bool:
        """Check if user can make a translation request"""
        now = time.time()
        
        if user_id in self.user_cooldowns:
            if now - self.user_cooldowns[user_id] < 10:  # 10 second cooldown
                return False
        
        self.user_cooldowns[user_id] = now
        
        # Cleanup old entries (older than 1 minute)
        to_remove = [uid for uid, timestamp in self.user_cooldowns.items() if now - timestamp > 60]
        for uid in to_remove:
            del self.user_cooldowns[uid]
        
        return True
    
    async def check_api_rate_limit(self) -> bool:
        """Check if we can make an API call (global rate limit)"""
        now = time.time()
        
        # Remove calls older than 1 minute
        while self.api_calls and now - self.api_calls[0] > 60:
            self.api_calls.popleft()
        
        if len(self.api_calls) >= self.max_calls_per_minute:
            logger.warning("Translation API rate limit reached")
            return False
        
        self.api_calls.append(now)
        return True
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        config = await self.db.get_guild_config(message.guild.id)
        if not config.translation_enabled:
            return
        
        # Skip commands, links, short messages
        if message.content.startswith(('/', '!', 'http://', 'https://')) or len(message.content) < 20:
            return
        
        # Per-guild cooldown for reactions (prevent spam)
        guild_id = message.guild.id
        now = time.time()
        if guild_id in self.guild_reaction_cooldown:
            if now - self.guild_reaction_cooldown[guild_id] < 5:  # 5 second cooldown per guild
                return
        
        self.guild_reaction_cooldown[guild_id] = now
        
        # Only add reaction to longer messages
        if len(message.content) > 50:
            try:
                await message.add_reaction("🌐")
            except Exception as e:
                logger.debug(f"Could not add reaction: {e}")
    
    @app_commands.command(name="translate", description="Translate a message to another language")
    async def translate(self, interaction: discord.Interaction, text: str, target_language: str):
        # Check rate limits
        if not await self.check_user_rate_limit(interaction.user.id):
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Rate Limited", "Please wait 10 seconds before translating again"),
                ephemeral=True
            )
        
        if not await self.check_api_rate_limit():
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Service Busy", "Translation service is temporarily busy. Please try again in a minute."),
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            translator = GoogleTranslator(source='auto', target=target_language)
            translated = translator.translate(text)
            
            embed = EmbedFactory.info(f"Translation to {target_language}", translated)
            embed.add_field(name="Original", value=text[:1024], inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            await interaction.followup.send(
                embed=EmbedFactory.error("Translation Error", "Could not translate. Please check the language code and try again."),
                ephemeral=True
            )
    
    @app_commands.command(name="translate_message", description="Translate a specific message by ID")
    async def translate_message(self, interaction: discord.Interaction, message_id: str, target_language: str):
        # Check rate limits
        if not await self.check_user_rate_limit(interaction.user.id):
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Rate Limited", "Please wait 10 seconds before translating again"),
                ephemeral=True
            )
        
        if not await self.check_api_rate_limit():
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Service Busy", "Translation service is temporarily busy. Please try again in a minute."),
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            message = await interaction.channel.fetch_message(int(message_id))
            translator = GoogleTranslator(source='auto', target=target_language)
            translated = translator.translate(message.content)
            
            embed = EmbedFactory.info(f"Translation to {target_language}", translated)
            embed.add_field(name="Original", value=message.content[:1024], inline=False)
            embed.add_field(name="Author", value=message.author.mention, inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.followup.send(
                embed=EmbedFactory.error("Invalid ID", "Please provide a valid message ID"),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Translation error: {e}")
            await interaction.followup.send(
                embed=EmbedFactory.error("Translation Error", "Could not translate this message"),
                ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.emoji.name != "🌐":
            return
        
        if payload.user_id == self.bot.user.id:
            return
        
        try:
            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                return
                
            message = await channel.fetch_message(payload.message_id)
            
            if message.author.bot:
                return
            
            # Send translation view
            view = TranslationView(message, self)
            
            user = await self.bot.fetch_user(payload.user_id)
            embed = EmbedFactory.info("Select Translation Language", "Click a button below to translate this message")
            await user.send(embed=embed, view=view)
        except discord.Forbidden:
            # User has DMs disabled
            logger.debug(f"Could not DM user {payload.user_id} for translation")
        except Exception as e:
            logger.error(f"Error in translation reaction handler: {e}")

async def setup(bot):
    await bot.add_cog(Translation(bot))
