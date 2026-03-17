"""
Music Player — PlayerManager + QueueManager
Handles per-guild voice state, queue operations, loop modes, and volume.
"""
import asyncio
import logging
import os
from collections import deque
from typing import Optional

import discord
import yt_dlp

logger = logging.getLogger("discord_bot.music.player")

# ── yt-dlp options ────────────────────────────────────────────────────────────

def _build_ytdl_opts() -> dict:
    opts = {
        "format": "bestaudio[ext=webm]/bestaudio/best",
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        # Prefer native HLS/DASH over ffmpeg for lower latency
        "hls_prefer_native": True,
        # Retries
        "retries": 3,
        "fragment_retries": 3,
        # Extractor args — use web client for best compatibility
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android"],
            }
        },
    }
    # Use cookies.txt if present (prevents 403 / bot-detection blocks)
    cookies_path = os.path.join(os.path.dirname(__file__), "..", "cookies.txt")
    if os.path.isfile(cookies_path):
        opts["cookiefile"] = os.path.abspath(cookies_path)
        logger.info("yt-dlp: using cookies.txt for authenticated requests")
    return opts


YTDL_OPTS = _build_ytdl_opts()

FFMPEG_OPTS = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5 "
        "-reconnect_at_eof 1"
    ),
    "options": "-vn -bufsize 64k",
}


# ── Track dataclass ───────────────────────────────────────────────────────────

class Track:
    """Lightweight metadata container — no audio source attached yet."""

    __slots__ = (
        "title", "url", "stream_url", "thumbnail",
        "duration", "channel", "video_id", "requester",
    )

    def __init__(self, data: dict, requester: Optional[discord.Member] = None):
        self.title: str = data.get("title", "Unknown")
        self.url: str = data.get("webpage_url") or data.get("url", "")
        self.stream_url: str = data.get("url", "")          # direct audio stream
        self.thumbnail: Optional[str] = data.get("thumbnail")
        self.duration: Optional[int] = data.get("duration")  # seconds
        self.channel: str = data.get("uploader") or data.get("channel", "Unknown")
        self.video_id: Optional[str] = data.get("id")
        self.requester: Optional[discord.Member] = requester

    @property
    def duration_str(self) -> str:
        if not self.duration:
            return "?"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def build_source(self) -> discord.PCMVolumeTransformer:
        """Create a playable FFmpeg audio source from the cached stream URL."""
        return discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(self.stream_url, **FFMPEG_OPTS),
            volume=0.5,
        )

    def __repr__(self) -> str:
        return f"<Track title={self.title!r} id={self.video_id}>"


# ── Queue ─────────────────────────────────────────────────────────────────────

class LoopMode:
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"


class MusicQueue:
    """FIFO queue with loop modes and history tracking."""

    def __init__(self):
        self._queue: deque[Track] = deque()
        self.current: Optional[Track] = None
        self.loop_mode: str = LoopMode.OFF
        # Last 20 played video IDs — used by autoplay to avoid repeats
        self.history: deque[str] = deque(maxlen=20)

    # ── Mutation ──────────────────────────────────────────────────────────

    def add(self, track: Track) -> int:
        """Append track; returns new queue length."""
        self._queue.append(track)
        return len(self._queue)

    def advance(self) -> Optional[Track]:
        """
        Move to the next track respecting loop mode.
        Returns the track to play next, or None if queue is exhausted.
        """
        if self.loop_mode == LoopMode.TRACK and self.current:
            # Re-play same track — keep current unchanged
            return self.current

        if self.current and self.current.video_id:
            self.history.append(self.current.video_id)

        if self.loop_mode == LoopMode.QUEUE and self.current:
            self._queue.append(self.current)

        if self._queue:
            self.current = self._queue.popleft()
            return self.current

        self.current = None
        return None

    def clear(self):
        self._queue.clear()
        self.current = None

    def shuffle(self):
        import random
        items = list(self._queue)
        random.shuffle(items)
        self._queue = deque(items)

    def remove(self, index: int) -> Optional[Track]:
        """Remove track at 1-based index from queue. Returns removed track."""
        items = list(self._queue)
        if not 1 <= index <= len(items):
            return None
        removed = items.pop(index - 1)
        self._queue = deque(items)
        return removed

    # ── Read ──────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._queue)

    def peek(self, n: int = 10) -> list[Track]:
        return list(self._queue)[:n]

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def cycle_loop(self) -> str:
        """Cycle: off → track → queue → off. Returns new mode label."""
        if self.loop_mode == LoopMode.OFF:
            self.loop_mode = LoopMode.TRACK
        elif self.loop_mode == LoopMode.TRACK:
            self.loop_mode = LoopMode.QUEUE
        else:
            self.loop_mode = LoopMode.OFF
        return self.loop_mode


# ── Extractor ─────────────────────────────────────────────────────────────────

class TrackExtractor:
    """Wraps yt-dlp in an async-friendly interface with metadata caching."""

    # Simple LRU-style cache: video_id → Track data dict
    _cache: dict[str, dict] = {}
    _CACHE_MAX = 200

    @classmethod
    async def extract(
        cls,
        query: str,
        loop: asyncio.AbstractEventLoop,
        *,
        timeout: float = 30.0,
    ) -> Track:
        """
        Resolve a URL or search query to a Track.
        Raises on failure.
        """
        ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

        def _run():
            return ytdl.extract_info(query, download=False)

        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, _run),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Extraction timed out after {timeout}s for: {query}")

        if not data:
            raise RuntimeError(f"No results found for: {query}")

        # Flatten playlist — take first entry
        if "entries" in data:
            entries = [e for e in data["entries"] if e]
            if not entries:
                raise RuntimeError("Playlist was empty or all entries failed.")
            data = entries[0]

        # Cache by video ID
        vid_id = data.get("id")
        if vid_id:
            if len(cls._cache) >= cls._CACHE_MAX:
                # Evict oldest
                oldest = next(iter(cls._cache))
                del cls._cache[oldest]
            cls._cache[vid_id] = data

        return Track(data)

    @classmethod
    async def extract_by_id(
        cls,
        video_id: str,
        loop: asyncio.AbstractEventLoop,
    ) -> Track:
        """Fetch a track by YouTube video ID, using cache when available."""
        if video_id in cls._cache:
            return Track(cls._cache[video_id])
        return await cls.extract(
            f"https://www.youtube.com/watch?v={video_id}", loop
        )


