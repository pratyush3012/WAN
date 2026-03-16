"""
WAN Bot - Music Cog (clean rewrite)
Commands: /play /pause /resume /skip /stop /queue /nowplaying /volume /loop /shuffle /stay /leave /radio
- /stay : 24/7 mode — bot never leaves, autoplays similar songs forever
- _reconnect_loop : rejoins VC every 30s if disconnected in stay mode
- _watchdog : restarts playback every 15s if connected but silent
- SoundCloud first (no IP blocks on cloud), YouTube fallback
- Dedup by URL + title — never repeats
- -ar 48000 -ac 2 for correct audio speed/pitch (Discord expects 48kHz stereo PCM)
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

SEEDS = [
    "top hits 2024", "popular songs 2024", "best music mix",
    "hip hop hits 2024", "pop hits 2024", "chill vibes music",
    "bollywood hits 2024", "punjabi songs 2024", "trending songs 2024",
]


# ── helpers (blocking, run in executor) ──────────────────────────────────────

def _is_url(q):
    return q.startswith(("http://", "https://", "www."))

def _ydl(opts, query):
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            d = ydl.extract_info(query, download=False)
        if not d:
            return None
        if d.get("url"):
            return d
        entries = [e for e in d.get("entries", []) if e and e.get("url")]
        return entries[0] if entries else None
    except Exception:
        return None

def _fetch(query):
    """Fetch one track. SoundCloud first, then YouTube."""
    if _is_url(query):
        if "youtube.com" in query or "youtu.be" in query:
            for c in YT_CLIENTS:
                r = _ydl({**YTDL_OPTS, "extractor_args": {"youtube": {"player_client": c}}}, query)
                if r:
                    return r
        return _ydl(YTDL_OPTS, query)
    # text search
    r = _ydl(YTDL_OPTS, f"scsearch1:{query}")
    if r:
        return r
    for c in YT_CLIENTS:
        r = _ydl({**YTDL_OPTS, "extractor_args": {"youtube": {"player_client": c}}}, f"ytsearch1:{query}")
        if r:
            return r
    return None

def _fetch_similar(seed, skip_urls, skip_titles):
    """Fetch a random unseen song similar to seed."""
    clean = re.sub(
        r"\(.*?\)|\[.*?\]|official\s*(video|audio|mv)?|lyrics?|hd|4k|ft\.?\s*\w+|feat\.?\s*\w+|\d{4}",
        "", seed, flags=re.IGNORECASE
    ).strip() or seed

    def unseen(e):
        if not e or not e.get("url"):
            return False
        return (e.get("webpage_url") or e.get("url", "")) not in skip_urls \
            and (e.get("title") or "").lower().strip() not in skip_titles

    # SoundCloud pool
    for n in (8, 5, 3):
        try:
            d = _ydl({**YTDL_OPTS, "noplaylist": False}, f"scsearch{n}:{clean}")
            if d and "entries" in d:
                pool = [e for e in d["entries"] if unseen(e)]
                if pool:
                    return random.choice(pool)
        except Exception:
            pass

    # YouTube pool
    for c in YT_CLIENTS:
        try:
            d = _ydl({**YTDL_OPTS, "noplaylist": False,
                      "extractor_args": {"youtube": {"player_client": c}}}, f"ytsearch5:{clean}")
            if d and "entries" in d:
                pool = [e for e in d["entries"] if unseen(e)]
                if pool:
                    return random.choice(pool)
        except Exception:
            pass

    return _fetch(random.choice(SEEDS))

def _fmt(sec):
    if not sec:
        return "?"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── Song ──────────────────────────────────────────────────────────────────────

class Song:
    def __init__(self, data, volume=0.5, requester=None):
        self.data = data
        self.title = data.get("title", "Unknown")
        self.url = data.get("webpage_url") or data.get("url", "")
        self.stream = data.get("url", "")
        self.thumbnail = data.get("thumbnail")
        self.duration = data.get("duration", 0)
        self.volume = volume
        self.requester = requester

    def make_source(self):
        src = discord.FFmpegPCMAudio(self.stream, **FFMPEG)
        return discord.PCMVolumeTransformer(src, volume=self.volume)


# ── Queue ─────────────────────────────────────────────────────────────────────

class Queue:
    def __init__(self):
        self._q: deque = deque()
        self.current: Song | None = None
        self.loop_song = False
        self.loop_queue = False
        self.history: deque = deque(maxlen=50)
        self.seen_urls: set = set()
        self.seen_titles: set = set()

    def add(self, song):
        self._q.append(song)

    def next(self):
        if self.loop_song and self.current:
            return self.current
        if self.current:
            self.history.append(self.current)
            u = self.current.url
            t = self.current.title.lower().strip()
            if u:
                self.seen_urls.add(u)
            if t:
                self.seen_titles.add(t)
            if len(self.seen_urls) > 300:
                self.seen_urls = set(list(self.seen_urls)[-150:])
            if len(self.seen_titles) > 300:
                self.seen_titles = set(list(self.seen_titles)[-150:])
            if self.loop_queue:
                self._q.append(self.current)
        if self._q:
            self.current = self._q.popleft()
            return self.current
        self.current = None
        return None

    def shuffle(self):
        lst = list(self._q)
        random.shuffle(lst)
        self._q = deque(lst)

    def clear(self):
        self._q.clear()
        self.current = None

    def __len__(self):
        return len(self._q)


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._queues: dict[int, Queue] = {}
        self._volumes: dict[int, float] = {}
        self._stay: dict[int, dict] = {}          # guild_id -> {channel_id, text_channel_id}
        self._locks: dict[int, asyncio.Lock] = {}
        self._load()
        self._reconnect.start()
        self._watchdog.start()

    def cog_unload(self):
        self._reconnect.cancel()
        self._watchdog.cancel()

    # ── persistence ───────────────────────────────────────────────────────────

    def _load(self):
        try:
            if os.path.exists(PERSIST):
                with open(PERSIST) as f:
                    raw = json.load(f)
                out = {}
                for k, v in raw.items():
                    out[int(k)] = v if isinstance(v, dict) else {"channel_id": int(v), "text_channel_id": int(v)}
                self._stay = out
        except Exception:
            self._stay = {}

    def _save(self):
        try:
            with open(PERSIST, "w") as f:
                json.dump({str(k): v for k, v in self._stay.items()}, f)
        except Exception:
            pass

    # ── helpers ───────────────────────────────────────────────────────────────

    def q(self, gid) -> Queue:
        if gid not in self._queues:
            self._queues[gid] = Queue()
        return self._queues[gid]

    def vol(self, gid) -> float:
        return self._volumes.get(gid, 0.5)

    def lock(self, gid) -> asyncio.Lock:
        if gid not in self._locks:
            self._locks[gid] = asyncio.Lock()
        return self._locks[gid]

    async def _join(self, interaction) -> discord.VoiceClient | None:
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

    async def _announce(self, gid, **kwargs):
        info = self._stay.get(gid)
        if not info:
            return
        ch = self.bot.get_channel(info.get("text_channel_id", 0))
        if ch:
            try:
                await ch.send(**kwargs)
            except Exception:
                pass

    # ── background tasks ──────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _reconnect(self):
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
                await asyncio.sleep(1)
                if not vc.is_playing():
                    asyncio.ensure_future(self._autoplay(guild, vc))
            except Exception as e:
                log.warning(f"[stay] Rejoin failed {guild.name}: {e}")

    @_reconnect.before_loop
    async def _before_reconnect(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=15)
    async def _watchdog(self):
        """Restart playback if connected but silent in stay mode."""
        for gid in list(self._stay.keys()):
            guild = self.bot.get_guild(gid)
            if not guild:
                continue
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                continue
            if vc.is_playing() or vc.is_paused():
                continue
            lk = self.lock(gid)
            if lk.locked():
                continue
            queue = self.q(gid)
            if len(queue) > 0:
                asyncio.ensure_future(self._play_next(guild, vc))
            else:
                asyncio.ensure_future(self._autoplay(guild, vc))

    @_watchdog.before_loop
    async def _before_watchdog(self):
        await self.bot.wait_until_ready()

    # ── playback core ─────────────────────────────────────────────────────────

    def _after(self, err, guild, vc):
        if err:
            log.error(f"Playback error in {guild.name}: {err}")
        asyncio.run_coroutine_threadsafe(self._play_next(guild, vc), self.bot.loop)

    async def _play_next(self, guild, vc):
        queue = self.q(guild.id)
        song = queue.next()
        if song:
            await self._play(guild, vc, song)
        elif guild.id in self._stay:
            await self._autoplay(guild, vc)

    async def _play(self, guild, vc, song: Song):
        if not vc or not vc.is_connected():
            return
        if vc.is_playing():
            vc.stop()
        queue = self.q(guild.id)
        queue.current = song
        song.volume = self.vol(guild.id)
        # Record as seen immediately so autoplay never picks it again
        if song.url:
            queue.seen_urls.add(song.url)
        if song.title:
            queue.seen_titles.add(song.title.lower().strip())
        try:
            source = song.make_source()
            vc.play(source, after=lambda e: self._after(e, guild, vc))
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
            await self._announce(guild.id, embed=embed)
        except Exception as e:
            log.error(f"_play error in {guild.name}: {e}")
            # stream URL expired — refetch
            asyncio.ensure_future(self._refetch(guild, vc, song))

    async def _refetch(self, guild, vc, song: Song):
        try:
            loop = asyncio.get_event_loop()
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: _fetch(song.url or song.title)),
                timeout=60,
            )
            if data:
                new = Song(data, self.vol(guild.id), song.requester)
                await self._play(guild, vc, new)
            else:
                await self._autoplay(guild, vc)
        except Exception as e:
            log.error(f"_refetch error: {e}")
            await self._autoplay(guild, vc)

    async def _autoplay(self, guild, vc):
        if not vc or not vc.is_connected():
            return
        lk = self.lock(guild.id)
        if lk.locked():
            return
        async with lk:
            if vc.is_playing() or vc.is_paused():
                return
            queue = self.q(guild.id)
            seed = None
            if queue.history:
                seed = queue.history[-1].title
            elif queue.current:
                seed = queue.current.title
            loop = asyncio.get_event_loop()
            for attempt in range(3):
                try:
                    if seed:
                        data = await asyncio.wait_for(
                            loop.run_in_executor(None, lambda s=seed: _fetch_similar(s, queue.seen_urls, queue.seen_titles)),
                            timeout=90,
                        )
                    else:
                        data = await asyncio.wait_for(
                            loop.run_in_executor(None, lambda: _fetch(random.choice(SEEDS))),
                            timeout=60,
                        )
                    if not data:
                        seed = random.choice(SEEDS)
                        continue
                    # dedup check on raw data before creating Song
                    raw_url = data.get("webpage_url") or data.get("url", "")
                    raw_title = (data.get("title") or "").lower().strip()
                    if raw_url in queue.seen_urls or raw_title in queue.seen_titles:
                        log.info(f"Autoplay dedup skip: {data.get('title')}")
                        seed = data.get("title", random.choice(SEEDS))
                        continue
                    song = Song(data, self.vol(guild.id))
                    await self._play(guild, vc, song)
                    return
                except asyncio.TimeoutError:
                    seed = random.choice(SEEDS)
                except Exception as e:
                    log.error(f"_autoplay attempt {attempt+1}: {e}")
                    seed = random.choice(SEEDS)
            log.error(f"_autoplay gave up for guild {guild.id}")

    # ── slash commands ────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a song or search query")
    @app_commands.describe(query="Song name, URL, or search query")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = await self._join(interaction)
        if not vc:
            return
        loop = asyncio.get_event_loop()
        try:
            data = await asyncio.wait_for(loop.run_in_executor(None, lambda: _fetch(query)), timeout=60)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Search timed out.")
            return
        if not data:
            await interaction.followup.send(f"❌ Nothing found for `{query}`")
            return
        song = Song(data, self.vol(interaction.guild_id), interaction.user)
        queue = self.q(interaction.guild_id)
        if vc.is_playing() or vc.is_paused():
            queue.add(song)
            embed = discord.Embed(title="➕ Added to Queue", description=f"[{song.title}]({song.url})", color=0x5865f2)
            embed.add_field(name="Position", value=str(len(queue)))
            embed.add_field(name="Duration", value=_fmt(song.duration))
            await interaction.followup.send(embed=embed)
        else:
            await self._play(interaction.guild, vc, song)
            await interaction.followup.send(f"▶️ Playing **{song.title}**")

    @app_commands.command(name="playlist", description="Load a YouTube/SoundCloud playlist")
    @app_commands.describe(url="Playlist URL")
    async def playlist(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        vc = await self._join(interaction)
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
        queue = self.q(interaction.guild_id)
        for e in entries:
            queue.add(Song(e, self.vol(interaction.guild_id), interaction.user))
        await interaction.followup.send(f"✅ Added **{len(entries)}** tracks.")
        if not vc.is_playing() and not vc.is_paused():
            song = queue.next()
            if song:
                await self._play(interaction.guild, vc, song)

    @app_commands.command(name="stay", description="Toggle 24/7 mode — bot never leaves, autoplays forever")
    async def stay(self, interaction: discord.Interaction):
        await interaction.response.defer()
        gid = interaction.guild_id
        if gid in self._stay:
            del self._stay[gid]
            self._save()
            await interaction.followup.send("⏹️ 24/7 mode **disabled**.")
        else:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("❌ Join a voice channel first.")
                return
            vc = await self._join(interaction)
            if not vc:
                return
            self._stay[gid] = {"channel_id": vc.channel.id, "text_channel_id": interaction.channel_id}
            self._save()
            await interaction.followup.send(f"✅ 24/7 mode **enabled** in {vc.channel.mention}. Autoplaying forever.")
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
        self._save()
        self.q(interaction.guild_id).clear()
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
        queue = self.q(interaction.guild_id)
        title = queue.current.title if queue.current else "Unknown"
        vc.stop()
        await interaction.followup.send(f"⏭️ Skipped **{title}**")

    @app_commands.command(name="stop", description="Stop music and clear queue")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        self.q(interaction.guild_id).clear()
        if vc and vc.is_playing():
            vc.stop()
        await interaction.followup.send("⏹️ Stopped and queue cleared.")

    @app_commands.command(name="nowplaying", description="Show current song info")
    async def nowplaying(self, interaction: discord.Interaction):
        queue = self.q(interaction.guild_id)
        s = queue.current
        if not s:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
            return
        embed = discord.Embed(title="🎵 Now Playing", description=f"[{s.title}]({s.url})", color=0x1db954)
        if s.thumbnail:
            embed.set_thumbnail(url=s.thumbnail)
        embed.add_field(name="Duration", value=_fmt(s.duration))
        if s.requester:
            embed.add_field(name="Requested by", value=s.requester.mention)
        loop_s = "🔂 Song" if queue.loop_song else ("🔁 Queue" if queue.loop_queue else "Off")
        embed.add_field(name="Loop", value=loop_s)
        embed.add_field(name="Queue", value=f"{len(queue)} songs")
        embed.set_footer(text=f"{'🟢 24/7 ON' if interaction.guild_id in self._stay else '⚪ 24/7 OFF'}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="queue", description="Show the music queue")
    async def show_queue(self, interaction: discord.Interaction):
        queue = self.q(interaction.guild_id)
        if not queue.current and not queue._q:
            await interaction.response.send_message("📭 Queue is empty.", ephemeral=True)
            return
        lines = []
        if queue.current:
            lines.append(f"**▶ Now:** {queue.current.title} `[{_fmt(queue.current.duration)}]`")
        for i, s in enumerate(list(queue._q)[:15], 1):
            lines.append(f"`{i}.` {s.title} `[{_fmt(s.duration)}]`")
        if len(queue) > 15:
            lines.append(f"… and {len(queue) - 15} more")
        embed = discord.Embed(title=f"🎶 Queue — {len(queue)} songs", description="\n".join(lines), color=0x5865f2)
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
        app_commands.Choice(name="song", value="song"),
        app_commands.Choice(name="queue", value="queue"),
        app_commands.Choice(name="off", value="off"),
    ])
    async def loop(self, interaction: discord.Interaction, mode: str):
        queue = self.q(interaction.guild_id)
        queue.loop_song = mode == "song"
        queue.loop_queue = mode == "queue"
        msgs = {"song": "🔂 Looping current song", "queue": "🔁 Looping queue", "off": "Loop off"}
        await interaction.response.send_message(msgs[mode])

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        queue = self.q(interaction.guild_id)
        if not queue._q:
            await interaction.response.send_message("❌ Queue is empty.", ephemeral=True)
            return
        queue.shuffle()
        await interaction.response.send_message(f"🔀 Shuffled {len(queue)} songs.")

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
        urls = {
            "lofi": "https://www.youtube.com/watch?v=jfKfPfyJRdk",
            "jazz": "https://www.youtube.com/watch?v=neV3EPgvZ3g",
            "classical": "https://www.youtube.com/watch?v=EhO_MrRfftU",
            "electronic": "https://www.youtube.com/watch?v=4xDzrJKXOOY",
            "chill": "https://www.youtube.com/watch?v=5qap5aO4i9A",
        }
        await interaction.response.defer()
        vc = await self._join(interaction)
        if not vc:
            return
        loop = asyncio.get_event_loop()
        try:
            data = await asyncio.wait_for(loop.run_in_executor(None, lambda: _fetch(urls.get(station, urls["lofi"]))), timeout=60)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Timed out loading radio.")
            return
        if not data:
            await interaction.followup.send("❌ Could not load radio.")
            return
        song = Song(data, self.vol(interaction.guild_id), interaction.user)
        queue = self.q(interaction.guild_id)
        if vc.is_playing() or vc.is_paused():
            queue.add(song)
            await interaction.followup.send(f"📻 Added **{station}** radio to queue.")
        else:
            await self._play(interaction.guild, vc, song)
            await interaction.followup.send(f"📻 Playing **{station}** radio.")


async def setup(bot):
    await bot.add_cog(Music(bot))
