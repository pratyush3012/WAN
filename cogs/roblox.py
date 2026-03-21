"""
WAN Bot - Roblox Integration Cog
Uses PUBLIC Roblox APIs (no API key needed) for real profile data.
In-game stats (kills/coins/level) require the game owner's Open Cloud key.
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

class RobloxIntegration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None

        # Public Roblox API endpoints (no key needed)
        self.USERS_API    = "https://users.roblox.com/v1"
        self.PRESENCE_API = "https://presence.roblox.com/v1"
        self.THUMBNAILS   = "https://thumbnails.roblox.com/v1"
        self.FRIENDS_API  = "https://friends.roblox.com/v1"
        self.BADGES_API   = "https://badges.roblox.com/v1"
        self.GAMES_API    = "https://games.roblox.com/v1"
        self.GROUPS_API   = "https://groups.roblox.com/v1"

        # Optional: Open Cloud DataStore (game owner's key)
        self.api_key     = os.getenv('ROBLOX_API_KEY')
        self.universe_id = os.getenv('ROBLOX_UNIVERSE_ID')
        self.place_id    = os.getenv('ROBLOX_PLACE_ID')
        self.DATASTORE   = "https://apis.roblox.com/datastores/v1"

        self.has_game_api = bool(self.api_key and self.universe_id)

        # Per-guild auto-DM setting: {guild_id: bool}
        self.auto_dm_guilds: set = set()
        self._auto_dm_file = os.path.join(os.path.dirname(__file__), '..', 'roblox_autodm.json')
        self._load_auto_dm()

        # Linked members & cache
        self.clan_members: Dict[int, dict] = {}
        self.player_cache: Dict[int, dict] = {}
        self.links_file = os.path.join(os.path.dirname(__file__), '..', 'roblox_links.json')
        self._load_links()

        self.update_player_stats.start()
        # Track users we've DM'd so we know to expect a Roblox username reply
        self._pending_dm: set = set()

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def cog_load(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "WANBot/1.0 (Discord bot; contact via Discord)"}
        )

    async def cog_unload(self):
        self.update_player_stats.cancel()
        if self.session:
            await self.session.close()

    # ── persistence ────────────────────────────────────────────────────────────

    def _save_links(self):
        try:
            with open(self.links_file, 'w') as f:
                json.dump({str(k): v for k, v in self.clan_members.items()}, f)
        except Exception as e:
            print(f"⚠️  roblox_links save error: {e}")

    def _load_links(self):
        try:
            if os.path.exists(self.links_file):
                with open(self.links_file) as f:
                    data = json.load(f)
                self.clan_members = {int(k): v for k, v in data.items()}
                print(f"✅ Loaded {len(self.clan_members)} Roblox links")
        except Exception as e:
            print(f"⚠️  roblox_links load error: {e}")

    def _save_auto_dm(self):
        try:
            with open(self._auto_dm_file, 'w') as f:
                json.dump(list(self.auto_dm_guilds), f)
        except Exception as e:
            print(f"⚠️  auto_dm save error: {e}")

    def _load_auto_dm(self):
        try:
            if os.path.exists(self._auto_dm_file):
                with open(self._auto_dm_file) as f:
                    self.auto_dm_guilds = set(json.load(f))
        except Exception:
            self.auto_dm_guilds = set()

    # ── Public Roblox API helpers ──────────────────────────────────────────────

    async def _get(self, url: str, **kwargs) -> Optional[dict]:
        """GET with error handling."""
        try:
            async with self.session.get(url, **kwargs) as r:
                if r.status == 200:
                    return await r.json()
        except Exception as e:
            print(f"Roblox GET {url}: {e}")
        return None

    async def _post(self, url: str, **kwargs) -> Optional[dict]:
        try:
            async with self.session.post(url, **kwargs) as r:
                if r.status == 200:
                    return await r.json()
        except Exception as e:
            print(f"Roblox POST {url}: {e}")
        return None

    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Resolve username → Roblox user object (public API)."""
        data = await self._post(
            f"{self.USERS_API}/usernames/users",
            json={"usernames": [username], "excludeBannedUsers": False}
        )
        if data and data.get('data'):
            u = data['data'][0]
            # Fetch full profile
            full = await self._get(f"{self.USERS_API}/users/{u['id']}")
            if full:
                u.update(full)
            return u
        return None

    async def get_user_by_id(self, roblox_id: int) -> Optional[Dict]:
        return await self._get(f"{self.USERS_API}/users/{roblox_id}")

    async def get_avatar_thumbnail(self, roblox_id: int, size: str = "150x150") -> Optional[str]:
        """Get headshot thumbnail URL (public)."""
        data = await self._get(
            f"{self.THUMBNAILS}/users/avatar-headshot",
            params={"userIds": roblox_id, "size": size, "format": "Png", "isCircular": "false"}
        )
        if data and data.get('data'):
            return data['data'][0].get('imageUrl')
        return None

    async def get_presence(self, roblox_id: int) -> Optional[Dict]:
        """Get online presence (public endpoint)."""
        data = await self._post(
            f"{self.PRESENCE_API}/presence/users",
            json={"userIds": [roblox_id]}
        )
        if data and data.get('userPresences'):
            return data['userPresences'][0]
        return None

    async def get_friend_count(self, roblox_id: int) -> int:
        data = await self._get(f"{self.FRIENDS_API}/users/{roblox_id}/friends/count")
        return data.get('count', 0) if data else 0

    async def get_badge_count(self, roblox_id: int) -> int:
        """Count badges awarded to user (public)."""
        data = await self._get(
            f"{self.BADGES_API}/users/{roblox_id}/badges",
            params={"limit": 10}
        )
        return len(data.get('data', [])) if data else 0

    async def get_game_visits(self, place_id: int) -> Optional[int]:
        """Get total visit count for a game place (public)."""
        if not place_id:
            return None
        data = await self._get(
            f"{self.GAMES_API}/games/multiget-place-details",
            params={"placeIds": place_id}
        )
        if data and isinstance(data, list) and data:
            return data[0].get('visits')
        return None

    async def get_game_stats_from_datastore(self, roblox_id: int) -> Optional[Dict]:
        """Fetch in-game stats via Open Cloud DataStore (requires ROBLOX_API_KEY)."""
        if not self.has_game_api:
            return None
        try:
            url = f"{self.DATASTORE}/universes/{self.universe_id}/standard-datastores/datastore/entries/entry"
            async with self.session.get(
                url,
                params={"datastoreName": "PlayerStats", "entryKey": f"Player_{roblox_id}"},
                headers={"x-api-key": self.api_key}
            ) as r:
                if r.status == 200:
                    return await r.json()
        except Exception as e:
            print(f"DataStore error: {e}")
        return None

    async def fetch_player_data(self, discord_id: int, roblox_username: str) -> Optional[Dict]:
        """Fetch all available real data for a linked member."""
        user = await self.get_user_by_username(roblox_username)
        if not user:
            return None

        roblox_id = user['id']

        # Run public API calls concurrently
        presence, avatar, friends, badges = await asyncio.gather(
            self.get_presence(roblox_id),
            self.get_avatar_thumbnail(roblox_id),
            self.get_friend_count(roblox_id),
            self.get_badge_count(roblox_id),
            return_exceptions=True
        )

        # Presence
        presence_type = 0
        last_location = "Offline"
        if isinstance(presence, dict):
            presence_type = presence.get('userPresenceType', 0)
            last_location = presence.get('lastLocation', 'Offline')

        is_online = presence_type > 0
        is_in_game = presence_type == 2

        # In-game stats (only if game owner provided API key)
        game_stats = await self.get_game_stats_from_datastore(roblox_id)
        stats = {
            'kills':          game_stats.get('kills', 0)          if game_stats else 0,
            'deaths':         game_stats.get('deaths', 0)         if game_stats else 0,
            'coins_collected':game_stats.get('coins_collected', 0) if game_stats else 0,
            'level':          game_stats.get('level', 0)          if game_stats else 0,
            'playtime':       game_stats.get('playtime', 0)       if game_stats else 0,
            'has_game_data':  game_stats is not None,
        }

        player_data = {
            'discord_id':      discord_id,
            'roblox_id':       roblox_id,
            'roblox_username': user['name'],
            'display_name':    user.get('displayName', user['name']),
            'description':     user.get('description', ''),
            'created':         user.get('created', ''),
            'is_banned':       user.get('isBanned', False),
            'avatar_url':      avatar if isinstance(avatar, str) else None,
            'is_online':       is_online,
            'is_in_game':      is_in_game,
            'last_location':   last_location,
            'friend_count':    friends if isinstance(friends, int) else 0,
            'badge_count':     badges  if isinstance(badges, int) else 0,
            'stats':           stats,
            'last_updated':    datetime.utcnow().isoformat(),
        }

        self.player_cache[discord_id] = player_data
        return player_data

    # ── DM helpers ─────────────────────────────────────────────────────────────

    async def _send_roblox_dm(self, member: discord.Member, guild: discord.Guild):
        """Send the 'what's your Roblox username?' DM to one member."""
        embed = discord.Embed(
            title="🎮 Link your Roblox account!",
            description=(
                f"Hey **{member.display_name}**! 👋\n\n"
                f"The admins of **{guild.name}** want to link your Roblox account "
                f"to track clan stats on the dashboard.\n\n"
                f"**Just reply to this DM** with your exact Roblox username.\n\n"
                f"Example: `Builderman`\n\n"
                f"*You can also use `/roblox-link` in the server anytime.*"
            ),
            color=discord.Color.from_rgb(102, 126, 234)
        )
        embed.set_footer(text=f"{guild.name} • Reply with your Roblox username below 👇")
        try:
            dm = await member.create_dm()
            await dm.send(embed=embed)
            # Track that we DM'd this user so on_message knows to expect a reply
            self._pending_dm.add(member.id)
            return True
        except discord.Forbidden:
            logger.warning(f"Cannot DM {member} — DMs closed")
            return False
        except Exception as e:
            logger.warning(f"DM error for {member}: {e}")
            return False

    # ── Event listeners ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Auto-DM new joiners if enabled for this guild."""
        if member.bot:
            return
        if member.guild.id not in self.auto_dm_guilds:
            return
        if member.id in self.clan_members:
            return
        try:
            await asyncio.sleep(3)  # small delay so member is fully loaded
            await self._send_roblox_dm(member, member.guild)
        except Exception as e:
            logger.warning(f"Auto-DM on_member_join error: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for DM replies with Roblox username.
        Accepts replies from anyone who was DM'd OR anyone who DMs the bot directly."""
        # Only handle DMs (not guild messages)
        if message.guild is not None or message.author.bot:
            return

        username = message.content.strip()
        if not username or len(username) > 50:
            return
        # Ignore commands
        if username.startswith('/') or username.startswith('!'):
            return
        # Ignore messages with spaces (not a valid Roblox username)
        if ' ' in username:
            return

        # Accept reply if: user was DM'd by us, OR user is already trying to link
        # (we accept from anyone to make it easy — they can always use /roblox-link too)
        user_info = await self.get_user_by_username(username)
        if user_info:
            self.clan_members[message.author.id] = {
                'discord_id':      message.author.id,
                'roblox_username': user_info['name'],
                'roblox_id':       user_info['id'],
                'linked_at':       datetime.utcnow().isoformat(),
                'source':          'dm_reply',
            }
            self._save_links()
            self._pending_dm.discard(message.author.id)
            embed = discord.Embed(
                title="✅ Roblox Account Linked!",
                description=(
                    f"Your Roblox account **{user_info['name']}** has been linked successfully! 🎮\n\n"
                    f"Your profile will appear on the clan dashboard shortly.\n"
                    f"Use `/roblox-stats` in the server to see your stats anytime."
                ),
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_info['id']}&width=150&height=150&format=png")
            await message.channel.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Username Not Found",
                description=(
                    f"Couldn't find a Roblox user named `{username}`.\n\n"
                    f"Make sure you typed it **exactly** as it appears on Roblox (case doesn't matter).\n"
                    f"Try again or use `/roblox-link` in the server."
                ),
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(name="roblox-link", description="🎮 Link your Roblox account to Discord")
    async def link_roblox(self, interaction: discord.Interaction, roblox_username: str):
        await interaction.response.defer(ephemeral=True)
        user_info = await self.get_user_by_username(roblox_username)
        if not user_info:
            await interaction.followup.send(embed=discord.Embed(title="❌ User Not Found", description=f"No Roblox user `{roblox_username}` found.", color=discord.Color.red()), ephemeral=True)
            return
        self.clan_members[interaction.user.id] = {
            'discord_id':      interaction.user.id,
            'roblox_username': user_info['name'],
            'roblox_id':       user_info['id'],
            'linked_at':       datetime.utcnow().isoformat(),
            'source':          'slash_command',
        }
        self._save_links()
        embed = discord.Embed(title="✅ Account Linked!", description=f"Linked to **{user_info['name']}**", color=discord.Color.green())
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_info['id']}&width=150&height=150&format=png")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="roblox-stats", description="📊 View your Wizard West game statistics")
    async def view_stats(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        await interaction.response.defer()
        if target.id not in self.clan_members:
            await interaction.followup.send(embed=discord.Embed(title="❌ Not Linked", description="Use `/roblox-link <username>` to link your account.", color=discord.Color.red()))
            return
        info = self.clan_members[target.id]
        data = await self.fetch_player_data(target.id, info['roblox_username'])
        if not data:
            await interaction.followup.send("❌ Failed to fetch data. Try again later.")
            return
        embed = discord.Embed(title=f"🎮 {data['display_name']}", description=f"@{data['roblox_username']}", color=discord.Color.from_rgb(102, 126, 234))
        status = "🟢 Online" if data['is_online'] else "⚫ Offline"
        if data['is_in_game']:
            status = f"🎮 In Game — {data['last_location']}"
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Friends", value=str(data['friend_count']), inline=True)
        embed.add_field(name="Badges", value=str(data['badge_count']), inline=True)
        if data['stats']['has_game_data']:
            s = data['stats']
            kd = s['kills'] / max(s['deaths'], 1)
            hrs = s['playtime'] // 3600
            embed.add_field(name="⚔️ Kills", value=str(s['kills']), inline=True)
            embed.add_field(name="💀 Deaths", value=str(s['deaths']), inline=True)
            embed.add_field(name="📊 K/D", value=f"{kd:.2f}", inline=True)
            embed.add_field(name="💰 Coins", value=f"{s['coins_collected']:,}", inline=True)
            embed.add_field(name="⭐ Level", value=str(s['level']), inline=True)
            embed.add_field(name="⏱️ Playtime", value=f"{hrs}h", inline=True)
        else:
            embed.add_field(name="ℹ️ In-Game Stats", value="Not available — game owner needs to set `ROBLOX_API_KEY`", inline=False)
        if data['avatar_url']:
            embed.set_thumbnail(url=data['avatar_url'])
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="roblox-unlink", description="🔗 Unlink your Roblox account")
    async def unlink_roblox(self, interaction: discord.Interaction):
        if interaction.user.id in self.clan_members:
            name = self.clan_members.pop(interaction.user.id)['roblox_username']
            self.player_cache.pop(interaction.user.id, None)
            self._save_links()
            await interaction.response.send_message(embed=discord.Embed(title="✅ Unlinked", description=f"Unlinked from **{name}**", color=discord.Color.green()), ephemeral=True)
        else:
            await interaction.response.send_message(embed=discord.Embed(title="❌ Not Linked", color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="roblox-leaderboard", description="🏆 View clan leaderboard")
    async def leaderboard(self, interaction: discord.Interaction, sort: str = "friends"):
        await interaction.response.defer()
        if not self.clan_members:
            await interaction.followup.send("No linked members yet. Use `/roblox-link`.")
            return
        all_data = []
        for did, info in self.clan_members.items():
            d = self.player_cache.get(did) or await self.fetch_player_data(did, info['roblox_username'])
            if d:
                all_data.append(d)
        sort_map = {
            'friends': lambda x: x['friend_count'],
            'badges':  lambda x: x['badge_count'],
            'kills':   lambda x: x['stats']['kills'],
            'level':   lambda x: x['stats']['level'],
            'coins':   lambda x: x['stats']['coins_collected'],
        }
        all_data.sort(key=sort_map.get(sort, sort_map['friends']), reverse=True)
        medals = ['🥇','🥈','🥉']
        lines = []
        for i, d in enumerate(all_data[:15]):
            rank = medals[i] if i < 3 else f"`{i+1}.`"
            val = d['friend_count'] if sort == 'friends' else d['badge_count'] if sort == 'badges' else d['stats'].get(sort, 0)
            lines.append(f"{rank} **{d['display_name']}** — {val}")
        embed = discord.Embed(title=f"🏆 Clan Leaderboard — {sort.title()}", description="\n".join(lines) or "No data", color=discord.Color.gold())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="collect-ingame-names", description="📨 DM ALL members asking for their Roblox username")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def collect_ingame_names(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        members = [m for m in interaction.guild.members if not m.bot and m.id not in self.clan_members]
        await interaction.followup.send(embed=discord.Embed(title="📨 Sending DMs...", description=f"Messaging {len(members)} unlinked members.", color=discord.Color.blue()), ephemeral=True)
        sent = failed = 0
        for m in members:
            try:
                ok = await self._send_roblox_dm(m, interaction.guild)
                if ok:
                    sent += 1
                else:
                    failed += 1
                await asyncio.sleep(0.6)
            except Exception:
                failed += 1
        embed = discord.Embed(title="✅ Done", color=discord.Color.green())
        embed.add_field(name="✅ Sent", value=str(sent), inline=True)
        embed.add_field(name="❌ Failed (DMs closed)", value=str(failed), inline=True)
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="roblox-autodm", description="🔔 Toggle auto-DM for new joiners asking for Roblox username")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle_auto_dm(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        if gid in self.auto_dm_guilds:
            self.auto_dm_guilds.discard(gid)
            status = "disabled"
            color = discord.Color.red()
        else:
            self.auto_dm_guilds.add(gid)
            status = "enabled"
            color = discord.Color.green()
        self._save_auto_dm()
        await interaction.response.send_message(
            embed=discord.Embed(title=f"🔔 Auto-DM {status}", description=f"New joiners will {'now' if status=='enabled' else 'no longer'} be automatically DM'd asking for their Roblox username.", color=color),
            ephemeral=True
        )

    @app_commands.command(name="roblox-sync-bloxlink", description="🔄 Auto-link all members via Bloxlink")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sync_bloxlink(self, interaction: discord.Interaction):
        await interaction.response.defer()
        synced = failed = 0
        for member in interaction.guild.members:
            if member.bot:
                continue
            try:
                url = f"https://api.blox.link/v4/public/guilds/{interaction.guild.id}/discord-to-roblox/{member.id}"
                async with self.session.get(url) as r:
                    if r.status == 200:
                        data = await r.json()
                        rid = data.get('robloxID')
                        if rid:
                            user = await self.get_user_by_id(int(rid))
                            if user:
                                self.clan_members[member.id] = {
                                    'discord_id': member.id,
                                    'roblox_username': user['name'],
                                    'roblox_id': user['id'],
                                    'linked_at': datetime.utcnow().isoformat(),
                                    'source': 'bloxlink',
                                }
                                synced += 1
                                continue
                failed += 1
                await asyncio.sleep(0.5)
            except Exception:
                failed += 1
        self._save_links()
        embed = discord.Embed(title="✅ Bloxlink Sync Complete", color=discord.Color.green())
        embed.add_field(name="✅ Synced", value=str(synced), inline=True)
        embed.add_field(name="❌ Not in Bloxlink", value=str(failed), inline=True)
        await interaction.followup.send(embed=embed)

    # ── Background task ────────────────────────────────────────────────────────

    @tasks.loop(minutes=10)
    async def update_player_stats(self):
        if not self.clan_members:
            return
        for discord_id, info in list(self.clan_members.items()):
            try:
                await self.fetch_player_data(discord_id, info['roblox_username'])
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Stats update error for {info['roblox_username']}: {e}")

    @update_player_stats.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(RobloxIntegration(bot))
