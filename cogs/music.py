"""
WAN Bot - Music Cog
- /play: plays immediately, NEVER overrides current song (adds to queue if playing)
- /stay: 24/7 mode, bot never leaves, autoplays by genre/artist/tags (not title)
- Autoplay: uses artist + genre + tags from metadata, NOT song title search
- Dedup: never repeats same URL or title
- Dashboard: broadcasts every song change via websocket
- _reconnect: rejoins VC every 30s if disconnected in stay mode
- _watchdog: restarts playback every 20s if silent (not 15s — less aggressive)
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import yt_dlp
import asyncio
import logging
import random
import json
import os
import re
from collections import deque

log = logging.getLogger("discord_bot.music")
PERSIST = "music_247.json"

YTDL_OPTS = {
    "format": "bestaudio/best",
    "nocheckcertificate": True,
    "ignoreerrors": True,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
    "noplaylist": True,
    "socket_timeout": 30,
}

FFMPEG = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -ar 48000 -ac 2",
}

YT_CLIENTS = [["android_embedded"], ["android_music"], ["ios"], ["mweb"]]

# Generic fallback seeds — only used when there's zero history
SEEDS = [
    "top hits 2024", "popular songs mix", "best music 2024",
    "hip hop mix 2024", "pop hits mix", "chill music mix",
    "bollywood hits mix", "punjabi songs mix", "trending music 2024",
]


# ─────────────────────────────────────────────────────────────────────────────
# Extraction helpers  (all blocking — run in executor)
# ─────────────────────────────────────────────────────────────────────────────

def _is_url(q: str) -> bool:
    return q.startswith(("http://", "https://", "www."))

def _ydl_single(opts: dict, query: str) -> dict | None:
    """Run yt-dlp and return first valid entry with a stream URL."""
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            d = ydl.extract_info(query, download=False)
        if not d:
            return None
        if d.get("url"):
            return d
        for e in d.get("entries", []):
            if e and e.get("url"):
                return e
    except Exception:
        pass
    return None

def _ydl_list(opts: dict, query: str) -> list[dict]:
    """Run yt-dlp and return all valid entries."""
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            d = ydl.extract_info(query, download=False)
        if not d:
            return []
        if d.get("url"):
            return [d]
        return [e for e in d.get("entries", []) if e and e.get("url")]
    except Exception:
        return []

def _fetch(query: str) -> dict | None:
    """Fetch one playable track. SoundCloud first, then YouTube."""
    if _is_url(query):
        if "youtube.com" in query or "youtu.be" in query:
            for c in YT_CLIENTS:
                r = _ydl_single({**YTDL_OPTS, "extractor_args": {"youtube": {"player_client": c}}}, query)
                if r:
                    return r
        return _ydl_single(YTDL_OPTS, query)
    # Text search — SoundCloud first (no IP blocks on cloud servers)
    r = _ydl_single(YTDL_OPTS, f"scsearch1:{query}")
    if r:
        return r
    for c in YT_CLIENTS:
        r = _ydl_single({**YTDL_OPTS, "extractor_args": {"youtube": {"player_client": c}}}, f"ytsearch1:{query}")
        if r:
            return r
    return None

def _smart_queries(data: dict) -> list[str]:
    """
    Build search queries from song METADATA (artist, genre, tags).
    This is what makes autoplay feel like Spotify recommendations —
    it finds songs of the same genre/artist, NOT the same title.
    """
    queries = []

    # Extract artist — prefer explicit field, fall back to uploader/channel
    artist = (data.get("artist") or data.get("uploader") or data.get("channel") or "").strip()
    # Strip YouTube channel suffixes
    artist = re.sub(r"\s*[-–]\s*(topic|vevo|official|music|records?|tv)\s*$", "", artist, flags=re.IGNORECASE).strip()

    genre  = (data.get("genre") or "").strip()
    tags   = [t for t in (data.get("tags") or [])
              if t and len(t) > 2
              and t.lower() not in {"music","song","official","video","audio","lyrics","hd","4k","mv"}][:4]

    # Priority 1: same artist (most relevant)
    if artist and len(artist) > 1:
        queries += [f"{artist} best songs", f"{artist} top tracks", f"{artist} mix"]

    # Priority 2: genre
    if genre:
        queries += [f"best {genre} songs", f"{genre} music mix 2024"]

    # Priority 3: tags
    for tag in tags[:2]:
        queries.append(f"{tag} music mix")

    # Priority 4: artist + genre combo
    if artist and genre:
        queries.append(f"{artist} {genre} songs")

    # Fallback: if we have nothing, use a few words from the title (not the full title)
    if not queries:
        title = data.get("title") or ""
        core = re.sub(
            r"\(.*?\)|\[.*?\]|official\s*(video|audio|mv)?|lyrics?|ft\.?\s*[\w\s,&]+|feat\.?\s*[\w\s,&]+|\d{4}",
            "", title, flags=re.IGNORECASE
        ).strip()
        words = [w for w in core.split() if len(w) > 2][:3]
        if words:
            queries.append(" ".join(words) + " similar songs")

    return queries

def _fetch_similar(data: dict, skip_urls: set, skip_titles: set) -> dict | None:
    """
    Find a song similar to `data` by genre/artist/tags.
    Returns a random unseen result, never the same song.
    """
    def unseen(e) -> bool:
        if not e or not e.get("url"):
            return False
        url   = e.get("webpage_url") or e.get("url", "")
        title = (e.get("title") or "").lower().strip()
        return url not in skip_urls and title not in skip_titles

    queries = _smart_queries(data)
    random.shuffle(queries)  # vary which query we try first each time

    for query in queries:
        # SoundCloud pool (8 results, pick random unseen)
        try:
            entries = _ydl_list({**YTDL_OPTS, "noplaylist": False}, f"scsearch8:{query}")
            pool = [e for e in entries if unseen(e)]
            if pool:
                pick = random.choice(pool)
                log.info(f"[autoplay] SC '{pick.get('title')}' via '{query}'")
                return pick
        except Exception as ex:
            log.debug(f"[autoplay] SC error '{query}': {ex}")

        # YouTube pool (8 results, pick random unseen)
        for c in YT_CLIENTS:
            try:
                entries = _ydl_list(
                    {**YTDL_OPTS, "noplaylist": False, "extractor_args": {"youtube": {"player_client": c}}},
                    f"ytsearch8:{query}"
                )
                pool = [e for e in entries if unseen(e)]
                if pool:
                    pick = random.choice(pool)
                    log.info(f"[autoplay] YT '{pick.get('title')}' via '{query}'")
                    return pick
                break  # one YT client per query is enough
            except Exception as ex:
                log.debug(f"[autoplay] YT error '{query}': {ex}")

    log.info("[autoplay] no similar found, falling back to random seed")
    return _fetch(random.choice(SEEDS))

def _fmt(sec) -> str:
    if not sec:
        return "?"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# Song & Queue
# ─────────────────────────────────────────────────────────────────────────────

class Song:
    def __init__(self, data: dict, volume: float = 0.5, requester=None):
        self.data      = data                                        # full metadata for similarity
        self.title     = data.get("title", "Unknown")
        self.url       = data.get("webpage_url") or data.get("url", "")
        self.stream    = data.get("url", "")                        # direct stream URL
        self.thumbnail = data.get("thumbnail")
        self.duration  = data.get("duration", 0)
        self.volume    = volume
        self.requester = requester

    def source(self) -> discord.PCMVolumeTransformer:
        return discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(self.stream, **FFMPEG),
            volume=self.volume
        )


class GuildQueue:
    def __init__(self):
        self._q:          deque      = deque()
        self.current:     Song|None  = None
        self.loop_song:   bool       = False
        self.loop_queue:  bool       = False
        self.history:     deque      = deque(maxlen=50)
        self.seen_urls:   set        = set()
        self.seen_titles: set        = set()

    # ── public ────────────────────────────────────────────────────────────────

    def add(self, song: Song):
        self._q.append(song)

    def advance(self) -> Song | None:
        """Move to next song. Records current as played. Returns next or None."""
        if self.loop_song and self.current:
            return self.current
        self._record(self.current)
        if self.loop_queue and self.current:
            self._q.append(self.current)
        if self._q:
            self.current = self._q.popleft()
            return self.current
        self.current = None
        return None

    def clear(self):
        self._q.clear()
        self.current = None

    def shuffle(self):
        lst = list(self._q); random.shuffle(lst); self._q = deque(lst)

    def mark_seen(self, song: Song):
        """Call when a song starts playing so autoplay never picks it again."""
        if song.url:
            self.seen_urls.add(song.url)
        if song.title:
            self.seen_titles.add(song.title.lower().strip())
        # trim to avoid unbounded growth
        if len(self.seen_urls) > 400:
            self.seen_urls = set(list(self.seen_urls)[-200:])
        if len(self.seen_titles) > 400:
            self.seen_titles = set(list(self.seen_titles)[-200:])

    def __len__(self):
        return len(self._q)

    # ── private ───────────────────────────────────────────────────────────────

    def _record(self, song: Song | None):
        if not song:
            return
        self.history.append(song)
        self.mark_seen(song)


# ─────────────────────────────────────────────────────────────────────────────
# Music Cog
# ─────────────────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._queues:  dict[int, GuildQueue]    = {}
        self._volumes: dict[int, float]         = {}
        self._stay:    dict[int, dict]          = {}   # {channel_id, text_channel_id}
        self._locks:   dict[int, asyncio.Lock]  = {}
        self._load_stay()
        self._reconnect_task.start()
        self._watchdog_task.start()

    def cog_unload(self):
        self._reconnect_task.cancel()
        self._watchdog_task.cancel()

    # ── persistence ───────────────────────────────────────────────────────────

    def _load_stay(self):
        try:
            if os.path.exists(PERSIST):
                with open(PERSIST) as f:
                    raw = json.load(f)
                self._stay = {
                    int(k): v if isinstance(v, dict) else {"channel_id": int(v), "text_channel_id": int(v)}
                    for k, v in raw.items()
                }
        except Exception:
            self._stay = {}

    def _save_stay(self):
        try:
            with open(PERSIST, "w") as f:
                json.dump({str(k): v for k, v in self._stay.items()}, f)
        except Exception:
            pass

    # ── internal helpers ──────────────────────────────────────────────────────

    def _q(self, gid: int) -> GuildQueue:
        if gid not in self._queues:
            self._queues[gid] = GuildQueue()
        return self._queues[gid]

    def _vol(self, gid: int) -> float:
        return self._volumes.get(gid, 0.5)

    def _lock(self, gid: int) -> asyncio.Lock:
        if gid not in self._locks:
            self._locks[gid] = asyncio.Lock()
        return self._locks[gid]

    async def _join_vc(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
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
            await interaction.followup.send(f"❌ Cannot join VC: {e}", ephemeral=True)
            return None

    def _broadcast(self, gid: int, title: str, thumbnail: str | None, queue_size: int):
        """Push music update to dashboard websocket."""
        try:
            from web_dashboard_enhanced import broadcast_update
            broadcast_update("music_update", {
                "guild_id": str(gid),
                "action": "now_playing",
                "title": title,
                "thumbnail": thumbnail,
                "queue_size": queue_size,
            })
        except Exception:
            pass

    async def _send_now_playing(self, gid: int, song: Song):
        """Send now-playing embed to text channel + broadcast to dashboard."""
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{song.title}]({song.url})",
            color=0x1db954,
        )
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        embed.add_field(name="Duration", value=_fmt(song.duration))
        if song.requester:
            embed.add_field(name="Requested by", value=song.requester.mention)
        else:
            embed.set_footer(text="🤖 Autoplay")

        info = self._stay.get(gid)
        if info:
            ch = self.bot.get_channel(info.get("text_channel_id", 0))
            if ch:
                try:
                    await ch.send(embed=embed)
                except Exception:
                    pass

        q = self._q(gid)
        self._broadcast(gid, song.title, song.thumbnail, len(q))

    # ── background tasks ──────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _reconnect_task(self):
        """Rejoin VC if disconnected in stay mode."""
        for gid, info in list(self._stay.items()):
            guild = self.bot.get_guild(gid)
            if not guild:
                continue
            vc = guild.voice_client
            if vc and vc.is_connected():
                continue
            ch = guild.get_channel(info["channel_id"])
            if not ch:
                continue
            try:
                vc = await ch.connect(timeout=15.0, reconnect=True)
                log.info(f"[stay] Rejoined {ch.name} in {guild.name}")
                await asyncio.sleep(2)
                if not vc.is_playing() and not self._lock(gid).locked():
                    asyncio.ensure_future(self._autoplay(guild, vc))
            except Exception as e:
                log.warning(f"[stay] Rejoin failed {guild.name}: {e}")

    @_reconnect_task.before_loop
    async def _before_reconnect(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=20)
    async def _watchdog_task(self):
        """If connected but silent in stay mode, restart playback."""
        for gid in list(self._stay.keys()):
            guild = self.bot.get_guild(gid)
            if not guild:
                continue
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                continue
            if vc.is_playing() or vc.is_paused():
                continue
            if self._lock(gid).locked():
                continue
            q = self._q(gid)
            if len(q) > 0:
                asyncio.ensure_future(self._play_next(guild, vc))
            else:
                asyncio.ensure_future(self._autoplay(guild, vc))

    @_watchdog_task.before_loop
    async def _before_watchdog(self):
        await self.bot.wait_until_ready()

    # ── playback core ─────────────────────────────────────────────────────────

    def _after_song(self, err, guild: discord.Guild, vc: discord.VoiceClient):
        """Called by discord.py when a song finishes. Schedules next song."""
        if err:
            log.error(f"[{guild.name}] Playback error: {err}")
        asyncio.run_coroutine_threadsafe(self._play_next(guild, vc), self.bot.loop)

    async def _play_next(self, guild: discord.Guild, vc: discord.VoiceClient):
        """Advance queue. If empty and stay mode on, trigger autoplay."""
        q = self._q(guild.id)
        song = q.advance()
        if song:
            await self._start(guild, vc, song)
        elif guild.id in self._stay:
            await self._autoplay(guild, vc)

    async def _start(self, guild: discord.Guild, vc: discord.VoiceClient, song: Song):
        """
        Start playing a song. Does NOT call vc.stop() first — that would
        trigger _after_song and cause a race condition. The caller is
        responsible for ensuring nothing is playing before calling this.
        """
        if not vc or not vc.is_connected():
            return

        q = self._q(guild.id)
        q.current = song
        q.mark_seen(song)  # mark seen so autoplay never picks it again
        song.volume = self._vol(guild.id)

        try:
            vc.play(song.source(), after=lambda e: self._after_song(e, guild, vc))
            asyncio.ensure_future(self._send_now_playing(guild.id, song))
        except Exception as e:
            log.error(f"[{guild.name}] _start error: {e}")
            # Stream URL likely expired — refetch
            asyncio.ensure_future(self._refetch_and_start(guild, vc, song))

    async def _refetch_and_start(self, guild: discord.Guild, vc: discord.VoiceClient, song: Song):
        """Re-extract stream URL for a song whose URL expired."""
        try:
            loop = asyncio.get_event_loop()
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: _fetch(song.url or song.title)),
                timeout=60,
            )
            if data:
                new_song = Song(data, self._vol(guild.id), song.requester)
                await self._start(guild, vc, new_song)
            else:
                await self._autoplay(guild, vc)
        except Exception as e:
            log.error(f"[{guild.name}] _refetch error: {e}")
            await self._autoplay(guild, vc)

    async def _autoplay(self, guild: discord.Guild, vc: discord.VoiceClient):
        """
        Pick a song similar to the last played (by genre/artist/tags) and play it.
        Uses a per-guild lock so only one autoplay runs at a time.
        """
        if not vc or not vc.is_connected():
            return

        lk = self._lock(guild.id)
        if lk.locked():
            return

        async with lk:
            # Double-check — something may have started while we waited
            if vc.is_playing() or vc.is_paused():
                return

            q = self._q(guild.id)
            # Use most recent history for seed data
            seed_data = None
            if q.history:
                seed_data = q.history[-1].data
            elif q.current:
                seed_data = q.current.data

            loop = asyncio.get_event_loop()

            for attempt in range(4):
                try:
                    seen_u = set(q.seen_urls)
                    seen_t = set(q.seen_titles)

                    if seed_data:
                        log.info(f"[autoplay] attempt {attempt+1} — similar to '{seed_data.get('title')}'")
                        data = await asyncio.wait_for(
                            loop.run_in_executor(None, lambda: _fetch_similar(seed_data, seen_u, seen_t)),
                            timeout=90,
                        )
                    else:
                        s = random.choice(SEEDS)
                        log.info(f"[autoplay] attempt {attempt+1} — random seed '{s}'")
                        data = await asyncio.wait_for(
                            loop.run_in_executor(None, lambda: _fetch(s)),
                            timeout=60,
                        )

                    if not data:
                        seed_data = None
                        continue

                    # Dedup check
                    raw_url   = data.get("webpage_url") or data.get("url", "")
                    raw_title = (data.get("title") or "").lower().strip()
                    if raw_url in q.seen_urls or raw_title in q.seen_titles:
                        log.info(f"[autoplay] dedup skip '{data.get('title')}'")
                        seed_data = data  # use as new seed
                        continue

                    song = Song(data, self._vol(guild.id))
                    await self._start(guild, vc, song)
                    return

                except asyncio.TimeoutError:
                    log.warning(f"[autoplay] timeout attempt {attempt+1}")
                    seed_data = None
                except Exception as e:
                    log.error(f"[autoplay] error attempt {attempt+1}: {e}")
                    seed_data = None

            log.error(f"[autoplay] gave up for guild {guild.id}")

    # ── slash commands ────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a song or search query")
    @app_commands.describe(query="Song name, URL, or search query")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = await self._join_vc(interaction)
        if not vc:
            return
        loop = asyncio.get_event_loop()
        try:
            data = await asyncio.wait_for(loop.run_in_executor(None, lambda: _fetch(query)), timeout=60)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Search timed out. Try a more specific query.")
            return
        if not data:
            await interaction.followup.send(f"❌ Nothing found for `{query}`")
            return

        song = Song(data, self._vol(interaction.guild_id), interaction.user)
        q = self._q(interaction.guild_id)

        if vc.is_playing() or vc.is_paused():
            # Something is already playing — add to queue, do NOT interrupt
            q.add(song)
            embed = discord.Embed(title="➕ Added to Queue", description=f"[{song.title}]({song.url})", color=0x5865f2)
            embed.add_field(name="Position", value=str(len(q)))
            embed.add_field(name="Duration", value=_fmt(song.duration))
            await interaction.followup.send(embed=embed)
        else:
            # Nothing playing — start immediately
            await self._start(interaction.guild, vc, song)
            await interaction.followup.send(f"▶️ Playing **{song.title}**")

    @app_commands.command(name="playlist", description="Load a YouTube/SoundCloud playlist")
    @app_commands.describe(url="Playlist URL")
    async def playlist(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        vc = await self._join_vc(interaction)
        if not vc:
            return
        await interaction.followup.send("⏳ Loading playlist…")
        def _get():
            opts = {**YTDL_OPTS, "noplaylist": False, "playlistend": 50,
                    "extractor_args": {"youtube": {"player_client": ["android_embedded"]}}}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    d = ydl.extract_info(url, download=False)
                if not d:
                    return []
                return [e for e in d.get("entries", [d]) if e and e.get("url")]
            except Exception as e:
                log.warning(f"Playlist error: {e}")
                return []
        loop = asyncio.get_event_loop()
        try:
            entries = await asyncio.wait_for(loop.run_in_executor(None, _get), timeout=90)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Playlist load timed out.")
            return
        if not entries:
            await interaction.followup.send("❌ No playable tracks found.")
            return
        q = self._q(interaction.guild_id)
        for e in entries:
            q.add(Song(e, self._vol(interaction.guild_id), interaction.user))
        await interaction.followup.send(f"✅ Added **{len(entries)}** tracks.")
        if not vc.is_playing() and not vc.is_paused():
            song = q.advance()
            if song:
                await self._start(interaction.guild, vc, song)

    @app_commands.command(name="stay", description="Toggle 24/7 mode — bot never leaves, autoplays forever")
    async def stay(self, interaction: discord.Interaction):
        await interaction.response.defer()
        gid = interaction.guild_id
        if gid in self._stay:
            del self._stay[gid]
            self._save_stay()
            await interaction.followup.send("⏹️ 24/7 mode **disabled**.")
        else:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("❌ Join a voice channel first.")
                return
            vc = await self._join_vc(interaction)
            if not vc:
                return
            self._stay[gid] = {
                "channel_id": vc.channel.id,
                "text_channel_id": interaction.channel_id,
            }
            self._save_stay()
            await interaction.followup.send(
                f"✅ 24/7 mode **enabled** in {vc.channel.mention}.\n"
                "Bot will never leave and autoplay similar songs forever."
            )
            if not vc.is_playing() and not vc.is_paused():
                asyncio.ensure_future(self._autoplay(interaction.guild, vc))

    @app_commands.command(name="leave", description="Disconnect from voice channel")
    async def leave(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.followup.send("❌ Not in a voice channel.")
            return
        self._stay.pop(interaction.guild_id, None)
        self._save_stay()
        self._q(interaction.guild_id).clear()
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
        q = self._q(interaction.guild_id)
        title = q.current.title if q.current else "Unknown"
        if vc.is_paused():
            vc.resume()  # must resume before stop so after-callback fires
        vc.stop()        # triggers _after_song → _play_next
        await interaction.followup.send(f"⏭️ Skipped **{title}**")

    @app_commands.command(name="stop", description="Stop music and clear queue")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        self._q(interaction.guild_id).clear()
        if vc and vc.is_playing():
            vc.stop()
        await interaction.followup.send("⏹️ Stopped and queue cleared.")

    @app_commands.command(name="nowplaying", description="Show current song info")
    async def nowplaying(self, interaction: discord.Interaction):
        q = self._q(interaction.guild_id)
        s = q.current
        if not s:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
            return
        embed = discord.Embed(title="🎵 Now Playing", description=f"[{s.title}]({s.url})", color=0x1db954)
        if s.thumbnail:
            embed.set_thumbnail(url=s.thumbnail)
        embed.add_field(name="Duration", value=_fmt(s.duration))
        if s.requester:
            embed.add_field(name="Requested by", value=s.requester.mention)
        loop_s = "🔂 Song" if q.loop_song else ("🔁 Queue" if q.loop_queue else "Off")
        embed.add_field(name="Loop", value=loop_s)
        embed.add_field(name="Queue", value=f"{len(q)} songs")
        embed.set_footer(text=f"{'🟢 24/7 ON' if interaction.guild_id in self._stay else '⚪ 24/7 OFF'}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="queue", description="Show the music queue")
    async def show_queue(self, interaction: discord.Interaction):
        q = self._q(interaction.guild_id)
        if not q.current and not q._q:
            await interaction.response.send_message("📭 Queue is empty.", ephemeral=True)
            return
        lines = []
        if q.current:
            lines.append(f"**▶ Now:** {q.current.title} `[{_fmt(q.current.duration)}]`")
        for i, s in enumerate(list(q._q)[:15], 1):
            lines.append(f"`{i}.` {s.title} `[{_fmt(s.duration)}]`")
        if len(q) > 15:
            lines.append(f"… and {len(q) - 15} more")
        embed = discord.Embed(title=f"🎶 Queue — {len(q)} songs", description="\n".join(lines), color=0x5865f2)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set volume 0-100")
    @app_commands.describe(level="Volume level 0-100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            await interaction.response.send_message("❌ Must be 0-100.", ephemeral=True)
            return
        self._volumes[interaction.guild_id] = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = level / 100
        await interaction.response.send_message(f"🔊 Volume → **{level}%**")

    @app_commands.command(name="loop", description="Toggle loop mode")
    @app_commands.describe(mode="song / queue / off")
    @app_commands.choices(mode=[
        app_commands.Choice(name="song",  value="song"),
        app_commands.Choice(name="queue", value="queue"),
        app_commands.Choice(name="off",   value="off"),
    ])
    async def loop(self, interaction: discord.Interaction, mode: str):
        q = self._q(interaction.guild_id)
        q.loop_song  = (mode == "song")
        q.loop_queue = (mode == "queue")
        msgs = {"song": "🔂 Looping current song", "queue": "🔁 Looping queue", "off": "Loop off"}
        await interaction.response.send_message(msgs[mode])

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        q = self._q(interaction.guild_id)
        if not q._q:
            await interaction.response.send_message("❌ Queue is empty.", ephemeral=True)
            return
        q.shuffle()
        await interaction.response.send_message(f"🔀 Shuffled {len(q)} songs.")

    @app_commands.command(name="radio", description="Play a 24/7 radio station")
    @app_commands.describe(station="lofi / jazz / classical / electronic / chill")
    @app_commands.choices(station=[
        app_commands.Choice(name="lofi",       value="lofi"),
        app_commands.Choice(name="jazz",       value="jazz"),
        app_commands.Choice(name="classical",  value="classical"),
        app_commands.Choice(name="electronic", value="electronic"),
        app_commands.Choice(name="chill",      value="chill"),
    ])
    async def radio(self, interaction: discord.Interaction, station: str = "lofi"):
        urls = {
            "lofi":       "https://www.youtube.com/watch?v=jfKfPfyJRdk",
            "jazz":       "https://www.youtube.com/watch?v=neV3EPgvZ3g",
            "classical":  "https://www.youtube.com/watch?v=EhO_MrRfftU",
            "electronic": "https://www.youtube.com/watch?v=4xDzrJKXOOY",
            "chill":      "https://www.youtube.com/watch?v=5qap5aO4i9A",
        }
        await interaction.response.defer()
        vc = await self._join_vc(interaction)
        if not vc:
            return
        loop = asyncio.get_event_loop()
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: _fetch(urls.get(station, urls["lofi"]))),
                timeout=60
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Timed out loading radio.")
            return
        if not data:
            await interaction.followup.send("❌ Could not load radio.")
            return
        song = Song(data, self._vol(interaction.guild_id), interaction.user)
        q = self._q(interaction.guild_id)
        if vc.is_playing() or vc.is_paused():
            q.add(song)
            await interaction.followup.send(f"📻 Added **{station}** radio to queue.")
        else:
            await self._start(interaction.guild, vc, song)
            await interaction.followup.send(f"📻 Playing **{station}** radio.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
