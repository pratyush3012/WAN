"""
WAN Bot - Roblox Integration
- All links stored in DB (persistent across redeploys)
- collect-ingame-names actually works: batched DMs with live progress
- Public Roblox APIs for real profile data
- Open Cloud DataStore for in-game stats (optional)
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
from datetime import datetime
from typing import Optional, Dict
import logging
import os

from utils.settings import get_setting, set_setting

logger = logging.getLogger("discord_bot.roblox")

USERS_API    = "https://users.roblox.com/v1"
PRESENCE_API = "https://presence.roblox.com/v1"
THUMBNAILS   = "https://thumbnails.roblox.com/v1"
FRIENDS_API  = "https://friends.roblox.com/v1"
BADGES_API   = "https://badges.roblox.com/v1"
DATASTORE    = "https://apis.roblox.com/datastores/v1"


class RobloxIntegration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None

        self.api_key     = os.getenv("ROBLOX_API_KEY")
        self.universe_id = os.getenv("ROBLOX_UNIVERSE_ID")
        self.has_game_api = bool(self.api_key and self.universe_id)

        # In-memory caches (loaded from DB on first use)
        self._links: Optional[Dict[int, dict]] = None   # discord_id -> link info
        self._auto_dm: Optional[set] = None             # guild_ids with auto-DM on
        self._player_cache: Dict[int, dict] = {}
        self._pending_dm: set = set()

        self.update_player_stats.start()

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def cog_load(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "WANBot/1.0 (Discord bot)"}
        )
        await self._ensure_links()

    async def cog_unload(self):
        self.update_player_stats.cancel()
        if self.session:
            await self.session.close()

    # ── DB-backed persistence ──────────────────────────────────────────────────

    async def _ensure_links(self):
        """Load links from DB into memory if not already loaded."""
        if self._links is None:
            stored = await get_setting(0, "roblox_links", {})
            self._links = {int(k): v for k, v in stored.items()} if stored else {}
        if self._auto_dm is None:
            stored = await get_setting(0, "roblox_autodm", [])
            self._auto_dm = set(stored) if stored else set()

    async def _save_links(self):
        await set_setting(0, "roblox_links", {str(k): v for k, v in self._links.items()})

    async def _save_auto_dm(self):
        await set_setting(0, "roblox_autodm", list(self._auto_dm))

    # ── HTTP helpers ───────────────────────────────────────────────────────────

    async def _get(self, url: str, **kwargs) -> Optional[dict]:
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=8), **kwargs) as r:
                if r.status == 200:
                    return await r.json()
        except Exception as e:
            logger.debug(f"Roblox GET {url}: {e}")
        return None

    async def _post(self, url: str, **kwargs) -> Optional[dict]:
        try:
            async with self.session.post(url, timeout=aiohttp.ClientTimeout(total=8), **kwargs) as r:
                if r.status == 200:
                    return await r.json()
        except Exception as e:
            logger.debug(f"Roblox POST {url}: {e}")
        return None

    # ── Roblox API helpers ─────────────────────────────────────────────────────

    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        data = await self._post(
            f"{USERS_API}/usernames/users",
            json={"usernames": [username], "excludeBannedUsers": False}
        )
        if data and data.get("data"):
            u = data["data"][0]
            full = await self._get(f"{USERS_API}/users/{u['id']}")
            if full:
                u.update(full)
            return u
        return None

    async def get_user_by_id(self, roblox_id: int) -> Optional[Dict]:
        return await self._get(f"{USERS_API}/users/{roblox_id}")

    async def get_avatar_thumbnail(self, roblox_id: int) -> Optional[str]:
        data = await self._get(
            f"{THUMBNAILS}/users/avatar-headshot",
            params={"userIds": roblox_id, "size": "150x150", "format": "Png", "isCircular": "false"}
        )
        if data and data.get("data"):
            return data["data"][0].get("imageUrl")
        return None

    async def get_presence(self, roblox_id: int) -> Optional[Dict]:
        data = await self._post(
            f"{PRESENCE_API}/presence/users",
            json={"userIds": [roblox_id]}
        )
        if data and data.get("userPresences"):
            return data["userPresences"][0]
        return None

    async def get_friend_count(self, roblox_id: int) -> int:
        data = await self._get(f"{FRIENDS_API}/users/{roblox_id}/friends/count")
        return data.get("count", 0) if data else 0

    async def get_badge_count(self, roblox_id: int) -> int:
        data = await self._get(
            f"{BADGES_API}/users/{roblox_id}/badges",
            params={"limit": 10}
        )
        return len(data.get("data", [])) if data else 0

    async def get_game_stats_from_datastore(self, roblox_id: int) -> Optional[Dict]:
        if not self.has_game_api:
            return None
        try:
            url = f"{DATASTORE}/universes/{self.universe_id}/standard-datastores/datastore/entries/entry"
            async with self.session.get(
                url,
                params={"datastoreName": "PlayerStats", "entryKey": f"Player_{roblox_id}"},
                headers={"x-api-key": self.api_key},
                timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                if r.status == 200:
                    return await r.json()
        except Exception as e:
            logger.debug(f"DataStore error: {e}")
        return None

    async def fetch_player_data(self, discord_id: int, roblox_username: str) -> Optional[Dict]:
        user = await self.get_user_by_username(roblox_username)
        if not user:
            return None
        roblox_id = user["id"]
        presence, avatar, friends, badges = await asyncio.gather(
            self.get_presence(roblox_id),
            self.get_avatar_thumbnail(roblox_id),
            self.get_friend_count(roblox_id),
            self.get_badge_count(roblox_id),
            return_exceptions=True
        )
        presence_type = 0
        last_location = "Offline"
        if isinstance(presence, dict):
            presence_type = presence.get("userPresenceType", 0)
            last_location = presence.get("lastLocation", "Offline")
        game_stats = await self.get_game_stats_from_datastore(roblox_id)
        stats = {
            "kills":           game_stats.get("kills", 0)           if game_stats else 0,
            "deaths":          game_stats.get("deaths", 0)          if game_stats else 0,
            "coins_collected": game_stats.get("coins_collected", 0) if game_stats else 0,
            "level":           game_stats.get("level", 0)           if game_stats else 0,
            "playtime":        game_stats.get("playtime", 0)        if game_stats else 0,
            "has_game_data":   game_stats is not None,
        }
        player_data = {
            "discord_id":      discord_id,
            "roblox_id":       roblox_id,
            "roblox_username": user["name"],
            "display_name":    user.get("displayName", user["name"]),
            "description":     user.get("description", ""),
            "created":         user.get("created", ""),
            "is_banned":       user.get("isBanned", False),
            "avatar_url":      avatar if isinstance(avatar, str) else None,
            "is_online":       presence_type > 0,
            "is_in_game":      presence_type == 2,
            "last_location":   last_location,
            "friend_count":    friends if isinstance(friends, int) else 0,
            "badge_count":     badges  if isinstance(badges, int) else 0,
            "stats":           stats,
            "last_updated":    datetime.utcnow().isoformat(),
        }
        self._player_cache[discord_id] = player_data
        return player_data

    # ── DM helper ──────────────────────────────────────────────────────────────

    async def _send_roblox_dm(self, member: discord.Member, guild: discord.Guild) -> bool:
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
            self._pending_dm.add(member.id)
            return True
        except discord.Forbidden:
            return False
        except Exception as e:
            logger.debug(f"DM error for {member}: {e}")
            return False

    # ── Event listeners ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        await self._ensure_links()
        if member.guild.id not in self._auto_dm:
            return
        if member.id in self._links:
            return
        await asyncio.sleep(3)
        await self._send_roblox_dm(member, member.guild)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Accept DM replies with Roblox username."""
        if message.guild is not None or message.author.bot:
            return
        username = message.content.strip()
        if not username or len(username) > 50 or " " in username:
            return
        if username.startswith("/") or username.startswith("!"):
            return
        await self._ensure_links()
        user_info = await self.get_user_by_username(username)
        if user_info:
            self._links[message.author.id] = {
                "discord_id":      message.author.id,
                "roblox_username": user_info["name"],
                "roblox_id":       user_info["id"],
                "linked_at":       datetime.utcnow().isoformat(),
                "source":          "dm_reply",
            }
            await self._save_links()
            self._pending_dm.discard(message.author.id)
            embed = discord.Embed(
                title="✅ Roblox Account Linked!",
                description=(
                    f"Your Roblox account **{user_info['name']}** has been linked! 🎮\n"
                    f"Use `/roblox-stats` in the server to see your stats."
                ),
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_info['id']}&width=150&height=150&format=png")
            await message.channel.send(embed=embed)
        else:
            await message.channel.send(
                embed=discord.Embed(
                    title="❌ Username Not Found",
                    description=f"Couldn't find `{username}` on Roblox. Check spelling and try again.",
                    color=discord.Color.red()
                )
            )

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(name="roblox-link", description="🎮 Link your Roblox account")
    async def link_roblox(self, interaction: discord.Interaction, roblox_username: str):
        await interaction.response.defer(ephemeral=True)
        await self._ensure_links()
        user_info = await self.get_user_by_username(roblox_username)
        if not user_info:
            return await interaction.followup.send(
                embed=discord.Embed(title="❌ User Not Found", description=f"No Roblox user `{roblox_username}` found.", color=discord.Color.red()),
                ephemeral=True
            )
        self._links[interaction.user.id] = {
            "discord_id":      interaction.user.id,
            "roblox_username": user_info["name"],
            "roblox_id":       user_info["id"],
            "linked_at":       datetime.utcnow().isoformat(),
            "source":          "slash_command",
        }
        await self._save_links()
        embed = discord.Embed(title="✅ Account Linked!", description=f"Linked to **{user_info['name']}**", color=discord.Color.green())
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_info['id']}&width=150&height=150&format=png")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="roblox-stats", description="📊 View your Roblox stats")
    async def view_stats(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        await interaction.response.defer()
        await self._ensure_links()
        if target.id not in self._links:
            return await interaction.followup.send(
                embed=discord.Embed(title="❌ Not Linked", description="Use `/roblox-link <username>` first.", color=discord.Color.red())
            )
        info = self._links[target.id]
        data = await self.fetch_player_data(target.id, info["roblox_username"])
        if not data:
            return await interaction.followup.send("❌ Failed to fetch data. Try again later.")
        embed = discord.Embed(
            title=f"🎮 {data['display_name']}",
            description=f"@{data['roblox_username']}",
            color=discord.Color.from_rgb(102, 126, 234)
        )
        status = "🟢 Online" if data["is_online"] else "⚫ Offline"
        if data["is_in_game"]:
            status = f"🎮 In Game — {data['last_location']}"
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Friends", value=str(data["friend_count"]), inline=True)
        embed.add_field(name="Badges", value=str(data["badge_count"]), inline=True)
        if data["stats"]["has_game_data"]:
            s = data["stats"]
            kd = s["kills"] / max(s["deaths"], 1)
            hrs = s["playtime"] // 3600
            embed.add_field(name="⚔️ Kills", value=str(s["kills"]), inline=True)
            embed.add_field(name="💀 Deaths", value=str(s["deaths"]), inline=True)
            embed.add_field(name="📊 K/D", value=f"{kd:.2f}", inline=True)
            embed.add_field(name="💰 Coins", value=f"{s['coins_collected']:,}", inline=True)
            embed.add_field(name="⭐ Level", value=str(s["level"]), inline=True)
            embed.add_field(name="⏱️ Playtime", value=f"{hrs}h", inline=True)
        else:
            embed.add_field(name="ℹ️ In-Game Stats", value="Not available — set `ROBLOX_API_KEY` env var", inline=False)
        if data["avatar_url"]:
            embed.set_thumbnail(url=data["avatar_url"])
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="roblox-unlink", description="🔗 Unlink your Roblox account")
    async def unlink_roblox(self, interaction: discord.Interaction):
        await self._ensure_links()
        if interaction.user.id in self._links:
            name = self._links.pop(interaction.user.id)["roblox_username"]
            self._player_cache.pop(interaction.user.id, None)
            await self._save_links()
            await interaction.response.send_message(
                embed=discord.Embed(title="✅ Unlinked", description=f"Unlinked from **{name}**", color=discord.Color.green()),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=discord.Embed(title="❌ Not Linked", color=discord.Color.red()),
                ephemeral=True
            )

    @app_commands.command(name="roblox-leaderboard", description="🏆 View clan leaderboard")
    async def leaderboard(self, interaction: discord.Interaction, sort: str = "friends"):
        await interaction.response.defer()
        await self._ensure_links()
        if not self._links:
            return await interaction.followup.send("No linked members yet. Use `/roblox-link`.")
        all_data = []
        for did, info in self._links.items():
            d = self._player_cache.get(did) or await self.fetch_player_data(did, info["roblox_username"])
            if d:
                all_data.append(d)
        sort_map = {
            "friends": lambda x: x["friend_count"],
            "badges":  lambda x: x["badge_count"],
            "kills":   lambda x: x["stats"]["kills"],
            "level":   lambda x: x["stats"]["level"],
            "coins":   lambda x: x["stats"]["coins_collected"],
        }
        all_data.sort(key=sort_map.get(sort, sort_map["friends"]), reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, d in enumerate(all_data[:15]):
            rank = medals[i] if i < 3 else f"`{i+1}.`"
            val = d["friend_count"] if sort == "friends" else d["badge_count"] if sort == "badges" else d["stats"].get(sort, 0)
            lines.append(f"{rank} **{d['display_name']}** — {val}")
        embed = discord.Embed(
            title=f"🏆 Clan Leaderboard — {sort.title()}",
            description="\n".join(lines) or "No data",
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="collect-ingame-names", description="📨 DM ALL unlinked members asking for Roblox username")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def collect_ingame_names(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._ensure_links()
        members = [m for m in interaction.guild.members if not m.bot and m.id not in self._links]
        total = len(members)
        if total == 0:
            return await interaction.followup.send("✅ All members are already linked!", ephemeral=True)

        await interaction.followup.send(
            embed=discord.Embed(
                title="📨 Sending DMs...",
                description=f"Messaging **{total}** unlinked members.\nThis may take a minute — Discord rate-limits DMs.",
                color=discord.Color.blue()
            ),
            ephemeral=True
        )

        sent = failed = 0
        for i, m in enumerate(members):
            try:
                ok = await self._send_roblox_dm(m, interaction.guild)
                if ok:
                    sent += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            # Discord DM rate limit: ~1/sec
            await asyncio.sleep(1.2)
            # Update progress every 10 members
            if (i + 1) % 10 == 0 or (i + 1) == total:
                try:
                    await interaction.edit_original_response(
                        embed=discord.Embed(
                            title=f"📨 Sending DMs... {i+1}/{total}",
                            description=f"✅ Sent: **{sent}** | ❌ Failed (DMs closed): **{failed}**",
                            color=discord.Color.blue()
                        )
                    )
                except Exception:
                    pass

        try:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="✅ Done!",
                    description=(
                        f"✅ Successfully sent: **{sent}**\n"
                        f"❌ Failed (DMs closed): **{failed}**\n\n"
                        f"Members who reply will be automatically linked."
                    ),
                    color=discord.Color.green()
                )
            )
        except Exception:
            pass

    @app_commands.command(name="roblox-autodm", description="🔔 Toggle auto-DM for new joiners")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle_auto_dm(self, interaction: discord.Interaction):
        await self._ensure_links()
        gid = interaction.guild.id
        if gid in self._auto_dm:
            self._auto_dm.discard(gid)
            status, color = "disabled", discord.Color.red()
        else:
            self._auto_dm.add(gid)
            status, color = "enabled", discord.Color.green()
        await self._save_auto_dm()
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"🔔 Auto-DM {status}",
                description=f"New joiners will {'now' if status == 'enabled' else 'no longer'} be auto-DM'd for their Roblox username.",
                color=color
            ),
            ephemeral=True
        )

    @app_commands.command(name="roblox-sync-bloxlink", description="🔄 Auto-link all members via Bloxlink")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sync_bloxlink(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_links()
        synced = failed = 0
        for member in interaction.guild.members:
            if member.bot:
                continue
            try:
                url = f"https://api.blox.link/v4/public/guilds/{interaction.guild.id}/discord-to-roblox/{member.id}"
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status == 200:
                        data = await r.json()
                        rid = data.get("robloxID")
                        if rid:
                            user = await self.get_user_by_id(int(rid))
                            if user:
                                self._links[member.id] = {
                                    "discord_id":      member.id,
                                    "roblox_username": user["name"],
                                    "roblox_id":       user["id"],
                                    "linked_at":       datetime.utcnow().isoformat(),
                                    "source":          "bloxlink",
                                }
                                synced += 1
                                continue
                failed += 1
                await asyncio.sleep(0.5)
            except Exception:
                failed += 1
        await self._save_links()
        embed = discord.Embed(title="✅ Bloxlink Sync Complete", color=discord.Color.green())
        embed.add_field(name="✅ Synced", value=str(synced), inline=True)
        embed.add_field(name="❌ Not in Bloxlink", value=str(failed), inline=True)
        await interaction.followup.send(embed=embed)

    # ── Background task ────────────────────────────────────────────────────────

    @tasks.loop(minutes=15)
    async def update_player_stats(self):
        if not self._links:
            return
        for discord_id, info in list(self._links.items()):
            try:
                await self.fetch_player_data(discord_id, info["roblox_username"])
                await asyncio.sleep(2)
            except Exception as e:
                logger.debug(f"Stats update error for {info['roblox_username']}: {e}")

    @update_player_stats.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()
        await self._ensure_links()

    # ── Properties for dashboard compatibility ─────────────────────────────────

    @property
    def clan_members(self):
        return self._links or {}

    @property
    def player_cache(self):
        return self._player_cache


async def setup(bot):
    await bot.add_cog(RobloxIntegration(bot))
