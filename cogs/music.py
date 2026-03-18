"""
WAN Bot — Music Cog (v3)
========================
Fixes applied:
  1. Watchdog bug: state.queue → state.empty()
  2. Race condition in _advance: protected by asyncio.Lock per guild
  3. Stale VoiceClient guard in _play_song
  4. Memory leak: _cleanup() removes idle guild states
  5. Autoplay semaphore: max 3 concurrent yt-dlp calls
  6. Reuse single YoutubeDL instance (module-level YTDL)
  7. Autoplay fallback: ytsearch5 instead of fragile HTML scraping
  8. /loop command (song / queue / off)
  9. Idle disconnect: leave after 5 min with no humans
 10. Queue display shows duration
 11. /remove and /shuffle commands added
 12. Autoplay scoring: penalise remix mismatch, boost VEVO
"""

import asyncio
import logging
import os
import re
from collections import deque
from typing import Optional

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger("discord_bot.music")

# ── Config ────────────────────────────────────────────────────────────────────

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "..", "cookies.txt")

def _build_opts(extra: dict = {}) -> dict:
    opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "extractor_args": {"youtube": {"player_client": ["web", "android"]}},
        **extra,
    }
    if os.path.isfile(COOKIES_FILE):
        opts["cookiefile"] = os.path.abspath(COOKIES_FILE)
    return opts

# Single reused instance — avoids re-init overhead on every search
YTDL = yt_dlp.YoutubeDL(_build_opts())

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


# ── Song ──────────────────────────────────────────────────────────────────────

class Song:
    """
    Wraps a yt-dlp info dict.
    Imported by web_dashboard_enhanced.py — attributes must stay stable.
    """
    __slots__ = ("title", "url", "stream_url", "thumbnail", "duration",
                 "channel", "video_id", "requester")

    def __init__(self, data: dict, requester=None):
        self.title: str      = data.get("title", "Unknown")
        self.url: str        = data.get("webpage_url") or data.get("url", "")
        self.stream_url: str = data.get("url", "")
        self.thumbnail       = data.get("thumbnail")
        self.duration        = data.get("duration")   # seconds (int) or None
        self.channel: str    = data.get("uploader") or data.get("channel", "Unknown")
        self.video_id        = data.get("id")
        self.requester       = requester

    @property
    def duration_str(self) -> str:
        if not self.duration:
            return "?"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def build_source(self, volume: float = 0.5) -> discord.PCMVolumeTransformer:
        return discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(self.stream_url, **FFMPEG_OPTS),
            volume=volume,
        )


# ── _fetch — dashboard imports this ──────────────────────────────────────────

def _fetch(query: str) -> Optional[dict]:
    """Sync yt-dlp extract. Called via run_in_executor from the dashboard."""
    try:
        data = YTDL.extract_info(query, download=False)
    except Exception as e:
        logger.error(f"[_fetch] {e}")
        return None
    if not data:
        return None
    if "entries" in data:
        entries = [e for e in data["entries"] if e]
        return entries[0] if entries else None
    return data


# ── Autoplay scoring ──────────────────────────────────────────────────────────

_MOOD_GROUPS = {
    "soft":      ["lofi", "acoustic", "chill", "calm", "relax", "sleep", "study",
                  "piano", "ambient", "slow", "soft"],
    "romantic":  ["romantic", "love", "sad", "emotional", "heartbreak", "ballad", "melancholy"],
    "energetic": ["edm", "dance", "party", "hype", "workout", "bass", "trap", "dubstep", "rave"],
    "rock":      ["rock", "metal", "punk", "grunge", "indie", "alternative", "guitar"],
    "hiphop":    ["rap", "hip hop", "hip-hop", "drill", "r&b", "rnb", "soul"],
    "classical": ["classical", "orchestra", "symphony", "opera", "baroque"],
    "hindi":     ["hindi", "bollywood", "punjabi", "bhajan", "ghazal", "arijit", "atif"],
    "kpop":      ["kpop", "k-pop", "bts", "blackpink", "twice"],
}

_INCOMPATIBLE = [
    ("soft", "energetic"), ("classical", "energetic"),
    ("classical", "hiphop"), ("hindi", "kpop"),
]


def _detect_mood(text: str) -> Optional[str]:
    t = text.lower()
    for mood, kws in _MOOD_GROUPS.items():
        if any(k in t for k in kws):
            return mood
    return None


