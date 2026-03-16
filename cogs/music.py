"""
WAN Bot - Music Cog v6
- /stay  : bot locks to VC forever, autoplays similar songs, NEVER leaves
- NO manual reconnect logic — discord.py reconnect=True handles it natively
- Watchdog only restarts PLAYBACK (not connection) — no more 4017 errors
- Dedup by URL + title — same song never plays twice in a row
- SoundCloud primary, YouTube fallback
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

logger = logging.getLogger("discord_bot.music")
PERSIST_FILE = "music_247.json"

# ── yt-dlp options ────────────────────────────────────────────────────────────
YTDL_BASE = {
    "format": "bestaudio/best",
    "nocheckcertificate": True,
    "ignoreerrors": True,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
    "noplaylist": True,
    "socket_timeout": 30,
}

_COOKIES_FILE = os.path.join(os.path.dirname(__file__), "..", "youtube_cookies.txt")
if os.getenv("YOUTUBE_COOKIES"):
    try:
        with open(_COOKIES_FILE, "w") as _f:
            _f.write(os.getenv("YOUTUBE_COOKIES"))
    except Exception:
        pass
if os.path.exists(_COOKIES_FILE):
    YTDL_BASE["cookiefile"] = os.path.abspath(_COOKIES_FILE)

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -af aresample=48000",
}

_YT_CLIENTS = [["android_embedded"], ["android_music"], ["ios"], ["mweb"]]

_SEEDS = [
    "top hits 2024", "popular songs 2024", "best music mix",
    "hip hop hits 2024", "pop hits 2024", "r&b hits 2024",
    "chill vibes music", "electronic music mix", "workout music",
    "bollywood hits 2024", "punjabi songs 2024", "trending songs 2024",
]


# ── Extraction helpers ────────────────────────────────────────────────────────

def _is_url(q: str) -> bool:
    return q.startswith(("http://", "https://", "www."))

def _clean_yt_url(url: str) -> str:
    import urllib.parse as up
    p = up.urlparse(url)
    qs = up.parse_qs(p.query)
    if "youtube.com/watch" in url and "v" in qs:
        return up.urlunparse(p._replace(query=up.urlencode({"v": qs["v"][0]})))
    return url

def _ydl_extract(opts: dict, query: str):
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(query, download=False)
        if not data:
            return None
        if data.get("url"):
            return data
        entries = [e for e in data.get("entries", []) if e and e.get("url")]
        return entries[0] if entries else None
    except Exception:
        return None

def _extract(query: str):
    """Fetch one track. SoundCloud first, then YouTube."""
    if _is_url(query):
        url = _clean_yt_url(query)
        if "youtube.com" in url or "youtu.be" in url:
            for clients in _YT_CLIENTS:
                r = _ydl_extract(
                    {**YTDL_BASE, "extractor_args": {"youtube": {"player_client": clients}}}, url
                )
                if r:
                    return r
        return _ydl_extract(YTDL_BASE, url)
    r = _ydl_extract(YTDL_BASE, f"scsearch1:{query}")
    if r:
        return r
    for clients in _YT_CLIENTS:
        r = _ydl_extract(
            {**YTDL_BASE, "extractor_args": {"youtube": {"player_client": clients}}},
            f"ytsearch1:{query}",
        )
        if r:
            return r
    return None

def _extract_similar(seed_title: str, exclude_urls: set, exclude_titles: set):
    clean = re.sub(
        r"\(.*?\)|\[.*?\]|official\s*(video|audio|mv)?|lyrics?|hd|4k|"
        r"ft\.?\s*\w+|feat\.?\s*\w+|\d{4}",
        "", seed_title, flags=re.IGNORECASE,
    ).strip()
    if len(clean) < 3:
        clean = seed_title

    def _unseen(e) -> bool:
        if not e or not e.get("url"):
            return False
        url = e.get("webpage_url") or e.get("url", "")
        title = (e.get("title") or "").lower().strip()
        return url not in exclude_urls and title not in exclude_titles

    for n in (8, 5, 3):
        try:
            opts = {**YTDL_BASE, "noplaylist": False}
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(f"scsearch{n}:{clean}", download=False)
            if data and "entries" in data:
                pool = [e for e in data["entries"] if _unseen(e)]
                if pool:
                    return random.choice(pool)
        except Exception:
            pass

    for clients in _YT_CLIENTS:
        try:
            opts = {**YTDL_BASE, "noplaylist": False,
                    "extractor_args": {"youtube": {"player_client": clients}}}
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(f"ytsearch5:{clean}", download=False)
            if data and "entries" in data:
                pool = [e for e in data["entries"] if _unseen(e)]
                if pool:
                    return random.choice(pool)
        except Exception:
            continue

    return _extract(random.choice(_SEEDS))

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
        self.loop = False
        self.loop_queue = False
        self.history: deque = deque(maxlen=50)
        self.played_urls: set = set()
        self.played_titles: set = set()

    def add(self, song):
        self.queue.append(song)

    def record_played(self, song):
        if not song:
            return
        self.history.append(song)
        url = song.url or ""
        title = (song.title or "").lower().strip()
        if url:
            self.played_urls.add(url)
        if title:
            self.played_titles.add(title)
        if len(self.played_urls) > 200:
            self.played_urls = set(list(self.played_urls)[-100:])
        if len(self.played_titles) > 200:
            self.played_titles = set(list(self.played_titles)[-100:])

    def advance(self):
        if self.loop and self.current:
            return self.current
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

    def clear(self):
        self.queue.clear()
        self.current = None


# ── YTDLSource ────────────────────────────────────────────────────────────────

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title", "Unknown")
        self.url = data.get("webpage_url") or data.get("url", "")
        self.thumbnail = data.get("thumbnail")
        self.duration = data.get("duration", 0)
        self.requester = None

    @classmethod
    async def from_data(cls, data: dict, volume: float = 0.5) -> "YTDLSource":
        src = discord.FFmpegPCMAudio(data["url"], **FFMPEG_OPTS)
        return cls(src, data=data, volume=volume)

    @classmethod
    async def from_query(cls, query: str, *, loop=None, volume=0.5) -> "YTDLSource":
        loop = loop or asyncio.get_event_loop()
        data = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _extract(query)),
            timeout=60.0,
        )
        if not data:
            raise ValueError(f"No results for: {query}")
        return await cls.from_data(data, volume)

    @classmethod
    async def from_playlist(cls, url: str, *, loop=None, volume=0.5):
        loop = loop or asyncio.get_event_loop()
        def _get():
            opts = {**YTDL_BASE, "noplaylist": False, "playlistend": 50,
                    "extractor_args": {"youtube": {"player_client": ["android_embedded"]}}}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    data = ydl.extract_info(url, download=False)
                if not data:
                    return []
                return [e for e in data.get("entries", [data]) if e and e.get("url")]
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
    """24/7 music — autoplay similar songs, never repeats, never leaves VC."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._queues: dict[int, MusicQueue] = {}
        self._volumes: dict[int, float] = {}
        self._stay: dict[int, dict] = {}
        self._autoplay_locks: dict[int, asyncio.Lock] = {}
        self._load_stay()
        self._watchdog.start()

    def cog_unload(self):
        self._watchdog.cancel()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_stay(self):
        try:
            if os.path.exists(PERSIST_FILE):
                with open(PERSIST_FILE) as f:
                    raw = json.load(f)
                migrated = {}
                for k, v in raw.items():
                    if isinstance(v, dict):
                        migrated[int(k)] = v
                    else:
                        migrated[int(k)] = {"channel_id": int(v), "text_channel_id": int(v)}
                self._stay = migrated
        except Exception:
            self._stay = {}

    def _save_stay(self):
        try:
            with open(PERSIST_FILE, "w") as f:
                json.dump({str(k): v for k, v in self._stay.items()}, f)
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

    async def _ensure_voice(self, interaction: discord.Interaction):
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

    async def _broadcast_now_playing(self, guild_id: int, song: "YTDLSource"):
        info = self._stay.get(guild_id)
        if not info:
            return
        ch = self.bot.get_channel(info.get("text_channel_id", 0))
        if not ch:
            return
        try:
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"[{song.title}]({song.url})",
                color=discord.Color.green(),
            )
            if song.thumbnail:
                embed.set_thumbnail(url=song.thumbnail)
            embed.add_field(name="Duration", value=_fmt(song.duration))
            if song.requester:
                embed.add_field(name="Requested by", value=song.requester.mention)
            else:
                embed.set_footer(text="🤖 Autoplay")
            await ch.send(embed=embed)
        except Exception:
            pass

    # ── Watchdog: ONLY restarts playback, never reconnects ────────────────────
    # The 4017 "already authenticated" error was caused by our code AND discord.py
    # both trying to connect at the same time. Solution: let discord.py handle
    # all reconnection (reconnect=True does this). We only restart PLAYBACK here.

    @tasks.loop(seconds=30)
    async def _watchdog(self):
        for guild_id in list(self._stay.keys()):
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            vc = guild.voice_client
            # Only act if we're connected — never try to reconnect manually
            if not vc or not vc.is_connected():
                continue
            if vc.is_playing() or vc.is_paused():
                continue
            # Connected but silent → restart autoplay
            q = self.get_queue(guild_id)
            lock = self._get_lock(guild_id)
            if lock.locked():
                continue
            if q.queue:
                asyncio.ensure_future(self._play_next_async(guild, vc))
            else:
                asyncio.ensure_future(self._autoplay_next(guild, vc))

    @_watchdog.before_loop
    async def _before_watchdog(self):
        await self.bot.wait_until_ready()

    # ── on_voice_state_update: ONLY restart playback after reconnect ──────────
    # We do NOT call vc.connect() here — discord.py's reconnect=True already
    # handles reconnection automatically. We just need to restart playback
    # once the bot is back in the channel.

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member,
        before: discord.VoiceState, after: discord.VoiceState
    ):
        if member.id != self.bot.user.id:
            return
        guild_id = member.guild.id
        if guild_id not in self._stay:
            return

        # Bot just joined/rejoined a channel (after.channel is set)
        if after.channel is not None and before.channel != after.channel:
            # Give discord.py a moment to fully establish the connection
            await asyncio.sleep(1.0)
            vc = member.guild.voice_client
            if vc and vc.is_connected() and not vc.is_playing():
                logger.info(f"[stay] Back in {after.channel.name}, restarting playback")
                asyncio.ensure_future(self._autoplay_next(member.guild, vc))

    # ── Playback core ─────────────────────────────────────────────────────────

    def _after_song(self, err, guild: discord.Guild, vc: discord.VoiceClient):
        if err:
            logger.error(f"Playback error in {guild.name}: {err}")
        asyncio.run_coroutine_threadsafe(
            self._play_next_async(guild, vc), self.bot.loop
        )

    async def _play_next_async(self, guild: discord.Guild, vc: discord.VoiceClient):
        q = self.get_queue(guild.id)
        next_song = q.advance()
        if next_song:
            await self._start_playing(guild, vc, next_song)
        else:
            await self._autoplay_next(guild, vc)

    async def _start_playing(self, guild: discord.Guild, vc: discord.VoiceClient, song: YTDLSource):
        if not vc or not vc.is_connected():
            return
        if vc.is_playing():
            vc.stop()
        q = self.get_queue(guild.id)
        q.current = song
        try:
            src = discord.FFmpegPCMAudio(song.data["url"], **FFMPEG_OPTS)
            player = discord.PCMVolumeTransformer(src, volume=self.get_volume(guild.id))
            player.data = song.data
            player.title = song.title
            player.url = song.url
            player.thumbnail = song.thumbnail
            player.duration = song.duration
            player.requester = song.requester
            vc.play(player, after=lambda e: self._after_song(e, guild, vc))
            await self._broadcast_now_playing(guild.id, song)
        except Exception as e:
            logger.error(f"_start_playing error in {guild.name}: {e}")
            asyncio.ensure_future(self._refetch_and_play(guild, vc, song))

    async def _refetch_and_play(self, guild: discord.Guild, vc: discord.VoiceClient, song: YTDLSource):
        try:
            loop = asyncio.get_event_loop()
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: _extract(song.url or song.title)),
                timeout=60.0,
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
        if not vc or not vc.is_connected():
            return
        lock = self._get_lock(guild.id)
        if lock.locked():
            return
        async with lock:
            q = self.get_queue(guild.id)
            if vc.is_playing() or vc.is_paused():
                return
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
                                lambda: _extract_similar(seed_title, q.played_urls, q.played_titles),
                            ),
                            timeout=90.0,
                        )
                    else:
                        seed = random.choice(_SEEDS)
                        data = await asyncio.wait_for(
                            loop.run_in_executor(None, lambda: _extract(seed)),
                            timeout=60.0,
                        )
                    if data:
                        song = await YTDLSource.from_data(data, self.get_volume(guild.id))
                        url = song.url or ""
                        title = (song.title or "").lower().strip()
                        if url in q.played_urls or title in q.played_titles:
                            seed_title = song.title
                            continue
                        q.current = song
                        await self._start_playing(guild, vc, song)
                        return
                    seed_title = random.choice(_SEEDS)
                except asyncio.TimeoutError:
                    logger.warning(f"Autoplay timeout attempt {attempt + 1}")
                    seed_title = random.choice(_SEEDS)
                except Exception as e:
                    logger.error(f"Autoplay error attempt {attempt + 1}: {e}")
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
            song = await YTDLSource.from_query(
                query, loop=self.bot.loop, volume=self.get_volume(interaction.guild_id)
            )
            song.requester = interaction.user
        except Exception as e:
            await interaction.followup.send(f"❌ Could not find: `{query}`\n`{e}`")
            return
        if vc.is_playing() or vc.is_paused():
            q.add(song)
            embed = discord.Embed(title="➕ Added to Queue", description=f"[{song.title}]({song.url})", color=discord.Color.blue())
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
        await interaction.followup.send("⏳ Loading playlist…")
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

    @app_commands.command(name="stay", description="Toggle 24/7 stay mode — bot never leaves and autoplays forever")
    async def stay(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild_id = interaction.guild_id
        if guild_id in self._stay:
            del self._stay[guild_id]
            self._save_stay()
            await interaction.followup.send("⏹️ Stay mode **disabled**.")
        else:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("❌ Join a voice channel first.")
                return
            vc = await self._ensure_voice(interaction)
            if not vc:
                return
            self._stay[guild_id] = {
                "channel_id": vc.channel.id,
                "text_channel_id": interaction.channel_id,
            }
            self._save_stay()
            await interaction.followup.send(
                f"✅ Stay mode **enabled** in {vc.channel.mention}.\n"
                "Bot will never leave and will autoplay similar songs forever."
            )
            if not vc.is_playing() and not vc.is_paused():
                asyncio.ensure_future(self._autoplay_next(interaction.guild, vc))

    @app_commands.command(name="leave", description="Disconnect bot from voice channel")
    async def leave(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.followup.send("❌ Not in a voice channel.")
            return
        self._stay.pop(interaction.guild_id, None)
        self._save_stay()
        q = self.get_queue(interaction.guild_id)
        q.clear()
        if vc.is_playing():
            vc.stop()
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
        vc.stop()
        await interaction.followup.send(f"⏭️ Skipped **{title}**")

    @app_commands.command(name="stop", description="Stop music and clear queue")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        q = self.get_queue(interaction.guild_id)
        q.clear()
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
        await interaction.followup.send("⏹️ Stopped and queue cleared.")

    @app_commands.command(name="nowplaying", description="Show current song")
    async def nowplaying(self, interaction: discord.Interaction):
        q = self.get_queue(interaction.guild_id)
        if not q.current:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
            return
        s = q.current
        embed = discord.Embed(title="🎵 Now Playing", description=f"[{s.title}]({s.url})", color=discord.Color.green())
        if s.thumbnail:
            embed.set_thumbnail(url=s.thumbnail)
        embed.add_field(name="Duration", value=_fmt(s.duration))
        if s.requester:
            embed.add_field(name="Requested by", value=s.requester.mention)
        loop_status = "🔂 Song" if q.loop else ("🔁 Queue" if q.loop_queue else "Off")
        embed.add_field(name="Loop", value=loop_status)
        embed.add_field(name="Queue", value=f"{len(q.queue)} songs")
        stay_on = interaction.guild_id in self._stay
        embed.set_footer(text=f"{'🟢 Stay ON' if stay_on else '⚪ Stay OFF'} • Autoplay always on")
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
            lines.append(f"… and {len(q.queue) - 15} more")
        embed = discord.Embed(title=f"🎶 Queue — {len(q.queue)} songs", description="\n".join(lines), color=discord.Color.blurple())
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

    @app_commands.command(name="radio", description="Play a 24/7 radio station")
    @app_commands.describe(station="lofi / jazz / classical / electronic / chill")
    @app_commands.choices(station=[
        app_commands.Choice(name="lofi", value="lofi"),
        app_commands.Choice(name="jazz", value="jazz"),
        app_commands.Choice(name="classical", value="classical"),
        app_commands.Choice(name="electronic", value="electronic"),
        app_commands.Choice(name="chill", value="chill"),
    ])
    async def radio(self, interaction: discord.Interaction, station: str = "lofi"):
        stations = {
            "lofi":       "https://www.youtube.com/watch?v=jfKfPfyJRdk",
            "jazz":       "https://www.youtube.com/watch?v=neV3EPgvZ3g",
            "classical":  "https://www.youtube.com/watch?v=EhO_MrRfftU",
            "electronic": "https://www.youtube.com/watch?v=4xDzrJKXOOY",
            "chill":      "https://www.youtube.com/watch?v=5qap5aO4i9A",
        }
        url = stations.get(station.lower(), stations["lofi"])
        await interaction.response.defer()
        vc = await self._ensure_voice(interaction)
        if not vc:
            return
        try:
            song = await YTDLSource.from_query(url, loop=self.bot.loop, volume=self.get_volume(interaction.guild_id))
            song.requester = interaction.user
        except Exception as e:
            await interaction.followup.send(f"❌ Could not load radio: {e}")
            return
        q = self.get_queue(interaction.guild_id)
        if vc.is_playing() or vc.is_paused():
            q.add(song)
            await interaction.followup.send(f"📻 Added **{station}** radio to queue.")
        else:
            q.current = song
            await self._start_playing(interaction.guild, vc, song)
            await interaction.followup.send(f"📻 Playing **{station}** radio.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
