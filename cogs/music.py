"""
WAN Bot - Music Cog
24/7 mode: bot stays in voice forever, queue never ends (autoplay from history).
Multiple YouTube player clients + SoundCloud fallback for cloud IP compatibility.
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

# Cookies file - supports both names
_COOKIES_FILE = None
for _cf in [
    os.path.join(os.path.dirname(__file__), '..', 'cookies.txt'),
    os.path.join(os.path.dirname(__file__), '..', 'youtube_cookies.txt'),
]:
    if os.path.exists(_cf):
        _COOKIES_FILE = os.path.abspath(_cf)
        logger.info(f"YouTube cookies loaded: {_cf}")
        break

_COOKIES_ENV = os.getenv('YOUTUBE_COOKIES', '')
if _COOKIES_ENV and not _COOKIES_FILE:
    _env_path = os.path.join(os.path.dirname(__file__), '..', 'cookies.txt')
    try:
        with open(_env_path, 'w') as _f:
            _f.write(_COOKIES_ENV)
        _COOKIES_FILE = os.path.abspath(_env_path)
        logger.info("YouTube cookies written from YOUTUBE_COOKIES env var")
    except Exception as _e:
        logger.warning(f"Could not write cookies from env: {_e}")

YTDL_BASE = {
    'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio[ext=opus]/bestaudio/best',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'noplaylist': True,
    'postprocessors': [],
}
if _COOKIES_FILE:
    YTDL_BASE['cookiefile'] = _COOKIES_FILE

FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -af aresample=48000',
}

AUTOPLAY_SEEDS = [
    "trending hits 2024", "popular songs mix", "top hits playlist",
    "best music 2024", "chill vibes mix", "hip hop hits",
    "pop music 2024", "electronic music mix", "r&b hits 2024", "workout music mix",
]

_PLAYER_CLIENTS = [
    ['android_embedded'],
    ['android_music'],
    ['mweb'],
    ['web_embedded'],
    ['ios'],
]


def _is_url(query: str) -> bool:
    return query.startswith(('http://', 'https://', 'www.'))


def _clean_url(url: str) -> str:
    import urllib.parse as up
    p = up.urlparse(url)
    qs = up.parse_qs(p.query)
    if 'youtube.com/watch' in url and 'v' in qs:
        return up.urlunparse(p._replace(query=up.urlencode({'v': qs['v'][0]})))
    return url


def _fmt(seconds) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _ytdl_extract_single(query: str):
    """Try multiple YouTube player clients, then fall back to SoundCloud."""
    is_url = _is_url(query)
    if is_url:
        query = _clean_url(query)
    search_query = query if is_url else f"ytsearch1:{query}"
    last_err = None

    for clients in _PLAYER_CLIENTS:
        opts = dict(YTDL_BASE)
        opts['extractor_args'] = {'youtube': {'player_client': clients}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(search_query, download=False)
            if not data:
                continue
            if 'entries' in data:
                entries = [e for e in data['entries'] if e and e.get('url')]
                if entries:
                    return entries[0]
                continue
            if data.get('url'):
                return data
        except Exception as e:
            last_err = e
            continue

    # SoundCloud fallback
    if not is_url:
        try:
            sc_opts = {**YTDL_BASE}
            sc_opts.pop('extractor_args', None)
            with yt_dlp.YoutubeDL(sc_opts) as ydl:
                data = ydl.extract_info(f"scsearch1:{query}", download=False)
            if data:
                if 'entries' in data:
                    entries = [e for e in data['entries'] if e and e.get('url')]
                    if entries:
                        logger.info(f"SoundCloud fallback OK for '{query}'")
                        return entries[0]
                elif data.get('url'):
                    logger.info(f"SoundCloud fallback OK for '{query}'")
                    return data
        except Exception as sc_err:
            logger.warning(f"SoundCloud fallback failed for '{query}': {sc_err}")

    logger.warning(f"All sources failed for '{query}': {last_err}")
    return None


def _ytdl_extract_playlist(url: str) -> list:
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


class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.current = None
        self.loop = False
        self.loop_queue = False
        self.history = deque(maxlen=50)

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


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title', 'Unknown')
        self.url = data.get('webpage_url', data.get('url', ''))
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration', 0)
        self.requester = None

    @classmethod
    async def from_query(cls, query: str, *, loop=None, volume=0.5):
        loop = loop or asyncio.get_event_loop()
        data = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _ytdl_extract_single(query)),
            timeout=60.0,
        )
        if not data:
            raise ValueError(f"No results found for: {query}")
        src = discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTS)
        return cls(src, data=data, volume=volume)

    @classmethod
    async def search_results(cls, query: str, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        def _search():
            for clients in _PLAYER_CLIENTS:
                opts = {**YTDL_BASE, 'noplaylist': False,
                        'extractor_args': {'youtube': {'player_client': clients}}}
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        data = ydl.extract_info(f"ytsearch5:{query}", download=False)
                    if data and 'entries' in data:
                        results = [e for e in data['entries'] if e][:5]
                        if results:
                            return results
                except Exception:
                    continue
            try:
                sc_opts = {**YTDL_BASE, 'noplaylist': False}
                sc_opts.pop('extractor_args', None)
                with yt_dlp.YoutubeDL(sc_opts) as ydl:
                    data = ydl.extract_info(f"scsearch5:{query}", download=False)
                if data and 'entries' in data:
                    return [e for e in data['entries'] if e][:5]
            except Exception:
                pass
            return []
        try:
            return await asyncio.wait_for(loop.run_in_executor(None, _search), timeout=30.0)
        except Exception:
            return []

    @classmethod
    async def from_playlist(cls, url: str, *, loop=None, volume=0.5):
        loop = loop or asyncio.get_event_loop()
        entries = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _ytdl_extract_playlist(url)),
            timeout=90.0,
        )
        sources = []
        for entry in entries:
            try:
                src = discord.FFmpegPCMAudio(entry['url'], **FFMPEG_OPTS)
                sources.append(cls(src, data=entry, volume=volume))
            except Exception:
                continue
        return sources


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self._volumes = {}
        self._247 = self._load_247()
        self._autoplay = {}
        self._reconnect_task = bot.loop.create_task(self._reconnect_loop())

    def _load_247(self):
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
                json.dump(self._247, f)
        except Exception as e:
            logger.error(f"Save 24/7 failed: {e}")

    async def _reconnect_loop(self):
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
                        await channel.connect()
                    elif vc.channel.id != channel_id:
                        await vc.move_to(channel)
                except Exception as e:
                    logger.warning(f"24/7 reconnect error guild {guild_id}: {e}")
            await asyncio.sleep(30)

    def get_queue(self, guild_id: int) -> MusicQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    def get_volume(self, guild_id: int) -> float:
        return self._volumes.get(guild_id, 0.5)

    async def cleanup(self, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        queue = self.get_queue(guild_id)
        queue.clear()
        self.queues.pop(guild_id, None)
        vc = guild.voice_client
        if vc:
            await vc.disconnect(force=True)

    async def _ensure_voice(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.followup.send("Join a voice channel first.", ephemeral=True)
            return None
        vc = interaction.guild.voice_client
        if not vc:
            try:
                vc = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f"Could not connect: {e}", ephemeral=True)
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
        queue = self.get_queue(guild.id)
        next_song = queue.next()
        if next_song:
            self._start_playing(guild, next_song, queue)
            return
        if self._autoplay.get(guild.id, True):
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

    async def _autoplay_next(self, guild: discord.Guild, _retries: int = 0):
        queue = self.get_queue(guild.id)
        vc = guild.voice_client
        if not vc or not vc.is_connected() or vc.is_playing():
            return
        seed = queue.history[-1].title if (_retries == 0 and queue.history) else random.choice(AUTOPLAY_SEEDS)
        try:
            vol = self.get_volume(guild.id)
            player = await YTDLSource.from_query(seed, loop=self.bot.loop, volume=vol)
            player.requester = None
            queue.current = player
            self._start_playing(guild, player, queue)
            logger.info(f"Autoplay: {player.title} in {guild.name}")
        except Exception as e:
            wait = min(5 * (2 ** min(_retries, 3)), 30)
            logger.warning(f"Autoplay failed (attempt {_retries+1}), retry in {wait}s: {e}")
            await asyncio.sleep(wait)
            asyncio.run_coroutine_threadsafe(
                self._autoplay_next(guild, _retries + 1), self.bot.loop
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
                embed = discord.Embed(title="Added to Queue",
                    description=f"**[{player.title}]({player.url})**", color=0x5865f2)
                embed.set_footer(text=f"Position #{len(queue.queue)} | {_fmt(player.duration)}")
            else:
                queue.current = player
                self._start_playing(interaction.guild, player, queue)
                embed = discord.Embed(title="Now Playing",
                    description=f"**[{player.title}]({player.url})**", color=0x57f287)
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                embed.add_field(name="Duration", value=_fmt(player.duration), inline=True)
                embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"_play_entry error: {e}")
            await interaction.followup.send(f"Could not play: {e}", ephemeral=True)

    # =========================================================================
    # SLASH COMMANDS
    # =========================================================================

    @app_commands.command(name="play", description="Play a song - YouTube URL or search query")
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
                embed = discord.Embed(title="Added to Queue",
                    description=f"**[{player.title}]({player.url})**", color=0x5865f2)
                embed.set_footer(text=f"Position #{len(queue.queue)} | {_fmt(player.duration)}")
            else:
                queue.current = player
                self._start_playing(interaction.guild, player, queue)
                embed = discord.Embed(title="Now Playing",
                    description=f"**[{player.title}]({player.url})**", color=0x57f287)
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                embed.add_field(name="Duration", value=_fmt(player.duration), inline=True)
                embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Play error: {e}")
            await interaction.followup.send(f"Could not play: {e}", ephemeral=True)

    @app_commands.command(name="playlist", description="Queue an entire YouTube playlist")
    async def playlist(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        vc = await self._ensure_voice(interaction)
        if not vc:
            return
        try:
            vol = self.get_volume(interaction.guild.id)
            songs = await YTDLSource.from_playlist(url, loop=self.bot.loop, volume=vol)
            if not songs:
                return await interaction.followup.send("No songs found in that playlist.", ephemeral=True)
            queue = self.get_queue(interaction.guild.id)
            for s in songs:
                s.requester = interaction.user
            if not vc.is_playing() and not vc.is_paused():
                first = songs.pop(0)
                queue.current = first
                self._start_playing(interaction.guild, first, queue)
            for s in songs:
                queue.add(s)
            embed = discord.Embed(title="Playlist Queued",
                description=f"Added **{len(songs) + 1}** songs to the queue.", color=0x5865f2)
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Playlist error: {e}")
            await interaction.followup.send(f"Could not load playlist: {e}", ephemeral=True)

    @app_commands.command(name="247", description="Toggle 24/7 mode - bot stays in VC forever")
    async def cmd_247(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
        gid = interaction.guild.id
        if gid in self._247:
            del self._247[gid]
            self._save_247()
            await interaction.response.send_message("24/7 mode disabled.")
        else:
            if not interaction.user.voice:
                return await interaction.response.send_message("Join a voice channel first.", ephemeral=True)
            ch = interaction.user.voice.channel
            self._247[gid] = ch.id
            self._save_247()
            vc = interaction.guild.voice_client
            if not vc:
                await ch.connect()
            elif vc.channel != ch:
                await vc.move_to(ch)
            await interaction.response.send_message(
                f"24/7 mode enabled in **{ch.name}**. Bot stays here and autoplays when queue ends.")

    @app_commands.command(name="autoplay", description="Toggle autoplay when queue ends")
    async def autoplay(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        current = self._autoplay.get(gid, True)
        self._autoplay[gid] = not current
        state = "enabled" if not current else "disabled"
        await interaction.response.send_message(f"Autoplay **{state}**.")

    @app_commands.command(name="leave", description="Leave voice channel")
    async def leave(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
        gid = interaction.guild.id
        was_247 = gid in self._247
        if was_247:
            del self._247[gid]
            self._save_247()
        queue = self.get_queue(gid)
        queue.clear()
        self.queues.pop(gid, None)
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect(force=True)
        msg = "Left voice channel."
        if was_247:
            msg += " 24/7 mode disabled."
        await interaction.response.send_message(msg)

    @app_commands.command(name="pause", description="Pause music")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("Paused.")
        else:
            await interaction.response.send_message("Nothing playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume music")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("Resumed.")
        else:
            await interaction.response.send_message("Not paused.", ephemeral=True)

    @app_commands.command(name="skip", description="Skip current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("Skipped.")
        else:
            await interaction.response.send_message("Nothing playing.", ephemeral=True)

    @app_commands.command(name="stop", description="Stop music and clear queue")
    async def stop(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        queue = self.get_queue(gid)
        queue.clear()
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
        await interaction.response.send_message("Stopped and cleared queue.")

    @app_commands.command(name="nowplaying", description="Show current song")
    async def nowplaying(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if not queue.current:
            return await interaction.response.send_message("Nothing playing.", ephemeral=True)
        p = queue.current
        embed = discord.Embed(title="Now Playing",
            description=f"**[{p.title}]({p.url})**", color=0x57f287)
        if p.thumbnail:
            embed.set_thumbnail(url=p.thumbnail)
        embed.add_field(name="Duration", value=_fmt(p.duration), inline=True)
        embed.add_field(name="Requested by",
            value=getattr(p.requester, 'mention', 'Autoplay'), inline=True)
        embed.add_field(name="Queue", value=f"{len(queue.queue)} song(s) up next", inline=True)
        is_247 = interaction.guild.id in self._247
        embed.set_footer(text=f"24/7: {'ON' if is_247 else 'OFF'} | Autoplay: {'ON' if self._autoplay.get(interaction.guild.id, True) else 'OFF'}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="queue", description="Show the music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        embed = discord.Embed(title="Music Queue", color=0x5865f2)
        if queue.current:
            embed.add_field(name="Now Playing",
                value=f"**{queue.current.title}** `{_fmt(queue.current.duration)}`", inline=False)
        if queue.queue:
            lines = [f"`{i+1}.` {s.title} `{_fmt(s.duration)}`"
                     for i, s in enumerate(list(queue.queue)[:15])]
            if len(queue.queue) > 15:
                lines.append(f"...and {len(queue.queue)-15} more")
            embed.add_field(name=f"Up Next ({len(queue.queue)} songs)", value="\n".join(lines), inline=False)
        else:
            ap = self._autoplay.get(interaction.guild.id, True)
            embed.add_field(name="Queue Empty",
                value="Autoplay will pick the next song." if ap else "Add songs with /play.",
                inline=False)
        loop_s = "Song" if queue.loop else ("Queue" if queue.loop_queue else "Off")
        is_247 = interaction.guild.id in self._247
        embed.set_footer(text=f"Loop: {loop_s} | 24/7: {'ON' if is_247 else 'OFF'}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set volume 0-100")
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]):
        self._volumes[interaction.guild.id] = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = level / 100
        await interaction.response.send_message(f"Volume set to **{level}%**")

    @app_commands.command(name="loop", description="Set loop mode")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Song - repeat current song", value="song"),
        app_commands.Choice(name="Queue - loop entire queue",  value="queue"),
        app_commands.Choice(name="Off - disable looping",     value="off"),
    ])
    async def loop(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        queue = self.get_queue(interaction.guild.id)
        queue.loop       = mode.value == "song"
        queue.loop_queue = mode.value == "queue"
        labels = {"song": "Looping current song", "queue": "Looping entire queue", "off": "Loop disabled"}
        await interaction.response.send_message(labels[mode.value])

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if not queue.queue:
            return await interaction.response.send_message("Queue is empty.", ephemeral=True)
        queue.shuffle()
        await interaction.response.send_message(f"Shuffled {len(queue.queue)} songs.")

    @app_commands.command(name="remove", description="Remove a song from the queue by position")
    async def remove(self, interaction: discord.Interaction, position: app_commands.Range[int, 1]):
        queue = self.get_queue(interaction.guild.id)
        removed = queue.remove(position)
        if removed:
            await interaction.response.send_message(f"Removed **{removed}** from queue.")
        else:
            await interaction.response.send_message("Invalid position.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
