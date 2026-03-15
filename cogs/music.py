"""
WAN Bot - Music Cog
- 24/7: bot NEVER leaves voice, NEVER disconnects, auto-rejoins on restart
- Queue NEVER empty: autoplay picks songs similar to last played, forever
- Audio: best quality, correct speed/pitch (48kHz resampled)
- SoundCloud primary (works on Render), YouTube fallback with cookies
"""
import discord
from discord import app_commands
from discord.ext import commands
try:
    import yt_dlp
except ImportError as e:
    raise ImportError(f"yt-dlp not installed: {e}")
import asyncio
import logging
import random
import json
import os
from collections import deque

logger = logging.getLogger('discord_bot.music')

PERSIST_FILE = 'music_247.json'

# ── yt-dlp options ────────────────────────────────────────────────────────────
# Best audio quality, no re-encode, stream directly
YTDL_OPTS = {
    'format': 'bestaudio/best',
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'noplaylist': True,
    'socket_timeout': 30,
}

# Write YouTube cookies from env var if provided (bypasses IP blocks on Render)
_COOKIES_FILE = os.path.join(os.path.dirname(__file__), '..', 'youtube_cookies.txt')
_COOKIES_ENV = os.getenv('YOUTUBE_COOKIES', '')
if _COOKIES_ENV:
    try:
        with open(_COOKIES_FILE, 'w') as _f:
            _f.write(_COOKIES_ENV)
        logger.info("YouTube cookies written from env var")
    except Exception as _e:
        logger.warning(f"Could not write cookies: {_e}")
if os.path.exists(_COOKIES_FILE):
    YTDL_OPTS['cookiefile'] = os.path.abspath(_COOKIES_FILE)
    logger.info("YouTube cookies loaded")

# ── FFmpeg options ────────────────────────────────────────────────────────────
# aresample=48000 fixes wrong speed/pitch from bad sample rate metadata (SoundCloud)
FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -af aresample=48000',
}

# ── YouTube player clients (try in order to bypass bot detection) ─────────────
_YT_CLIENTS = [['android_embedded'], ['android_music'], ['ios'], ['mweb'], ['web_embedded']]

