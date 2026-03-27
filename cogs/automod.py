import discord
from discord import app_commands
from discord.ext import commands
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from utils.permissions import is_admin

logger = logging.getLogger('discord_bot.automod')

# Default config — used by dashboard API
DEFAULT_CFG = {
    'spam_enabled': True,
    'spam_threshold': 5,
    'link_filter_enabled': False,
    'invite_filter_enabled': False,
    'bad_words_enabled': True,
    'caps_filter_enabled': False,
    'caps_threshold': 70,
    'mention_spam_enabled': True,
    'mention_threshold': 5,
    'emoji_flood_enabled': False,
    'slowmode_auto': False,
    'log_channel': None,
}

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
        
        # Bad words — default list of slurs/hate speech, always active
        self.bad_words = defaultdict(lambda: {
            'nigga', 'nigger', 'faggot', 'fag', 'retard', 'retarded',
            'chink', 'spic', 'kike', 'cunt', 'whore', 'slut'
        })  # {guild_id: {words}} — guilds can add/remove via /add-badword
        
        # Raid protection
        self.join_history = defaultdict(list)  # {guild_id: [timestamps]}
        self.raid_threshold = 10  # joins
        self.raid_window = 10  # seconds
        
        # Settings per guild
        self.settings = defaultdict(lambda: {
            'spam_enabled': True,
            'link_filter_enabled': False,
            'bad_words_enabled': True,   # ON by default
            'raid_protection_enabled': True,
            'caps_filter_enabled': False,
            'mention_spam_enabled': True
        })

        # Warn tracking for escalation: {guild_id: {user_id: warn_count}}
        self.warn_counts = defaultdict(lambda: defaultdict(int))
    
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
        """Check for bad words — delete, warn, and escalate to timeout"""
        guild_id = message.guild.id
        content_lower = message.content.lower()

        for word in self.bad_words[guild_id]:
            if word.lower() in content_lower:
                try:
                    await message.delete()
                except Exception:
                    pass

                # Increment warn count
                self.warn_counts[guild_id][message.author.id] += 1
                count = self.warn_counts[guild_id][message.author.id]

                try:
                    if count == 1:
                        await message.channel.send(
                            f"⚠️ {message.author.mention} Watch your language! (Warning 1/3)",
                            delete_after=8
                        )
                    elif count == 2:
                        await message.channel.send(
                            f"⚠️ {message.author.mention} Final warning — next offense will result in a timeout. (Warning 2/3)",
                            delete_after=8
                        )
                    else:
                        # 3rd+ offense — timeout 10 minutes
                        timeout_mins = min(10 * (count - 2), 60)  # escalates up to 60 min
                        await message.author.timeout(
                            timedelta(minutes=timeout_mins),
                            reason=f"Repeated bad language (offense #{count})"
                        )
                        await message.channel.send(
                            f"🔇 {message.author.mention} has been timed out for {timeout_mins} minutes for repeated bad language.",
                            delete_after=10
                        )
                except Exception as e:
                    logger.error(f"Failed to action bad word from {message.author}: {e}")

                logger.info(f"Bad word blocked from {message.author} in {message.guild} (offense #{count})")
                return True

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
    
    @app_commands.command(name="automod-config", description="🤖 Show AutoMod configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_config(self, interaction: discord.Interaction):
        settings = self.settings[interaction.guild.id]
        embed = discord.Embed(title="🤖 Auto-Moderation Configuration", color=discord.Color.blue())
        embed.add_field(name="Spam Detection", value="✅" if settings['spam_enabled'] else "❌", inline=True)
        embed.add_field(name="Link Filter", value="✅" if settings['link_filter_enabled'] else "❌", inline=True)
        embed.add_field(name="Bad Words", value="✅" if settings.get('bad_words_enabled') else "❌", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="automod-toggle", description="🔀 Toggle an AutoMod feature")
    @app_commands.describe(feature="Feature to toggle: spam, links, badwords, raid, caps, mentions")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_toggle(self, interaction: discord.Interaction, feature: str):
        valid = ['spam', 'links', 'badwords', 'raid', 'caps', 'mentions']
        if feature not in valid:
            return await interaction.response.send_message(f"❌ Choose from: {', '.join(valid)}", ephemeral=True)
        settings = self.settings[interaction.guild.id]
        key_map = {'spam': 'spam_enabled', 'links': 'link_filter_enabled', 'badwords': 'bad_words_enabled',
                   'raid': 'raid_protection_enabled', 'caps': 'caps_filter_enabled', 'mentions': 'mention_spam_enabled'}
        key = key_map[feature]
        settings[key] = not settings.get(key, False)
        status = "✅ Enabled" if settings[key] else "❌ Disabled"
        await interaction.response.send_message(f"AutoMod `{feature}` is now {status}", ephemeral=True)

    @app_commands.command(name="automod-badword-add", description="🚫 Add a word to the bad words filter")
    @app_commands.describe(word="Word to filter")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_badword(self, interaction: discord.Interaction, word: str):
        self.bad_words[interaction.guild.id].add(word.lower())
        await interaction.response.send_message(f"✅ Added `{word}` to bad words filter", ephemeral=True)

    @app_commands.command(name="automod-badword-remove", description="✅ Remove a word from the bad words filter")
    @app_commands.describe(word="Word to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_badword(self, interaction: discord.Interaction, word: str):
        if word.lower() in self.bad_words[interaction.guild.id]:
            self.bad_words[interaction.guild.id].remove(word.lower())
            await interaction.response.send_message(f"✅ Removed `{word}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ `{word}` not in filter", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
