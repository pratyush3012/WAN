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

print(f"[STARTUP] DISCORD_TOKEN set: {bool(os.getenv('DISCORD_TOKEN'))}", flush=True)
print(f"[STARTUP] OWNER_ID set: {bool(os.getenv('OWNER_ID'))}", flush=True)

# Validate required environment variables — warn but don't exit
REQUIRED_ENV_VARS = ['DISCORD_TOKEN', 'OWNER_ID']
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    print(f"⚠️ WARNING: Missing env vars: {', '.join(missing_vars)} — bot may not work", flush=True)

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
            help_command=None,
            chunk_guilds_at_startup=True
        )
        self.db = None
        self.start_time = datetime.now(timezone.utc)  # Track bot start time for uptime
        # Live activity counters — reset daily, keyed by guild_id (str)
        self._live_stats: dict = {}  # {guild_id: {messages, joins, leaves, commands, date}}

    def _get_live_stats(self, guild_id: str) -> dict:
        """Return today's live stats for a guild, resetting if it's a new day."""
        today = datetime.now(timezone.utc).date().isoformat()
        entry = self._live_stats.get(guild_id)
        if not entry or entry.get('date') != today:
            entry = {'messages': 0, 'joins': 0, 'leaves': 0, 'commands': 0, 'date': today}
            self._live_stats[guild_id] = entry
        return entry
        
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

        guild_id_env = os.getenv('GUILD_ID', '').strip()
        if guild_id_env:
            self._home_guild = discord.Object(id=int(guild_id_env))
        else:
            self._home_guild = None
            logger.info(
                "GUILD_ID not set — guild-only slash sync disabled. "
                "Set GUILD_ID in .env if you use SLASH_SYNC_MODE=guild or both."
            )

        # Cogs — welcome, leveling, music, watch party, web dashboard
        all_cogs = [
            'cogs.welcome',
            'cogs.leveling',
            'cogs.music',
            'cogs.watch_party_complete',
            'cogs.watch_party_enhanced',
            'cogs.webdashboard',
        ]

        self.cog_errors = {}

        for cog in all_cogs:
            try:
                await self.load_extension(cog)
                logger.info(f'✅ Loaded {cog}')
            except Exception as e:
                import traceback
                self.cog_errors[cog] = str(e)
                logger.error(f'❌ Failed to load {cog}: {e}\n{traceback.format_exc()}')

        # Set up global error handler
        self.tree.error(self.on_app_command_error)
    
    def _broadcast(self, event: str, data: dict):
        """Broadcast a real-time update to the dashboard (thread-safe)"""
        try:
            from web_dashboard_enhanced import broadcast_update
            broadcast_update(event, data)
        except Exception:
            pass

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        stats = self._get_live_stats(str(message.guild.id))
        stats['messages'] += 1
        await self.process_commands(message)

    async def on_member_join(self, member: discord.Member):
        self._get_live_stats(str(member.guild.id))['joins'] += 1
        self._broadcast('member_join', {
            'guild_id': member.guild.id,
            'user_id': member.id,
            'name': member.display_name,
            'avatar': str(member.display_avatar.url),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        self._broadcast('audit', {
            'guild_id': member.guild.id,
            'type': 'join',
            'icon': '👋',
            'title': f'{member.display_name} joined',
            'desc': f'Total: {member.guild.member_count} members',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_member_remove(self, member: discord.Member):
        self._get_live_stats(str(member.guild.id))['leaves'] += 1
        self._broadcast('member_leave', {
            'guild_id': member.guild.id,
            'user_id': member.id,
            'name': member.display_name,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        self._broadcast('audit', {
            'guild_id': member.guild.id,
            'type': 'leave',
            'icon': '👋',
            'title': f'{member.display_name} left',
            'desc': f'Total: {member.guild.member_count} members',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles or before.nick != after.nick:
            added = [r.name for r in after.roles if r not in before.roles]
            removed = [r.name for r in before.roles if r not in after.roles]
            self._broadcast('member_update', {
                'guild_id': after.guild.id,
                'user_id': after.id,
                'name': after.display_name,
                'roles': [r.name for r in after.roles if r.name != '@everyone'],
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            if added or removed:
                desc = ''
                if added: desc += f'Got: {", ".join(added)}'
                if removed: desc += (' • ' if desc else '') + f'Lost: {", ".join(removed)}'
                self._broadcast('audit', {
                    'guild_id': after.guild.id,
                    'type': 'role',
                    'icon': '🎭',
                    'title': f'{after.display_name} roles changed',
                    'desc': desc,
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

    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if before.name != after.name or before.permissions != after.permissions:
            self._broadcast('audit', {
                'guild_id': after.guild.id,
                'type': 'role',
                'icon': '🎭',
                'title': 'Role Updated',
                'desc': f'{before.name} → {after.name}' if before.name != after.name else f'{after.name} permissions changed',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

    async def on_guild_channel_update(self, before, after):
        if before.name != after.name:
            self._broadcast('audit', {
                'guild_id': after.guild.id,
                'type': 'channel',
                'icon': '📝',
                'title': 'Channel Renamed',
                'desc': f'#{before.name} → #{after.name}',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        self._broadcast('audit', {
            'guild_id': guild.id,
            'type': 'mod',
            'icon': '🔨',
            'title': 'Member Banned',
            'desc': f'{user.name} was banned',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        self._broadcast('audit', {
            'guild_id': guild.id,
            'type': 'mod',
            'icon': '✅',
            'title': 'Member Unbanned',
            'desc': f'{user.name} was unbanned',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_guild_join(self, guild: discord.Guild):
        """Auto-setup when bot joins a new server"""
        logger.info(f'📥 Joined new guild: {guild.name} ({guild.id})')
        self._broadcast('audit', {
            'guild_id': guild.id,
            'type': 'join',
            'icon': '🎉',
            'title': 'Bot Joined Server',
            'desc': guild.name,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        try:
            await self._auto_setup(guild)
        except Exception as e:
            logger.error(f'Auto-setup failed for {guild.name}: {e}')

    async def _auto_setup(self, guild: discord.Guild):
        """Create default channels and send welcome embed on guild join"""
        # Find or create a general/bot channel to send welcome
        target = discord.utils.get(guild.text_channels, name='general') or \
                 discord.utils.get(guild.text_channels, name='bot-commands') or \
                 (guild.text_channels[0] if guild.text_channels else None)

        if not target:
            return

        embed = discord.Embed(
            title="👋 Thanks for adding WAN Bot!",
            description=(
                "WAN Bot is now ready to power your community.\n\n"
                "**Quick Start:**\n"
                "• `/web` — Open the web dashboard\n"
                "• `/backend` — Get the dashboard link\n"
                "• `/help` — See all commands\n"
                "• `/badge-setup` — Configure clan branding\n\n"
                "**Dashboard:** Set up your server from the web at any time."
            ),
            color=0x7c3aed
        )
        embed.add_field(name="📊 Server Stats", value=f"**{guild.member_count}** members • **{len(guild.text_channels)}** channels • **{len(guild.roles)}** roles", inline=False)
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.set_footer(text="WAN Bot • Type /help to get started")

        try:
            await target.send(embed=embed)
        except Exception:
            pass

    async def on_ready(self):
        logger.info(f'🤖 {self.user} is now online!')
        logger.info(f'📊 Connected to {len(self.guilds)} guilds')
        logger.info(f'👥 Serving {sum(g.member_count for g in self.guilds)} members')
        
        try:
            # SLASH_SYNC_MODE: global (default) | guild | both
            mode = os.getenv('SLASH_SYNC_MODE', 'global').strip().lower()
            if mode == 'guild' and getattr(self, '_home_guild', None) is not None:
                synced = await self.tree.sync(guild=self._home_guild)
                logger.info(f'✅ Synced {len(synced)} slash commands to guild {self._home_guild.id} only')
            elif mode == 'both' and getattr(self, '_home_guild', None) is not None:
                g = await self.tree.sync()
                logger.info(f'✅ Global sync: {len(g)} slash commands')
                h = await self.tree.sync(guild=self._home_guild)
                logger.info(f'✅ Guild sync: {len(h)} slash commands (home guild)')
            elif mode in ('guild', 'both') and getattr(self, '_home_guild', None) is None:
                logger.warning(
                    f'SLASH_SYNC_MODE={mode!r} requires GUILD_ID — falling back to global sync'
                )
                synced = await self.tree.sync()
                logger.info(f'✅ Synced {len(synced)} slash commands globally')
            else:
                synced = await self.tree.sync()
                logger.info(f'✅ Synced {len(synced)} slash commands globally')
        except Exception as e:
            logger.error(f'❌ Failed to sync commands: {e}')
        
        try:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="your community 🎮"
                )
            )
        except Exception as e:
            logger.error(f'❌ Failed to set presence: {e}')

        # Keep-alive: ping own health endpoint every 8 min so Render never sleeps
        # Render free tier sleeps after 15 min of inactivity — we ping every 8 min to stay awake
        dashboard_url = os.getenv('DASHBOARD_URL', '').rstrip('/')
        if dashboard_url:
            async def _keep_alive():
                import aiohttp
                consecutive_failures = 0
                # Initial delay so bot is fully ready before first ping
                await asyncio.sleep(30)
                while not self.is_closed():
                    try:
                        async with aiohttp.ClientSession() as s:
                            async with s.get(f"{dashboard_url}/api/health", timeout=aiohttp.ClientTimeout(total=15)) as r:
                                if r.status == 200:
                                    consecutive_failures = 0
                                    logger.debug(f"Keep-alive ping OK: {r.status}")
                                else:
                                    consecutive_failures += 1
                                    logger.warning(f"Keep-alive ping returned {r.status}")
                    except Exception as e:
                        consecutive_failures += 1
                        logger.debug(f"Keep-alive ping failed: {e}")

                    if consecutive_failures > 5:
                        logger.warning(f"⚠️ Keep-alive pinger has failed {consecutive_failures} times in a row")

                    await asyncio.sleep(480)  # every 8 minutes (well under Render's 15-min sleep threshold)

            try:
                self.loop.create_task(_keep_alive())
                logger.info(f"✅ Keep-alive pinger started (every 8 min) → {dashboard_url}/api/health")
            except Exception as e:
                logger.error(f"❌ Failed to start keep-alive pinger: {e}")
    
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
        elif isinstance(error, app_commands.NoPrivateMessage):
            message = "📭 This command only works inside a server."
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
    
    async def on_error(self, event_method, *args, **kwargs):
        """Global error handler for events"""
        logger.error(f"Error in {event_method}", exc_info=True)
        # Don't crash on event errors, just log them
    
    async def close(self):
        """Cleanup on shutdown"""
        logger.info("🛑 Shutting down bot...")
        if self.db:
            await self.db.close()
        await super().close()
    
    def start_web_dashboard(self):
        """Kept for compatibility — actual startup is handled in main()"""
        pass

async def main():
    port = int(os.getenv('PORT', os.getenv('DASHBOARD_PORT', 10000)))
    host = os.getenv('DASHBOARD_HOST', '0.0.0.0')

    bot = GamingBot()

    if os.getenv('ENABLE_DASHBOARD', 'true').lower() == 'true':
        from web_dashboard_enhanced import start_web_dashboard
        ready = threading.Event()

        def _start_flask():
            # Signal ready after a short delay so Flask has time to bind
            import time as _t
            def _signal():
                _t.sleep(3)
                ready.set()
            threading.Thread(target=_signal, daemon=True).start()
            start_web_dashboard(bot, host=host, port=port, ready_event=None)

        t = threading.Thread(target=_start_flask, daemon=True)
        t.start()

        # Wait for Flask to actually bind the port before starting the bot
        if not ready.wait(timeout=30):
            logger.warning("⚠️ Dashboard did not bind in 30s — continuing anyway")
        else:
            logger.info("✅ Dashboard is up and serving")

    max_retries = 999  # Effectively infinite — only stop on keyboard interrupt or bad token
    retry_count = 0
    retry_delay = 5

    while retry_count < max_retries:
        try:
            async with bot:
                token = os.getenv('DISCORD_TOKEN', '').strip()
                if not token:
                    logger.critical("❌ DISCORD_TOKEN not found in environment variables")
                    await asyncio.sleep(30)
                    continue
                logger.info(f"🔑 DISCORD_TOKEN loaded (length={len(token)})")
                logger.info(f"🚀 Starting bot (attempt {retry_count + 1})...")
                await bot.start(token)
        except KeyboardInterrupt:
            logger.info("⚠️ Received keyboard interrupt")
            break
        except discord.LoginFailure as e:
            retry_count += 1
            logger.error(f"❌ Invalid token (attempt {retry_count}): {e}")
            await asyncio.sleep(10)
            bot = GamingBot()
        except discord.errors.HTTPException as e:
            retry_count += 1
            logger.error(f"❌ HTTP {e.status} (attempt {retry_count}): {e}")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
            bot = GamingBot()
        except Exception as e:
            retry_count += 1
            logger.error(f"❌ Bot error (attempt {retry_count}): {e}", exc_info=True)
            logger.info(f"🔄 Restarting bot in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
            bot = GamingBot()

    logger.info("👋 Bot shutdown complete")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"❌ Fatal error in main: {e}", exc_info=True)
        sys.exit(1)