# ── Autoplay seed pool ────────────────────────────────────────────────────────
# Generic search terms that work on SoundCloud (no IP blocks on cloud servers)
_AUTOPLAY_SEEDS = [
    "top hits 2024", "popular songs 2024", "best music mix",
    "hip hop hits", "pop hits 2024", "r&b hits", "chill vibes",
    "electronic music", "workout music", "trending songs",
    "bollywood hits", "punjabi songs", "english hits 2024",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_url(q: str) -> bool:
    return q.startswith(('http://', 'https://', 'www.'))

def _clean_yt_url(url: str) -> str:
    """Keep only ?v= param so yt-dlp treats it as single video, not playlist."""
    import urllib.parse as up
    p = up.urlparse(url)
    qs = up.parse_qs(p.query)
    if 'youtube.com/watch' in url and 'v' in qs:
        return up.urlunparse(p._replace(query=up.urlencode({'v': qs['v'][0]})))
    return url

def _extract(query: str) -> dict | None:
    """
    Extract audio info. Strategy:
    1. SoundCloud search (always works on cloud IPs)
    2. YouTube with multiple player clients (may be blocked)
    3. Direct URL fallback
    """
    is_url = _is_url(query)

    # ── Direct URL ────────────────────────────────────────────────────────
    if is_url:
        url = _clean_yt_url(query)
        # Try YouTube clients for YT URLs
        if 'youtube.com' in url or 'youtu.be' in url:
            for clients in _YT_CLIENTS:
                opts = {**YTDL_OPTS, 'extractor_args': {'youtube': {'player_client': clients}}}
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        data = ydl.extract_info(url, download=False)
                    if data and data.get('url'):
                        return data
                    if data and 'entries' in data:
                        entries = [e for e in data['entries'] if e and e.get('url')]
                        if entries:
                            return entries[0]
                except Exception:
                    continue
        # Non-YouTube URL (SoundCloud, etc.)
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
                data = ydl.extract_info(url, download=False)
            if data and data.get('url'):
                return data
        except Exception:
            pass
        return None

    # ── Search query ──────────────────────────────────────────────────────
    # Try SoundCloud FIRST — it works on Render/cloud IPs without blocks
    try:
        with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
            data = ydl.extract_info(f"scsearch1:{query}", download=False)
        if data:
            if 'entries' in data:
                entries = [e for e in data['entries'] if e and e.get('url')]
                if entries:
                    logger.info(f"SoundCloud: found '{entries[0].get('title')}' for '{query}'")
                    return entries[0]
            elif data.get('url'):
                return data
    except Exception as sc_err:
        logger.debug(f"SoundCloud search failed for '{query}': {sc_err}")

    # Try YouTube as fallback
    for clients in _YT_CLIENTS:
        opts = {**YTDL_OPTS, 'extractor_args': {'youtube': {'player_client': clients}}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if data and 'entries' in data:
                entries = [e for e in data['entries'] if e and e.get('url')]
                if entries:
                    logger.info(f"YouTube: found '{entries[0].get('title')}' for '{query}'")
                    return entries[0]
        except Exception:
            continue

    logger.warning(f"No results found for: '{query}'")
    return None

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
        self.history: deque = deque(maxlen=100)  # last 100 songs for autoplay seeds

    def add(self, song):
        self.queue.append(song)

    def next(self):
        if self.loop and self.current:
            return self.current
        if self.current:
            self.history.append(self.current)
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
    async def from_query(cls, query: str, *, loop=None, volume=0.5):
        loop = loop or asyncio.get_event_loop()
        data = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _extract(query)),
            timeout=60.0,
        )
        if not data:
            raise ValueError(f"No results found for: {query}")
        src = discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTS)
        return cls(src, data=data, volume=volume)

    @classmethod
    async def from_playlist(cls, url: str, *, loop=None, volume=0.5):
        loop = loop or asyncio.get_event_loop()
        def _get_playlist():
            opts = {**YTDL_OPTS, 'noplaylist': False, 'playlistend': 50,
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
        entries = await asyncio.wait_for(loop.run_in_executor(None, _get_playlist), timeout=90.0)
        sources = []
        for entry in entries:
            try:
                src = discord.FFmpegPCMAudio(entry['url'], **FFMPEG_OPTS)
                sources.append(cls(src, data=entry, volume=volume))
            except Exception:
                continue
        return sources


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues: dict[int, MusicQueue] = {}
        self._volumes: dict[int, float] = {}
        self._247: dict[int, int] = self._load_247()   # guild_id -> voice_channel_id
        self._autoplay: dict[int, bool] = {}           # guild_id -> bool (default True)
        # Start background tasks
        self._reconnect_task = bot.loop.create_task(self._reconnect_loop())
        self._watchdog_task = bot.loop.create_task(self._playback_watchdog())

    # ── Persistence ───────────────────────────────────────────────────────

    def _load_247(self) -> dict:
        try:
            if os.path.exists(PERSIST_FILE):
                with open(PERSIST_FILE) as f:
                    return {int(k): int(v) for k, v in json.load(f).items()}
        except Exception:
            pass
        return {}

    def _save_247(self):
        try:
            with open(PERSIST_FILE, 'w') as f:
                json.dump({str(k): v for k, v in self._247.items()}, f)
        except Exception as e:
            logger.error(f"Save 24/7 failed: {e}")

    # ── Background tasks ──────────────────────────────────────────────────

    async def _reconnect_loop(self):
        """Every 20s: reconnect to 24/7 channels if disconnected."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            for guild_id, channel_id in list(self._247.items()):
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        continue
                    vc = guild.voice_client
                    if not vc or not vc.is_connected():
                        logger.info(f"24/7 reconnect → {channel.name} in {guild.name}")
                        await channel.connect()
                    elif vc.channel.id != channel_id:
                        await vc.move_to(channel)
                except Exception as e:
                    logger.warning(f"Reconnect error guild {guild_id}: {e}")
            await asyncio.sleep(20)

    async def _playback_watchdog(self):
        """Every 15s: if 24/7 guild is connected but silent, kick off autoplay."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            for guild_id in list(self._247.keys()):
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    vc = guild.voice_client
                    if not vc or not vc.is_connected():
                        continue
                    if not vc.is_playing() and not vc.is_paused():
                        queue = self.get_queue(guild_id)
                        if not queue.current and not queue.queue:
                            logger.info(f"Watchdog: silent in {guild.name}, starting autoplay")
                            asyncio.ensure_future(self._autoplay_next(guild))
                except Exception as e:
                    logger.warning(f"Watchdog error guild {guild_id}: {e}")
            await asyncio.sleep(15)

    # ── Helpers ───────────────────────────────────────────────────────────

    def get_queue(self, guild_id: int) -> MusicQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    def get_volume(self, guild_id: int) -> float:
        return self._volumes.get(guild_id, 0.5)

    async def cleanup(self, guild_id: int):
        """Stop music and disconnect (dashboard stop button)."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        self.get_queue(guild_id).clear()
        self.queues.pop(guild_id, None)
        vc = guild.voice_client
        if vc:
            await vc.disconnect(force=True)

    async def _ensure_voice(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.followup.send("❌ Join a voice channel first.", ephemeral=True)
            return None
        vc = interaction.guild.voice_client
        if not vc:
            try:
                vc = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f"❌ Could not connect: {e}", ephemeral=True)
                return None
        elif vc.channel != interaction.user.voice.channel:
            await vc.move_to(interaction.user.voice.channel)
        return vc

    def _broadcast(self, guild, player, queue):
        try:
            from web_dashboard_enhanced import broadcast_update
            broadcast_update('music_update', {
                'guild_id': guild.id,
                'action': 'now_playing',
                'title': player.title,
                'thumbnail': player.thumbnail,
                'duration': player.duration,
                'requester': getattr(player.requester, 'display_name', 'Autoplay'),
                'queue_size': len(queue.queue),
            })
        except Exception:
            pass

    def _play_next(self, guild: discord.Guild):
        """Called after each song ends. Pulls from queue or triggers autoplay."""
        queue = self.get_queue(guild.id)
        next_song = queue.next()
        if next_song:
            self._start_playing(guild, next_song, queue)
        else:
            # Queue empty — autoplay is always on for 24/7 guilds
            asyncio.run_coroutine_threadsafe(
                self._autoplay_next(guild), self.bot.loop
            )

    def _start_playing(self, guild: discord.Guild, player, queue):
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return
        def after(err):
            if err:
                logger.error(f"Playback error: {err}")
            self._play_next(guild)
        vc.play(player, after=after)
        self._broadcast(guild, player, queue)

    async def _autoplay_next(self, guild: discord.Guild, _attempt: int = 0):
        """
        Pick a song similar to the last played and play it.
        NEVER gives up — retries forever with backoff.
        """
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return
        if vc.is_playing() or vc.is_paused():
            return  # already playing, nothing to do

        queue = self.get_queue(guild.id)

        # Build seed: use last played title for "similar songs", else random genre
        if queue.history:
            # Use the last played title — SoundCloud will find similar tracks
            last_title = queue.history[-1].title
            # Strip common noise from title for better search results
            import re
            seed = re.sub(r'\(.*?\)|\[.*?\]|official|video|lyrics|audio|hd|4k', '', last_title, flags=re.IGNORECASE).strip()
            if not seed:
                seed = random.choice(_AUTOPLAY_SEEDS)
        else:
            seed = random.choice(_AUTOPLAY_SEEDS)

        logger.info(f"Autoplay seed: '{seed}' (attempt {_attempt+1}) in {guild.name}")

        try:
            vol = self.get_volume(guild.id)
            player = await YTDLSource.from_query(seed, loop=self.bot.loop, volume=vol)
            player.requester = None  # marks as autoplay
            queue.current = player
            self._start_playing(guild, player, queue)
            logger.info(f"Autoplay playing: '{player.title}' in {guild.name}")
        except Exception as e:
            # Exponential backoff: 5s, 10s, 20s, 30s max — then keep retrying
            wait = min(5 * (2 ** min(_attempt, 3)), 30)
            logger.warning(f"Autoplay attempt {_attempt+1} failed ({e}), retry in {wait}s")
            await asyncio.sleep(wait)
            # Use a fresh random seed after first failure so we don't keep hammering same query
            asyncio.run_coroutine_threadsafe(
                self._autoplay_next(guild, _attempt + 1), self.bot.loop
            )

    async def _play_entry(self, interaction: discord.Interaction, entry: dict):
        vc = await self._ensure_voice(interaction)
        if not vc:
            return
        try:
            vol = self.get_volume(interaction.guild.id)
            src = discord.FFmpegPCMAudio(entry['url'], **FFMPEG_OPTS)
            player = YTDLSource(src, data=entry, volume=vol)
            player.requester = interaction.user
            queue = self.get_queue(interaction.guild.id)
            if vc.is_playing() or vc.is_paused():
                queue.add(player)
                embed = discord.Embed(title="➕ Added to Queue",
                    description=f"**[{player.title}]({player.url})**", color=0x5865f2)
                embed.set_footer(text=f"Position #{len(queue.queue)} • {_fmt(player.duration)}")
            else:
                queue.current = player
                self._start_playing(interaction.guild, player, queue)
                embed = discord.Embed(title="🎵 Now Playing",
                    description=f"**[{player.title}]({player.url})**", color=0x57f287)
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                embed.add_field(name="Duration", value=_fmt(player.duration), inline=True)
                embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"_play_entry error: {e}")
            await interaction.followup.send(f"❌ Could not play: {e}", ephemeral=True)

    # ═══════════════════════════════════════════════════════════════════════
    # SLASH COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    @app_commands.command(name="play", description="🎵 Play a song or YouTube URL")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = await self._ensure_voice(interaction)
        if not vc:
            return
        try:
            vol = self.get_volume(interaction.guild.id)
            player = await YTDLSource.from_query(query, loop=self.bot.loop, volume=vol)
            player.requester = interaction.user
            queue = self.get_queue(interaction.guild.id)
            if vc.is_playing() or vc.is_paused():
                queue.add(player)
                embed = discord.Embed(title="➕ Added to Queue",
                    description=f"**[{player.title}]({player.url})**", color=0x5865f2)
                embed.set_footer(text=f"Position #{len(queue.queue)} • {_fmt(player.duration)}")
            else:
                queue.current = player
                self._start_playing(interaction.guild, player, queue)
                embed = discord.Embed(title="🎵 Now Playing",
                    description=f"**[{player.title}]({player.url})**", color=0x57f287)
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                embed.add_field(name="Duration", value=_fmt(player.duration), inline=True)
                embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Play error: {e}")
            await interaction.followup.send(f"❌ Could not play: {e}", ephemeral=True)

    @app_commands.command(name="playlist", description="📋 Queue an entire YouTube/SoundCloud playlist")
    async def playlist(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        vc = await self._ensure_voice(interaction)
        if not vc:
            return
        try:
            vol = self.get_volume(interaction.guild.id)
            songs = await YTDLSource.from_playlist(url, loop=self.bot.loop, volume=vol)
            if not songs:
                return await interaction.followup.send("❌ No songs found in that playlist.", ephemeral=True)
            queue = self.get_queue(interaction.guild.id)
            for s in songs:
                s.requester = interaction.user
            if not vc.is_playing() and not vc.is_paused():
                first = songs.pop(0)
                queue.current = first
                self._start_playing(interaction.guild, first, queue)
            for s in songs:
                queue.add(s)
            embed = discord.Embed(title="📋 Playlist Queued",
                description=f"Added **{len(songs)+1}** songs to the queue.", color=0x5865f2)
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Playlist error: {e}")
            await interaction.followup.send(f"❌ Could not load playlist: {e}", ephemeral=True)

    @app_commands.command(name="247", description="🔴 Toggle 24/7 mode — bot stays in VC forever")
    async def cmd_247(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Need Manage Server permission.", ephemeral=True)
        gid = interaction.guild.id
        if gid in self._247:
            del self._247[gid]
            self._save_247()
            await interaction.response.send_message("🔴 24/7 mode **disabled**.")
        else:
            if not interaction.user.voice:
                return await interaction.response.send_message("❌ Join a voice channel first.", ephemeral=True)
            ch = interaction.user.voice.channel
            self._247[gid] = ch.id
            self._save_247()
            vc = interaction.guild.voice_client
            if not vc:
                await ch.connect()
            elif vc.channel != ch:
                await vc.move_to(ch)
            await interaction.response.send_message(
                f"🟢 24/7 mode **enabled** in **{ch.name}**.\n"
                "Bot will stay here forever and autoplay similar songs when queue ends."
            )

    @app_commands.command(name="leave", description="📤 Leave voice channel (disables 24/7)")
    async def leave(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Need Manage Server permission.", ephemeral=True)
        gid = interaction.guild.id
        was_247 = gid in self._247
        if was_247:
            del self._247[gid]
            self._save_247()
        self.get_queue(gid).clear()
        self.queues.pop(gid, None)
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect(force=True)
        msg = "📤 Left voice channel."
        if was_247:
            msg += " 24/7 disabled — use `/247` to re-enable."
        await interaction.response.send_message(msg)

    @app_commands.command(name="pause", description="⏸ Pause music")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)

    @app_commands.command(name="resume", description="▶️ Resume music")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Not paused.", ephemeral=True)

    @app_commands.command(name="skip", description="⏭ Skip current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭ Skipped.")
        else:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)

    @app_commands.command(name="stop", description="⏹ Stop music and clear queue (bot stays in VC)")
    async def stop(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        self.get_queue(gid).clear()
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
        await interaction.response.send_message("⏹ Stopped and cleared queue. Bot stays in VC.")

    @app_commands.command(name="nowplaying", description="🎵 Show current song")
    async def nowplaying(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if not queue.current:
            return await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
        p = queue.current
        embed = discord.Embed(title="🎵 Now Playing",
            description=f"**[{p.title}]({p.url})**", color=0x57f287)
        if p.thumbnail:
            embed.set_thumbnail(url=p.thumbnail)
        embed.add_field(name="Duration", value=_fmt(p.duration), inline=True)
        embed.add_field(name="Requested by", value=getattr(p.requester, 'mention', '🤖 Autoplay'), inline=True)
        embed.add_field(name="Queue", value=f"{len(queue.queue)} song(s) up next", inline=True)
        is_247 = interaction.guild.id in self._247
        embed.set_footer(text=f"{'🟢 24/7 ON' if is_247 else '🔴 24/7 OFF'} • Autoplay: always on")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="queue", description="📋 Show the music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        embed = discord.Embed(title="📋 Music Queue", color=0x5865f2)
        if queue.current:
            embed.add_field(name="🎵 Now Playing",
                value=f"**{queue.current.title}** `{_fmt(queue.current.duration)}`", inline=False)
        if queue.queue:
            lines = [f"`{i+1}.` {s.title} `{_fmt(s.duration)}`"
                     for i, s in enumerate(list(queue.queue)[:15])]
            if len(queue.queue) > 15:
                lines.append(f"*...and {len(queue.queue)-15} more*")
            embed.add_field(name=f"Up Next ({len(queue.queue)} songs)", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Queue Empty",
                value="🤖 Autoplay will pick a similar song next.", inline=False)
        is_247 = interaction.guild.id in self._247
        embed.set_footer(text=f"{'🟢 24/7 ON' if is_247 else '🔴 24/7 OFF'} • Loop: {'Song' if queue.loop else 'Queue' if queue.loop_queue else 'Off'}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="🔊 Set volume (0–100)")
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]):
        self._volumes[interaction.guild.id] = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = level / 100
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**")

    @app_commands.command(name="loop", description="🔁 Set loop mode")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Song — repeat current song", value="song"),
        app_commands.Choice(name="Queue — loop entire queue",  value="queue"),
        app_commands.Choice(name="Off — disable looping",     value="off"),
    ])
    async def loop(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        queue = self.get_queue(interaction.guild.id)
        queue.loop       = mode.value == "song"
        queue.loop_queue = mode.value == "queue"
        labels = {"song": "🔁 Looping current song", "queue": "🔁 Looping entire queue", "off": "Loop disabled"}
        await interaction.response.send_message(labels[mode.value])

    @app_commands.command(name="shuffle", description="🔀 Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if not queue.queue:
            return await interaction.response.send_message("❌ Queue is empty.", ephemeral=True)
        queue.shuffle()
        await interaction.response.send_message(f"🔀 Shuffled {len(queue.queue)} songs.")


async def setup(bot):
    await bot.add_cog(Music(bot))
