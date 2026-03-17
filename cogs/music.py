"""
WAN Bot — Music Cog (v2)
========================
Production-ready music system built from scratch.

Commands:
  /play       — play a song (URL or search query)
  /pause      — pause playback
  /resume     — resume playback
  /skip       — skip current track
  /stop       — stop and clear queue
  /queue      — display queue
  /nowplaying — show current track
  /loop       — cycle loop mode (off → track → queue)
  /volume     — set volume 0–100
  /shuffle    — shuffle the queue
  /remove     — remove a track from the queue by position
  /autoplay   — toggle smart autoplay
  /leave      — disconnect bot from voice

Architecture:
  - PlayerManager  (utils/music_player.py)  — per-guild voice + queue state
  - AutoplayEngine (utils/music_autoplay.py) — intelligent recommendation
"""

import asyncio
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.music_player import PlayerManager, TrackExtractor, LoopMode

logger = logging.getLogger("discord_bot.music")

# ── Embed helpers ─────────────────────────────────────────────────────────────

_COLOR_PLAY  = 0x10B981   # green
_COLOR_QUEUE = 0x7C3AED   # purple
_COLOR_INFO  = 0x3B82F6   # blue
_COLOR_WARN  = 0xF59E0B   # amber
_COLOR_ERR   = 0xEF4444   # red


def _embed(title: str, desc: str = "", color: int = _COLOR_INFO) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color)


def _track_embed(track, label: str = "▶ Now Playing", color: int = _COLOR_PLAY) -> discord.Embed:
    e = discord.Embed(
        title=label,
        description=f"**{track.title}**",
        color=color,
    )
    if track.thumbnail:
        e.set_thumbnail(url=track.thumbnail)
    e.add_field(name="Duration", value=track.duration_str, inline=True)
    e.add_field(name="Channel", value=track.channel or "Unknown", inline=True)
    if track.requester:
        e.set_footer(text=f"Requested by {track.requester.display_name}")
    return e


