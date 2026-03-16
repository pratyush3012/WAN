"""
WAN Bot - Music Cog (v4 - bulletproof)
- 24/7: NEVER leaves VC, auto-rejoins on restart
- Queue NEVER empty: autoplay picks DIFFERENT songs similar to last played
- Dedup by URL + title — same song NEVER plays twice in a row
- SoundCloud primary (no IP blocks on Render), YouTube fallback
- Correct audio speed/pitch via aresample=48000
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
try:
    import yt_dlp
except ImportError as e:
    raise ImportError(f"yt-dlp not installed: {e}")
import asyncio
import logging
import random
import json
import os
import re
from collections import deque

logger = logging.getLogger('discord_bot.music')
PERSIST_FILE = 'music_247.json'

# ── yt-dlp base options ───────────────────────────────────────────────────────
YTDL_BASE = {
    'format': 'bestaudio/best',
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'noplaylist': True,
    'socket_timeout': 30,
}

# Write YouTube cookies from env if provided
_COOKIES_FILE = os.path.join(os.path.dirname(__file__), '..', 'youtube_cookies.txt')
if os.getenv('YOUTUBE_COOKIES'):
    try:
        with open(_COOKIES_FILE, 'w') as _f:
            _f.write(os.getenv('YOUTUBE_COOKIES'))
    except Exception:
        pass
if os.path.exists(_COOKIES_FILE):
    YTDL_BASE['cookiefile'] = os.path.abspath(_COOKIES_FILE)

# ── FFmpeg options ────────────────────────────────────────────────────────────
FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -af aresample=48000',
}

# ── YT player clients to try in order ────────────────────────────────────────
_YT_CLIENTS = [['android_embedded'], ['android_music'], ['ios'], ['mweb']]

# ── Generic seeds used when history is empty ─────────────────────────────────
_SEEDS = [
    "top hits 2024", "popular songs 2024", "best music mix",
    "hip hop hits 2024", "pop hits 2024", "r&b hits 2024",
    "chill vibes music", "electronic music mix", "workout music",
    "bollywood hits 2024", "punjabi songs 2024", "trending songs 2024",
]


# ── Extraction helpers (run in executor — blocking) ───────────────────────────

def _is_url(q: str) -> bool:
    return q.startswith(('http://', 'https://', 'www.'))

def _clean_yt_url(url: str) -> str:
    import urllib.parse as up
    p = up.urlparse(url)
    qs = up.parse_qs(p.query)
    if 'youtube.com/watch' in url and 'v' in qs:
        return up.urlunparse(p._replace(query=up.urlencode({'v': qs['v'][0]})))
    return url

def _ydl_extract(opts: dict, query: str) -> dict | None:
    """Single yt-dlp call, returns first valid entry or None."""
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(query, download=False)
        if not data:
            return None
        if data.get('url'):
            return data
        entries = [e for e in data.get('entries', []) if e and e.get('url')]
        return entries[0] if entries else None
    except Exception:
        return None

def _extract(query: str) -> dict | None:
    """Fetch one track. SoundCloud first, then YouTube clients."""
    if _is_url(query):
        url = _clean_yt_url(query)
        if 'youtube.com' in url or 'youtu.be' in url:
            for clients in _YT_CLIENTS:
                r = _ydl_extract({**YTDL_BASE, 'extractor_args': {'youtube': {'player_client': clients}}}, url)
                if r:
                    return r
        return _ydl_extract(YTDL_BASE, url)

    # Text search — SoundCloud first (no IP blocks on cloud)
    r = _ydl_extract(YTDL_BASE, f"scsearch1:{query}")
    if r:
        logger.info(f"SC hit: '{r.get('title')}' for '{query}'")
        return r

    for clients in _YT_CLIENTS:
        r = _ydl_extract({**YTDL_BASE, 'extractor_args': {'youtube': {'player_client': clients}}},
                         f"ytsearch1:{query}")
        if r:
            logger.info(f"YT hit: '{r.get('title')}' for '{query}'")
            return r

    logger.warning(f"No results: '{query}'")
    return None


def _extract_similar(seed_title: str, exclude_urls: set, exclude_titles: set) -> dict | None:
    """
    Search for songs similar to seed_title.
    Returns a RANDOM result that hasn't been played yet.
    Tries SoundCloud (8 results), then YouTube (5 results), then random seed.
    """
    # Clean noise from title for better search results
    clean = re.sub(
        r'\(.*?\)|\[.*?\]|official\s*(video|audio|mv)?|lyrics?|hd|4k|'
        r'ft\.?\s*\w+|feat\.?\s*\w+|\d{4}',
        '', seed_title, flags=re.IGNORECASE
    ).strip()
    if len(clean) < 3:
        clean = seed_title

    def _unseen(e) -> bool:
        if not e or not e.get('url'):
            return False
        url = e.get('webpage_url') or e.get('url', '')
        title = (e.get('title') or '').lower().strip()
        # Reject if URL or title was already played
        return url not in exclude_urls and title not in exclude_titles

    # SoundCloud: fetch 8, pick random unseen
    for n in (8, 5, 3):
        try:
            opts = {**YTDL_BASE, 'noplaylist': False}
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(f"scsearch{n}:{clean}", download=False)
            if data and 'entries' in data:
                pool = [e for e in data['entries'] if _unseen(e)]
                if pool:
                    pick = random.choice(pool)
                    logger.info(f"Autoplay SC: '{pick.get('title')}' (seed: '{clean}')")
                    return pick
        except Exception:
            pass

    # YouTube: fetch 5, pick random unseen
    for clients in _YT_CLIENTS:
        try:
            opts = {**YTDL_BASE, 'noplaylist': False,
                    'extractor_args': {'youtube': {'player_client': clients}}}
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(f"ytsearch5:{clean}", download=False)
            if data and 'entries' in data:
                pool = [e for e in data['entries'] if _unseen(e)]
                if pool:
                    pick = random.choice(pool)
                    logger.info(f"Autoplay YT: '{pick.get('title')}' (seed: '{clean}')")
                    return pick
        except Exception:
            continue

    # Last resort: random generic seed
    seed = random.choice(_SEEDS)
    logger.info(f"Autoplay fallback seed: '{seed}'")
    return _extract(seed)


def _fmt(seconds) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── MusicQueue ────────────────────────────────────────────────────────────────

class MusicQueue:
    def __init__(self):
        self.queue: deque = deque()
        self.current = None
        self.loop = False        # loop current song
        self.loop_queue = False  # loop entire queue
        self.history: deque = deque(maxlen=50)  # played YTDLSource objects
        self.played_urls: set = set()           # dedup by URL
        self.played_titles: set = set()         # dedup by title (lowercase)

    def add(self, song):
        self.queue.append(song)

    def record_played(self, song):
        """Mark a song as played so autoplay never picks it again."""
        if not song:
            return
        self.history.append(song)
        url = song.url or ''
        title = (song.title or '').lower().strip()
        if url:
            self.played_urls.add(url)
        if title:
            self.played_titles.add(title)
        # Trim to avoid unbounded growth
        if len(self.played_urls) > 200:
            self.played_urls = set(list(self.played_urls)[-100:])
        if len(self.played_titles) > 200:
            self.played_titles = set(list(self.played_titles)[-100:])

    def advance(self):
        """
        Move to next song. Records current as played.
        Returns next song or None if queue is empty.
        """
        if self.loop and self.current:
            return self.current  # repeat same song (loop mode)

        # Record current as played BEFORE advancing
        self.record_played(self.current)

        if self.loop_queue and self.current:
            self.queue.append(self.current)

        if self.queue:
            self.current = self.queue.popleft()
            return self.current

        self.current = None
        return None

    def shuffle(self):
        lst = list(self.queue)
        random.shuffle(lst)
        self.queue = deque(lst)

    def remove(self, idx: int):
        lst = list(self.queue)
        if 0 < idx <= len(lst):
            removed = lst.pop(idx - 1)
            self.queue = deque(lst)
            return removed.title
        return None

    def clear(self):
        self.queue.clear()
        self.current = None


# ── YTDLSource ────────────────────────────────────────────────────────────────

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title', 'Unknown')
        self.url = data.get('webpage_url') or data.get('url', '')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration', 0)
        self.requester = None

    @classmethod
    async def from_data(cls, data: dict, volume: float = 0.5) -> 'YTDLSource':
        src = discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTS)
        return cls(src, data=data, volume=volume)

    @classmethod
    async def from_query(cls, query: str, *, loop=None, volume=0.5) -> 'YTDLSource':
        loop = loop or asyncio.get_event_loop()
        data = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _extract(query)),
            timeout=60.0,
        )
        if not data:
            raise ValueError(f"No results found for: {query}")
        return await cls.from_data(data, volume)

    @classmethod
    async def from_playlist(cls, url: str, *, loop=None, volume=0.5):
        loop = loop or asyncio.get_event_loop()
        def _get():
            opts = {**YTDL_BASE, 'noplaylist': False, 'playlistend': 50,
                    'extractor_args': {'youtube': {'player_client': ['android_embedded']}}}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    data = ydl.extract_info(url, download=False)
                if not data:
                    return []
                return [e for e in data.get('entries', [data]) if e and e.get('url')]
            except Exception as e:
                logger.warning(f"Playlist extract failed: {e}")
                return []
        entries = await asyncio.wait_for(loop.run_in_executor(None, _get), timeout=90.0)
        out = []
        for e in entries:
            try:
                out.append(await cls.from_data(e, volume))
            except Exception:
                continue
        return out


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    """24/7 music bot — autoplay similar songs, never repeats, never leaves."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._queues: dict[int, MusicQueue] = {}
        self._volumes: dict[int, float] = {}
        self._247: dict[int, dict] = {}          # guild_id -> {channel_id, text_channel_id}
        self._autoplay_locks: dict[int, asyncio.Lock] = {}
        self._load_247()
        self._reconnect_loop.start()
        self._playback_watchdog.start()

    def cog_unload(self):
        self._reconnect_loop.cancel()
        self._playback_watchdog.cancel()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load_247(self):
        try:
            if os.path.exists(PERSIST_FILE):
                with open(PERSIST_FILE) as f:
                    raw = json.load(f)
                migrated = {}
                for k, v in raw.items():
                    if isinstance(v, dict):
                        migrated[int(k)] = v
                    else:
                        # old flat format: {guild_id: channel_id}
                        migrated[int(k)] = {"channel_id": int(v), "text_channel_id": int(v)}
                self._247 = migrated
        except Exception:
            self._247 = {}

    def _save_247(self):
        try:
            with open(PERSIST_FILE, 'w') as f:
                json.dump({str(k): v for k, v in self._247.items()}, f)
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._autoplay_locks:
            self._autoplay_locks[guild_id] = asyncio.Lock()
        return self._autoplay_locks[guild_id]

    def get_queue(self, guild_id: int) -> MusicQueue:
        if guild_id not in self._queues:
            self._queues[guild_id] = MusicQueue()
        return self._queues[guild_id]

    def get_volume(self, guild_id: int) -> float:
        return self._volumes.get(guild_id, 0.5)

    async def cleanup(self, guild: discord.Guild):
        """Stop playback and clear queue (but stay in VC if 24/7)."""
        q = self.get_queue(guild.id)
        q.clear()
        if guild.voice_client and guild.voice_client.is_playing():
            guild.voice_client.stop()

    async def _ensure_voice(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
        """Join the user's VC or return existing. Returns None on failure."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("❌ Join a voice channel first.", ephemeral=True)
            return None
        vc = interaction.guild.voice_client
        if vc:
            if vc.channel != interaction.user.voice.channel:
                await vc.move_to(interaction.user.voice.channel)
            return vc
        try:
            return await interaction.user.voice.channel.connect(timeout=15.0, reconnect=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Could not join VC: {e}", ephemeral=True)
            return None

    async def _broadcast(self, guild_id: int, **kwargs):
        """Send a message to the text channel stored for this guild."""
        info = self._247.get(guild_id)
        if not info:
            return
        ch = self.bot.get_channel(info.get('text_channel_id', 0))
        if ch:
            try:
                await ch.send(**kwargs)
            except Exception:
                pass

    # ── Background tasks ──────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _reconnect_loop(self):
        """Re-join 24/7 VCs that got disconnected."""
        for guild_id, info in list(self._247.items()):
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            vc = guild.voice_client
            if vc and vc.is_connected():
                continue
            ch = guild.get_channel(info['channel_id'])
            if not ch:
                continue
            try:
                new_vc = await ch.connect(timeout=15.0, reconnect=True)
                logger.info(f"[247] Reconnected to {ch.name} in {guild.name}")
                # Resume playback if queue has something
                q = self.get_queue(guild_id)
                if q.current and not new_vc.is_playing():
                    await self._start_playing(guild, new_vc, q.current)
                elif not q.current:
                    await self._autoplay_next(guild, new_vc)
            except Exception as e:
                logger.warning(f"[247] Reconnect failed for {guild_id}: {e}")

    @_reconnect_loop.before_loop
    async def _before_reconnect(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=15)
    async def _playback_watchdog(self):
        """If VC is connected but silent and queue is empty, trigger autoplay."""
        for guild_id in list(self._247.keys()):
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                continue
            if vc.is_playing() or vc.is_paused():
                continue
            q = self.get_queue(guild_id)
            if q.queue:
                continue  # _play_next will handle it
            # Silent + no queue → trigger autoplay
            lock = self._get_lock(guild_id)
            if not lock.locked():
                asyncio.ensure_future(self._autoplay_next(guild, vc))

    @_playback_watchdog.before_loop
    async def _before_watchdog(self):
        await self.bot.wait_until_ready()

    # ── Playback core ─────────────────────────────────────────────────────────

    def _play_next(self, guild: discord.Guild, vc: discord.VoiceClient):
        """
        Called by discord after a track ends (sync callback).
        Schedules async _play_next_async.
        """
        asyncio.run_coroutine_threadsafe(
            self._play_next_async(guild, vc), self.bot.loop
        )

    async def _play_next_async(self, guild: discord.Guild, vc: discord.VoiceClient):
        q = self.get_queue(guild.id)
        next_song = q.advance()  # records current as played, returns next

        if next_song:
            await self._start_playing(guild, vc, next_song)
        else:
            # Queue empty — autoplay
            await self._autoplay_next(guild, vc)

    async def _start_playing(self, guild: discord.Guild, vc: discord.VoiceClient, song: YTDLSource):
        """Actually play a YTDLSource on the VC."""
        if not vc or not vc.is_connected():
            return
        if vc.is_playing():
            vc.stop()

        q = self.get_queue(guild.id)
        q.current = song

        try:
            # Re-create FFmpeg source (stream URLs expire)
            src = discord.FFmpegPCMAudio(song.data['url'], **FFMPEG_OPTS)
            player = discord.PCMVolumeTransformer(src, volume=self.get_volume(guild.id))
            player.data = song.data
            player.title = song.title
            player.url = song.url
            player.thumbnail = song.thumbnail
            player.duration = song.duration
            player.requester = song.requester

            vc.play(player, after=lambda e: (
                logger.error(f"Playback error: {e}") if e else None,
                self._play_next(guild, vc)
            )[-1])

            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"[{song.title}]({song.url})",
                color=discord.Color.green()
            )
            if song.thumbnail:
                embed.set_thumbnail(url=song.thumbnail)
            embed.add_field(name="Duration", value=_fmt(song.duration))
            if song.requester:
                embed.add_field(name="Requested by", value=song.requester.mention)
            await self._broadcast(guild.id, embed=embed)

        except Exception as e:
            logger.error(f"_start_playing error: {e}")
            # Try to refetch and play
            asyncio.ensure_future(self._refetch_and_play(guild, vc, song))

    async def _refetch_and_play(self, guild: discord.Guild, vc: discord.VoiceClient, song: YTDLSource):
        """Re-extract URL for a song whose stream expired, then play."""
        try:
            loop = asyncio.get_event_loop()
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: _extract(song.url or song.title)),
                timeout=60.0
            )
            if data:
                new_song = await YTDLSource.from_data(data, self.get_volume(guild.id))
                new_song.requester = song.requester
                await self._start_playing(guild, vc, new_song)
            else:
                await self._autoplay_next(guild, vc)
        except Exception as e:
            logger.error(f"_refetch_and_play error: {e}")
            await self._autoplay_next(guild, vc)

    async def _autoplay_next(self, guild: discord.Guild, vc: discord.VoiceClient):
        """
        Pick a SIMILAR song to the last played and start it.
        Uses a per-guild lock so only one autoplay runs at a time.
        NEVER retries on success. Only retries (up to 3x) on failure.
        """
        if not vc or not vc.is_connected():
            return

        lock = self._get_lock(guild.id)
        if lock.locked():
            return  # already running for this guild

        async with lock:
            q = self.get_queue(guild.id)

            # If something started playing while we waited for the lock, bail
            if vc.is_playing() or vc.is_paused():
                return

            # Determine seed from history
            seed_title = None
            if q.history:
                seed_title = q.history[-1].title
            elif q.current:
                seed_title = q.current.title

            loop = asyncio.get_event_loop()

            for attempt in range(3):
                try:
                    if seed_title:
                        data = await asyncio.wait_for(
                            loop.run_in_executor(
                                None,
                                lambda: _extract_similar(seed_title, q.played_urls, q.played_titles)
                            ),
                            timeout=90.0
                        )
                    else:
                        seed = random.choice(_SEEDS)
                        data = await asyncio.wait_for(
                            loop.run_in_executor(None, lambda: _extract(seed)),
                            timeout=60.0
                        )

                    if data:
                        song = await YTDLSource.from_data(data, self.get_volume(guild.id))
                        # Double-check dedup
                        url = song.url or ''
                        title = (song.title or '').lower().strip()
                        if url in q.played_urls or title in q.played_titles:
                            logger.info(f"Autoplay dedup skip: '{song.title}', retrying...")
                            seed_title = song.title  # use it as new seed
                            continue

                        q.current = song
                        await self._start_playing(guild, vc, song)
                        return  # SUCCESS — do not retry

                    # data was None — try again with a random seed
                    seed_title = random.choice(_SEEDS)

                except asyncio.TimeoutError:
                    logger.warning(f"Autoplay timeout attempt {attempt+1}")
                    seed_title = random.choice(_SEEDS)
                except Exception as e:
                    logger.error(f"Autoplay error attempt {attempt+1}: {e}")
                    seed_title = random.choice(_SEEDS)

            logger.error(f"Autoplay failed after 3 attempts for guild {guild.id}")

    # ── Slash commands ────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a song or search query")
    @app_commands.describe(query="Song name, URL, or search query")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        q = self.get_queue(interaction.guild_id)
        try:
            song = await YTDLSource.from_query(query, loop=self.bot.loop, volume=self.get_volume(interaction.guild_id))
            song.requester = interaction.user
        except Exception as e:
            await interaction.followup.send(f"❌ Could not find: `{query}`\n`{e}`")
            return

        if vc.is_playing() or vc.is_paused():
            q.add(song)
            embed = discord.Embed(
                title="➕ Added to Queue",
                description=f"[{song.title}]({song.url})",
                color=discord.Color.blue()
            )
            embed.add_field(name="Position", value=str(len(q.queue)))
            embed.add_field(name="Duration", value=_fmt(song.duration))
            await interaction.followup.send(embed=embed)
        else:
            q.current = song
            await self._start_playing(interaction.guild, vc, song)
            await interaction.followup.send(f"▶️ Playing **{song.title}**")

    @app_commands.command(name="playlist", description="Load a YouTube/SoundCloud playlist")
    @app_commands.describe(url="Playlist URL")
    async def playlist(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        await interaction.followup.send("⏳ Loading playlist...")
        try:
            songs = await YTDLSource.from_playlist(url, loop=self.bot.loop, volume=self.get_volume(interaction.guild_id))
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to load playlist: {e}")
            return

        if not songs:
            await interaction.followup.send("❌ No playable tracks found.")
            return

        q = self.get_queue(interaction.guild_id)
        for s in songs:
            s.requester = interaction.user
            q.add(s)

        await interaction.followup.send(f"✅ Added **{len(songs)}** tracks to queue.")
        if not vc.is_playing() and not vc.is_paused():
            next_song = q.advance()
            if next_song:
                await self._start_playing(interaction.guild, vc, next_song)

    @app_commands.command(name="stay", description="Toggle 24/7 mode (bot stays in VC forever)")
    async def toggle_247(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild_id = interaction.guild_id

        if guild_id in self._247:
            del self._247[guild_id]
            self._save_247()
            await interaction.followup.send("⏹️ 24/7 mode **disabled**. Bot will leave when queue ends.")
        else:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("❌ Join a voice channel first.")
                return
            vc = await self._ensure_voice(interaction)
            if not vc:
                return
            self._247[guild_id] = {
                'channel_id': vc.channel.id,
                'text_channel_id': interaction.channel_id,
            }
            self._save_247()
            await interaction.followup.send(
                f"✅ 24/7 mode **enabled** in {vc.channel.mention}. "
                f"Bot will stay and autoplay similar songs forever."
            )
            # Start autoplay if not already playing
            if not vc.is_playing() and not vc.is_paused():
                asyncio.ensure_future(self._autoplay_next(interaction.guild, vc))

    @app_commands.command(name="leave", description="Disconnect bot from voice channel")
    async def leave(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.followup.send("❌ Not in a voice channel.")
            return
        # Remove 24/7 so it doesn't reconnect
        self._247.pop(interaction.guild_id, None)
        self._save_247()
        await self.cleanup(interaction.guild)
        await vc.disconnect()
        await interaction.followup.send("👋 Disconnected.")

    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume playback")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Not paused.", ephemeral=True)

    @app_commands.command(name="skip", description="Skip current song")
    async def skip(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if not vc or not (vc.is_playing() or vc.is_paused()):
            await interaction.followup.send("❌ Nothing playing.")
            return
        q = self.get_queue(interaction.guild_id)
        title = q.current.title if q.current else "Unknown"
        vc.stop()  # triggers _play_next via after callback
        await interaction.followup.send(f"⏭️ Skipped **{title}**")

    @app_commands.command(name="stop", description="Stop music and clear queue")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.cleanup(interaction.guild)
        await interaction.followup.send("⏹️ Stopped and queue cleared.")

    @app_commands.command(name="nowplaying", description="Show current song")
    async def nowplaying(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        if not q.current:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
            return
        s = q.current
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{s.title}]({s.url})",
            color=discord.Color.green()
        )
        if s.thumbnail:
            embed.set_thumbnail(url=s.thumbnail)
        embed.add_field(name="Duration", value=_fmt(s.duration))
        if s.requester:
            embed.add_field(name="Requested by", value=s.requester.mention)
        loop_status = "🔂 Song" if q.loop else ("🔁 Queue" if q.loop_queue else "Off")
        embed.add_field(name="Loop", value=loop_status)
        embed.add_field(name="Queue", value=f"{len(q.queue)} songs")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="queue", description="Show the music queue")
    async def show_queue(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        if not q.current and not q.queue:
            await interaction.response.send_message("📭 Queue is empty.", ephemeral=True)
            return
        lines = []
        if q.current:
            lines.append(f"**Now:** {q.current.title} `[{_fmt(q.current.duration)}]`")
        for i, s in enumerate(list(q.queue)[:15], 1):
            lines.append(f"`{i}.` {s.title} `[{_fmt(s.duration)}]`")
        if len(q.queue) > 15:
            lines.append(f"... and {len(q.queue) - 15} more")
        embed = discord.Embed(
            title=f"🎶 Queue — {len(q.queue)} songs",
            description="\n".join(lines),
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set volume (0-100)")
    @app_commands.describe(level="Volume level 0-100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            await interaction.response.send_message("❌ Volume must be 0-100.", ephemeral=True)
            return
        vol = level / 100
        self._volumes[interaction.guild_id] = vol
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = vol
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**")

    @app_commands.command(name="loop", description="Toggle loop mode")
    @app_commands.describe(mode="song = loop current, queue = loop all, off = disable")
    @app_commands.choices(mode=[
        app_commands.Choice(name="song", value="song"),
        app_commands.Choice(name="queue", value="queue"),
        app_commands.Choice(name="off", value="off"),
    ])
    async def loop(self, interaction: discord.Interaction, mode: str):
        q = self.get_queue(interaction.guild_id)
        q.loop = (mode == "song")
        q.loop_queue = (mode == "queue")
        labels = {"song": "🔂 Looping current song", "queue": "🔁 Looping entire queue", "off": "Loop disabled"}
        await interaction.response.send_message(labels[mode])

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        if not q.queue:
            await interaction.response.send_message("❌ Queue is empty.", ephemeral=True)
            return
        q.shuffle()
        await interaction.response.send_message(f"🔀 Shuffled {len(q.queue)} songs.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
