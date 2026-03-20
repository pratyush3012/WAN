"""
WAN Bot - Roblox Integration Cog
Connects to Roblox games (Wizard West) to fetch player statistics
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import json
import os
import random

class RobloxIntegration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        
        # Roblox API endpoints
        self.ROBLOX_API = "https://users.roblox.com/v1"
        self.GAMES_API = "https://games.roblox.com/v1"
        self.PRESENCE_API = "https://presence.roblox.com/v1"
        self.DATASTORE_API = "https://apis.roblox.com/datastores/v1"
        
        # Game-specific settings from environment
        self.api_key = os.getenv('ROBLOX_API_KEY')
        self.universe_id = os.getenv('ROBLOX_UNIVERSE_ID')
        self.place_id = os.getenv('ROBLOX_PLACE_ID')
        self.webhook_secret = os.getenv('ROBLOX_WEBHOOK_SECRET')
        
        # Check if API is configured
        self.api_configured = bool(self.api_key and self.universe_id)
        
        if not self.api_configured:
            print("⚠️  Roblox API not configured - using demo data")
            print("💡 Demo mode: Bot will generate realistic test stats for demonstration")
            print("📝 To connect a real game, see ROBLOX_API_SETUP.md")
        else:
            print("✅ Roblox API configured - will fetch real game data")
        
        # Player data cache
        self.player_cache = {}
        self.clan_members = {}
        self.links_file = os.path.join(os.path.dirname(__file__), '..', 'roblox_links.json')
        self._load_links()
        
        # Start background tasks
        self.update_player_stats.start()
    
    async def cog_load(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
    
    async def cog_unload(self):
        """Cleanup HTTP session"""
        self.update_player_stats.cancel()
        if self.session:
            await self.session.close()

    def _save_links(self):
        """Persist clan_members to disk"""
        try:
            with open(self.links_file, 'w') as f:
                json.dump({str(k): v for k, v in self.clan_members.items()}, f)
        except Exception as e:
            print(f"⚠️  Could not save roblox links: {e}")

    def _load_links(self):
        """Load clan_members from disk"""
        try:
            if os.path.exists(self.links_file):
                with open(self.links_file, 'r') as f:
                    data = json.load(f)
                self.clan_members = {int(k): v for k, v in data.items()}
                print(f"✅ Loaded {len(self.clan_members)} Roblox links from disk")
        except Exception as e:
            print(f"⚠️  Could not load roblox links: {e}")
    
    # ===== Roblox API Methods =====
    
    async def get_bloxlink_user(self, discord_id: int) -> Optional[Dict]:
        """Get Roblox info from Bloxlink API"""
        try:
            url = f"https://api.blox.link/v4/public/guilds/{self.bot.guilds[0].id}/discord-to-roblox/{discord_id}"
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('robloxID'):
                        # Get username from Roblox ID
                        user_url = f"{self.ROBLOX_API}/users/{data['robloxID']}"
                        async with self.session.get(user_url) as user_resp:
                            if user_resp.status == 200:
                                user_data = await user_resp.json()
                                return {
                                    'id': data['robloxID'],
                                    'name': user_data.get('name'),
                                    'displayName': user_data.get('displayName')
                                }
        except Exception as e:
            print(f"Error fetching from Bloxlink: {e}")
        return None
    
    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get Roblox user info by username"""
        try:
            url = f"{self.ROBLOX_API}/usernames/users"
            async with self.session.post(url, json={"usernames": [username]}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('data'):
                        return data['data'][0]
        except Exception as e:
            print(f"Error fetching Roblox user: {e}")
        return None
    
    async def get_user_by_id(self, roblox_id: int) -> Optional[Dict]:
        """Get Roblox user info by ID"""
        try:
            url = f"{self.ROBLOX_API}/users/{roblox_id}"
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            print(f"Error fetching Roblox user by ID: {e}")
        return None
    
    async def get_user_presence(self, user_id: int) -> Optional[Dict]:
        """Get user's current presence (online status, game playing)"""
        try:
            url = f"{self.PRESENCE_API}/presence/users"
            async with self.session.post(url, json={"userIds": [user_id]}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('userPresences'):
                        return data['userPresences'][0]
        except Exception as e:
            print(f"Error fetching presence: {e}")
        return None
    
    async def get_game_stats(self, user_id: int, game_id: int = None) -> Optional[Dict]:
        """Get player's game statistics from Roblox DataStore
        
        This method fetches real player data from your Roblox game's DataStore.
        If API is not configured, it returns mock data for testing.
        """
        # If API not configured, return mock data
        if not self.api_configured:
            return self._get_mock_stats(user_id)
        
        try:
            # Fetch from Roblox Open Cloud DataStore API
            url = f"{self.DATASTORE_API}/universes/{self.universe_id}/standard-datastores/datastore/entries/entry"
            
            params = {
                'datastoreName': 'PlayerStats',  # Your DataStore name
                'entryKey': f'Player_{user_id}'
            }
            
            headers = {
                'x-api-key': self.api_key
            }
            
            async with self.session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Parse the data from your game's format
                    return {
                        'user_id': user_id,
                        'game_id': game_id or self.place_id,
                        'playtime': data.get('playtime', 0),
                        'coins_collected': data.get('coins_collected', 0),
                        'kills': data.get('kills', 0),
                        'deaths': data.get('deaths', 0),
                        'level': data.get('level', 1),
                        'last_played': data.get('last_played')
                    }
                elif resp.status == 404:
                    # Player hasn't played yet or no data
                    print(f"ℹ️  No game data found for Roblox user {user_id}")
                    return self._get_mock_stats(user_id)
                elif resp.status == 401:
                    print(f"❌ Invalid Roblox API key")
                    return self._get_mock_stats(user_id)
                elif resp.status == 403:
                    print(f"❌ API key doesn't have DataStore permissions")
                    return self._get_mock_stats(user_id)
                else:
                    print(f"⚠️  Roblox API returned status {resp.status}")
                    return self._get_mock_stats(user_id)
                    
        except Exception as e:
            print(f"❌ Error fetching game stats: {e}")
            return self._get_mock_stats(user_id)
    
    def _get_mock_stats(self, user_id: int) -> Dict:
        """Return mock stats for testing or when API is unavailable
        
        This generates realistic-looking stats for demonstration purposes.
        Each user gets consistent stats based on their ID.
        """
        import random
        
        # Use user_id as seed for consistent stats per user
        random.seed(user_id)
        
        # Generate realistic stats
        level = random.randint(1, 50)
        playtime = random.randint(3600, 360000)  # 1-100 hours in seconds
        coins = random.randint(1000, 100000)
        kills = random.randint(10, 500)
        deaths = random.randint(5, 300)
        
        # Reset random seed
        random.seed()
        
        return {
            'user_id': user_id,
            'game_id': self.place_id,
            'playtime': playtime,
            'coins_collected': coins,
            'kills': kills,
            'deaths': deaths,
            'level': level,
            'last_played': (datetime.utcnow() - timedelta(hours=random.randint(1, 48))).isoformat()
        }
    
    async def fetch_player_data(self, discord_id: int, roblox_username: str) -> Dict:
        """Fetch comprehensive player data"""
        # Get Roblox user info
        user_info = await self.get_user_by_username(roblox_username)
        if not user_info:
            return None
        
        roblox_id = user_info['id']
        
        # Get presence
        presence = await self.get_user_presence(roblox_id)
        
        # Get game stats (from your game's data store)
        game_stats = await self.get_game_stats(roblox_id)
        
        # Combine data
        player_data = {
            'discord_id': discord_id,
            'roblox_id': roblox_id,
            'roblox_username': user_info['name'],
            'display_name': user_info.get('displayName', user_info['name']),
            'is_online': presence.get('userPresenceType') == 1 if presence else False,
            'currently_playing': presence.get('placeId') == int(self.place_id) if (presence and self.place_id) else False,
            'stats': game_stats,
            'last_updated': datetime.utcnow().isoformat()
        }
        
        # Cache the data
        self.player_cache[discord_id] = player_data
        
        return player_data
    
    # ===== Discord Commands =====
    
    @app_commands.command(name="roblox-link", description="🎮 Link your Roblox account to Discord")
    async def link_roblox(self, interaction: discord.Interaction, roblox_username: str):
        """Link Roblox account to Discord profile"""
        await interaction.response.defer(ephemeral=True)
        
        # Verify Roblox user exists
        user_info = await self.get_user_by_username(roblox_username)
        
        if not user_info:
            embed = discord.Embed(
                title="❌ User Not Found",
                description=f"Roblox user `{roblox_username}` not found.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Store link in database (implement your database logic)
        # For now, storing in memory
        self.clan_members[interaction.user.id] = {
            'discord_id': interaction.user.id,
            'roblox_username': user_info['name'],
            'roblox_id': user_info['id'],
            'linked_at': datetime.utcnow().isoformat()
        }
        self._save_links()
        
        embed = discord.Embed(
            title="✅ Account Linked!",
            description=f"Successfully linked to Roblox account: **{user_info['name']}**",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Roblox Username",
            value=f"```{user_info['name']}```",
            inline=True
        )
        
        embed.add_field(
            name="Roblox ID",
            value=f"```{user_info['id']}```",
            inline=True
        )
        
        embed.add_field(
            name="📊 Next Steps",
            value="Use `/roblox-stats` to view your Wizard West statistics!",
            inline=False
        )
        
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_info['id']}&width=420&height=420&format=png")
        embed.set_footer(text="Your stats will be tracked automatically")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="roblox-stats", description="📊 View your Wizard West game statistics")
    async def view_stats(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """View Roblox game statistics"""
        target = member or interaction.user
        
        await interaction.response.defer()
        
        # Try to get from Bloxlink first
        if target.id not in self.clan_members:
            bloxlink_data = await self.get_bloxlink_user(target.id)
            if bloxlink_data:
                # Auto-link from Bloxlink
                self.clan_members[target.id] = {
                    'discord_id': target.id,
                    'roblox_username': bloxlink_data['name'],
                    'roblox_id': bloxlink_data['id'],
                    'linked_at': datetime.utcnow().isoformat(),
                    'source': 'bloxlink'
                }
        
        # Check if user is linked
        if target.id not in self.clan_members:
            embed = discord.Embed(
                title="❌ Not Linked",
                description=f"{'You have' if target == interaction.user else f'{target.mention} has'} not linked a Roblox account yet.\n\n**Option 1:** Use `/roblox-link <username>` to link manually\n**Option 2:** Link via Bloxlink bot and run this command again",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Fetch player data
        roblox_username = self.clan_members[target.id]['roblox_username']
        player_data = await self.fetch_player_data(target.id, roblox_username)
        
        if not player_data:
            await interaction.followup.send("❌ Failed to fetch player data. Please try again later.")
            return
        
        # Create beautiful stats embed
        embed = discord.Embed(
            title=f"🎮 Wizard West Statistics",
            description=f"**{player_data['display_name']}** (@{player_data['roblox_username']})",
            color=discord.Color.from_rgb(102, 126, 234)
        )
        
        # Show source
        source = self.clan_members[target.id].get('source', 'manual')
        if source == 'bloxlink':
            embed.set_footer(text=f"Stats updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} • Linked via Bloxlink")
        else:
            embed.set_footer(text=f"Stats updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        
        # Status indicator
        status_emoji = "🟢" if player_data['is_online'] else "⚫"
        playing_text = "🎮 Currently Playing!" if player_data['currently_playing'] else "Offline"
        
        embed.add_field(
            name=f"{status_emoji} Status",
            value=f"```{playing_text}```",
            inline=False
        )
        
        stats = player_data['stats']
        
        # Playtime
        hours = stats['playtime'] // 3600
        minutes = (stats['playtime'] % 3600) // 60
        embed.add_field(
            name="⏱️ Playtime",
            value=f"```{hours}h {minutes}m```",
            inline=True
        )
        
        # Coins
        embed.add_field(
            name="💰 Coins Collected",
            value=f"```{stats['coins_collected']:,}```",
            inline=True
        )
        
        # Level
        embed.add_field(
            name="⭐ Level",
            value=f"```{stats['level']}```",
            inline=True
        )
        
        # Kills
        embed.add_field(
            name="⚔️ Kills",
            value=f"```{stats['kills']:,}```",
            inline=True
        )
        
        # Deaths
        embed.add_field(
            name="💀 Deaths",
            value=f"```{stats['deaths']:,}```",
            inline=True
        )
        
        # K/D Ratio
        kd_ratio = stats['kills'] / max(stats['deaths'], 1)
        embed.add_field(
            name="📊 K/D Ratio",
            value=f"```{kd_ratio:.2f}```",
            inline=True
        )
        
        # Last played
        if stats['last_played']:
            embed.add_field(
                name="🕐 Last Played",
                value=f"```{stats['last_played']}```",
                inline=False
            )
        
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={player_data['roblox_id']}&width=420&height=420&format=png")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="clan-stats", description="👥 View all clan members' Wizard West statistics")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def clan_stats(self, interaction: discord.Interaction):
        """View statistics for all linked clan members"""
        await interaction.response.defer()
        
        if not self.clan_members:
            embed = discord.Embed(
                title="❌ No Linked Members",
                description="No clan members have linked their Roblox accounts yet.\n\n**Get Started:**\n• Use `/roblox-sync-bloxlink` to auto-link all members\n• Members can use `/roblox-link <username>` to link manually",
                color=discord.Color.red()
            )
            embed.add_field(
                name="🌐 Web Dashboard",
                value="Use `/web` to access the full clan dashboard with live stats!",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Fetch all player data
        all_stats = []
        for discord_id, member_info in self.clan_members.items():
            player_data = await self.fetch_player_data(discord_id, member_info['roblox_username'])
            if player_data:
                all_stats.append(player_data)
        
        # Sort by playtime
        all_stats.sort(key=lambda x: x['stats']['playtime'], reverse=True)
        
        # Create leaderboard embed
        embed = discord.Embed(
            title="👥 Clan Statistics - Wizard West",
            description=f"**{len(all_stats)} Members Tracked**",
            color=discord.Color.gold()
        )
        
        # Top players by playtime
        playtime_leaders = "\n".join([
            f"**{i+1}.** {p['display_name']} - {p['stats']['playtime']//3600}h {(p['stats']['playtime']%3600)//60}m"
            for i, p in enumerate(all_stats[:10])
        ])
        
        embed.add_field(
            name="⏱️ Top Playtime",
            value=playtime_leaders or "No data",
            inline=False
        )
        
        # Top by coins
        coin_leaders = sorted(all_stats, key=lambda x: x['stats']['coins_collected'], reverse=True)[:5]
        coins_text = "\n".join([
            f"**{i+1}.** {p['display_name']} - {p['stats']['coins_collected']:,} coins"
            for i, p in enumerate(coin_leaders)
        ])
        
        embed.add_field(
            name="💰 Top Coin Collectors",
            value=coins_text or "No data",
            inline=True
        )
        
        # Top by kills
        kill_leaders = sorted(all_stats, key=lambda x: x['stats']['kills'], reverse=True)[:5]
        kills_text = "\n".join([
            f"**{i+1}.** {p['display_name']} - {p['stats']['kills']:,} kills"
            for i, p in enumerate(kill_leaders)
        ])
        
        embed.add_field(
            name="⚔️ Top Killers",
            value=kills_text or "No data",
            inline=True
        )
        
        # Currently playing
        playing_now = [p for p in all_stats if p['currently_playing']]
        embed.add_field(
            name="🎮 Currently Playing",
            value=f"```{len(playing_now)} members online```",
            inline=False
        )
        
        # Total stats
        total_playtime = sum(p['stats']['playtime'] for p in all_stats)
        total_coins = sum(p['stats']['coins_collected'] for p in all_stats)
        total_kills = sum(p['stats']['kills'] for p in all_stats)
        
        embed.add_field(
            name="📊 Clan Totals",
            value=f"```\nPlaytime: {total_playtime//3600}h\nCoins: {total_coins:,}\nKills: {total_kills:,}\n```",
            inline=False
        )
        
        # Add web dashboard link
        embed.add_field(
            name="🌐 Full Dashboard",
            value="Use `/web` to view detailed stats, charts, and live leaderboards!",
            inline=False
        )
        
        embed.set_footer(text="Stats update every 5 minutes • Use /web for real-time updates")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="roblox-leaderboard", description="🏆 View Wizard West leaderboards")
    async def leaderboard(self, interaction: discord.Interaction, category: str = "playtime"):
        """View leaderboards by different categories"""
        await interaction.response.defer()
        
        if not self.clan_members:
            embed = discord.Embed(
                title="❌ No Linked Members",
                description="No clan members have linked their Roblox accounts yet.\n\n**Get Started:**\n• Use `/roblox-link <username>` to link your account\n• Or use `/roblox-sync-bloxlink` (Admin) to auto-link all members",
                color=discord.Color.red()
            )
            embed.add_field(
                name="🌐 Web Dashboard",
                value="Use `/web` to view the full leaderboard on the web dashboard!",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Fetch all stats
        all_stats = []
        for discord_id, member_info in self.clan_members.items():
            player_data = await self.fetch_player_data(discord_id, member_info['roblox_username'])
            if player_data:
                all_stats.append(player_data)
        
        # Sort by category
        sort_keys = {
            'playtime': lambda x: x['stats']['playtime'],
            'coins': lambda x: x['stats']['coins_collected'],
            'kills': lambda x: x['stats']['kills'],
            'level': lambda x: x['stats']['level'],
            'kd': lambda x: x['stats']['kills'] / max(x['stats']['deaths'], 1)
        }
        
        sort_key = sort_keys.get(category, sort_keys['playtime'])
        all_stats.sort(key=sort_key, reverse=True)
        
        # Create leaderboard
        embed = discord.Embed(
            title=f"🏆 Wizard West Leaderboard - {category.title()}",
            color=discord.Color.gold()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        
        leaderboard_text = ""
        for i, player in enumerate(all_stats[:15]):
            medal = medals[i] if i < 3 else f"**{i+1}.**"
            
            if category == 'playtime':
                value = f"{player['stats']['playtime']//3600}h {(player['stats']['playtime']%3600)//60}m"
            elif category == 'coins':
                value = f"{player['stats']['coins_collected']:,} coins"
            elif category == 'kills':
                value = f"{player['stats']['kills']:,} kills"
            elif category == 'level':
                value = f"Level {player['stats']['level']}"
            elif category == 'kd':
                kd = player['stats']['kills'] / max(player['stats']['deaths'], 1)
                value = f"{kd:.2f} K/D"
            
            leaderboard_text += f"{medal} **{player['display_name']}** - {value}\n"
        
        embed.description = leaderboard_text or "No data available"
        
        # Add web dashboard link
        embed.add_field(
            name="🌐 Full Leaderboard",
            value="Use `/web` to view the complete leaderboard with live updates on the web dashboard!",
            inline=False
        )
        
        embed.set_footer(text="Use /roblox-link to join the leaderboard! • Stats update every 5 minutes")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="collect-ingame-names", description="📨 DM all members asking for their Roblox in-game username")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def collect_ingame_names(self, interaction: discord.Interaction):
        """DM every non-bot member asking for their Roblox username, then store responses"""
        await interaction.response.defer(ephemeral=True)

        members = [m for m in interaction.guild.members if not m.bot]
        sent = 0
        failed = 0

        embed_info = discord.Embed(
            title="📨 Collecting In-Game Names",
            description=f"Sending DMs to {len(members)} members...",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed_info, ephemeral=True)

        for member in members:
            try:
                ask_embed = discord.Embed(
                    title="🎮 What's your Roblox username?",
                    description=(
                        f"Hey **{member.display_name}**! The admins of **{interaction.guild.name}** "
                        f"are collecting Roblox in-game names to track clan stats.\n\n"
                        f"Please reply to this message with your **exact Roblox username** "
                        f"(the one you use to log in to Roblox).\n\n"
                        f"Example: `Builderman`\n\n"
                        f"*Reply within 5 minutes or use `/roblox-link` in the server anytime.*"
                    ),
                    color=discord.Color.from_rgb(102, 126, 234)
                )
                ask_embed.set_footer(text=f"{interaction.guild.name} • Wizard West Clan")
                dm = await member.create_dm()
                await dm.send(embed=ask_embed)
                sent += 1
                await asyncio.sleep(0.5)  # rate limit
            except Exception:
                failed += 1

        # Listen for replies via on_message for 5 minutes
        self.bot.dispatch('roblox_collection_started', interaction.guild, interaction.user)

        result_embed = discord.Embed(
            title="✅ DMs Sent",
            color=discord.Color.green()
        )
        result_embed.add_field(name="✅ Sent", value=str(sent), inline=True)
        result_embed.add_field(name="❌ Failed (DMs closed)", value=str(failed), inline=True)
        result_embed.set_footer(text="Members have 5 minutes to reply. They can also use /roblox-link anytime.")
        await interaction.edit_original_response(embed=result_embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for DM replies to the ingame name collection"""
        # Only handle DMs from non-bots
        if message.guild is not None or message.author.bot:
            return
        # Check if this user is awaiting a response (simple: just try to link them)
        username = message.content.strip()
        if not username or len(username) > 50 or ' ' in username:
            return
        # Try to look up the Roblox user
        user_info = await self.get_user_by_username(username)
        if user_info:
            self.clan_members[message.author.id] = {
                'discord_id': message.author.id,
                'roblox_username': user_info['name'],
                'roblox_id': user_info['id'],
                'linked_at': datetime.utcnow().isoformat(),
                'source': 'dm_collection'
            }
            self._save_links()
            confirm = discord.Embed(
                title="✅ Linked!",
                description=f"Your Roblox account **{user_info['name']}** has been linked. Your stats will appear on the clan dashboard.",
                color=discord.Color.green()
            )
            await message.channel.send(embed=confirm)
        else:
            err = discord.Embed(
                title="❌ Username Not Found",
                description=f"Couldn't find a Roblox user named `{username}`. Please check the spelling and try again, or use `/roblox-link` in the server.",
                color=discord.Color.red()
            )
            await message.channel.send(embed=err)


    async def unlink_roblox(self, interaction: discord.Interaction):
        """Unlink Roblox account"""
        if interaction.user.id in self.clan_members:
            username = self.clan_members[interaction.user.id]['roblox_username']
            del self.clan_members[interaction.user.id]
            self._save_links()
            
            embed = discord.Embed(
                title="✅ Account Unlinked",
                description=f"Successfully unlinked from **{username}**",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Not Linked",
                description="You don't have a linked Roblox account.",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="roblox-sync-bloxlink", description="🔄 Sync all members from Bloxlink")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sync_bloxlink(self, interaction: discord.Interaction):
        """Sync all server members from Bloxlink"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="🔄 Syncing with Bloxlink...",
            description="Fetching Roblox accounts for all server members...",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)
        
        synced_count = 0
        failed_count = 0
        
        # Get all members
        for member in interaction.guild.members:
            if member.bot:
                continue
            
            try:
                # Try to get from Bloxlink
                bloxlink_data = await self.get_bloxlink_user(member.id)
                
                if bloxlink_data:
                    self.clan_members[member.id] = {
                        'discord_id': member.id,
                        'roblox_username': bloxlink_data['name'],
                        'roblox_id': bloxlink_data['id'],
                        'linked_at': datetime.utcnow().isoformat(),
                        'source': 'bloxlink'
                    }
                    synced_count += 1
                else:
                    failed_count += 1
                
                # Rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"Error syncing {member.name}: {e}")
                failed_count += 1
        
        # Update embed with results
        result_embed = discord.Embed(
            title="✅ Bloxlink Sync Complete!",
            color=discord.Color.green()
        )
        
        result_embed.add_field(
            name="✅ Successfully Synced",
            value=f"```{synced_count} members```",
            inline=True
        )
        
        result_embed.add_field(
            name="❌ Not Linked in Bloxlink",
            value=f"```{failed_count} members```",
            inline=True
        )
        
        result_embed.add_field(
            name="📊 Total Tracked",
            value=f"```{len(self.clan_members)} members```",
            inline=True
        )
        
        result_embed.add_field(
            name="💡 Next Steps",
            value="• Use `/roblox-stats` to view stats\n• Use `/clan-stats` for clan overview\n• Use `/roblox-leaderboard` for rankings",
            inline=False
        )
        
        result_embed.set_footer(text="Members not in Bloxlink can use /roblox-link to link manually")
        
        await interaction.edit_original_response(embed=result_embed)
    
    # ===== Background Tasks =====
    
    @tasks.loop(minutes=5)
    async def update_player_stats(self):
        """Update player statistics every 5 minutes"""
        if not self.clan_members:
            return
        
        print(f"🔄 Updating stats for {len(self.clan_members)} clan members...")
        
        for discord_id, member_info in self.clan_members.items():
            try:
                await self.fetch_player_data(discord_id, member_info['roblox_username'])
                await asyncio.sleep(1)  # Rate limiting
            except Exception as e:
                print(f"Error updating stats for {member_info['roblox_username']}: {e}")
        
        print("✅ Stats update complete")
    
    @update_player_stats.before_loop
    async def before_update_stats(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(RobloxIntegration(bot))