# ── Cog ───────────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    """Smart music system with queue, loop, volume, and context-aware autoplay."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.manager = PlayerManager(bot)
        self._watchdog.start()

    def cog_unload(self):
        self._watchdog.cancel()

    # ── Watchdog: 24/7 reconnect ──────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _watchdog(self):
        """
        Every 30 s, check all active players.
        If the voice client dropped but we still have a queue/autoplay,
        attempt to reconnect to the last known channel.
        """
        for guild_id, player in list(self.manager._players.items()):
            vc = player.vc
            if vc is None or not vc.is_connected():
                # Only reconnect if autoplay is on or queue has tracks
                if player.autoplay or not player.queue.is_empty:
                    # Find the last channel the bot was in
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    # Try to find a populated voice channel
                    target = None
                    for ch in guild.voice_channels:
                        if any(not m.bot for m in ch.members):
                            target = ch
                            break
                    if target:
                        try:
                            await player.connect(target)
                            logger.info(
                                f"[Watchdog] Reconnected to {target.name} "
                                f"in {guild.name}"
                            )
                            # Resume playback if there's a current track
                            if player.queue.current and not player.is_playing:
                                player._play_track(player.queue.current)
                        except Exception as e:
                            logger.warning(f"[Watchdog] Reconnect failed: {e}")

    @_watchdog.before_loop
    async def _before_watchdog(self):
        await self.bot.wait_until_ready()

    # ── Guard helpers ─────────────────────────────────────────────────────

    async def _ensure_voice(
        self, interaction: discord.Interaction
    ) -> Optional[discord.VoiceClient]:
        """Connect to user's voice channel. Returns vc or None (and replies)."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send(
                embed=_embed("❌ Not in Voice", "Join a voice channel first.", _COLOR_ERR),
                ephemeral=True,
            )
            return None
        player = self.manager.get(interaction.guild)
        try:
            vc = await player.connect(interaction.user.voice.channel)
            return vc
        except Exception as e:
            await interaction.followup.send(
                embed=_embed("❌ Connection Failed", str(e), _COLOR_ERR),
                ephemeral=True,
            )
            return None

    # ── /play ─────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a song — paste a YouTube URL or type a search query")
    @app_commands.describe(query="YouTube URL or search terms")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        try:
            track = await TrackExtractor.extract(query, self.bot.loop)
        except Exception as e:
            logger.error(f"[play] Extraction failed: {e}")
            await interaction.followup.send(
                embed=_embed("❌ Extraction Failed", str(e), _COLOR_ERR),
                ephemeral=True,
            )
            return

        track.requester = interaction.user
        player = self.manager.get(interaction.guild)
        pos = await player.play_track(track)

        if pos == 0:
            await interaction.followup.send(embed=_track_embed(track))
        else:
            e = _track_embed(track, label="📋 Added to Queue", color=_COLOR_QUEUE)
            e.add_field(name="Position", value=f"#{pos}", inline=True)
            await interaction.followup.send(embed=e)

    # ── /pause ────────────────────────────────────────────────────────────

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        player = self.manager.get(interaction.guild)
        if player.pause():
            await interaction.response.send_message(
                embed=_embed("⏸ Paused", "", _COLOR_INFO)
            )
        else:
            await interaction.response.send_message(
                embed=_embed("❌ Not Playing", "Nothing is currently playing.", _COLOR_ERR),
                ephemeral=True,
            )

    # ── /resume ───────────────────────────────────────────────────────────

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        player = self.manager.get(interaction.guild)
        if player.resume():
            await interaction.response.send_message(
                embed=_embed("▶ Resumed", "", _COLOR_PLAY)
            )
        else:
            await interaction.response.send_message(
                embed=_embed("❌ Not Paused", "Nothing is paused.", _COLOR_ERR),
                ephemeral=True,
            )

    # ── /skip ─────────────────────────────────────────────────────────────

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        player = self.manager.get(interaction.guild)
        if player.skip():
            await interaction.response.send_message(
                embed=_embed("⏭ Skipped", "", _COLOR_INFO)
            )
        else:
            await interaction.response.send_message(
                embed=_embed("❌ Nothing to Skip", "", _COLOR_ERR),
                ephemeral=True,
            )

    # ── /stop ─────────────────────────────────────────────────────────────

    @app_commands.command(name="stop", description="Stop music and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        player = self.manager.get(interaction.guild)
        player.stop()
        await interaction.response.send_message(
            embed=_embed("⏹ Stopped", "Queue cleared.", _COLOR_WARN)
        )

    # ── /queue ────────────────────────────────────────────────────────────

    @app_commands.command(name="queue", description="Show the music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        player = self.manager.get(interaction.guild)
        q = player.queue

        e = discord.Embed(title="🎵 Music Queue", color=_COLOR_QUEUE)

        if q.current:
            status = "▶ Playing" if player.is_playing else "⏸ Paused"
            e.add_field(
                name=f"Now Playing  [{status}]",
                value=f"**{q.current.title}** `{q.current.duration_str}`",
                inline=False,
            )

        upcoming = q.peek(10)
        if upcoming:
            lines = "\n".join(
                f"`{i+1}.` {t.title} `{t.duration_str}`"
                for i, t in enumerate(upcoming)
            )
            e.add_field(name="Up Next", value=lines, inline=False)
            if len(q) > 10:
                e.set_footer(text=f"...and {len(q) - 10} more  |  Loop: {q.loop_mode}")
            else:
                e.set_footer(text=f"Loop: {q.loop_mode}  |  Autoplay: {'on' if player.autoplay else 'off'}")
        else:
            e.add_field(name="Queue", value="Empty", inline=False)
            e.set_footer(text=f"Autoplay: {'on' if player.autoplay else 'off'}")

        await interaction.response.send_message(embed=e)

    # ── /nowplaying ───────────────────────────────────────────────────────

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        player = self.manager.get(interaction.guild)
        track = player.queue.current
        if not track:
            await interaction.response.send_message(
                embed=_embed("❌ Nothing Playing", "", _COLOR_ERR),
                ephemeral=True,
            )
            return

        e = _track_embed(track)
        status = "▶ Playing" if player.is_playing else "⏸ Paused"
        e.add_field(name="Status", value=status, inline=True)
        e.add_field(name="Loop", value=player.queue.loop_mode, inline=True)
        e.add_field(name="Queue", value=f"{len(player.queue)} track(s) up next", inline=True)
        await interaction.response.send_message(embed=e)

    # ── /loop ─────────────────────────────────────────────────────────────

    @app_commands.command(name="loop", description="Cycle loop mode: off → track → queue → off")
    async def loop(self, interaction: discord.Interaction):
        player = self.manager.get(interaction.guild)
        mode = player.queue.cycle_loop()
        icons = {LoopMode.OFF: "➡", LoopMode.TRACK: "🔂", LoopMode.QUEUE: "🔁"}
        await interaction.response.send_message(
            embed=_embed(f"{icons[mode]} Loop: **{mode}**", "", _COLOR_INFO)
        )

    # ── /volume ───────────────────────────────────────────────────────────

    @app_commands.command(name="volume", description="Set music volume (0–100)")
    @app_commands.describe(level="Volume level from 0 to 100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            await interaction.response.send_message(
                embed=_embed("❌ Invalid Volume", "Must be between 0 and 100.", _COLOR_ERR),
                ephemeral=True,
            )
            return
        player = self.manager.get(interaction.guild)
        player.set_volume(level / 100)
        icon = "🔇" if level == 0 else "🔉" if level < 50 else "🔊"
        await interaction.response.send_message(
            embed=_embed(f"{icon} Volume: {level}%", "", _COLOR_INFO)
        )

    # ── /shuffle ──────────────────────────────────────────────────────────

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        player = self.manager.get(interaction.guild)
        if len(player.queue) < 2:
            await interaction.response.send_message(
                embed=_embed("❌ Not Enough Songs", "Need at least 2 songs in queue.", _COLOR_ERR),
                ephemeral=True,
            )
            return
        player.queue.shuffle()
        await interaction.response.send_message(
            embed=_embed(f"🔀 Shuffled {len(player.queue)} songs", "", _COLOR_INFO)
        )

    # ── /remove ───────────────────────────────────────────────────────────

    @app_commands.command(name="remove", description="Remove a song from the queue by its position")
    @app_commands.describe(position="Queue position (1 = next song)")
    async def remove(self, interaction: discord.Interaction, position: int):
        player = self.manager.get(interaction.guild)
        removed = player.queue.remove(position)
        if removed:
            await interaction.response.send_message(
                embed=_embed("🗑 Removed", f"**{removed.title}**", _COLOR_WARN)
            )
        else:
            await interaction.response.send_message(
                embed=_embed("❌ Invalid Position", f"Queue has {len(player.queue)} track(s).", _COLOR_ERR),
                ephemeral=True,
            )

    # ── /autoplay ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="autoplay",
        description="Toggle smart autoplay — bot picks related songs when queue ends",
    )
    async def autoplay(self, interaction: discord.Interaction):
        player = self.manager.get(interaction.guild)
        player.autoplay = not player.autoplay
        state = "on" if player.autoplay else "off"
        icon = "🤖" if player.autoplay else "🔕"
        desc = (
            "Bot will automatically queue related songs when the queue ends."
            if player.autoplay
            else "Autoplay disabled. Bot will stay connected but stop playing."
        )
        await interaction.response.send_message(
            embed=_embed(f"{icon} Autoplay: **{state}**", desc, _COLOR_INFO)
        )

    # ── /leave ────────────────────────────────────────────────────────────

    @app_commands.command(name="leave", description="Disconnect the bot from voice")
    async def leave(self, interaction: discord.Interaction):
        player = self.manager.get(interaction.guild)
        if not player.vc or not player.vc.is_connected():
            await interaction.response.send_message(
                embed=_embed("❌ Not Connected", "", _COLOR_ERR),
                ephemeral=True,
            )
            return
        await self.manager.destroy(interaction.guild.id)
        await interaction.response.send_message(
            embed=_embed("👋 Disconnected", "", _COLOR_WARN)
        )

    # ── Voice state: auto-leave when alone ───────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """If everyone leaves the voice channel, pause (but stay connected for 24/7)."""
        if member.bot:
            return
        guild = member.guild
        player = self.manager.get(guild)
        vc = player.vc
        if not vc or not vc.is_connected():
            return
        # Check if bot's channel is now empty of humans
        human_members = [m for m in vc.channel.members if not m.bot]
        if not human_members and player.is_playing:
            player.pause()
            logger.info(
                f"[{guild.name}] Auto-paused — no humans in voice channel."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
