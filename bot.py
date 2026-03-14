import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import logging
import sys
import threading
from datetime import datetime, timezone
from utils.database import Database

# Load environment variables
load_dotenv()

# Validate required environment variables
REQUIRED_ENV_VARS = ['DISCORD_TOKEN', 'OWNER_ID']
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    print(f"❌ ERROR: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please check your .env file and ensure all required variables are set.")
    sys.exit(1)

# Configure logging with better formatting
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('discord_bot')

class GamingBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        self.db = None
        self.start_time = datetime.now(timezone.utc)  # Track bot start time for uptime
        
    async def setup_hook(self):
        """Load all cogs and initialize database"""
        # Initialize database singleton
        try:
            self.db = Database()
            await self.db.init_db()
            logger.info("✅ Database initialized successfully")
        except Exception as e:
            logger.critical(f"❌ Failed to initialize database: {e}")
            raise
        
        # Load cogs (Essential only - Discord has 100 command limit)
        cogs = [
            'cogs.admin',         # 8 commands - Essential for bot management
            'cogs.moderation',    # 8 commands - Essential for server moderation
            'cogs.utility',       # 8 commands - Essential utilities
            'cogs.logging',       # 0 commands - Background logging
            'cogs.fun',           # 5 commands - Basic fun commands
            'cogs.economy',       # 9 commands - Economy system
            'cogs.social',        # 7 commands - Social features
            'cogs.roles',         # 17 commands - Role management
            'cogs.badges',        # 5 commands - Badge system
            'cogs.automod',       # 4 commands - Auto moderation
            'cogs.tickets',       # 4 commands - Ticket system
            'cogs.suggestions',   # 1 command - Suggestions
            'cogs.birthdays',     # 5 commands - Birthday tracking
            'cogs.webdashboard',  # 3 commands - Web Dashboard (CRITICAL)
            'cogs.leaderboard',   # 2 commands - Real activity leaderboard
            'cogs.roblox',        # 6 commands - Roblox Integration (CRITICAL)
            'cogs.music'          # 9 commands - Music player
            # Total: ~85 commands (under 100 limit)
            # Disabled to stay under limit: music(30), games(7), minigames(6), ai(9), 
            # server(7), advanced(5), customcmds(5), automation(4), rewards(4), 
            # tempvoice(5), starboard(3), voicestats(3), bump(3), dashboard(3), 
            # gaming(3), youtube(3), translation(2)
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f'✅ Loaded {cog}')
            except Exception as e:
                logger.error(f'❌ Failed to load {cog}: {e}', exc_info=True)
        
        # Set up global error handler
        self.tree.error(self.on_app_command_error)
    
    def _broadcast(self, event: str, data: dict):
        """Broadcast a real-time update to the dashboard (thread-safe)"""
        try:
            from web_dashboard_enhanced import broadcast_update
            broadcast_update(event, data)
        except Exception:
            pass

    async def on_member_join(self, member: discord.Member):
        self._broadcast('member_join', {
            'guild_id': member.guild.id,
            'user_id': member.id,
            'name': member.display_name,
            'avatar': str(member.display_avatar.url),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_member_remove(self, member: discord.Member):
        self._broadcast('member_leave', {
            'guild_id': member.guild.id,
            'user_id': member.id,
            'name': member.display_name,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles or before.nick != after.nick:
            self._broadcast('member_update', {
                'guild_id': after.guild.id,
                'user_id': after.id,
                'name': after.display_name,
                'roles': [r.name for r in after.roles if r.name != '@everyone'],
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

    async def on_guild_channel_create(self, channel):
        self._broadcast('channel_create', {
            'guild_id': channel.guild.id,
            'channel_id': channel.id,
            'name': channel.name,
            'type': str(channel.type),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_guild_channel_delete(self, channel):
        self._broadcast('channel_delete', {
            'guild_id': channel.guild.id,
            'channel_id': channel.id,
            'name': channel.name,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_guild_role_create(self, role: discord.Role):
        self._broadcast('role_create', {
            'guild_id': role.guild.id,
            'role_id': role.id,
            'name': role.name,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_guild_role_delete(self, role: discord.Role):
        self._broadcast('role_delete', {
            'guild_id': role.guild.id,
            'role_id': role.id,
            'name': role.name,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_ready(self):
        logger.info(f'🤖 {self.user} is now online!')
        logger.info(f'📊 Connected to {len(self.guilds)} guilds')
        logger.info(f'👥 Serving {sum(g.member_count for g in self.guilds)} members')
        
        try:
            # Sync commands globally only (no guild-specific sync to avoid duplicates)
            synced = await self.tree.sync()
            logger.info(f'✅ Synced {len(synced)} slash commands globally')
            logger.info('⚠️ Note: Global commands may take up to 1 hour to appear in all servers')
        except Exception as e:
            logger.error(f'❌ Failed to sync commands: {e}')
        
        # Set status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="your community 🎮"
            )
        )
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Global error handler for slash commands"""
        logger.error(f"Command error in {interaction.command.name if interaction.command else 'unknown'}: {error}", exc_info=error)
        
        # Create user-friendly error message
        if isinstance(error, app_commands.CommandOnCooldown):
            message = f"⏰ This command is on cooldown. Try again in {error.retry_after:.1f}s"
        elif isinstance(error, app_commands.MissingPermissions):
            message = f"🔒 You don't have permission to use this command.\nRequired: {', '.join(error.missing_permissions)}"
        elif isinstance(error, app_commands.BotMissingPermissions):
            message = f"❌ I don't have the required permissions.\nMissing: {', '.join(error.missing_permissions)}"
        elif isinstance(error, app_commands.CheckFailure):
            message = "🚫 You don't have permission to use this command."
        else:
            message = "❌ An error occurred while executing this command. The issue has been logged."
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except:
            logger.error("Failed to send error message to user")
    
    async def close(self):
        """Cleanup on shutdown"""
        logger.info("🛑 Shutting down bot...")
        if self.db:
            await self.db.close()
        await super().close()
    
    def start_web_dashboard(self):
        """Start web dashboard in separate thread"""
        try:
            from web_dashboard_enhanced import start_web_dashboard
            dashboard_thread = threading.Thread(
                target=start_web_dashboard,
                args=(self,),
                kwargs={
                    'host': os.getenv('DASHBOARD_HOST', '0.0.0.0'),
                    'port': int(os.getenv('PORT', os.getenv('DASHBOARD_PORT', 5000)))
                },
                daemon=True
            )
            dashboard_thread.start()
            logger.info("🌐 Web dashboard started successfully")
        except Exception as e:
            logger.error(f"❌ Failed to start web dashboard: {e}")
            logger.info("ℹ️ Bot will continue without web dashboard")

async def main():
    bot = GamingBot()
    
    # Start web dashboard if enabled
    if os.getenv('ENABLE_DASHBOARD', 'true').lower() == 'true':
        bot.start_web_dashboard()
    
    try:
        async with bot:
            token = os.getenv('DISCORD_TOKEN')
            if not token:
                logger.critical("❌ DISCORD_TOKEN not found in environment variables")
                return
            await bot.start(token)
    except KeyboardInterrupt:
        logger.info("⚠️ Received keyboard interrupt")
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)
    finally:
        logger.info("👋 Bot shutdown complete")

if __name__ == '__main__':
    asyncio.run(main())
