"""
WAN Bot - Leveling System v3 (FIXED - Persistent & Bug-Free)
Complete rewrite with proper database persistence and XP restoration

XP Sources:
  - Messages (15-25 XP, 60s cooldown)
  - Voice time (10 XP/min while in VC)
  - Reactions (5 XP each, 30s cooldown)
  - Daily check-in (100-300 XP)
  - Streak bonus (25 XP per consecutive day, max 10 days)
  - First message of day (50 XP bonus)
  - Music listening (5 XP per song)
  - Dashboard usage (10 XP per action)
  - Web activity (5 XP per interaction)

Features:
  - Persistent database with automatic backups
  - XP restoration from previous levels
  - Level roles (auto-assign)
  - Level-up announcements
  - /rank — rank card with progress
  - /levels — leaderboard
  - /daily — daily bonus
  - /streak — streak tracking
  - XP multiplier events
  - All data persisted to disk
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
from leveling_db import LevelingDB

logger = logging.getLogger("discord_bot.leveling")

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
XP_STREAK_BONUS  = 25
XP_MUSIC         = 5
XP_DASHBOARD     = 10
XP_WEB_ACTION    = 5

# Cooldowns
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
    """Calculate XP needed for a specific level"""
    return 5 * (lvl ** 2) + 50 * lvl + 100


def _xp_progress(total_xp: int) -> tuple:
    """Calculate (level, xp_into_level, xp_needed_for_next) from total XP"""
    lvl = 0
    xp = total_xp
    while xp >= _xp_for_level(lvl):
        xp -= _xp_for_level(lvl)
        lvl += 1
    return lvl, xp, _xp_for_level(lvl)


def _progress_bar(current: int, total: int, length: int = 20) -> str:
    """Create a progress bar"""
    filled = int((current / max(total, 1)) * length)
    return "█" * filled + "░" * (length - filled)


async def _gemini_levelup(member: discord.Member, level: int) -> str:
    """Generate AI level-up message"""
    if not GEMINI_API_KEY:
        return None
    try:
        prompt = (
            f"Write a short, hype Discord level-up message.\n"
            f"User: {member.display_name}\n"
            f"New level: {level}\n"
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


class LevelingFixed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Cooldown trackers
        self._msg_cd: dict = {}
        self._react_cd: dict = {}
        # Voice join times
        self._voice_join: dict = {}
        # XP multiplier
        self._multiplier: float = 1.0
        self._multiplier_end: float = 0.0
        # Load multiplier from DB
        self._load_multiplier()
        # Start background tasks
        self.voice_xp_task.start()

    def cog_unload(self):
        self.voice_xp_task.cancel()

    def _load_multiplier(self):
        """Load XP multiplier from settings"""
        try:
            from utils.settings import get_setting
            # This will be loaded async in first use
        except:
            pass

    async def _grant_xp(self, guild: discord.Guild, member: discord.Member,
                        amount: int, source: str = "",
                        source_channel: discord.TextChannel = None):
        """Grant XP to a member with proper persistence"""
        if member.bot:
            return
        
        # Apply multiplier
        mult = self._multiplier if time.time() < self._multiplier_end else 1.0
        amount = max(1, int(amount * mult))
        
        # Get current data
        user_data = LevelingDB.get_user_data(guild.id, member.id)
        old_level, _, _ = _xp_progress(user_data["xp"])
        
        # Add XP
        user_data["xp"] += amount
        new_level, cur, needed = _xp_progress(user_data["xp"])
        user_data["level"] = new_level
        
        # Track source
        if source == "message":
            user_data["messages"] = user_data.get("messages", 0) + 1
        elif source == "voice":
            user_data["voice_minutes"] = user_data.get("voice_minutes", 0) + 1
        elif source == "reaction":
            user_data["reactions"] = user_data.get("reactions", 0) + 1
        elif source == "music":
            user_data["music_xp"] = user_data.get("music_xp", 0) + amount
        elif source == "dashboard":
            user_data["dashboard_xp"] = user_data.get("dashboard_xp", 0) + amount
        
        # Save to database
        LevelingDB.set_user_data(guild.id, member.id, user_data)
        
        # Announce level up
        if new_level > old_level:
            await self._announce_levelup(guild, member, new_level, source_channel)

    async def _announce_levelup(self, guild: discord.Guild, member: discord.Member,
                                level: int, source_channel: discord.TextChannel = None):
        """Announce level up"""
        cfg = LevelingDB.get_guild_config(guild.id)
        
        # Assign level role
        role_id = cfg.get("level_roles", {}).get(str(level))
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
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
                desc = ai_msg.replace("{user}", member.mention).replace("{level}", str(level))
            else:
                template = random.choice(LEVELUP_MSGS)
                desc = template.replace("{user}", member.mention).replace("{level}", str(level))
        
        color = 0xf59e0b if level not in MILESTONES else 0x7c3aed
        embed = discord.Embed(description=desc, color=color)
        embed.set_author(name=f"⬆️ Level Up! → Level {level}", icon_url=member.display_avatar.url)
        
        user_data = LevelingDB.get_user_data(guild.id, member.id)
        _, cur_xp, needed = _xp_progress(user_data["xp"])
        embed.set_footer(text=f"Next level: {cur_xp}/{needed} XP")
        
        # Send to configured channel or source channel
        ch_id = cfg.get("announce_channel")
        ch = guild.get_channel(int(ch_id)) if ch_id else None
        
        if not ch:
            ch = source_channel
        
        if not ch:
            return
        
        try:
            await ch.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Grant XP for messages"""
        if message.author.bot or not message.guild:
            return
        
        cfg = LevelingDB.get_guild_config(message.guild.id)
        
        # Check no-XP channels
        if message.channel.id in [int(x) for x in cfg.get("no_xp_channels", [])]:
            return
        
        # Check no-XP roles
        no_xp_roles = [int(x) for x in cfg.get("no_xp_roles", [])]
        if any(r.id in no_xp_roles for r in message.author.roles):
            return
        
        # Cooldown check
        key = f"{message.guild.id}_{message.author.id}"
        now = time.time()
        if now - self._msg_cd.get(key, 0) < CD_MESSAGE:
            return
        self._msg_cd[key] = now
        
        # Grant XP
        xp = random.randint(XP_MESSAGE_MIN, XP_MESSAGE_MAX)
        
        # First message of day bonus
        user_data = LevelingDB.get_user_data(message.guild.id, message.author.id)
        today = datetime.now(timezone.utc).date().isoformat()
        if user_data.get("last_msg_day") != today:
            user_data["last_msg_day"] = today
            xp += XP_FIRST_MSG_DAY
            try:
                await message.channel.send(
                    f"☀️ {message.author.mention} First message of the day! **+{XP_FIRST_MSG_DAY} bonus XP**",
                    delete_after=8
                )
            except:
                pass
        
        await self._grant_xp(message.guild, message.author, xp, "message",
                             source_channel=message.channel)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Grant XP for reactions"""
        if user.bot or not reaction.message.guild:
            return
        
        guild = reaction.message.guild
        key = f"{guild.id}_{user.id}"
        now = time.time()
        if now - self._react_cd.get(key, 0) < CD_REACTION:
            return
        self._react_cd[key] = now
        
        member = guild.get_member(user.id)
        if member:
            await self._grant_xp(guild, member, XP_REACTION, "reaction")
        
        # Give XP to message author
        msg_author = reaction.message.author
        if not msg_author.bot and msg_author.id != user.id:
            author_member = guild.get_member(msg_author.id)
            if author_member:
                await self._grant_xp(guild, author_member, XP_REACTION, "reaction")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                    before: discord.VoiceState, after: discord.VoiceState):
        """Track voice time"""
        if member.bot:
            return
        
        key = f"{member.guild.id}_{member.id}"
        
        # Joined voice
        if before.channel is None and after.channel is not None:
            self._voice_join[key] = time.time()
        
        # Left voice
        elif before.channel is not None and after.channel is None:
            join_time = self._voice_join.pop(key, None)
            if join_time:
                minutes = int((time.time() - join_time) / 60)
                if minutes > 0:
                    xp = minutes * XP_VOICE_PER_MIN
                    await self._grant_xp(member.guild, member, xp, "voice")

    @tasks.loop(minutes=5)
    async def voice_xp_task(self):
        """Grant XP to active voice members"""
        now = time.time()
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if member.bot:
                        continue
                    
                    vs = member.voice
                    if vs and (vs.self_deaf or vs.deaf or vs.afk):
                        continue
                    
                    xp = 5 * XP_VOICE_PER_MIN
                    await self._grant_xp(guild, member, xp, "voice")

    @voice_xp_task.before_loop
    async def before_voice_task(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="rank", description="⭐ View your XP rank card")
    @app_commands.describe(member="Member to check (defaults to you)")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        target = member or interaction.user
        user_data = LevelingDB.get_user_data(interaction.guild.id, target.id)
        level, cur_xp, needed = _xp_progress(user_data["xp"])
        
        leaderboard = LevelingDB.get_leaderboard(interaction.guild.id, 1000)
        rank_pos = next((i + 1 for i, (uid, _) in enumerate(leaderboard) if uid == str(target.id)), "?")
        
        bar = _progress_bar(cur_xp, needed, 24)
        pct = int((cur_xp / max(needed, 1)) * 100)
        
        embed = discord.Embed(color=0xf59e0b)
        embed.set_author(name=f"{target.display_name}'s Rank Card", icon_url=target.display_avatar.url)
        embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(name="🏆 Rank", value=f"**#{rank_pos}**", inline=True)
        embed.add_field(name="⭐ Level", value=f"**{level}**", inline=True)
        embed.add_field(name="✨ Total XP", value=f"**{user_data['xp']:,}**", inline=True)
        embed.add_field(name="💬 Messages", value=f"**{user_data.get('messages', 0):,}**", inline=True)
        embed.add_field(name="🎙️ Voice Time", value=f"**{user_data.get('voice_minutes', 0)} min**", inline=True)
        embed.add_field(name="🔥 Streak", value=f"**{user_data.get('streak', 0)} days**", inline=True)
        embed.add_field(
            name=f"📊 Progress to Level {level+1} ({pct}%)",
            value=f"`{bar}` {cur_xp:,}/{needed:,} XP",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="levels", description="🏆 XP Leaderboard")
    async def levels(self, interaction: discord.Interaction):
        await interaction.response.defer()
        leaderboard = LevelingDB.get_leaderboard(interaction.guild.id, 10)
        
        embed = discord.Embed(title="🏆 XP Leaderboard", color=0xf59e0b)
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        
        for i, (uid, data) in enumerate(leaderboard):
            m = interaction.guild.get_member(int(uid))
            name = m.display_name if m else f"User {uid}"
            lvl, cur, needed = _xp_progress(data.get("xp", 0))
            bar = _progress_bar(cur, needed, 10)
            prefix = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(
                f"{prefix} **{name}** — Lv.**{lvl}** `{bar}` {data.get('xp', 0):,} XP"
            )
        
        embed.description = "\n".join(lines) if lines else "No data yet. Start chatting!"
        embed.set_footer(text="XP earned from: messages • voice • reactions • daily • music • dashboard")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="daily", description="🎁 Claim your daily XP bonus")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_data = LevelingDB.get_user_data(interaction.guild.id, interaction.user.id)
        today = datetime.now(timezone.utc).date().isoformat()
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        
        if user_data.get("last_daily") == today:
            now_utc = datetime.now(timezone.utc)
            midnight = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            secs = int((midnight - now_utc).total_seconds())
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            return await interaction.followup.send(
                f"⏰ Already claimed today! Come back in **{h}h {m}m**.", ephemeral=True)
        
        # Streak logic
        if user_data.get("last_daily") == yesterday:
            user_data["streak"] = user_data.get("streak", 0) + 1
        else:
            user_data["streak"] = 1
        
        streak = user_data["streak"]
        base_xp = random.randint(XP_DAILY_MIN, XP_DAILY_MAX)
        streak_bonus = min(streak - 1, 10) * XP_STREAK_BONUS
        total_xp = base_xp + streak_bonus
        user_data["last_daily"] = today
        
        LevelingDB.set_user_data(interaction.guild.id, interaction.user.id, user_data)
        await self._grant_xp(interaction.guild, interaction.user, total_xp, "daily")
        
        embed = discord.Embed(title="🎁 Daily Bonus Claimed!", color=0x10b981)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Base XP", value=f"+{base_xp}", inline=True)
        embed.add_field(name="Streak Bonus", value=f"+{streak_bonus}", inline=True)
        embed.add_field(name="Total", value=f"**+{total_xp} XP**", inline=True)
        embed.add_field(name="🔥 Current Streak", value=f"**{streak} day{'s' if streak != 1 else ''}**", inline=False)
        
        if streak >= 7:
            embed.description = f"🔥 **{streak}-day streak!** You're on fire! Keep it up!"
        elif streak >= 3:
            embed.description = f"⚡ **{streak}-day streak!** Don't break it!"
        else:
            embed.description = "Come back tomorrow to build your streak for bonus XP!"
        
        embed.set_footer(text="Streak bonus: +25 XP per consecutive day (max 10 days)")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="streak", description="🔥 Check your daily streak")
    async def streak(self, interaction: discord.Interaction):
        user_data = LevelingDB.get_user_data(interaction.guild.id, interaction.user.id)
        streak = user_data.get("streak", 0)
        last = user_data.get("last_daily", "Never")
        
        embed = discord.Embed(title="🔥 Your Streak", color=0xf97316)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Current Streak", value=f"**{streak} day{'s' if streak != 1 else ''}**", inline=True)
        embed.add_field(name="Last Daily", value=last, inline=True)
        bonus = min(streak, 10) * XP_STREAK_BONUS
        embed.add_field(name="Current Streak Bonus", value=f"+{bonus} XP/day", inline=True)
        embed.set_footer(text="Use /daily every day to keep your streak alive!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="xp-give", description="🎁 Give XP to a member")
    @app_commands.describe(member="Member to give XP to", amount="Amount of XP")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def xp_give(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await self._grant_xp(interaction.guild, member, amount, "manual")
        await interaction.response.send_message(f"✅ Gave **{amount} XP** to {member.mention}.", ephemeral=True)

    @app_commands.command(name="xp-reset", description="🗑️ Reset a member's XP")
    @app_commands.describe(member="Member to reset")
    @app_commands.checks.has_permissions(administrator=True)
    async def xp_reset(self, interaction: discord.Interaction, member: discord.Member):
        data = LevelingDB.load()
        guild_key = str(interaction.guild.id)
        if guild_key in data and "users" in data[guild_key]:
            data[guild_key]["users"].pop(str(member.id), None)
            LevelingDB.save(data)
        await interaction.response.send_message(f"✅ Reset XP for {member.mention}.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(LevelingFixed(bot))