def _moods_ok(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b or a == b:
        return True
    pair = tuple(sorted([a, b]))
    return pair not in [tuple(sorted(x)) for x in _INCOMPATIBLE]


def _score(candidate: dict, last: dict) -> int:
    score = 0
    title       = candidate.get("title", "")
    channel     = candidate.get("uploader") or candidate.get("channel", "")
    dur         = candidate.get("duration")
    last_title  = last.get("title", "")
    last_ch     = last.get("uploader") or last.get("channel", "")
    last_dur    = last.get("duration")

    # Reject shorts / memes
    if dur and dur < 60:
        return -999

    # +50 same artist
    if channel and last_ch and channel.lower() == last_ch.lower():
        score += 50

    # +5 VEVO boost (verified artist)
    if "vevo" in channel.lower():
        score += 5

    # +30 title word overlap
    stop = {"the", "a", "an", "of", "in", "on", "ft", "feat", "and", "or"}
    lw = set(re.findall(r"\w+", last_title.lower())) - stop
    cw = set(re.findall(r"\w+", title.lower())) - stop
    overlap = len(lw & cw)
    if overlap:
        score += min(30, overlap * 8)

    # -10 remix mismatch
    is_remix = "remix" in title.lower()
    last_is_remix = "remix" in last_title.lower()
    if is_remix and not last_is_remix:
        score -= 10

    # +20 same mood / -999 incompatible
    last_mood = _detect_mood(f"{last_title} {last_ch}")
    cand_mood = _detect_mood(f"{title} {channel}")
    if not _moods_ok(last_mood, cand_mood):
        return -999
    if last_mood and last_mood == cand_mood:
        score += 20

    # +10 similar duration (within 30%)
    if dur and last_dur:
        ratio = min(dur, last_dur) / max(dur, last_dur)
        if ratio >= 0.7:
            score += 10

    return score


# ── Per-guild state ───────────────────────────────────────────────────────────

class GuildMusicState:
    """All music state for one guild."""

    def __init__(self):
        self._q: list[Song]          = []               # dashboard reads ._q
        self.current: Optional[Song] = None             # dashboard reads .current
        self.volume: float           = 0.5
        self.autoplay: bool          = False
        self.loop_song: bool         = False            # dashboard reads .loop_song
        self.loop_queue: bool        = False            # dashboard reads .loop_queue
        self._history: deque         = deque(maxlen=20)
        self._player_task: Optional[asyncio.Task] = None
        self._lock: asyncio.Lock     = asyncio.Lock()  # FIX #2: prevents _advance race
        self._idle_since: Optional[float] = None       # FIX #9: idle disconnect timer

    # ── Queue helpers (dashboard + internal) ─────────────────────────────

    def empty(self) -> bool:
        return len(self._q) == 0

    def add(self, song: Song):
        """dashboard: queue.add(song)"""
        self._q.append(song)

    def clear(self):
        """dashboard: queue.clear()"""
        self._q.clear()
        self.current = None

    def reset(self):
        self.clear()

    def __len__(self) -> int:
        return len(self._q)


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    """Music — play, queue, skip, pause, resume, stop, loop, autoplay."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, GuildMusicState] = {}
        self._watchdog.start()

    def cog_unload(self):
        self._watchdog.cancel()
        for state in self._states.values():
            if state._player_task:
                state._player_task.cancel()

    # ── State management ──────────────────────────────────────────────────

    def _state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildMusicState()
        return self._states[guild_id]

    def _cleanup(self, guild_id: int):
        """FIX #4: remove idle state to prevent memory leak."""
        state = self._states.get(guild_id)
        if state and state.empty() and not state.current and not state.autoplay:
            self._states.pop(guild_id, None)
            logger.debug(f"[cleanup] Removed idle state for guild {guild_id}")

    # ── Dashboard-facing API ──────────────────────────────────────────────

    def _q(self, guild_id: int) -> GuildMusicState:
        """dashboard: music_cog._q(guild_id)"""
        return self._state(guild_id)

    async def _start(self, guild: discord.Guild, vc: discord.VoiceClient, song: Song):
        """dashboard: music_cog._start(guild, vc, song)"""
        state = self._state(guild.id)
        state.current = song
        if vc.is_playing():
            vc.stop()
        self._play_song(guild, vc, song, state)
        if not state._player_task or state._player_task.done():
            state._player_task = self.bot.loop.create_task(self._player_loop(guild))

    # ── Extraction ────────────────────────────────────────────────────────

    async def _extract(self, query: str) -> Optional[Song]:
        """Async wrapper around _fetch."""
        try:
            data = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, lambda: _fetch(query)),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.error(f"[extract] Timed out: {query}")
            return None
        return Song(data) if data else None

    # ── Playback core ─────────────────────────────────────────────────────

    def _play_song(self, guild: discord.Guild, vc: discord.VoiceClient,
                   song: Song, state: GuildMusicState):
        """Build FFmpeg source and start playing. FIX #3: guard stale vc."""
        if not vc or not vc.is_connected():                          # FIX #3
            logger.warning(f"[{guild.name}] VC not connected, skipping play")
            return

        source = song.build_source(state.volume)
        state._idle_since = None  # reset idle timer

        def _after(err):
            if err:
                logger.error(f"[{guild.name}] Playback error: {err}")
            asyncio.run_coroutine_threadsafe(self._advance(guild), self.bot.loop)

        vc.play(source, after=_after)
        logger.info(f"[{guild.name}] ▶ {song.title} — {song.channel}")

    async def _advance(self, guild: discord.Guild):
        """
        Move to the next track. FIX #2: wrapped in per-guild lock so
        concurrent _after() callbacks can't cause double-skip.
        """
        state = self._state(guild.id)

        async with state._lock:                                       # FIX #2
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                return

            # Loop single track
            if state.loop_song and state.current:
                self._play_song(guild, vc, state.current, state)
                return

            # Loop queue
            if state.loop_queue and state.current:
                state._q.append(state.current)

            # Next in queue
            if state._q:
                song = state._q.pop(0)
                state.current = song
                if song.video_id:
                    state._history.append(song.video_id)
                self._play_song(guild, vc, song, state)
                return

            # Queue empty — try autoplay
            if state.autoplay and state.current:
                song = await self._autoplay_next(state)
                if song:
                    state.current = song
                    if song.video_id:
                        state._history.append(song.video_id)
                    self._play_song(guild, vc, song, state)
                    return

            # Nothing left
            import time
            state.current = None
            state._idle_since = asyncio.get_event_loop().time()
            logger.info(f"[{guild.name}] Queue exhausted")
            self._cleanup(guild.id)                                   # FIX #4

    async def _player_loop(self, guild: discord.Guild):
        """Kicks off first song; keeps task alive while vc is connected."""
        state = self._state(guild.id)
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return

        # Start first song if idle
        if not vc.is_playing() and not vc.is_paused() and state._q:
            async with state._lock:
                if state._q:  # re-check inside lock
                    song = state._q.pop(0)
                    state.current = song
                    if song.video_id:
                        state._history.append(song.video_id)
                    self._play_song(guild, vc, song, state)

        while True:
            await asyncio.sleep(2)
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                break
            # Safety net: if not playing and queue has items, advance
            if not vc.is_playing() and not vc.is_paused() and state._q:
                await self._advance(guild)

        state._player_task = None
        logger.info(f"[{guild.name}] Player loop ended")

    # ── Smart autoplay ────────────────────────────────────────────────────

    async def _autoplay_next(self, state: GuildMusicState) -> Optional[Song]:
        last = state.current
        if not last:
            return None

        history_ids = set(state._history)
        last_dict = {
            "title": last.title, "uploader": last.channel,
            "duration": last.duration, "id": last.video_id,
        }

        # FIX #7: use yt-dlp search instead of fragile HTML scraping
        # Search for related tracks using artist + title keywords
        search_query = (
            f"ytsearch5:{last.channel} {last.title}"
            if last.channel and last.channel.lower() not in ("unknown", "")
            else f"ytsearch5:{last.title} similar"
        )
        logger.info(f"[autoplay] Searching: {search_query!r}")

        try:
            raw = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, lambda: YTDL.extract_info(search_query, download=False)),
                timeout=20.0,
            )
        except Exception as e:
            logger.warning(f"[autoplay] Search failed: {e}")
            return None

        candidates = [e for e in (raw.get("entries") or []) if e and e.get("id") not in history_ids]

        # FIX #5: semaphore — max 3 concurrent yt-dlp metadata fetches
        sem = asyncio.Semaphore(3)
        best_score = -1
        best_song: Optional[Song] = None

        async def _fetch_and_score(entry: dict):
            nonlocal best_score, best_song
            async with sem:
                # entries from ytsearch may already have enough metadata
                info_dict = {
                    "title":    entry.get("title", ""),
                    "uploader": entry.get("uploader") or entry.get("channel", ""),
                    "duration": entry.get("duration"),
                    "id":       entry.get("id"),
                }
                s = _score(info_dict, last_dict)
                logger.debug(f"[autoplay] {info_dict['title']!r} score={s}")
                if s > best_score:
                    best_score = s
                    # Fetch full stream URL only for the winner (lazy)
                    best_song = Song(entry)

        await asyncio.gather(*[_fetch_and_score(e) for e in candidates], return_exceptions=True)

        if best_song and best_score >= 0:
            # Fetch full stream URL now
            full = await self._extract(f"https://www.youtube.com/watch?v={best_song.video_id}")
            if full:
                logger.info(f"[autoplay] ✅ {full.title!r} (score={best_score})")
                return full

        # Final fallback
        fallback = f"{last.channel} similar songs" if last.channel not in ("Unknown", "") else f"{last.title} similar"
        logger.info(f"[autoplay] Fallback: {fallback!r}")
        return await self._extract(fallback)


    # ── Watchdog ──────────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _watchdog(self):
        for guild_id, state in list(self._states.items()):
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            vc = guild.voice_client

            # FIX #1: was state.queue.empty() — now state.empty()
            has_work = not state.empty() or (state.autoplay and state.current)
            task_dead = not state._player_task or state._player_task.done()

            if task_dead and has_work and vc and vc.is_connected():
                logger.info(f"[watchdog] Restarting player for {guild.name}")
                state._player_task = self.bot.loop.create_task(self._player_loop(guild))

            # FIX #9: idle disconnect after 5 min with no humans
            if vc and vc.is_connected():
                humans = [m for m in vc.channel.members if not m.bot]
                if not humans:
                    idle = asyncio.get_event_loop().time() - (state._idle_since or asyncio.get_event_loop().time())
                    if idle >= 300:  # 5 minutes
                        logger.info(f"[watchdog] Idle disconnect: {guild.name}")
                        state.reset()
                        if state._player_task:
                            state._player_task.cancel()
                        await vc.disconnect()
                        self._cleanup(guild_id)

    @_watchdog.before_loop
    async def _before_watchdog(self):
        await self.bot.wait_until_ready()

    # ── Voice state listener ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return
        humans = [m for m in vc.channel.members if not m.bot]
        state = self._state(guild.id)
        if not humans:
            if vc.is_playing():
                vc.pause()
                logger.info(f"[{guild.name}] Auto-paused — channel empty")
            # Start idle timer
            if state._idle_since is None:
                state._idle_since = asyncio.get_event_loop().time()
        else:
            # Humans rejoined — resume if paused
            if vc.is_paused():
                vc.resume()
            state._idle_since = None

    # ── Slash Commands ────────────────────────────────────────────────────

    @app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            await vc.move_to(interaction.user.voice.channel)
        else:
            vc = await interaction.user.voice.channel.connect()
        await interaction.response.send_message(f"✅ Joined **{interaction.user.voice.channel.name}**")

    @app_commands.command(name="play", description="Play a song — YouTube URL or search query")
    @app_commands.describe(query="YouTube URL or search terms")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
        await interaction.response.defer()

        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            try:
                vc = await interaction.user.voice.channel.connect()
            except Exception as e:
                return await interaction.followup.send(f"❌ Could not connect: {e}", ephemeral=True)

        song = await self._extract(query)
        if not song:
            return await interaction.followup.send("❌ Could not find that track.", ephemeral=True)

        song.requester = interaction.user
        state = self._state(interaction.guild.id)
        state._q.append(song)

        if not state._player_task or state._player_task.done():
            state._player_task = self.bot.loop.create_task(self._player_loop(interaction.guild))

        embed = discord.Embed(color=0x7C3AED)
        if state.current and (vc.is_playing() or vc.is_paused()):
            embed.title = "📋 Added to Queue"
            embed.description = f"**{song.title}** `{song.duration_str}`"
            embed.set_footer(text=f"By {song.channel} • Requested by {interaction.user.display_name}")
        else:
            embed.title = "▶ Playing Soon"
            embed.description = f"**{song.title}** `{song.duration_str}`"
            if song.thumbnail:
                embed.set_thumbnail(url=song.thumbnail)
            embed.set_footer(text=f"By {song.channel}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭ Skipped.")
        else:
            await interaction.response.send_message("❌ Nothing to skip.", ephemeral=True)

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶ Resumed.")
        else:
            await interaction.response.send_message("❌ Not paused.", ephemeral=True)

    @app_commands.command(name="stop", description="Stop music and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        state.reset()
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
        if state._player_task:
            state._player_task.cancel()
            state._player_task = None
        self._cleanup(interaction.guild.id)
        await interaction.response.send_message("⏹ Stopped and disconnected.")

    @app_commands.command(name="queue", description="Show the music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        items = list(state._q)
        embed = discord.Embed(title="🎵 Music Queue", color=0x7C3AED)
        if state.current:
            vc = interaction.guild.voice_client
            status = "▶" if (vc and vc.is_playing()) else "⏸"
            embed.add_field(
                name=f"{status} Now Playing",
                value=f"**{state.current.title}** `{state.current.duration_str}` — {state.current.channel}",
                inline=False,
            )
        if items:
            # FIX #10: show duration in queue list
            lines = "\n".join(
                f"`{i+1}.` {s.title} `{s.duration_str}`"
                for i, s in enumerate(items[:10])
            )
            embed.add_field(name="Up Next", value=lines, inline=False)
            if len(items) > 10:
                embed.set_footer(text=f"...and {len(items)-10} more  |  Autoplay: {'on' if state.autoplay else 'off'}")
            else:
                embed.set_footer(text=f"Autoplay: {'on' if state.autoplay else 'off'}  |  Loop: {'song' if state.loop_song else 'queue' if state.loop_queue else 'off'}")
        else:
            embed.add_field(name="Queue", value="Empty", inline=False)
            embed.set_footer(text=f"Autoplay: {'on' if state.autoplay else 'off'}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        if not state.current:
            return await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        t = state.current
        vc = interaction.guild.voice_client
        embed = discord.Embed(title="▶ Now Playing", description=f"**{t.title}**", color=0x10B981)
        if t.thumbnail:
            embed.set_thumbnail(url=t.thumbnail)
        embed.add_field(name="Channel", value=t.channel or "?", inline=True)
        embed.add_field(name="Duration", value=t.duration_str, inline=True)
        embed.add_field(name="Status", value="▶ Playing" if (vc and vc.is_playing()) else "⏸ Paused", inline=True)
        embed.add_field(name="Queue", value=f"{len(state._q)} up next", inline=True)
        embed.add_field(name="Loop", value="song" if state.loop_song else "queue" if state.loop_queue else "off", inline=True)
        if t.requester:
            embed.set_footer(text=f"Requested by {t.requester.display_name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="loop", description="Set loop mode: song / queue / off")
    @app_commands.describe(mode="song — repeat current track | queue — loop whole queue | off — no loop")
    @app_commands.choices(mode=[
        app_commands.Choice(name="song",  value="song"),
        app_commands.Choice(name="queue", value="queue"),
        app_commands.Choice(name="off",   value="off"),
    ])
    async def loop(self, interaction: discord.Interaction, mode: str):
        state = self._state(interaction.guild.id)
        state.loop_song  = (mode == "song")
        state.loop_queue = (mode == "queue")
        icons = {"song": "🔂", "queue": "🔁", "off": "➡"}
        await interaction.response.send_message(f"{icons[mode]} Loop: **{mode}**")

    @app_commands.command(name="volume", description="Set volume (0–100)")
    @app_commands.describe(level="Volume from 0 to 100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            return await interaction.response.send_message("❌ Must be 0–100.", ephemeral=True)
        state = self._state(interaction.guild.id)
        state.volume = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = state.volume
        icon = "🔇" if level == 0 else "🔉" if level < 50 else "🔊"
        await interaction.response.send_message(f"{icon} Volume: **{level}%**")

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        import random
        state = self._state(interaction.guild.id)
        if len(state._q) < 2:
            return await interaction.response.send_message("❌ Need at least 2 songs to shuffle.", ephemeral=True)
        random.shuffle(state._q)
        await interaction.response.send_message(f"🔀 Shuffled {len(state._q)} songs.")

    @app_commands.command(name="remove", description="Remove a song from the queue by position")
    @app_commands.describe(position="Position in queue (1 = next song)")
    async def remove(self, interaction: discord.Interaction, position: int):
        state = self._state(interaction.guild.id)
        if not 1 <= position <= len(state._q):
            return await interaction.response.send_message(
                f"❌ Invalid position. Queue has {len(state._q)} track(s).", ephemeral=True
            )
        removed = state._q.pop(position - 1)
        await interaction.response.send_message(f"🗑 Removed: **{removed.title}**")

    @app_commands.command(name="autoplay", description="Toggle smart autoplay when queue ends")
    async def autoplay(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        state.autoplay = not state.autoplay
        icon = "🤖" if state.autoplay else "🔕"
        await interaction.response.send_message(f"{icon} Autoplay: **{'on' if state.autoplay else 'off'}**")

    @app_commands.command(name="leave", description="Disconnect the bot from voice")
    async def leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("❌ Not in a voice channel.", ephemeral=True)
        state = self._state(interaction.guild.id)
        state.reset()
        if state._player_task:
            state._player_task.cancel()
            state._player_task = None
        await vc.disconnect()
        self._cleanup(interaction.guild.id)
        await interaction.response.send_message("👋 Disconnected.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
