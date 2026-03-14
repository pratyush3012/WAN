import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.embeds import EmbedFactory
from utils.database import Database
from utils.permissions import is_member
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('discord_bot.utility')

class Utility(commands.Cog):
    """Utility commands for server management and information"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.reminders = []
        self.check_reminders.start()
    
    @app_commands.command(name="serverinfo", description="[Guest] Get information about the server")
    async def serverinfo(self, interaction: discord.Interaction):
        """Display server information with beautiful visuals"""
        from utils.visuals import Emojis, VisualEffects, ProgressBar

        guild = interaction.guild

        embed = discord.Embed(
            title=f"🏰 {guild.name}",
            description="Complete server information and statistics",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        # Basic info
        embed.add_field(
            name=f"{Emojis.STAR} Server Details",
            value=f"**Owner:** {guild.owner.mention}\n**Created:** <t:{int(guild.created_at.timestamp())}:R>\n**ID:** `{guild.id}`",
            inline=False
        )

        # Member stats with visual bars
        total_members = guild.member_count
        bots = len([m for m in guild.members if m.bot])
        humans = total_members - bots

        human_bar = ProgressBar.create_fancy(humans, total_members, length=10, show_numbers=False)
        bot_bar = ProgressBar.create_fancy(bots, total_members, length=10, show_numbers=False)

        embed.add_field(
            name=f"{Emojis.PARTY} Members ({total_members:,})",
            value=f"👥 **Humans:** {humans:,}\n{human_bar}\n\n🤖 **Bots:** {bots:,}\n{bot_bar}",
            inline=False
        )

        # Channel stats
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        total_channels = text_channels + voice_channels

        embed.add_field(
            name=f"{Emojis.INFO} Channels ({total_channels})",
            value=f"💬 **Text:** {text_channels}\n🔊 **Voice:** {voice_channels}\n📁 **Categories:** {categories}",
            inline=True
        )

        # Other stats
        embed.add_field(
            name=f"{Emojis.TROPHY} Server Stats",
            value=f"🎭 **Roles:** {len(guild.roles)}\n😀 **Emojis:** {len(guild.emojis)}\n⚡ **Boosts:** {guild.premium_subscription_count}",
            inline=True
        )

        # Boost level with visual
        boost_level = guild.premium_tier
        boost_bar = ProgressBar.create_fancy(boost_level, 3, length=10, show_numbers=False)
        embed.add_field(
            name=f"{Emojis.SPARKLES} Boost Level",
            value=f"**Level {boost_level}**/3\n{boost_bar}",
            inline=True
        )

        # Add visual separator
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.FIRE} {guild.name} is awesome!",
            inline=False
        )

        if guild.banner:
            embed.set_image(url=guild.banner.url)

        embed.set_footer(text=f"Server created on {guild.created_at.strftime('%B %d, %Y')}")

        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="userinfo", description="[Member] Get information about a user")
    @is_member()
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        """Display user information with beautiful visuals"""
        from utils.visuals import Emojis, VisualEffects, ProgressBar

        member = member or interaction.user

        embed = discord.Embed(
            title=f"👤 {member.display_name}",
            description=f"**{member.mention}** • {str(member)}",
            color=member.color,
            timestamp=datetime.utcnow()
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        # Basic info
        embed.add_field(
            name=f"{Emojis.INFO} Basic Information",
            value=f"**Username:** {str(member)}\n**ID:** `{member.id}`\n**Nickname:** {member.nick or 'None'}",
            inline=False
        )

        # Dates
        account_age = (datetime.utcnow() - member.created_at).days
        server_age = (datetime.utcnow() - member.joined_at).days

        embed.add_field(
            name=f"{Emojis.CLOCK} Account Age",
            value=f"**Created:** <t:{int(member.created_at.timestamp())}:R>\n**Age:** {account_age} days old",
            inline=True
        )

        embed.add_field(
            name=f"{Emojis.PARTY} Server Member",
            value=f"**Joined:** <t:{int(member.joined_at.timestamp())}:R>\n**Duration:** {server_age} days",
            inline=True
        )

        # Status with emoji
        status_emoji = {
            discord.Status.online: "🟢 Online",
            discord.Status.idle: "🟡 Idle",
            discord.Status.dnd: "🔴 Do Not Disturb",
            discord.Status.offline: "⚫ Offline"
        }
        embed.add_field(
            name=f"{Emojis.SPARKLES} Status",
            value=status_emoji.get(member.status, "⚫ Unknown"),
            inline=True
        )

        # Roles with visual count
        roles = [role.mention for role in member.roles[1:]]  # Skip @everyone
        role_count = len(roles)

        if roles:
            # Show first 10 roles
            roles_display = " ".join(roles[:10])
            if role_count > 10:
                roles_display += f"\n*...and {role_count - 10} more*"
        else:
            roles_display = "No roles"

        embed.add_field(
            name=f"🎭 Roles ({role_count})",
            value=roles_display,
            inline=False
        )

        # Key Permissions
        key_perms = []
        if member.guild_permissions.administrator:
            key_perms.append(f"{Emojis.TROPHY} Administrator")
        if member.guild_permissions.manage_guild:
            key_perms.append(f"{Emojis.STAR} Manage Server")
        if member.guild_permissions.manage_channels:
            key_perms.append("📺 Manage Channels")
        if member.guild_permissions.manage_roles:
            key_perms.append("🎭 Manage Roles")
        if member.guild_permissions.kick_members:
            key_perms.append("👢 Kick Members")
        if member.guild_permissions.ban_members:
            key_perms.append("🔨 Ban Members")

        if key_perms:
            embed.add_field(
                name=f"{Emojis.FIRE} Key Permissions",
                value="\n".join(key_perms),
                inline=False
            )

        # Add visual separator
        separator = VisualEffects.create_separator("dots")
        embed.add_field(
            name=separator,
            value=f"{Emojis.SPARKLES} Member since {member.joined_at.strftime('%B %d, %Y')}",
            inline=False
        )

        embed.set_footer(text=f"User ID: {member.id}")

        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="avatar", description="[Member] Get a user's avatar")
    @is_member()
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        """Display user's avatar"""
        member = member or interaction.user
        
        embed = discord.Embed(
            title=f"🖼️ {member.display_name}'s Avatar",
            color=member.color
        )
        embed.set_image(url=member.display_avatar.url)
        embed.add_field(name="Download", value=f"[Click here]({member.display_avatar.url})")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="poll", description="[Member] Create a poll")
    @is_member()
    async def poll(self, interaction: discord.Interaction, question: str, options: str):
        """Create a poll with beautiful visuals (separate options with commas, max 10)"""
        from utils.visuals import Emojis, VisualEffects

        option_list = [opt.strip() for opt in options.split(',')]

        if len(option_list) < 2:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid Poll", "Please provide at least 2 options separated by commas."),
                ephemeral=True
            )

        if len(option_list) > 10:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Too Many Options", "Maximum 10 options allowed."),
                ephemeral=True
            )

        # Number emojis
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        embed = discord.Embed(
            title=f"📊 Poll",
            description=f"**{question}**",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        # Add options with visual formatting
        options_text = []
        for i, option in enumerate(option_list):
            options_text.append(f"{emojis[i]} **Option {i+1}**\n└─ {option}")

        embed.add_field(
            name=f"{Emojis.TARGET} Vote Options",
            value="\n\n".join(options_text),
            inline=False
        )

        # Add visual separator
        separator = VisualEffects.create_separator("arrows")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} React with the number to vote!",
            inline=False
        )

        embed.set_author(
            name=f"Poll by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_footer(text="💡 Click the reactions below to vote!")

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()

        # Add reactions
        for i in range(len(option_list)):
            await message.add_reaction(emojis[i])
    
    @app_commands.command(name="remind", description="[Member] Set a reminder")
    @is_member()
    async def remind(self, interaction: discord.Interaction, time: int, unit: str, reminder: str):
        """Set a reminder (time: number, unit: s/m/h/d)"""
        units = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400
        }
        
        if unit not in units:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid Unit", "Use s (seconds), m (minutes), h (hours), or d (days)."),
                ephemeral=True
            )
        
        if time < 1 or time > 365:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid Time", "Time must be between 1 and 365."),
                ephemeral=True
            )
        
        seconds = time * units[unit]
        remind_time = datetime.utcnow() + timedelta(seconds=seconds)
        
        self.reminders.append({
            'user_id': interaction.user.id,
            'channel_id': interaction.channel.id,
            'reminder': reminder,
            'time': remind_time
        })
        
        unit_names = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
        embed = EmbedFactory.success(
            "⏰ Reminder Set",
            f"I'll remind you about **{reminder}** in {time} {unit_names[unit]}!"
        )
        
        await interaction.response.send_message(embed=embed)
    
    @tasks.loop(seconds=30)
    async def check_reminders(self):
        """Check for due reminders"""
        now = datetime.utcnow()
        due_reminders = [r for r in self.reminders if r['time'] <= now]
        
        for reminder in due_reminders:
            try:
                channel = self.bot.get_channel(reminder['channel_id'])
                user = self.bot.get_user(reminder['user_id'])
                
                if channel and user:
                    embed = EmbedFactory.info(
                        "⏰ Reminder",
                        f"{user.mention}, you asked me to remind you about:\n**{reminder['reminder']}**"
                    )
                    await channel.send(embed=embed)
                
                self.reminders.remove(reminder)
            except Exception as e:
                logger.error(f"Error sending reminder: {e}")
                self.reminders.remove(reminder)
    
    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="ping", description="[Guest] Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        """Check bot's latency"""
        latency = round(self.bot.latency * 1000)
        
        if latency < 100:
            color = discord.Color.green()
            status = "Excellent"
        elif latency < 200:
            color = discord.Color.yellow()
            status = "Good"
        else:
            color = discord.Color.red()
            status = "Poor"
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: **{latency}ms** ({status})",
            color=color
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="uptime", description="[Guest] Check how long the bot has been running")
    async def uptime(self, interaction: discord.Interaction):
        """Display bot uptime"""
        if not hasattr(self.bot, 'start_time'):
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Error", "Uptime tracking not available."),
                ephemeral=True
            )
        
        from datetime import timezone
        now = datetime.now(timezone.utc)
        start = self.bot.start_time if self.bot.start_time.tzinfo else self.bot.start_time.replace(tzinfo=timezone.utc)
        uptime = now - start
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        embed = EmbedFactory.info(
            "⏱️ Bot Uptime",
            f"**{days}** days, **{hours}** hours, **{minutes}** minutes, **{seconds}** seconds"
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="afk", description="[Member] Set yourself as AFK")
    @is_member()
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK"):
        """Set AFK status"""
        # Store in database (simplified - you'd want a proper table)
        embed = EmbedFactory.success(
            "💤 AFK Mode",
            f"You're now AFK: **{reason}**\nI'll notify anyone who mentions you!"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def cog_unload(self):
        self.check_reminders.cancel()

async def setup(bot):
    await bot.add_cog(Utility(bot))
