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
            help_command=None,
            chunk_guilds_at_startup=True
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
        
        # Load cogs — Discord hard limit is 100 slash commands
        cogs = [
            # ── Core ──────────────────────────────────────────────────────
            'cogs.admin',           # addrole, removerole, setlogchannel, togglemodule, config, reload
            'cogs.moderation',      # kick, ban, unban, timeout, lock, unlock, purge, lockdown
            'cogs.utility',         # serverinfo, userinfo, avatar, poll, remind, ping, uptime, afk
            'cogs.logging',         # 0 commands (background event logging)
            'cogs.roles',           # slowmode, nickname, setup-roles, shutdown
            # ── Automation ────────────────────────────────────────────────
            'cogs.automod',         # automod-config, automod-toggle, automod-badword-add/remove
            'cogs.autoresponder',   # ar-add, ar-remove, ar-list
            'cogs.welcome',         # welcome-set, goodbye-set, autorole, welcome-test
            'cogs.reactionroles',   # rr-add, rr-remove, rr-list, rr-panel
            'cogs.leveling',        # rank, levels, set-level-role, xp-channel
            'cogs.badges',          # badge, sync-badges, badge-stats, badge-setup
            'cogs.birthdays',       # birthday-set, birthday-remove, birthday-list, birthday-setup
            'cogs.suggestions',     # suggest, suggest-setup
            'cogs.starboard',       # starboard-setup, starboard-disable, starboard-stats
            'cogs.tickets',         # ticket-setup, ticket-close, ticket-add, ticket-remove
            'cogs.tempvoice',       # tempvoice-setup, voice-lock, voice-unlock, voice-limit, voice-rename
            # ── Features ──────────────────────────────────────────────────
            'cogs.music',           # play, skip, pause, resume, stop, queue, nowplaying, loop, volume, shuffle, remove
            'cogs.translation',     # translate, languages
            'cogs.ai',              # ai, ai-personality, ai-clear, ai-image, ai-translate, ai-summarize, ai-code, ai-analyze, ai-stats
            'cogs.roblox',          # roblox-link, roblox-stats, clan-stats, roblox-leaderboard, roblox-unlink, roblox-sync-bloxlink
            # ── Dashboard ─────────────────────────────────────────────────
            'cogs.webdashboard',    # web (dashboard link)
            'cogs.dashboard',       # wan, dashboard, help
        ]
        
        self.cog_errors = {}  # store load errors for /api/health
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f'✅ Loaded {cog}')
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                logger.error(f'❌ Failed to load {cog}: {e}\n{err}')
                self.cog_errors[cog] = str(e)
        
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
        self._broadcast('audit', {
            'guild_id': member.guild.id,
            'type': 'join',
            'icon': '👋',
            'title': f'{member.display_name} joined',
            'desc': f'Total: {member.guild.member_count} members',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    async def on_member_remove(self, member: discord.Member):
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
            synced = await self.tree.sync()
            logger.info(f'✅ Synced {len(synced)} slash commands globally')
            logger.info('⚠️ Note: Global commands may take up to 1 hour to appear in all servers')
        except Exception as e:
            logger.error(f'❌ Failed to sync commands: {e}')
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="your community 🎮"
            )
        )

        # Keep-alive: ping own health endpoint every 10 min so Render never sleeps
        dashboard_url = os.getenv('DASHBOARD_URL', '').rstrip('/')
        if dashboard_url:
            async def _keep_alive():
                import aiohttp
                while not self.is_closed():
                    try:
                        async with aiohttp.ClientSession() as s:
                            async with s.get(f"{dashboard_url}/api/health", timeout=aiohttp.ClientTimeout(total=10)) as r:
                                logger.debug(f"Keep-alive ping: {r.status}")
                    except Exception as e:
                        logger.debug(f"Keep-alive ping failed: {e}")
                    await asyncio.sleep(600)  # every 10 minutes
            self.loop.create_task(_keep_alive())
            logger.info(f"✅ Keep-alive pinger started → {dashboard_url}/api/health")
    
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
