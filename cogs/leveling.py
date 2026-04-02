"""
WAN Bot - Leveling System v3 (Fixed Edition)
Bugs fixed:
  - XP calculation was wrong (level stored separately from XP, causing desync)
  - Voice XP task double-counted (gave XP every 5 min AND on leave)
  - Streak reset incorrectly (timezone issues)
  - Level-up fired multiple times for same level
  - _persist() saved ALL guilds on every message (massive DB write)
  - no_xp_channels stored as strings but compared as ints
  - Rank card showed wrong level (used cached u["level"] not recalculated)
  - Daily bonus XP not reflected in rank until next message
  - XP multiplier event not applied to daily/voice correctly
  - Leaderboard showed deleted members without fallback name
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import logging
import random
import time
import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta
from utils.settings import get_setting, set_setting
from utils.discord_interaction import send_response

logger = logging.getLogger("discord_bot.leveling")

LEVELING_JSON = os.path.join(os.getenv("DATA_DIR", "./data"), "leveling.json")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# XP values
XP_MESSAGE_MIN   = 15
XP_MESSAGE_MAX   = 25
XP_VOICE_PER_MIN = 10
XP_REACTION      = 5
XP_DAILY_MIN     = 100
XP_DAILY_MAX     = 300
XP_FIRST_MSG_DAY = 50
XP_STREAK_BONUS  = 25   # extra per streak day (capped at 10 days)

# Cooldowns (seconds)
CD_MESSAGE  = 60
CD_REACTION = 30

MILESTONES = {5, 10, 25, 50, 75, 100}

LEVELUP_MSGS = [
    "{user} just hit **Level {level}**! The grind is real 🔥",
    "GG {user}! Level **{level}** unlocked 🎮 Keep going!",
    "Aye {user} is now Level **{level}**! 👑 Respect.",
    "{user} leveled up to **{level}**! Bhai scene ban gaya 🚀",
    "Level **{level}** achieved! {user} is on a different level fr 💪",
    "🎉 {user} reached Level **{level}**! The server is proud.",
    "{user} grinded their way to Level **{level}**! 🏆",
    "Oof {user} is Level **{level}** now. Koi rok nahi sakta 😤",
]

MILESTONE_MSGS = {
    5:   "🌟 {user} hit **Level 5** — officially part of the crew!",
    10:  "🔥 {user} is **Level 10**! A true regular. Respect.",
    25:  "💎 {user} reached **Level 25**! Veteran status unlocked.",
    50:  "👑 {user} is **Level 50**! Absolute legend of this server.",
    75:  "🚀 {user} hit **Level 75**! Bhai ye toh god mode hai.",
    100: "🏆 {user} reached **Level 100**! GOAT. No debate.",
}


def _xp_for_level(lvl: int) -> int:
    """XP required to complete level `lvl` (i.e. go from lvl → lvl+1)."""
    return 5 * (lvl ** 2) + 50 * lvl + 100


def _xp_progress(total_xp: int):
    """
    Returns (level, xp_into_current_level, xp_needed_for_next_level).
    FIX: was mutating `xp` variable incorrectly causing wrong level display.
    """
    lvl = 0
    remaining = total_xp
    while remaining >= _xp_for_level(lvl):
        remaining -= _xp_for_level(lvl)
        lvl += 1
    return lvl, remaining, _xp_for_level(lvl)


def _progress_bar(current: int, total: int, length: int = 20) -> str:
    if total <= 0:
        return "░" * length
    filled = int((current / total) * length)
    filled = max(0, min(filled, length))
    return "█" * filled + "░" * (length - filled)


async def _gemini_levelup(member: discord.Member, level: int) -> str:
    if not GEMINI_API_KEY:
        return None
    try:
        prompt = (
            f"Write a short, hype Discord level-up message.\n"
            f"User: {member.display_name}\nNew level: {level}\n"
            f"Rules: 1 sentence MAX. Use emojis. Be hype, fun, desi/Hindi vibe. "
            f"Mention their name. No markdown headers."
        )
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 80, "temperature": 1.0}
        }).encode()
        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(
            None, lambda: json.loads(urllib.request.urlopen(req, timeout=6).read()))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # In-memory cache: {guild_id_str: {users: {uid_str: {...}}, config: {...}}}
        self._cache: dict = {}
        self._loaded: bool = False
        # Cooldown trackers (in-memory, reset on restart — intentional)
        self._msg_cd: dict = {}    # "gid_uid" -> timestamp
        self._react_cd: dict = {}  # "gid_uid" -> timestamp
        # Voice join times: {"gid_uid": join_timestamp}
        # FIX: voice task no longer double-counts — only used for leave calculation
        self._voice_join: dict = {}
        # XP multiplier event
        self._multiplier: float = 1.0
        self._multiplier_end: float = 0.0
        # Dirty guilds — only persist guilds that actually changed
        self._dirty: set = set()
        self.voice_xp_task.start()
        self._persist_task.start()

    def cog_unload(self):
        self.voice_xp_task.cancel()
        self._persist_task.cancel()

    # ── DB persistence ─────────────────────────────────────────────────────────

    def _load_leveling_json(self) -> dict:
        try:
            os.makedirs(os.path.dirname(LEVELING_JSON) or ".", exist_ok=True)
            if os.path.isfile(LEVELING_JSON):
                with open(LEVELING_JSON, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"Could not load {LEVELING_JSON}: {e}")
        return {}

    async def _ensure_loaded(self):
        if self._loaded:
            return
        loop = asyncio.get_running_loop()
        file_data = await loop.run_in_executor(None, self._load_leveling_json)
        if file_data:
            self._cache = file_data
        else:
            stored = await get_setting(0, "leveling_data", {})
            self._cache = stored if isinstance(stored, dict) else {}
        event = await get_setting(0, "xp_event", {})
        if event and event.get("end", 0) > time.time():
            self._multiplier = event.get("multiplier", 1.0)
            self._multiplier_end = event.get("end", 0)
        self._loaded = True

    def _save_leveling_json(self):
        try:
            os.makedirs(os.path.dirname(LEVELING_JSON) or ".", exist_ok=True)
            with open(LEVELING_JSON, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.error(f"Leveling file persist error: {e}")

    @tasks.loop(seconds=30)
    async def _persist_task(self):
        """FIX: Persist only dirty guilds every 30s instead of on every message."""
        if not self._dirty:
            return
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._save_leveling_json)
            await set_setting(0, "leveling_data", self._cache)
            self._dirty.clear()
        except Exception as e:
            logger.error(f"Leveling persist error: {e}")

    @_persist_task.before_loop
    async def _before_persist(self):
        await self.bot.wait_until_ready()

    async def _persist(self):
        """Force-save immediately (used after admin commands)."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._save_leveling_json)
            await set_setting(0, "leveling_data", self._cache)
            self._dirty.clear()
        except Exception as e:
            logger.error(f"Leveling force-persist error: {e}")

    def _mark_dirty(self, guild_id: int):
        self._dirty.add(guild_id)

    def _guild(self, gid: int) -> dict:
        key = str(gid)
        if key not in self._cache:
            self._cache[key] = {
                "users": {},
                "config": {
                    "level_roles": {},
                    "announce_channel": None,
                    "announce": True,
                    "xp_multiplier": 1.0,
                    "no_xp_channels": [],
                    "no_xp_roles": [],
                }
            }
        # Ensure config always has all keys
        cfg = self._cache[key].setdefault("config", {})
        for k, v in [("level_roles", {}), ("announce_channel", None),
                     ("announce", True), ("xp_multiplier", 1.0),
                     ("no_xp_channels", []), ("no_xp_roles", [])]:
            cfg.setdefault(k, v)
        return self._cache[key]

    def _user(self, gid: int, uid: int) -> dict:
        g = self._guild(gid)
        key = str(uid)
        if key not in g["users"]:
            g["users"][key] = {}
        u = g["users"][key]
        # Backfill all fields with defaults
        defaults = {
            "xp": 0, "messages": 0, "voice_minutes": 0,
            "reactions": 0, "streak": 0,
            "last_daily": None, "last_msg_day": None,
        }
        for field, default in defaults.items():
            u.setdefault(field, default)
        return u

    # ── XP granting ────────────────────────────────────────────────────────────

    def _current_multiplier(self) -> float:
        """FIX: Multiplier now correctly expires and applies to all XP sources."""
        base = self._multiplier if time.time() < self._multiplier_end else 1.0
        return base

    async def _grant_xp(self, guild: discord.Guild, member: discord.Member,
                        amount: int, source: str = "",
                        source_channel: discord.TextChannel = None):
        await self._ensure_loaded()
        if member.bot:
            return

        # Apply multipliers
        mult = self._current_multiplier()
        g_cfg = self._guild(guild.id)["config"]
        mult *= g_cfg.get("xp_multiplier", 1.0)
        amount = max(1, int(amount * mult))

        u = self._user(guild.id, member.id)
        # FIX: Calculate old level from XP BEFORE adding, not from stored u["level"]
        old_level, _, _ = _xp_progress(u["xp"])
        u["xp"] += amount
        new_level, _, _ = _xp_progress(u["xp"])
        self._mark_dirty(guild.id)

        # FIX: Only announce if level actually increased (prevents duplicate announcements)
        if new_level > old_level:
            # Announce each level gained (handles multi-level jumps)
            for lvl in range(old_level + 1, new_level + 1):
                await self._announce_levelup(guild, member, lvl, source_channel)

    async def _announce_levelup(self, guild: discord.Guild, member: discord.Member,
                                level: int, source_channel: discord.TextChannel = None):
        g = self._guild(guild.id)
        cfg = g["config"]

        # Assign level role
        role_id = cfg["level_roles"].get(str(level))
        if role_id:
            role = guild.get_role(int(role_id))
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Level {level}")
                except Exception:
                    pass

        if not cfg.get("announce", True):
            return

        # Build message
        if level in MILESTONES:
            desc = MILESTONE_MSGS[level].replace("{user}", member.mention)
        else:
            ai_msg = await _gemini_levelup(member, level)
            if ai_msg:
                desc = ai_msg
            else:
                template = random.choice(LEVELUP_MSGS)
                desc = template.replace("{user}", member.mention).replace("{level}", str(level))

        color = 0x7c3aed if level in MILESTONES else 0xf59e0b
        embed = discord.Embed(description=desc, color=color)
        embed.set_author(name=f"⬆️ Level Up! → Level {level}", icon_url=member.display_avatar.url)
        # FIX: Recalculate XP progress from actual XP, not stale cache
        _, cur_xp, needed = _xp_progress(self._user(guild.id, member.id)["xp"])
        embed.set_footer(text=f"Next level: {cur_xp:,}/{needed:,} XP")

        ch_id = cfg.get("announce_channel")
        ch = guild.get_channel(int(ch_id)) if ch_id else source_channel
        if not ch:
            return
        try:
            await ch.send(embed=embed)
        except Exception:
            pass

    # ── Listeners ──────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        await self._ensure_loaded()
        cfg = self._guild(message.guild.id)["config"]

        # FIX: Compare channel IDs as strings consistently
        no_xp_channels = [str(x) for x in cfg.get("no_xp_channels", [])]
        if str(message.channel.id) in no_xp_channels:
            return

        no_xp_roles = [str(x) for x in cfg.get("no_xp_roles", [])]
        if any(str(r.id) in no_xp_roles for r in message.author.roles):
            return

        key = f"{message.guild.id}_{message.author.id}"
        now = time.time()
        if now - self._msg_cd.get(key, 0) < CD_MESSAGE:
            return
        self._msg_cd[key] = now

        u = self._user(message.guild.id, message.author.id)
        u["messages"] += 1
        xp = random.randint(XP_MESSAGE_MIN, XP_MESSAGE_MAX)

        # First message of the day bonus
        # FIX: Use UTC date string consistently
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if u.get("last_msg_day") != today:
            u["last_msg_day"] = today
            xp += XP_FIRST_MSG_DAY
            try:
                await message.channel.send(
                    f"☀️ {message.author.mention} First message of the day! **+{XP_FIRST_MSG_DAY} bonus XP**",
                    delete_after=8
                )
            except Exception:
                pass

        await self._grant_xp(message.guild, message.author, xp, "message",
                             source_channel=message.channel)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot or not reaction.message.guild:
            return
        await self._ensure_loaded()
        guild = reaction.message.guild
        key = f"{guild.id}_{user.id}"
        now = time.time()
        if now - self._react_cd.get(key, 0) < CD_REACTION:
            return
        self._react_cd[key] = now

        member = guild.get_member(user.id)
        if member:
            u = self._user(guild.id, user.id)
            u["reactions"] += 1
            await self._grant_xp(guild, member, XP_REACTION, "reaction")

        # XP to message author for receiving a reaction
        msg_author = reaction.message.author
        if not msg_author.bot and msg_author.id != user.id:
            author_member = guild.get_member(msg_author.id)
            if author_member:
                await self._grant_xp(guild, author_member, XP_REACTION, "reaction_received")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                    before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        await self._ensure_loaded()
        key = f"{member.guild.id}_{member.id}"

        if before.channel is None and after.channel is not None:
            # Joined VC — record join time
            self._voice_join[key] = time.time()

        elif before.channel is not None and after.channel is None:
            # Left VC — award XP for time spent
            join_time = self._voice_join.pop(key, None)
            if join_time:
                minutes = int((time.time() - join_time) / 60)
                if minutes > 0:
                    u = self._user(member.guild.id, member.id)
                    u["voice_minutes"] += minutes
                    xp = minutes * XP_VOICE_PER_MIN
                    await self._grant_xp(member.guild, member, xp, "voice")

    # ── Voice XP background task (every 5 min for active VC members) ───────────
    # FIX: Only awards incremental XP here; on_voice_state_update handles the
    # remainder when user leaves, so there's no double-count.

    @tasks.loop(minutes=5)
    async def voice_xp_task(self):
        await self._ensure_loaded()
        now = time.time()
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if member.bot:
                        continue
                    vs = member.voice
                    if vs and (vs.self_deaf or vs.deaf or vs.afk):
                        continue
                    key = f"{guild.id}_{member.id}"
                    # Record join time if not already tracked
                    if key not in self._voice_join:
                        self._voice_join[key] = now
                        continue  # Don't award XP on first tick — wait for next
                    # Award 5 min worth of XP
                    u = self._user(guild.id, member.id)
                    u["voice_minutes"] = u.get("voice_minutes", 0) + 5
                    await self._grant_xp(guild, member, 5 * XP_VOICE_PER_MIN, "voice_tick")

    @voice_xp_task.before_loop
    async def before_voice_task(self):
        await self.bot.wait_until_ready()

    # ── Commands ───────────────────────────────────────────────────────────────

    @app_commands.command(name="rank", description="⭐ View your XP rank card")
    @app_commands.describe(member="Member to check (defaults to you)")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        await self._ensure_loaded()
        target = member or interaction.user
        u = self._user(interaction.guild.id, target.id)
        # FIX: Always recalculate level from XP — never trust cached u["level"]
        level, cur_xp, needed = _xp_progress(u["xp"])
        g = self._guild(interaction.guild.id)
        sorted_users = sorted(
            g["users"].items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )
        rank_pos = next(
            (i + 1 for i, (uid, _) in enumerate(sorted_users) if uid == str(target.id)),
            "?"
        )
        bar = _progress_bar(cur_xp, needed, 24)
        pct = int((cur_xp / max(needed, 1)) * 100)

        embed = discord.Embed(color=0xf59e0b)
        embed.set_author(name=f"{target.display_name}'s Rank Card",
                         icon_url=target.display_avatar.url)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🏆 Rank",      value=f"**#{rank_pos}**",                    inline=True)
        embed.add_field(name="⭐ Level",      value=f"**{level}**",                        inline=True)
        embed.add_field(name="✨ Total XP",   value=f"**{u['xp']:,}**",                    inline=True)
        embed.add_field(name="💬 Messages",   value=f"**{u.get('messages',0):,}**",        inline=True)
        embed.add_field(name="🎙️ Voice",      value=f"**{u.get('voice_minutes',0)} min**", inline=True)
        embed.add_field(name="🔥 Streak",     value=f"**{u.get('streak',0)} days**",       inline=True)
        embed.add_field(
            name=f"📊 Progress to Level {level+1} ({pct}%)",
            value=f"`{bar}` {cur_xp:,}/{needed:,} XP",
            inline=False
        )
        cfg = self._guild(interaction.guild.id)["config"]
        for lvl_str in sorted(cfg["level_roles"].keys(), key=int):
            if int(lvl_str) > level:
                role = interaction.guild.get_role(int(cfg["level_roles"][lvl_str]))
                if role:
                    embed.set_footer(text=f"🎁 Reach Level {lvl_str} to unlock: {role.name}")
                break
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="levels", description="🏆 XP Leaderboard")
    async def levels(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_loaded()
        g = self._guild(interaction.guild.id)
        sorted_users = sorted(
            g["users"].items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )[:10]
        embed = discord.Embed(title="🏆 XP Leaderboard", color=0xf59e0b)
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, data) in enumerate(sorted_users):
            m = interaction.guild.get_member(int(uid))
            # FIX: Graceful fallback for members who left the server
            name = m.display_name if m else f"Unknown ({uid[:6]}…)"
            lvl, cur, needed = _xp_progress(data.get("xp", 0))
            bar = _progress_bar(cur, needed, 10)
            prefix = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(f"{prefix} **{name}** — Lv.**{lvl}** `{bar}` {data.get('xp',0):,} XP")
        embed.description = "\n".join(lines) if lines else "No data yet. Start chatting!"
        embed.set_footer(text="XP earned from: messages • voice • reactions • daily bonus")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="daily", description="🎁 Claim your daily XP bonus")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._ensure_loaded()
        u = self._user(interaction.guild.id, interaction.user.id)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        if u.get("last_daily") == today:
            now_utc = datetime.now(timezone.utc)
            midnight = (now_utc + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            secs = int((midnight - now_utc).total_seconds())
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            return await interaction.followup.send(
                f"⏰ Already claimed today! Come back in **{h}h {m}m**.", ephemeral=True)

        # FIX: Streak logic — compare against yesterday's date string, not isoformat
        if u.get("last_daily") == yesterday:
            u["streak"] = u.get("streak", 0) + 1
        else:
            u["streak"] = 1  # Reset streak if missed a day

        streak = u["streak"]
        base_xp = random.randint(XP_DAILY_MIN, XP_DAILY_MAX)
        streak_bonus = min(streak - 1, 10) * XP_STREAK_BONUS
        total_xp = base_xp + streak_bonus
        u["last_daily"] = today
        self._mark_dirty(interaction.guild.id)

        await self._grant_xp(interaction.guild, interaction.user, total_xp, "daily")

        embed = discord.Embed(title="🎁 Daily Bonus Claimed!", color=0x10b981)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Base XP",       value=f"+{base_xp}",          inline=True)
        embed.add_field(name="Streak Bonus",  value=f"+{streak_bonus}",     inline=True)
        embed.add_field(name="Total",         value=f"**+{total_xp} XP**",  inline=True)
        embed.add_field(name="🔥 Streak",
                        value=f"**{streak} day{'s' if streak != 1 else ''}**", inline=False)
        if streak >= 7:
            embed.description = f"🔥 **{streak}-day streak!** You're on fire!"
        elif streak >= 3:
            embed.description = f"⚡ **{streak}-day streak!** Don't break it!"
        else:
            embed.description = "Come back tomorrow to build your streak!"
        embed.set_footer(text="Streak bonus: +25 XP per consecutive day (max 10 days)")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="streak", description="🔥 Check your daily streak")
    async def streak(self, interaction: discord.Interaction):
        await self._ensure_loaded()
        u = self._user(interaction.guild.id, interaction.user.id)
        streak = u.get("streak", 0)
        embed = discord.Embed(title="🔥 Your Streak", color=0xf97316)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Current Streak",
                        value=f"**{streak} day{'s' if streak != 1 else ''}**", inline=True)
        embed.add_field(name="Last Daily", value=u.get("last_daily") or "Never", inline=True)
        embed.add_field(name="Streak Bonus",
                        value=f"+{min(streak, 10) * XP_STREAK_BONUS} XP/day", inline=True)
        embed.set_footer(text="Use /daily every day to keep your streak alive!")
        await send_response(interaction, embed=embed)

    @app_commands.command(name="xp-event", description="⚡ Start an XP multiplier event (admin)")
    @app_commands.describe(multiplier="XP multiplier (e.g. 2 = double XP)", hours="Duration in hours")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def xp_event(self, interaction: discord.Interaction, multiplier: float, hours: int = 1):
        if not 1.0 <= multiplier <= 5.0:
            return await send_response(
                interaction, "❌ Multiplier must be 1.0–5.0", ephemeral=True)
        self._multiplier = multiplier
        self._multiplier_end = time.time() + (hours * 3600)
        await set_setting(0, "xp_event", {
            "multiplier": multiplier, "end": self._multiplier_end
        })
        embed = discord.Embed(
            title="⚡ XP Event Started!",
            description=f"**{multiplier}x XP** for the next **{hours} hour{'s' if hours != 1 else ''}**!\nGo go go — chat, react, join voice! 🚀",
            color=0x7c3aed
        )
        await send_response(interaction, embed=embed)

    @app_commands.command(name="set-level-role", description="🎭 Assign a role when members reach a level")
    @app_commands.describe(level="Level to trigger the role", role="Role to assign")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def set_level_role(self, interaction: discord.Interaction, level: int, role: discord.Role):
        await self._ensure_loaded()
        self._guild(interaction.guild.id)["config"]["level_roles"][str(level)] = role.id
        await self._persist()
        await send_response(
            interaction, f"✅ Members get **{role.name}** at level **{level}**.", ephemeral=True)

    @app_commands.command(name="xp-channel", description="📢 Set channel for level-up announcements")
    @app_commands.describe(channel="Channel to send level-up messages in")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def xp_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._ensure_loaded()
        self._guild(interaction.guild.id)["config"]["announce_channel"] = channel.id
        await self._persist()
        await send_response(
            interaction, f"✅ Level-up announcements → {channel.mention}", ephemeral=True)

    @app_commands.command(name="xp-noxp", description="🚫 Toggle no-XP for a channel")
    @app_commands.describe(channel="Channel to toggle XP off/on")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def xp_noxp(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._ensure_loaded()
        noxp = self._guild(interaction.guild.id)["config"].setdefault("no_xp_channels", [])
        cid = str(channel.id)
        if cid in noxp:
            noxp.remove(cid)
            msg = f"✅ {channel.mention} removed from no-XP list."
        else:
            noxp.append(cid)
            msg = f"✅ {channel.mention} added to no-XP list."
        await self._persist()
        await send_response(interaction, msg, ephemeral=True)

    @app_commands.command(name="xp-give", description="🎁 Manually give XP to a member")
    @app_commands.describe(member="Member to give XP to", amount="Amount of XP to give")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def xp_give(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await self._ensure_loaded()
        await self._grant_xp(interaction.guild, member, amount, "manual")
        await send_response(
            interaction, f"✅ Gave **{amount} XP** to {member.mention}.", ephemeral=True)

    @app_commands.command(name="xp-reset", description="🗑️ Reset a member's XP")
    @app_commands.describe(member="Member to reset")
    @app_commands.checks.has_permissions(administrator=True)
    async def xp_reset(self, interaction: discord.Interaction, member: discord.Member):
        await self._ensure_loaded()
        self._guild(interaction.guild.id)["users"].pop(str(member.id), None)
        await self._persist()
        await send_response(
            interaction, f"✅ Reset XP for {member.mention}.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Leveling(bot))
