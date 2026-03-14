"""
WAN Bot - Real Activity Leaderboard
Tracks actual Discord activity: messages, voice time, reactions
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
from typing import Optional
import json, os

DATA_FILE = "leaderboard_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_data()   # {guild_id: {user_id: {messages, voice_seconds, reactions}}}
        self.voice_join_times = {}  # {(guild_id, user_id): datetime}
        self.save_task.start()

    def cog_unload(self):
        self.save_task.cancel()
        save_data(self.data)

    def _guild(self, guild_id: int) -> dict:
        gid = str(guild_id)
        if gid not in self.data:
            self.data[gid] = {}
        return self.data[gid]

    def _user(self, guild_id: int, user_id: int) -> dict:
        g = self._guild(guild_id)
        uid = str(user_id)
        if uid not in g:
            g[uid] = {"messages": 0, "voice_seconds": 0, "reactions": 0}
        return g[uid]

    # ── Event listeners ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        self._user(message.guild.id, message.author.id)["messages"] += 1

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot or not reaction.message.guild:
            return
        self._user(reaction.message.guild.id, user.id)["reactions"] += 1

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        key = (member.guild.id, member.id)
        if not before.channel and after.channel:
            # Joined voice
            self.voice_join_times[key] = datetime.now(timezone.utc)
        elif before.channel and not after.channel:
            # Left voice
            if key in self.voice_join_times:
                elapsed = (datetime.now(timezone.utc) - self.voice_join_times.pop(key)).total_seconds()
                self._user(member.guild.id, member.id)["voice_seconds"] += int(elapsed)

    # ── Auto-save every 5 min ────────────────────────────────────────────────

    @tasks.loop(minutes=5)
    async def save_task(self):
        save_data(self.data)

    @save_task.before_loop
    async def before_save(self):
        await self.bot.wait_until_ready()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def get_sorted(self, guild_id: int, key: str, top: int = 15):
        g = self._guild(guild_id)
        entries = []
        for uid, stats in g.items():
            entries.append((int(uid), stats.get(key, 0)))
        entries.sort(key=lambda x: x[1], reverse=True)
        return entries[:top]

    def fmt_voice(self, seconds: int) -> str:
        h, m = divmod(seconds // 60, 60)
        return f"{h}h {m}m" if h else f"{m}m"

    # ── Commands ─────────────────────────────────────────────────────────────

    @app_commands.command(name="leaderboard", description="🏆 Real server activity leaderboard")
    @app_commands.describe(category="messages | voice | reactions | score")
    async def leaderboard(self, interaction: discord.Interaction, category: str = "score"):
        await interaction.response.defer()

        valid = {"messages", "voice", "reactions", "score"}
        if category not in valid:
            await interaction.followup.send(f"Category must be one of: {', '.join(valid)}", ephemeral=True)
            return

        guild = interaction.guild
        medals = ["🥇", "🥈", "🥉"]

        if category == "score":
            # Combined score: messages*1 + voice_minutes*2 + reactions*0.5
            g = self._guild(guild.id)
            entries = []
            for uid, stats in g.items():
                score = stats.get("messages", 0) + (stats.get("voice_seconds", 0) // 60) * 2 + int(stats.get("reactions", 0) * 0.5)
                entries.append((int(uid), score))
            entries.sort(key=lambda x: x[1], reverse=True)
            entries = entries[:15]

            embed = discord.Embed(title="🏆 Activity Score Leaderboard", color=discord.Color.gold(), timestamp=datetime.utcnow())
            lines = []
            for i, (uid, score) in enumerate(entries):
                member = guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
                prefix = medals[i] if i < 3 else f"**{i+1}.**"
                lines.append(f"{prefix} {name} — **{score:,} pts**")
            embed.description = "\n".join(lines) or "No activity yet. Start chatting!"

        elif category == "messages":
            entries = self.get_sorted(guild.id, "messages")
            embed = discord.Embed(title="💬 Messages Leaderboard", color=discord.Color.blue(), timestamp=datetime.utcnow())
            lines = []
            for i, (uid, val) in enumerate(entries):
                member = guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
                prefix = medals[i] if i < 3 else f"**{i+1}.**"
                lines.append(f"{prefix} {name} — **{val:,} messages**")
            embed.description = "\n".join(lines) or "No messages tracked yet."

        elif category == "voice":
            entries = self.get_sorted(guild.id, "voice_seconds")
            embed = discord.Embed(title="🎙️ Voice Time Leaderboard", color=discord.Color.green(), timestamp=datetime.utcnow())
            lines = []
            for i, (uid, val) in enumerate(entries):
                member = guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
                prefix = medals[i] if i < 3 else f"**{i+1}.**"
                lines.append(f"{prefix} {name} — **{self.fmt_voice(val)}**")
            embed.description = "\n".join(lines) or "No voice activity tracked yet."

        elif category == "reactions":
            entries = self.get_sorted(guild.id, "reactions")
            embed = discord.Embed(title="😄 Reactions Leaderboard", color=discord.Color.orange(), timestamp=datetime.utcnow())
            lines = []
            for i, (uid, val) in enumerate(entries):
                member = guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
                prefix = medals[i] if i < 3 else f"**{i+1}.**"
                lines.append(f"{prefix} {name} — **{val:,} reactions**")
            embed.description = "\n".join(lines) or "No reactions tracked yet."

        embed.set_footer(text=f"Tracking since bot joined • {guild.name}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="rank", description="📊 View your activity rank")
    async def rank(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        stats = self._user(interaction.guild.id, target.id)

        score = stats["messages"] + (stats["voice_seconds"] // 60) * 2 + int(stats["reactions"] * 0.5)

        # Calculate rank
        g = self._guild(interaction.guild.id)
        all_scores = sorted(
            [(int(uid), s.get("messages", 0) + (s.get("voice_seconds", 0) // 60) * 2 + int(s.get("reactions", 0) * 0.5))
             for uid, s in g.items()],
            key=lambda x: x[1], reverse=True
        )
        rank = next((i + 1 for i, (uid, _) in enumerate(all_scores) if uid == target.id), len(all_scores))

        embed = discord.Embed(
            title=f"📊 Activity Rank — {target.display_name}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🏆 Rank", value=f"**#{rank}** of {len(all_scores)}", inline=True)
        embed.add_field(name="⭐ Score", value=f"**{score:,} pts**", inline=True)
        embed.add_field(name="💬 Messages", value=f"{stats['messages']:,}", inline=True)
        embed.add_field(name="🎙️ Voice Time", value=self.fmt_voice(stats["voice_seconds"]), inline=True)
        embed.add_field(name="😄 Reactions", value=f"{stats['reactions']:,}", inline=True)
        await interaction.followup.send(embed=embed) if interaction.response.is_done() else await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
