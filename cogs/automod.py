import discord
from discord import app_commands
from discord.ext import commands
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from utils.permissions import is_admin

logger = logging.getLogger('discord_bot.automod')

class AutoMod(commands.Cog):
    """Auto-Moderation - Automated spam and content filtering"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Spam detection
        self.message_history = defaultdict(list)  # {user_id: [timestamps]}
        self.spam_threshold = 5  # messages
        self.spam_window = 5  # seconds
        
        # Link filtering
        self.link_whitelist = defaultdict(set)  # {guild_id: {domains}}
        self.link_blacklist = defaultdict(set)  # {guild_id: {domains}}
        
        # Bad words
        self.bad_words = defaultdict(set)  # {guild_id: {words}}
        
        # Raid protection
        self.join_history = defaultdict(list)  # {guild_id: [timestamps]}
        self.raid_threshold = 10  # joins
        self.raid_window = 10  # seconds
        
        # Settings per guild
        self.settings = defaultdict(lambda: {
            'spam_enabled': True,
            'link_filter_enabled': False,
            'bad_words_enabled': False,
            'raid_protection_enabled': True,
            'caps_filter_enabled': False,
            'mention_spam_enabled': True
        })
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Check messages for violations"""
        if message.author.bot or not message.guild:
            return
        
        # Skip if user is admin
        if message.author.guild_permissions.administrator:
            return
        
        guild_id = message.guild.id
        settings = self.settings[guild_id]
        
        # Spam detection
        if settings['spam_enabled']:
            if await self.check_spam(message):
                return
        
        # Link filtering
        if settings['link_filter_enabled']:
            if await self.check_links(message):
                return
        
        # Bad words
        if settings['bad_words_enabled']:
            if await self.check_bad_words(message):
                return
        
        # Caps filter
        if settings['caps_filter_enabled']:
            if await self.check_caps(message):
                return
        
        # Mention spam
        if settings['mention_spam_enabled']:
            if await self.check_mention_spam(message):
                return
    
    async def check_spam(self, message):
        """Check for spam (repeated messages)"""
        user_id = message.author.id
        now = datetime.utcnow()
        
        # Add current message
        self.message_history[user_id].append(now)
        
        # Remove old messages
        self.message_history[user_id] = [
            ts for ts in self.message_history[user_id]
            if now - ts < timedelta(seconds=self.spam_window)
        ]
        
        # Check if spam
        if len(self.message_history[user_id]) > self.spam_threshold:
            try:
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention} Slow down! (Spam detected)",
                    delete_after=5
                )
                
                # Timeout for 1 minute
                await message.author.timeout(
                    timedelta(minutes=1),
                    reason="Spam detected"
                )
                
                logger.info(f"Spam detected from {message.author} in {message.guild}")
                return True
            except:
                pass
        
        return False
    
    async def check_links(self, message):
        """Check for unauthorized links"""
        guild_id = message.guild.id
        
        # Find URLs in message
        url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
        urls = re.findall(url_pattern, message.content)
        
        if not urls:
            return False
        
        # Check against whitelist/blacklist
        for domain in urls:
            # If whitelist exists and domain not in it
            if self.link_whitelist[guild_id] and domain not in self.link_whitelist[guild_id]:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"⚠️ {message.author.mention} That link is not allowed!",
                        delete_after=5
                    )
                    logger.info(f"Blocked unauthorized link from {message.author}")
                    return True
                except:
                    pass
            
            # If domain in blacklist
            if domain in self.link_blacklist[guild_id]:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"⚠️ {message.author.mention} That link is blacklisted!",
                        delete_after=5
                    )
                    logger.info(f"Blocked blacklisted link from {message.author}")
                    return True
                except:
                    pass
        
        return False
    
    async def check_bad_words(self, message):
        """Check for bad words"""
        guild_id = message.guild.id
        content_lower = message.content.lower()
        
        for word in self.bad_words[guild_id]:
            if word.lower() in content_lower:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"⚠️ {message.author.mention} Watch your language!",
                        delete_after=5
                    )
                    logger.info(f"Blocked bad word from {message.author}")
                    return True
                except:
                    pass
        
        return False
    
    async def check_caps(self, message):
        """Check for excessive caps"""
        if len(message.content) < 10:
            return False
        
        caps_count = sum(1 for c in message.content if c.isupper())
        caps_ratio = caps_count / len(message.content)
        
        if caps_ratio > 0.7:  # 70% caps
            try:
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention} Please don't use excessive caps!",
                    delete_after=5
                )
                return True
            except:
                pass
        
        return False
    
    async def check_mention_spam(self, message):
        """Check for mention spam"""
        if len(message.mentions) > 5:
            try:
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention} Don't spam mentions!",
                    delete_after=5
                )
                
                # Timeout for 5 minutes
                await message.author.timeout(
                    timedelta(minutes=5),
                    reason="Mention spam"
                )
                return True
            except:
                pass
        
        return False
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Check for raid (mass joins)"""
        guild_id = member.guild.id
        
        if not self.settings[guild_id]['raid_protection_enabled']:
            return
        
        now = datetime.utcnow()
        
        # Add join
        self.join_history[guild_id].append(now)
        
        # Remove old joins
        self.join_history[guild_id] = [
            ts for ts in self.join_history[guild_id]
            if now - ts < timedelta(seconds=self.raid_window)
        ]
        
        # Check if raid
        if len(self.join_history[guild_id]) > self.raid_threshold:
            logger.warning(f"Possible raid detected in {member.guild}")
            
            # Notify admins
            for channel in member.guild.text_channels:
                if channel.permissions_for(member.guild.me).send_messages:
                    await channel.send(
                        f"🚨 **RAID ALERT** - {self.raid_threshold}+ members joined in {self.raid_window} seconds!\n"
                        f"Consider enabling verification or locking the server."
                    )
                    break
    
    @app_commands.command(name="automod-config", description="[Admin] Configure auto-moderation")
    @is_admin()
    async def automod_config(self, interaction: discord.Interaction):
        """Show automod configuration"""
        settings = self.settings[interaction.guild.id]
        
        embed = discord.Embed(
            title="🤖 Auto-Moderation Configuration",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Spam Detection",
            value="✅ Enabled" if settings['spam_enabled'] else "❌ Disabled",
            inline=True
        )
        embed.add_field(
            name="Link Filter",
            value="✅ Enabled" if settings['link_filter_enabled'] else "❌ Disabled",
            inline=True
        )
        embed.add_field(
            name="Bad Words",
            value="✅ Enabled" if settings['bad_words_enabled'] else "❌ Disabled",
            inline=True
        )
        embed.add_field(
            name="Raid Protection",
            value="✅ Enabled" if settings['raid_protection_enabled'] else "❌ Disabled",
            inline=True
        )
        embed.add_field(
            name="Caps Filter",
            value="✅ Enabled" if settings['caps_filter_enabled'] else "❌ Disabled",
            inline=True
        )
        embed.add_field(
            name="Mention Spam",
            value="✅ Enabled" if settings['mention_spam_enabled'] else "❌ Disabled",
            inline=True
        )
        
        embed.set_footer(text="Use /automod-toggle to enable/disable features")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="automod-toggle", description="[Admin] Toggle auto-mod features")
    @is_admin()
    async def automod_toggle(
        self,
        interaction: discord.Interaction,
        feature: str
    ):
        """Toggle automod features"""
        
        valid_features = ['spam', 'links', 'badwords', 'raid', 'caps', 'mentions']
        
        if feature not in valid_features:
            return await interaction.response.send_message(
                f"❌ Invalid feature! Choose from: {', '.join(valid_features)}",
                ephemeral=True
            )
        
        settings = self.settings[interaction.guild.id]
        feature_map = {
            'spam': 'spam_enabled',
            'links': 'link_filter_enabled',
            'badwords': 'bad_words_enabled',
            'raid': 'raid_protection_enabled',
            'caps': 'caps_filter_enabled',
            'mentions': 'mention_spam_enabled'
        }
        
        key = feature_map[feature]
        settings[key] = not settings[key]
        status = "enabled" if settings[key] else "disabled"
        
        await interaction.response.send_message(
            f"✅ {feature.title()} protection {status}",
            ephemeral=True
        )
    
    @app_commands.command(name="automod-badword-add", description="[Admin] Add a bad word to filter")
    @is_admin()
    async def add_badword(self, interaction: discord.Interaction, word: str):
        """Add bad word to filter"""
        self.bad_words[interaction.guild.id].add(word.lower())
        await interaction.response.send_message(
            f"✅ Added '{word}' to bad words filter",
            ephemeral=True
        )
    
    @app_commands.command(name="automod-badword-remove", description="[Admin] Remove a bad word from filter")
    @is_admin()
    async def remove_badword(self, interaction: discord.Interaction, word: str):
        """Remove bad word from filter"""
        if word.lower() in self.bad_words[interaction.guild.id]:
            self.bad_words[interaction.guild.id].remove(word.lower())
            await interaction.response.send_message(
                f"✅ Removed '{word}' from bad words filter",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ '{word}' is not in the filter",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
