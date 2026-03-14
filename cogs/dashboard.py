import discord
from discord import app_commands
from discord.ext import commands
from utils.permissions import get_permission_level, get_permission_name, PermissionLevel
import logging

logger = logging.getLogger('discord_bot.dashboard')

class CommandModal(discord.ui.Modal, title="💬 Command Helper"):
    """Modal for getting command suggestions"""
    
    command_input = discord.ui.TextInput(
        label="What do you want to do?",
        placeholder="Example: play music, kick user, check balance, weather Tokyo",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=200
    )
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.command_input.value.strip().lower()

        # Parse the input and suggest commands
        suggestions = self.parse_command(user_input)

        if suggestions:
            embed = discord.Embed(
                title="💡 Command Suggestions",
                description=f"**You asked:** {self.command_input.value}\n\n**📋 Copy and paste these commands in chat:**",
                color=discord.Color.green()
            )

            for i, cmd in enumerate(suggestions[:5], 1):
                embed.add_field(
                    name=f"{i}. {cmd['name']}",
                    value=f"```{cmd['usage']}```\n{cmd['description']}",
                    inline=False
                )

            embed.set_footer(text="💡 Discord doesn't allow bots to execute commands for you - copy the command above and paste it in any channel!")
        else:
            embed = discord.Embed(
                title="❓ No Commands Found",
                description=f"**You asked:** {self.command_input.value}\n\nI couldn't find a matching command. Try these tips:",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="💡 Search Tips",
                value="• Use keywords: `play`, `kick`, `balance`, `weather`\n• Be specific: `play music` instead of just `music`\n• Check category buttons for all commands\n• Type `/` in chat to see Discord's command list",
                inline=False
            )
            embed.add_field(
                name="🔍 Popular Commands",
                value="`/play <song>` - Play music\n`/balance` - Check coins\n`/weather <city>` - Get weather\n`/meme` - Random meme\n`/serverinfo` - Server info",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def parse_command(self, text: str) -> list:
        """Parse user input and return matching commands"""
        suggestions = []

        # Music commands (8 commands)
        if any(word in text for word in ['play', 'music', 'song', 'listen', 'youtube']):
            suggestions.append({'name': '/play', 'usage': '/play <song name or URL>', 'description': '🎵 Play music from YouTube'})
        if 'stop' in text and any(word in text for word in ['music', 'song', 'playing']):
            suggestions.append({'name': '/stop', 'usage': '/stop', 'description': '⏹️ Stop music playback'})
        if 'pause' in text:
            suggestions.append({'name': '/pause', 'usage': '/pause', 'description': '⏸️ Pause music'})
        if 'resume' in text or 'unpause' in text:
            suggestions.append({'name': '/resume', 'usage': '/resume', 'description': '▶️ Resume music'})
        if 'skip' in text or 'next' in text:
            suggestions.append({'name': '/skip', 'usage': '/skip', 'description': '⏭️ Skip current song'})
        if 'queue' in text or 'playlist' in text:
            suggestions.append({'name': '/queue', 'usage': '/queue', 'description': '📋 View music queue'})
        if 'volume' in text or 'loud' in text or 'quiet' in text:
            suggestions.append({'name': '/volume', 'usage': '/volume <0-100>', 'description': '🔊 Set volume'})
        if 'nowplaying' in text or 'current song' in text or 'what song' in text:
            suggestions.append({'name': '/nowplaying', 'usage': '/nowplaying', 'description': '🎵 Show current song'})

        # Moderation commands (15 commands)
        if 'kick' in text:
            suggestions.append({'name': '/kick', 'usage': '/kick @user <reason>', 'description': '👢 Kick a member'})
        if 'ban' in text and 'unban' not in text:
            suggestions.append({'name': '/ban', 'usage': '/ban @user <reason>', 'description': '🔨 Ban a member'})
        if 'unban' in text:
            suggestions.append({'name': '/unban', 'usage': '/unban <user_id>', 'description': '✅ Unban a user'})
        if any(word in text for word in ['timeout', 'mute', 'silence']):
            suggestions.append({'name': '/timeout', 'usage': '/timeout @user <duration> <reason>', 'description': '⏱️ Timeout a member'})
        if 'warn' in text:
            suggestions.append({'name': '/warn', 'usage': '/warn @user <reason>', 'description': '⚠️ Warn a member'})
        if any(word in text for word in ['purge', 'delete', 'clear', 'clean']) and any(word in text for word in ['message', 'msg', 'chat']):
            suggestions.append({'name': '/purge', 'usage': '/purge <amount>', 'description': '🗑️ Delete messages'})
        if 'lock' in text and 'unlock' not in text:
            suggestions.append({'name': '/lock', 'usage': '/lock', 'description': '🔒 Lock channel'})
        if 'unlock' in text:
            suggestions.append({'name': '/unlock', 'usage': '/unlock', 'description': '🔓 Unlock channel'})
        if 'slowmode' in text or 'slow mode' in text:
            suggestions.append({'name': '/slowmode', 'usage': '/slowmode <seconds>', 'description': '🐌 Set slowmode'})
        if 'nickname' in text or 'nick' in text:
            suggestions.append({'name': '/nickname', 'usage': '/nickname @user <new_name>', 'description': '✏️ Change nickname'})
        if 'warnings' in text or 'check warn' in text:
            suggestions.append({'name': '/warnings', 'usage': '/warnings @user', 'description': '📋 View warnings'})
        if 'modstats' in text or 'mod stats' in text:
            suggestions.append({'name': '/modstats', 'usage': '/modstats', 'description': '📊 Moderation statistics'})

        # Economy commands (9 commands)
        if any(word in text for word in ['balance', 'money', 'coins', 'cash', 'wallet']):
            suggestions.append({'name': '/balance', 'usage': '/balance', 'description': '💰 Check your balance'})
        if 'daily' in text:
            suggestions.append({'name': '/daily', 'usage': '/daily', 'description': '🎁 Claim daily coins'})
        if 'work' in text and 'job' not in text:
            suggestions.append({'name': '/work', 'usage': '/work', 'description': '💼 Work to earn coins'})
        if 'shop' in text or 'store' in text:
            suggestions.append({'name': '/shop', 'usage': '/shop', 'description': '🏪 View the shop'})
        if 'buy' in text:
            suggestions.append({'name': '/buy', 'usage': '/buy <item>', 'description': '🛒 Buy an item'})
        if 'inventory' in text or 'items' in text:
            suggestions.append({'name': '/inventory', 'usage': '/inventory', 'description': '🎒 View your inventory'})
        if 'gamble' in text or 'bet' in text:
            suggestions.append({'name': '/gamble', 'usage': '/gamble <amount>', 'description': '🎲 Gamble coins'})
        if 'give' in text and any(word in text for word in ['coin', 'money']):
            suggestions.append({'name': '/give', 'usage': '/give @user <amount>', 'description': '💸 Give coins to user'})
        if 'leaderboard' in text and 'coin' in text:
            suggestions.append({'name': '/leaderboard-coins', 'usage': '/leaderboard-coins', 'description': '🏆 Top richest users'})

        # Fun commands (9 commands)
        if 'meme' in text:
            suggestions.append({'name': '/meme', 'usage': '/meme', 'description': '😂 Get a random meme'})
        if 'joke' in text:
            suggestions.append({'name': '/joke', 'usage': '/joke', 'description': '🤣 Get a random joke'})
        if '8ball' in text or 'magic' in text:
            suggestions.append({'name': '/8ball', 'usage': '/8ball <question>', 'description': '🎱 Ask the magic 8ball'})
        if 'coinflip' in text or 'flip coin' in text or 'heads tails' in text:
            suggestions.append({'name': '/coinflip', 'usage': '/coinflip', 'description': '🪙 Flip a coin'})
        if 'dice' in text or 'roll' in text:
            suggestions.append({'name': '/dice', 'usage': '/dice <sides>', 'description': '🎲 Roll dice'})
        if 'rps' in text or 'rock paper' in text:
            suggestions.append({'name': '/rps', 'usage': '/rps <choice>', 'description': '✊ Rock Paper Scissors'})
        if 'trivia' in text or 'quiz' in text:
            suggestions.append({'name': '/trivia', 'usage': '/trivia', 'description': '🧠 Play trivia'})
        if 'choose' in text or 'pick' in text or 'decide' in text:
            suggestions.append({'name': '/choose', 'usage': '/choose <option1> <option2> ...', 'description': '🎯 Random chooser'})
        if 'rate' in text:
            suggestions.append({'name': '/rate', 'usage': '/rate <thing>', 'description': '⭐ Rate anything'})

        # Utility commands (9 commands)
        if 'weather' in text or 'temperature' in text or 'forecast' in text:
            suggestions.append({'name': '/weather', 'usage': '/weather <city>', 'description': '🌤️ Get weather info'})
        if 'wiki' in text or 'wikipedia' in text:
            suggestions.append({'name': '/wiki', 'usage': '/wiki <query>', 'description': '📚 Search Wikipedia'})
        if 'crypto' in text or 'bitcoin' in text or 'ethereum' in text:
            suggestions.append({'name': '/crypto', 'usage': '/crypto <coin>', 'description': '💎 Crypto prices'})
        if 'quote' in text and 'inspire' not in text:
            suggestions.append({'name': '/quote', 'usage': '/quote', 'description': '💭 Inspirational quote'})
        if 'fact' in text or 'random fact' in text:
            suggestions.append({'name': '/fact', 'usage': '/fact', 'description': '🤓 Random fact'})
        if 'server' in text and 'info' in text:
            suggestions.append({'name': '/serverinfo', 'usage': '/serverinfo', 'description': '🏰 Server information'})
        if 'user' in text and 'info' in text:
            suggestions.append({'name': '/userinfo', 'usage': '/userinfo <user>', 'description': '👤 User information'})
        if 'avatar' in text or 'pfp' in text or 'profile pic' in text:
            suggestions.append({'name': '/avatar', 'usage': '/avatar <user>', 'description': '🖼️ View avatar'})
        if 'ping' in text or 'latency' in text:
            suggestions.append({'name': '/ping', 'usage': '/ping', 'description': '🏓 Check bot latency'})
        if 'poll' in text or 'vote' in text:
            suggestions.append({'name': '/poll', 'usage': '/poll <question>', 'description': '📊 Create a poll'})
        if 'remind' in text or 'reminder' in text:
            suggestions.append({'name': '/remind', 'usage': '/remind <time> <message>', 'description': '⏰ Set reminder'})
        if 'afk' in text or 'away' in text:
            suggestions.append({'name': '/afk', 'usage': '/afk <reason>', 'description': '💤 Set AFK status'})

        # Social commands (8 commands)
        if 'marry' in text or 'marriage' in text or 'propose' in text:
            suggestions.append({'name': '/marry', 'usage': '/marry @user', 'description': '💍 Propose marriage'})
        if 'divorce' in text:
            suggestions.append({'name': '/divorce', 'usage': '/divorce', 'description': '💔 Divorce partner'})
        if 'adopt' in text and 'pet' not in text:
            suggestions.append({'name': '/adopt', 'usage': '/adopt', 'description': '👶 Adopt a child'})
        if 'pet' in text or 'buy pet' in text or 'buy-pet' in text:
            suggestions.append({'name': '/buy-pet', 'usage': '/buy-pet', 'description': '🐾 Buy a pet'})
        if 'pet' in text and 'buy' not in text:
            suggestions.append({'name': '/pet', 'usage': '/pet', 'description': '🐕 View your pet'})
        if 'achievement' in text or 'trophy' in text:
            suggestions.append({'name': '/achievements', 'usage': '/achievements', 'description': '🏆 View achievements'})
        if 'streak' in text or 'daily streak' in text:
            suggestions.append({'name': '/streak', 'usage': '/streak', 'description': '🔥 View daily streak'})

        # Gaming commands
        if 'rank' in text or 'level' in text or 'xp' in text:
            suggestions.append({'name': '/rank', 'usage': '/rank', 'description': '📈 Check your rank'})
        if 'leaderboard' in text and 'coin' not in text:
            suggestions.append({'name': '/leaderboard', 'usage': '/leaderboard', 'description': '🏆 XP leaderboard'})

        # Admin commands
        if 'config' in text or 'settings' in text:
            suggestions.append({'name': '/config', 'usage': '/config', 'description': '⚙️ View configuration'})
        if 'setlogchannel' in text or 'log channel' in text:
            suggestions.append({'name': '/setlogchannel', 'usage': '/setlogchannel <channel>', 'description': '📝 Set log channel'})
        if 'setwelcome' in text or 'welcome channel' in text:
            suggestions.append({'name': '/setwelcome', 'usage': '/setwelcome <channel>', 'description': '👋 Set welcome channel'})
        if 'setautorole' in text or 'auto role' in text:
            suggestions.append({'name': '/setautorole', 'usage': '/setautorole <role>', 'description': '🎭 Set auto-role'})
        if 'giveaway' in text:
            suggestions.append({'name': '/giveaway', 'usage': '/giveaway <duration> <prize>', 'description': '🎉 Start giveaway'})
        if 'announce' in text or 'announcement' in text:
            suggestions.append({'name': '/announce', 'usage': '/announce <message>', 'description': '📢 Make announcement'})

        # Translation
        if 'translate' in text or 'hinglish' in text:
            suggestions.append({'name': '/translate', 'usage': '/translate <text>', 'description': '🌐 Translate to Hinglish'})

        # Owner commands
        if 'shutdown' in text or 'stop bot' in text:
            suggestions.append({'name': '/shutdown', 'usage': '/shutdown', 'description': '🛑 Shutdown bot (Owner only)'})
        if 'reload' in text:
            suggestions.append({'name': '/reload', 'usage': '/reload <cog>', 'description': '🔄 Reload cog (Owner only)'})

        return suggestions


class DashboardView(discord.ui.View):
    """Interactive dashboard view that updates in place"""
    
    def __init__(self, bot, user: discord.Member, guild: discord.Guild, permission_level: int):
        super().__init__(timeout=900)  # 15 minutes (Discord's max interaction time)
        self.bot = bot
        self.user = user
        self.guild = guild
        self.permission_level = permission_level
        self.permission_name = get_permission_name(permission_level)
        self.current_page = "home"
        self.message = None  # Store message reference
        
        # Add buttons based on permission
        self.setup_buttons()
    
    async def on_timeout(self):
        """Handle timeout by disabling buttons and showing refresh message"""
        try:
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            # Create timeout embed
            embed = discord.Embed(
                title="⏱️ Dashboard Timed Out",
                description="This dashboard has expired after 15 minutes of inactivity.\n\n**To open a new dashboard, type:** `/wan`",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Dashboards expire after 15 minutes to save resources")
            
            if self.message:
                await self.message.edit(embed=embed, view=self)
        except:
            pass  # Message might be deleted
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user clicking is the dashboard owner"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ This is not your dashboard! Use `/wan` to open your own.",
                ephemeral=True
            )
            return False
        return True
    
    def setup_buttons(self):
        """Setup all buttons"""
        self.clear_items()
        
        # Row 0 - Main actions
        home_btn = discord.ui.Button(label="🏠 Home", style=discord.ButtonStyle.primary, row=0)
        home_btn.callback = self.show_home
        self.add_item(home_btn)
        
        type_btn = discord.ui.Button(label="⌨️ Type Command", style=discord.ButtonStyle.success, row=0)
        type_btn.callback = self.show_command_modal
        self.add_item(type_btn)
        
        stats_btn = discord.ui.Button(label="📊 Stats", style=discord.ButtonStyle.secondary, row=0)
        stats_btn.callback = self.show_stats
        self.add_item(stats_btn)
        
        refresh_btn = discord.ui.Button(label="🔄 Refresh", style=discord.ButtonStyle.secondary, row=0)
        refresh_btn.callback = self.refresh_dashboard
        self.add_item(refresh_btn)
        
        # Row 1 - Categories (Member+)
        if self.permission_level >= PermissionLevel.MEMBER:
            music_btn = discord.ui.Button(label="🎵 Music", style=discord.ButtonStyle.success, row=1)
            music_btn.callback = self.show_music
            self.add_item(music_btn)
            
            economy_btn = discord.ui.Button(label="💰 Economy", style=discord.ButtonStyle.success, row=1)
            economy_btn.callback = self.show_economy
            self.add_item(economy_btn)
            
            fun_btn = discord.ui.Button(label="🎮 Fun", style=discord.ButtonStyle.success, row=1)
            fun_btn.callback = self.show_fun
            self.add_item(fun_btn)
            
            util_btn = discord.ui.Button(label="🛠️ Utility", style=discord.ButtonStyle.success, row=1)
            util_btn.callback = self.show_utility
            self.add_item(util_btn)
        
        # Row 2 - Mod/Admin (Moderator+)
        if self.permission_level >= PermissionLevel.MODERATOR:
            mod_btn = discord.ui.Button(label="🛡️ Moderation", style=discord.ButtonStyle.danger, row=2)
            mod_btn.callback = self.show_moderation
            self.add_item(mod_btn)
        
        if self.permission_level >= PermissionLevel.ADMIN:
            admin_btn = discord.ui.Button(label="⚙️ Admin", style=discord.ButtonStyle.danger, row=2)
            admin_btn.callback = self.show_admin
            self.add_item(admin_btn)
        
        if self.permission_level >= PermissionLevel.OWNER:
            owner_btn = discord.ui.Button(label="👑 Owner", style=discord.ButtonStyle.danger, row=2)
            owner_btn.callback = self.show_owner
            self.add_item(owner_btn)
    
    def create_embed(self, title: str, description: str, color: discord.Color) -> discord.Embed:
        """Create base embed"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(
            name=f"{self.user.display_name}'s Dashboard",
            icon_url=self.user.display_avatar.url
        )
        embed.set_footer(
            text=f"{self.permission_name} • Click buttons to navigate • Type commands with ⌨️ button"
        )
        return embed
    
    async def show_home(self, interaction: discord.Interaction):
        """Show home page"""
        try:
            self.current_page = "home"
            
            # Progress bar
            progress = (self.permission_level / 4) * 100
            filled = int(progress / 10)
            bar = "█" * filled + "░" * (10 - filled)
            
            embed = self.create_embed(
                "✨ WAN BOT ULTIMATE ✨",
                f"**THE ALL-IN-ONE DISCORD BOT**\n93 Commands • 15 Categories • 100% Free",
                discord.Color.blurple()
            )
            
            # Profile
            embed.add_field(
                name="👤 Your Profile",
                value=f"**Level:** {self.permission_name}\n**Progress:** [{bar}] {int(progress)}%\n**Commands:** {self.get_command_count()}",
                inline=True
            )
            
            # Server
            embed.add_field(
                name="🏰 Server",
                value=f"**{self.guild.name}**\n👥 {self.guild.member_count:,} Members\n📺 {len(self.guild.channels)} Channels",
                inline=True
            )
            
            # Bot
            embed.add_field(
                name="🤖 Bot",
                value=f"**WAN Bot**\n⚡ 93 Commands\n🟢 Online\n💰 Free",
                inline=True
            )
            
            # Features
            features = self.get_features()
            embed.add_field(
                name="⚡ Available Features",
                value=features,
                inline=False
            )
            
            # Instructions
            embed.add_field(
                name="💡 How to Use",
                value="🏠 **Home** - Return here\n⌨️ **Type Command** - Execute commands directly\n📊 **Stats** - View detailed statistics\n🎵 **Category Buttons** - Browse commands by category",
                inline=False
            )
            
            embed.set_thumbnail(url=self.user.display_avatar.url)
            if self.guild.icon:
                embed.set_image(url=self.guild.icon.url)
            
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.errors.NotFound:
            await interaction.response.send_message(
                "❌ Dashboard expired. Use `/wan` to open a new one.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in show_home: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Dashboard expired or error occurred. Use `/wan` to open a new one.",
                    ephemeral=True
                )
            except:
                pass
    
    async def show_command_modal(self, interaction: discord.Interaction):
        """Show modal to type commands"""
        try:
            modal = CommandModal(self.bot)
            await interaction.response.send_modal(modal)
        except discord.errors.NotFound:
            await interaction.response.send_message(
                "❌ Dashboard expired. Use `/wan` to open a new one.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error showing modal: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Error opening command helper. Try `/wan` to open a new dashboard.",
                    ephemeral=True
                )
            except:
                pass
    
    async def refresh_dashboard(self, interaction: discord.Interaction):
        """Refresh the dashboard to current page"""
        try:
            # Redirect to current page
            if self.current_page == "home":
                await self.show_home(interaction)
            elif self.current_page == "stats":
                await self.show_stats(interaction)
            elif self.current_page == "music":
                await self.show_music(interaction)
            elif self.current_page == "economy":
                await self.show_economy(interaction)
            elif self.current_page == "fun":
                await self.show_fun(interaction)
            elif self.current_page == "utility":
                await self.show_utility(interaction)
            elif self.current_page == "moderation":
                await self.show_moderation(interaction)
            elif self.current_page == "admin":
                await self.show_admin(interaction)
            elif self.current_page == "owner":
                await self.show_owner(interaction)
            else:
                await self.show_home(interaction)
        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Dashboard expired. Use `/wan` to open a new one.",
                    ephemeral=True
                )
            except:
                pass
    
    async def show_stats(self, interaction: discord.Interaction):
        """Show statistics page"""
        try:
            self.current_page = "stats"
            
            embed = self.create_embed(
                "📊 Statistics & Information",
                "Detailed bot and server statistics",
                discord.Color.blue()
            )
            
            # Bot stats
            embed.add_field(
                name="🤖 Bot Statistics",
                value=f"```yaml\nCommands: 93\nCategories: 15\nServers: {len(self.bot.guilds)}\nLatency: {round(self.bot.latency * 1000)}ms\nUptime: 24/7\nCost: $0/month\n```",
                inline=True
            )
            
            # Server stats
            embed.add_field(
                name="🏰 Server Statistics",
                value=f"```yaml\nMembers: {self.guild.member_count:,}\nChannels: {len(self.guild.channels)}\nRoles: {len(self.guild.roles)}\nBoost Level: {self.guild.premium_tier}\nBoosts: {self.guild.premium_subscription_count}\n```",
                inline=True
            )
            
            # Your stats
            embed.add_field(
                name="👤 Your Statistics",
                value=f"```yaml\nPermission: {self.permission_name}\nLevel: {self.permission_level}/4\nCommands: {self.get_command_count()}\nJoined: {discord.utils.format_dt(self.user.joined_at, 'R')}\n```",
                inline=True
            )
            
            # Features breakdown
            embed.add_field(
                name="✨ Features Breakdown",
                value="🎵 Music (8) • 💰 Economy (9) • 🎮 Fun (9)\n🛠️ Utility (9) • 🛡️ Moderation (15) • ⚙️ Admin (15)\n👑 Owner (4) • 🌤️ Weather • 💎 Crypto • 📚 Wiki\n💍 Social (8) • 🐾 Pets • 🏆 Achievements • 🔥 Streaks",
                inline=False
            )
            
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.errors.NotFound:
            await interaction.response.send_message(
                "❌ Dashboard expired. Use `/wan` to open a new one.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in show_stats: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Dashboard expired or error occurred. Use `/wan` to open a new one.",
                    ephemeral=True
                )
            except:
                pass
    
    async def show_music(self, interaction: discord.Interaction):
        """Show music commands"""
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your dashboard!", ephemeral=True)

        self.current_page = "music"

        embed = self.create_embed(
            "🎵 Music Commands",
            "Control music playback in voice channels",
            discord.Color.purple()
        )

        embed.add_field(
            name="▶️ Playback",
            value="```/play <song>```Play music from YouTube\n\n```/stop```Stop playback\n\n```/pause```Pause music\n\n```/resume```Resume music",
            inline=True
        )

        embed.add_field(
            name="⏭️ Control",
            value="```/skip```Skip current song\n\n```/queue```View music queue\n\n```/volume <0-100>```Set volume\n\n```/nowplaying```Current song info",
            inline=True
        )

        embed.add_field(
            name="💡 Quick Start",
            value="1️⃣ Join a voice channel\n2️⃣ Copy: `/play <song name>`\n3️⃣ Paste in chat and press Enter\n4️⃣ Enjoy music! 🎶",
            inline=False
        )

        embed.add_field(
            name="✨ Features",
            value="• YouTube search & URLs\n• Queue up to 50 songs\n• Volume control (0-100)\n• Skip, pause, resume\n• 100% Free streaming",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_economy(self, interaction: discord.Interaction):
        """Show economy commands"""
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your dashboard!", ephemeral=True)

        self.current_page = "economy"

        embed = self.create_embed(
            "💰 Economy Commands",
            "Earn coins, buy items, and compete!",
            discord.Color.gold()
        )

        embed.add_field(
            name="💵 Earning",
            value="```/daily```Daily reward (100-500 coins)\n\n```/work```Work for coins (30-250)\n\n```/gamble <amount>```Gamble your coins",
            inline=True
        )

        embed.add_field(
            name="🏪 Shopping",
            value="```/shop```View available items\n\n```/buy <item>```Purchase items\n\n```/inventory```View your items\n\n```/give @user <amount>```Give coins",
            inline=True
        )

        embed.add_field(
            name="📊 Stats",
            value="```/balance```Check your balance\n\n```/leaderboard-coins```Top richest users",
            inline=True
        )

        embed.add_field(
            name="💡 Quick Start",
            value="1️⃣ Type `/daily` to get free coins\n2️⃣ Use `/work` to earn more\n3️⃣ Check `/shop` for items\n4️⃣ Build your wealth! 💎",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_fun(self, interaction: discord.Interaction):
        """Show fun commands"""
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your dashboard!", ephemeral=True)

        self.current_page = "fun"

        embed = self.create_embed(
            "🎮 Fun & Games",
            "Entertainment commands for everyone!",
            discord.Color.green()
        )

        embed.add_field(
            name="🎱 Games",
            value="```/8ball <question>```Magic 8ball answers\n\n```/coinflip```Heads or tails\n\n```/dice <sides>```Roll dice\n\n```/rps <choice>```Rock Paper Scissors\n\n```/trivia```Trivia questions",
            inline=True
        )

        embed.add_field(
            name="😂 Entertainment",
            value="```/meme```Random memes\n\n```/joke```Random jokes\n\n```/choose <options>```Random picker\n\n```/rate <thing>```Rate anything 1-10",
            inline=True
        )

        embed.add_field(
            name="💡 Try These",
            value="• `/meme` - Get instant laughs\n• `/8ball Will I win?` - Ask anything\n• `/trivia` - Test your knowledge\n• `/rps rock` - Play RPS",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_utility(self, interaction: discord.Interaction):
        """Show utility commands"""
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your dashboard!", ephemeral=True)

        self.current_page = "utility"

        embed = self.create_embed(
            "🛠️ Utility Commands",
            "Useful tools and information",
            discord.Color.blue()
        )

        embed.add_field(
            name="📊 Information",
            value="```/serverinfo```Server details\n\n```/userinfo <user>```User details\n\n```/avatar <user>```View avatars\n\n```/ping```Bot latency",
            inline=True
        )

        embed.add_field(
            name="🌐 Advanced",
            value="```/weather <city>```Weather info\n\n```/wiki <query>```Wikipedia search\n\n```/crypto <coin>```Crypto prices\n\n```/quote```Inspirational quotes\n\n```/fact```Random facts",
            inline=True
        )

        embed.add_field(
            name="🛠️ Tools",
            value="```/poll <question>```Create polls\n\n```/remind <time> <msg>```Set reminders\n\n```/afk <reason>```AFK mode",
            inline=True
        )

        embed.add_field(
            name="💡 Popular Commands",
            value="• `/weather Tokyo` - Get weather\n• `/crypto bitcoin` - BTC price\n• `/wiki Python` - Learn anything\n• `/serverinfo` - Server stats",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_moderation(self, interaction: discord.Interaction):
        """Show moderation commands"""
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your dashboard!", ephemeral=True)

        self.current_page = "moderation"

        embed = self.create_embed(
            "🛡️ Moderation Commands",
            "Keep your server safe and organized",
            discord.Color.red()
        )

        embed.add_field(
            name="👮 User Actions",
            value="```/kick @user <reason>```Kick members\n\n```/ban @user <reason>```Ban members\n\n```/unban <user_id>```Unban users\n\n```/timeout @user <duration>```Timeout members\n\n```/warn @user <reason>```Warn members",
            inline=True
        )

        embed.add_field(
            name="🔒 Channel Control",
            value="```/lock```Lock channel\n\n```/unlock```Unlock channel\n\n```/slowmode <seconds>```Set slowmode\n\n```/purge <amount>```Delete messages",
            inline=True
        )

        embed.add_field(
            name="📊 Management",
            value="```/nickname @user <name>```Change nicknames\n\n```/modstats```View mod statistics\n\n```/warnings @user```View user warnings",
            inline=True
        )

        embed.add_field(
            name="⚠️ Moderator Access Required",
            value="These commands require Manage Messages or Moderate Members permission.",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_admin(self, interaction: discord.Interaction):
        """Show admin commands"""
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your dashboard!", ephemeral=True)

        self.current_page = "admin"

        embed = self.create_embed(
            "⚙️ Admin Commands",
            "Server configuration and management",
            discord.Color.orange()
        )

        embed.add_field(
            name="⚙️ Configuration",
            value="```/config```View all settings\n\n```/setlogchannel <channel>```Set log channel\n\n```/setwelcome <channel>```Set welcome channel\n\n```/setautorole <role>```Set auto-role",
            inline=True
        )

        embed.add_field(
            name="🎭 Server Setup",
            value="```/setup-roles```Create default roles\n\n```/backup```Create server backup\n\n```/audit <limit>```View audit log\n\n```/announce <msg>```Make announcements",
            inline=True
        )

        embed.add_field(
            name="📺 YouTube Tracking",
            value="```/addyoutube <url>```Track YouTube channel\n\n```/removeyoutube <id>```Stop tracking\n\n```/listyoutube```List tracked channels",
            inline=True
        )

        embed.add_field(
            name="🎉 Events",
            value="```/giveaway <duration> <prize>```Start giveaway\n\n```/translate <text>```Hinglish translation",
            inline=True
        )

        embed.add_field(
            name="⚠️ Administrator Access Required",
            value="These commands require Administrator permission.",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_owner(self, interaction: discord.Interaction):
        """Show owner commands"""
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your dashboard!", ephemeral=True)

        self.current_page = "owner"

        embed = self.create_embed(
            "👑 Owner Commands",
            "Bot control and management",
            discord.Color.dark_red()
        )

        embed.add_field(
            name="🤖 Bot Control",
            value="```/shutdown```Shutdown the bot\n\n```/reload <cog>```Reload a cog\n\n```/reload-cog <cog>```Reload cog (alias)",
            inline=True
        )

        embed.add_field(
            name="🔧 Development",
            value="```/eval <code>```Execute Python code\n\n```/permissions <user>```Check user permissions",
            inline=True
        )

        embed.add_field(
            name="📋 Available Cogs",
            value="`moderation`, `music`, `automation`, `translation`, `youtube`, `gaming`, `admin`, `logging`, `fun`, `utility`, `economy`, `roles`, `dashboard`, `advanced`, `social`",
            inline=False
        )

        embed.add_field(
            name="⚠️ DANGER ZONE",
            value="These commands have full bot access. Only the bot owner can use them. Use with extreme caution!",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
    
    def get_command_count(self) -> str:
        """Get command count"""
        counts = {
            PermissionLevel.GUEST: "6",
            PermissionLevel.MEMBER: "70+",
            PermissionLevel.MODERATOR: "85+",
            PermissionLevel.ADMIN: "90+",
            PermissionLevel.OWNER: "93"
        }
        return counts.get(self.permission_level, "0")
    
    def get_features(self) -> str:
        """Get features list"""
        if self.permission_level >= PermissionLevel.OWNER:
            return "🎵 Music • 💰 Economy • 🎮 Games • 🛠️ Utility • 🛡️ Moderation\n⚙️ Admin • 👑 Owner • 🌤️ Weather • 💎 Crypto • 💍 Social\n🐾 Pets • 🏆 Achievements • 🔥 Streaks • 📚 Wiki • 🤖 AI"
        elif self.permission_level >= PermissionLevel.ADMIN:
            return "🎵 Music • 💰 Economy • 🎮 Games • 🛠️ Utility • 🛡️ Moderation\n⚙️ Admin • 🌤️ Weather • 💎 Crypto • 💍 Social • 🐾 Pets\n🏆 Achievements • 🔥 Streaks • 📚 Wiki • 🤖 AI"
        elif self.permission_level >= PermissionLevel.MODERATOR:
            return "🎵 Music • 💰 Economy • 🎮 Games • 🛠️ Utility • 🛡️ Moderation\n🌤️ Weather • 💎 Crypto • 💍 Social • 🐾 Pets • 🏆 Achievements\n🔥 Streaks • 📚 Wiki • 🤖 AI"
        elif self.permission_level >= PermissionLevel.MEMBER:
            return "🎵 Music • 💰 Economy • 🎮 Games • 🛠️ Utility • 🌤️ Weather\n💎 Crypto • 💍 Social • 🐾 Pets • 🏆 Achievements • 🔥 Streaks\n📚 Wiki • 🤖 AI"
        else:
            return "📊 Server Info • ❓ Help • 🤖 AI\n⏰ Stay 10 minutes to unlock 90+ commands!"


class Dashboard(commands.Cog):
    """Ultimate Interactive Dashboard"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="wan", description="🌟 Open the ULTIMATE interactive dashboard")
    async def wan_dashboard(self, interaction: discord.Interaction):
        """Open the ultimate dashboard"""
        
        permission_level = get_permission_level(interaction.user)
        permission_name = get_permission_name(permission_level)
        
        # Progress bar
        progress = (permission_level / 4) * 100
        filled = int(progress / 10)
        bar = "█" * filled + "░" * (10 - filled)
        
        # Create initial embed
        embed = discord.Embed(
            title="✨ WAN BOT ULTIMATE ✨",
            description=f"**THE ALL-IN-ONE DISCORD BOT**\n93 Commands • 15 Categories • 100% Free",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.set_author(
            name=f"{interaction.user.display_name}'s Dashboard",
            icon_url=interaction.user.display_avatar.url
        )
        
        # Profile
        embed.add_field(
            name="👤 Your Profile",
            value=f"**Level:** {permission_name}\n**Progress:** [{bar}] {int(progress)}%\n**Commands:** {self.get_command_count(permission_level)}",
            inline=True
        )
        
        # Server
        embed.add_field(
            name="🏰 Server",
            value=f"**{interaction.guild.name}**\n👥 {interaction.guild.member_count:,} Members\n📺 {len(interaction.guild.channels)} Channels",
            inline=True
        )
        
        # Bot
        embed.add_field(
            name="🤖 Bot",
            value=f"**WAN Bot**\n⚡ 93 Commands\n🟢 Online\n💰 Free",
            inline=True
        )
        
        # Features
        features = self.get_features(permission_level)
        embed.add_field(
            name="⚡ Available Features",
            value=features,
            inline=False
        )
        
        # Instructions
        embed.add_field(
            name="💡 How to Use",
            value="🏠 **Home** - Return here\n⌨️ **Type Command** - Execute commands directly\n📊 **Stats** - View detailed statistics\n🎵 **Category Buttons** - Browse commands by category",
            inline=False
        )
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        if interaction.guild.icon:
            embed.set_image(url=interaction.guild.icon.url)
        
        embed.set_footer(
            text=f"{permission_name} • Click buttons to navigate • Type commands with ⌨️ button"
        )
        
        # Create view
        view = DashboardView(self.bot, interaction.user, interaction.guild, permission_level)
        
        # Send initial message and store reference
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
    
    def get_command_count(self, level: int) -> str:
        """Get command count"""
        counts = {
            PermissionLevel.GUEST: "6",
            PermissionLevel.MEMBER: "70+",
            PermissionLevel.MODERATOR: "85+",
            PermissionLevel.ADMIN: "90+",
            PermissionLevel.OWNER: "93"
        }
        return counts.get(level, "0")
    
    def get_features(self, level: int) -> str:
        """Get features list"""
        if level >= PermissionLevel.OWNER:
            return "🎵 Music • 💰 Economy • 🎮 Games • 🛠️ Utility • 🛡️ Moderation\n⚙️ Admin • 👑 Owner • 🌤️ Weather • 💎 Crypto • 💍 Social\n🐾 Pets • 🏆 Achievements • 🔥 Streaks • 📚 Wiki • 🤖 AI"
        elif level >= PermissionLevel.ADMIN:
            return "🎵 Music • 💰 Economy • 🎮 Games • 🛠️ Utility • 🛡️ Moderation\n⚙️ Admin • 🌤️ Weather • 💎 Crypto • 💍 Social • 🐾 Pets\n🏆 Achievements • 🔥 Streaks • 📚 Wiki • 🤖 AI"
        elif level >= PermissionLevel.MODERATOR:
            return "🎵 Music • 💰 Economy • 🎮 Games • 🛠️ Utility • 🛡️ Moderation\n🌤️ Weather • 💎 Crypto • 💍 Social • 🐾 Pets • 🏆 Achievements\n🔥 Streaks • 📚 Wiki • 🤖 AI"
        elif level >= PermissionLevel.MEMBER:
            return "🎵 Music • 💰 Economy • 🎮 Games • 🛠️ Utility • 🌤️ Weather\n💎 Crypto • 💍 Social • 🐾 Pets • 🏆 Achievements • 🔥 Streaks\n📚 Wiki • 🤖 AI"
        else:
            return "📊 Server Info • ❓ Help • 🤖 AI\n⏰ Stay 10 minutes to unlock 90+ commands!"
    
    @app_commands.command(name="dashboard", description="Open dashboard (alias for /wan)")
    async def dashboard_alias(self, interaction: discord.Interaction):
        """Alias for wan command"""
        await self.wan_dashboard(interaction)
    
    @app_commands.command(name="help", description="Get help and learn how to use the bot")
    async def help_command(self, interaction: discord.Interaction):
        """Show comprehensive help"""
        embed = discord.Embed(
            title="❓ WAN Bot Help & Guide",
            description="**Welcome to WAN Bot - The Ultimate All-in-One Discord Bot!**\n93 Commands • 15 Categories • 100% Free",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="🎯 Quick Start",
            value="1️⃣ Type `/wan` to open the interactive dashboard\n2️⃣ Click category buttons to browse commands\n3️⃣ Copy commands from the dashboard\n4️⃣ Paste them in chat and press Enter!",
            inline=False
        )

        embed.add_field(
            name="⌨️ How to Execute Commands",
            value="**IMPORTANT:** Discord doesn't let bots run commands for you (security feature)\n\n✅ **What Works:**\n• Dashboard shows you which commands to use\n• AI suggests the perfect command\n• Commands displayed in code blocks\n\n❌ **What Doesn't Work:**\n• Bot cannot auto-execute commands\n• Typing in modal doesn't run commands\n\n💡 **Solution:** Copy the command and paste it in chat!",
            inline=False
        )

        embed.add_field(
            name="🎮 Using the Dashboard",
            value="**🏠 Home** - Main view with stats\n**⌨️ Type Command** - AI command helper\n**📊 Stats** - Detailed statistics\n**🎵 Categories** - Browse by category",
            inline=True
        )

        embed.add_field(
            name="🔐 Permission Levels",
            value="**👤 Guest** - 6 commands (new users)\n**👥 Member** - 70+ commands (10 min)\n**🛡️ Moderator** - 85+ commands\n**⚙️ Admin** - 90+ commands\n**👑 Owner** - All 93 commands",
            inline=True
        )

        embed.add_field(
            name="📚 Popular Commands",
            value="`/wan` - Open dashboard\n`/play <song>` - Play music\n`/balance` - Check coins\n`/daily` - Daily reward\n`/meme` - Random meme\n`/weather <city>` - Weather\n`/serverinfo` - Server info",
            inline=False
        )

        embed.add_field(
            name="💡 Pro Tips",
            value="• Type `/` in chat to see all commands\n• Use the AI helper for natural language\n• Dashboard updates in place (no spam)\n• Commands are shown in ```code blocks```\n• Copy entire command including `/`",
            inline=False
        )

        embed.add_field(
            name="📖 Full Documentation",
            value="Read `DASHBOARD_EXPLAINED.md` for complete guide\nRead `README.md` for setup and features\nRead `PRODUCTION_GUIDE.md` for deployment",
            inline=False
        )

        embed.set_footer(text="Need help? Open /wan and explore! • 100% Free Forever")

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Dashboard(bot))