# ── GuildPlayer ───────────────────────────────────────────────────────────────

class GuildPlayer:
    """
    Manages voice connection + playback for a single guild.
    Owns the MusicQueue and coordinates with the autoplay engine.
    """

    def __init__(self, bot: commands.Bot, guild: discord.Guild):  # type: ignore[name-defined]
        self.bot = bot
        self.guild = guild
        self.queue = MusicQueue()
        self.volume: float = 0.5
        self.autoplay: bool = False
        self._autoplay_lock = asyncio.Lock()
        self._reconnect_task: Optional[asyncio.Task] = None

    # ── Voice helpers ─────────────────────────────────────────────────────

    @property
    def vc(self) -> Optional[discord.VoiceClient]:
        return self.guild.voice_client  # type: ignore[return-value]

    async def connect(self, channel: discord.VoiceChannel) -> discord.VoiceClient:
        if self.vc and self.vc.is_connected():
            if self.vc.channel != channel:
                await self.vc.move_to(channel)
            return self.vc
        return await channel.connect(timeout=10.0, reconnect=True)

    async def disconnect(self):
        if self.vc:
            await self.vc.disconnect(force=True)
        self.queue.clear()

    # ── Playback ──────────────────────────────────────────────────────────

    def _play_track(self, track: Track):
        """Build source and start playing. Must be called from async context."""
        if not self.vc or not self.vc.is_connected():
            return

        source = track.build_source()
        source.volume = self.volume

        def _after(err):
            if err:
                logger.error(f"[{self.guild.name}] Playback error: {err}")
            asyncio.run_coroutine_threadsafe(
                self._advance(), self.bot.loop
            )

        self.vc.play(source, after=_after)
        logger.info(f"[{self.guild.name}] ▶ Playing: {track.title}")

    async def _advance(self):
        """Called after each track ends. Advances queue or triggers autoplay."""
        next_track = self.queue.advance()

        if next_track:
            self._play_track(next_track)
            return

        # Queue exhausted — try autoplay
        if self.autoplay:
            async with self._autoplay_lock:
                await self._trigger_autoplay()

    async def _trigger_autoplay(self):
        """Ask the autoplay engine for the next track and enqueue it."""
        from utils.music_autoplay import AutoplayEngine  # lazy import avoids circular

        last = self.queue.current
        if not last:
            logger.debug(f"[{self.guild.name}] Autoplay: no last track to base on.")
            return

        logger.info(
            f"[{self.guild.name}] Autoplay triggered — "
            f"last track: {last.title!r} ({last.video_id})"
        )

        try:
            next_track = await AutoplayEngine.get_next(
                last_track=last,
                history=list(self.queue.history),
                loop=self.bot.loop,
            )
        except Exception as e:
            logger.error(f"[{self.guild.name}] Autoplay engine error: {e}")
            return

        if next_track:
            self.queue.add(next_track)
            next_track = self.queue.advance()
            if next_track:
                self._play_track(next_track)
        else:
            logger.warning(f"[{self.guild.name}] Autoplay: no suitable track found.")

    async def play_track(self, track: Track):
        """
        Public entry point: add track to queue.
        If nothing is playing, start immediately.
        """
        if self.vc and (self.vc.is_playing() or self.vc.is_paused()):
            pos = self.queue.add(track)
            return pos  # position in queue (1-based)
        else:
            self.queue.current = track
            self._play_track(track)
            return 0  # 0 = now playing

    def pause(self) -> bool:
        if self.vc and self.vc.is_playing():
            self.vc.pause()
            return True
        return False

    def resume(self) -> bool:
        if self.vc and self.vc.is_paused():
            self.vc.resume()
            return True
        return False

    def skip(self) -> bool:
        if self.vc and (self.vc.is_playing() or self.vc.is_paused()):
            self.vc.stop()  # triggers _after → _advance
            return True
        return False

    def stop(self):
        if self.vc:
            self.vc.stop()
        self.queue.clear()

    def set_volume(self, level: float):
        """level: 0.0 – 1.0"""
        self.volume = level
        if self.vc and self.vc.source:
            self.vc.source.volume = level

    @property
    def is_playing(self) -> bool:
        return bool(self.vc and self.vc.is_playing())

    @property
    def is_paused(self) -> bool:
        return bool(self.vc and self.vc.is_paused())


# ── PlayerManager ─────────────────────────────────────────────────────────────

class PlayerManager:
    """
    Singleton-style registry of GuildPlayer instances.
    One per guild, created on demand.
    """

    def __init__(self, bot):
        self.bot = bot
        self._players: dict[int, GuildPlayer] = {}

    def get(self, guild: discord.Guild) -> GuildPlayer:
        if guild.id not in self._players:
            self._players[guild.id] = GuildPlayer(self.bot, guild)
        return self._players[guild.id]

    async def destroy(self, guild_id: int):
        player = self._players.pop(guild_id, None)
        if player:
            await player.disconnect()

    def __contains__(self, guild_id: int) -> bool:
        return guild_id in self._players


# Avoid circular import — import commands only for type hint
try:
    from discord.ext import commands  # noqa: F401
except ImportError:
    pass
