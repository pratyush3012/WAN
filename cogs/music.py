"""
WAN Bot - Music Cog v4
- /music-setup <voice_channel> — sets up live player in voice channel's linked text chat
- /247 — 24/7 mode, bot stays in VC forever
- /play /skip /stop /pause /resume /volume /queue /np /shuffle /loop /autoplay
- Live dashboard embed updates every 15s with progress bar
- Autoplay: language-aware recommendations (Hindi stays Hindi)
- Loop: properly replays current song
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import yt_dlp
import logging
import random
import re
import os
import time
from collections import deque
from utils.settings import get_setting, set_setting

logger = logging.getLogger("discord_bot.music")

# ── yt-dlp configs ─────────────────────────────────────────────────────────────
SC_OPTS = {
    "format": "bestaudio/best", "noplaylist": True,
    "quiet": True, "no_warnings": True,
    "source_address": "0.0.0.0", "skip_download": True,
}
YT_OPTS = {
    "format": "bestaudio/best", "noplaylist": True,
    "quiet": True, "no_warnings": True,
    "source_address": "0.0.0.0", "skip_download": True,
    "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
    "geo_bypass": True, "geo_bypass_country": "US",
}
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

# ── Helpers ─────────────────────────────────────────────────────────────────────
def _fmt_time(secs: int) -> str:
    if not secs:
        return "0:00"
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def _progress_bar(elapsed: int, total: int, length: int = 16) -> str:
    if not total:
        return "▓" * length
    pct = min(elapsed / total, 1.0)
    filled = int(pct * length)
    bar = "▓" * filled + "🔘" + "░" * (length - filled)
    return bar

def _is_hindi(text: str) -> bool:
    """Detect Hindi/Urdu/Bollywood content."""
    if re.search(r'[\u0900-\u097F\u0600-\u06FF]', text):
        return True
    hinglish = {'pyaar','dil','ishq','mohabbat','teri','meri','tere','mere',
                'aaja','suno','raat','yaad','zindagi','khwab','jaan','sanam',
                'woh','yeh','nahi','kya','toh','bollywood','hindi','arijit',
                'atif','neha','shreya','sonu','lata','kishore','rafi','kumar'}
    words = set(re.findall(r'[a-zA-Z]+', text.lower()))
    return len(words & hinglish) >= 1

def _spotify_to_search(url: str) -> str:
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        cid = os.getenv("SPOTIFY_CLIENT_ID")
        secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if cid and secret:
            sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                client_id=cid, client_secret=secret))
            if "/track/" in url:
                tid = url.split("/track/")[1].split("?")[0]
                t = sp.track(tid)
                return f"{t['name']} {', '.join(a['name'] for a in t['artists'])}"
            elif "/album/" in url:
                aid = url.split("/album/")[1].split("?")[0]
                a = sp.album(aid)
                return f"{a['name']} {a['artists'][0]['name']}"
            elif "/playlist/" in url:
                pid = url.split("/playlist/")[1].split("?")[0]
                return sp.playlist(pid)["name"]
    except Exception as e:
        logger.debug(f"Spotify: {e}")
    return url

def _sc_search(query: str) -> dict | None:
    ytdl = yt_dlp.YoutubeDL(SC_OPTS)
    try:
        info = ytdl.extract_info(f"scsearch:{query}", download=False)
        if not info or not info.get("entries"):
            return None
        e = info["entries"][0]
        return e if e and e.get("url") else None
    except Exception as ex:
        logger.warning(f"SC '{query}': {ex}")
        return None

def _yt_search(query: str, is_url: bool = False) -> dict | None:
    ytdl = yt_dlp.YoutubeDL(YT_OPTS)
    try:
        search = query if is_url else f"ytsearch:{query}"
        info = ytdl.extract_info(search, download=False)
        if not info:
            return None
        if "entries" in info:
            entries = [e for e in info["entries"] if e]
            if not entries:
                return None
            entry = entries[0]
            url = entry.get("webpage_url") or entry.get("url")
            if not url:
                return None
            info = ytdl.extract_info(url, download=False)
        return info if info and info.get("url") else None
    except Exception as ex:
        logger.warning(f"YT '{query}': {ex}")
        return None

def _sc_related(sc_url: str, limit: int = 3) -> list:
    """Fetch SoundCloud recommended tracks for a URL."""
    try:
        opts = {**SC_OPTS, "noplaylist": False, "playlistend": limit + 2}
        ytdl = yt_dlp.YoutubeDL(opts)
        info = ytdl.extract_info(sc_url.rstrip("/") + "/recommended", download=False)
        if not info:
            return []
        return [e for e in info.get("entries", []) if e and e.get("url")][:limit]
    except Exception as ex:
        logger.debug(f"SC related: {ex}")
        return []

def _sc_search_multi(query: str, limit: int = 5) -> list:
    """Search SoundCloud for multiple results."""
    try:
        opts = {**SC_OPTS, "noplaylist": False, "playlistend": limit + 3}
        ytdl = yt_dlp.YoutubeDL(opts)
        info = ytdl.extract_info(f"scsearch{limit + 3}:{query}", download=False)
        if not info or not info.get("entries"):
            return []
        return [e for e in info["entries"] if e and e.get("url")]
    except Exception as ex:
        logger.debug(f"SC multi '{query}': {ex}")
        return []

def _get_autoplay_songs(title: str, uploader: str, sc_url: str, limit: int = 3) -> list:
    """
    Get language-aware autoplay recommendations.
    Hindi song → Hindi recommendations only.
    English song → English/similar recommendations.
    """
    is_hindi = _is_hindi(title) or _is_hindi(uploader)
    seen = {title.lower()}
    results = []

    # Step 1: Try SoundCloud /recommended (most accurate)
    if sc_url and "soundcloud.com" in sc_url:
        related = _sc_related(sc_url, limit=limit + 2)
        for e in related:
            t = (e.get("title") or "").strip()
            if t.lower() in seen:
                continue
            # Language filter: if Hindi song, skip clearly English results
            if is_hindi and not _is_hindi(t) and not _is_hindi(e.get("uploader", "")):
                continue
            seen.add(t.lower())
            results.append(e)
            if len(results) >= limit:
                return results

    # Step 2: Search by artist (same artist = same language)
    artist_results = _sc_search_multi(uploader, limit=limit + 3)
    for e in artist_results:
        t = (e.get("title") or "").strip()
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        results.append(e)
        if len(results) >= limit:
            return results

    # Step 3: Language-specific search
    if len(results) < limit:
        if is_hindi:
            clean = re.sub(r'\([^)]*\)', '', title).split('-')[0].strip()
            extra = _sc_search_multi(f"hindi sad songs {clean}", limit=limit)
        else:
            clean = re.sub(r'\([^)]*\)', '', title).split('-')[0].strip()
            extra = _sc_search_multi(f"songs like {clean}", limit=limit)
        for e in extra:
            t = (e.get("title") or "").strip()
            if t.lower() in seen:
                continue
            if is_hindi and not _is_hindi(t) and not _is_hindi(e.get("uploader", "")):
                continue
            seen.add(t.lower())
            results.append(e)
            if len(results) >= limit:
                break

    return results[:limit]


# ── Song ────────────────────────────────────────────────────────────────────────
class Song:
    def __init__(self, data: dict, requester):
        self.stream_url = data.get("url", "")
        self.title      = (data.get("title") or "Unknown").strip()
        self.duration   = data.get("duration", 0)
        self.thumbnail  = data.get("thumbnail") or data.get("artwork_url")
        self.uploader   = data.get("uploader") or data.get("channel") or data.get("artist", "Unknown")
        self.webpage    = data.get("webpage_url") or data.get("permalink_url", "")
        self.requester  = requester
        self.started_at: float = 0.0

    @property
    def duration_str(self):
        return _fmt_time(self.duration) if self.duration else "∞"

    @property
    def elapsed(self) -> int:
        return int(time.time() - self.started_at) if self.started_at else 0

    def player_embed(self, gp) -> discord.Embed:
        elapsed = min(self.elapsed, self.duration or 9999)
        total   = self.duration or 0
        bar     = _progress_bar(elapsed, total)
        icons   = ("🔁 " if gp.loop else "") + ("✨ " if gp.autoplay else "") + ("🌙 " if gp.mode_247 else "")
        status  = "▶️" if gp.vc_playing else "⏸"

        e = discord.Embed(color=0x1DB954)
        e.set_author(name=f"{status} Now Playing  {icons}".strip())
        e.title = self.title[:200]
        if self.webpage:
            e.url = self.webpage
        e.description = (
            f"`{_fmt_time(elapsed)}` {bar} `{self.duration_str}`\n"
            f"{'─' * 20}"
        )
        e.add_field(name="🎤 Artist", value=self.uploader[:50], inline=True)
        e.add_field(name="🔊 Volume", value=f"{int(gp.volume * 100)}%", inline=True)
        e.add_field(name="📋 Queue", value=f"{len(gp.queue)} song{'s' if len(gp.queue) != 1 else ''}", inline=True)
        if self.requester and hasattr(self.requester, "mention"):
            e.add_field(name="👤 Requested by", value=self.requester.mention, inline=True)
        if gp.queue:
            e.add_field(name="⏭ Up Next", value=list(gp.queue)[0].title[:50], inline=True)
        if self.thumbnail and self.thumbnail.startswith("http"):
            e.set_thumbnail(url=self.thumbnail)
        e.set_footer(text="🎵 WAN Music  •  /play to add songs  •  Updates every 15s")
        return e

    def simple_embed(self):
        e = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{self.title}]({self.webpage})" if self.webpage else self.title,
            color=0x1DB954
        )
        e.add_field(name="Duration", value=self.duration_str, inline=True)
        e.add_field(name="Artist", value=self.uploader, inline=True)
        if self.thumbnail and self.thumbnail.startswith("http"):
            e.set_thumbnail(url=self.thumbnail)
        return e


# ── GuildPlayer ─────────────────────────────────────────────────────────────────
class GuildPlayer:
    def __init__(self):
        self.queue: deque     = deque()
        self.current: Song    = None
        self.volume: float    = 0.5
        self.loop: bool       = False
        self.autoplay: bool   = True
        self.vc_playing: bool = False
        self.mode_247: bool   = False
        self.vc_channel_id: int  = None
        self.dash_channel_id: int = None   # text channel for live embed
        self.dash_message_id: int = None   # message ID to edit


# ── Persistent Controls View ────────────────────────────────────────────────────
# custom_id on every button = Discord can re-attach them after restart
class MusicControls(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=None)
        self.cog      = cog
        self.guild_id = guild_id

    def _vc(self):
        g = self.cog.bot.get_guild(self.guild_id)
        return g.voice_client if g else None

    def _gp(self) -> GuildPlayer:
        return self.cog._get_player(self.guild_id)

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.primary, row=0,
                       custom_id="music_pause")
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self._vc(); gp = self._gp()
        if vc and vc.is_playing():
            vc.pause(); gp.vc_playing = False
            await interaction.response.send_message("⏸ Paused.", ephemeral=True, delete_after=3)
        elif vc and vc.is_paused():
            vc.resume(); gp.vc_playing = True
            await interaction.response.send_message("▶️ Resumed.", ephemeral=True, delete_after=3)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.primary, row=0,
                       custom_id="music_skip")
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self._vc()
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭ Skipped.", ephemeral=True, delete_after=3)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, row=0,
                       custom_id="music_stop")
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp(); vc = self._vc()
        gp.queue.clear(); gp.loop = False; gp.vc_playing = False
        if vc:
            vc.stop()
            if not gp.mode_247:
                await vc.disconnect()
        await interaction.response.send_message("⏹ Stopped.", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=1,
                       custom_id="music_shuffle")
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp()
        q = list(gp.queue); random.shuffle(q); gp.queue = deque(q)
        await interaction.response.send_message("🔀 Shuffled!", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=1,
                       custom_id="music_loop")
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp(); gp.loop = not gp.loop
        await interaction.response.send_message(
            f"🔁 Loop {'**ON**' if gp.loop else 'off'}", ephemeral=True, delete_after=4)

    @discord.ui.button(label="✨ Auto", style=discord.ButtonStyle.success, row=1,
                       custom_id="music_autoplay")
    async def autoplay_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp(); gp.autoplay = not gp.autoplay
        await interaction.response.send_message(
            f"✨ Autoplay {'on' if gp.autoplay else 'off'}", ephemeral=True, delete_after=4)

    @discord.ui.button(label="🌙 24/7", style=discord.ButtonStyle.secondary, row=1,
                       custom_id="music_247")
    async def mode247_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp(); gp.mode_247 = not gp.mode_247
        if gp.mode_247:
            vc = self._vc()
            if vc:
                gp.vc_channel_id = vc.channel.id
        await interaction.response.send_message(
            f"🌙 24/7 {'on' if gp.mode_247 else 'off'}", ephemeral=True, delete_after=4)

    @discord.ui.button(label="🔉 Vol-", style=discord.ButtonStyle.secondary, row=2,
                       custom_id="music_vol_down")
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp(); gp.volume = max(0.1, round(gp.volume - 0.1, 1))
        vc = self._vc()
        if vc and vc.source:
            vc.source.volume = gp.volume
        await interaction.response.send_message(
            f"🔉 Volume: **{int(gp.volume * 100)}%**", ephemeral=True, delete_after=3)

    @discord.ui.button(label="🔊 Vol+", style=discord.ButtonStyle.secondary, row=2,
                       custom_id="music_vol_up")
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp(); gp.volume = min(1.0, round(gp.volume + 0.1, 1))
        vc = self._vc()
        if vc and vc.source:
            vc.source.volume = gp.volume
        await interaction.response.send_message(
            f"🔊 Volume: **{int(gp.volume * 100)}%**", ephemeral=True, delete_after=3)


def _idle_embed() -> discord.Embed:
    e = discord.Embed(
        title="🎵 WAN Music Player",
        description=(
            "```\n  ♪  Nothing playing right now  ♪\n```\n"
            "**Use `/play <song name>` to start!**\n\n"
            "🎵 SoundCloud  •  📺 YouTube  •  🎧 Spotify\n\n"
            "**Controls below ↓**\n"
            "⏸ Pause  ⏭ Skip  ⏹ Stop\n"
            "🔀 Shuffle  🔁 Loop  ✨ Autoplay  🌙 24/7\n"
            "🔉 Vol-  🔊 Vol+"
        ),
        color=0x1DB954
    )
    e.set_footer(text="🎵 WAN Music  •  Updates every 15s")
    return e


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._players: dict = {}
        self._update_task.start()
        self._247_task.start()

    def cog_unload(self):
        self._update_task.cancel()
        self._247_task.cancel()

    def _get_player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer()
        return self._players[guild_id]

    # ── Live embed update (every 15s) ───────────────────────────────────────────
    @tasks.loop(seconds=15)
    async def _update_task(self):
        for guild_id, gp in list(self._players.items()):
            if not gp.dash_channel_id or not gp.dash_message_id:
                continue
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            ch = guild.get_channel(gp.dash_channel_id)
            if not ch:
                continue
            try:
                msg = await ch.fetch_message(gp.dash_message_id)
                embed = gp.current.player_embed(gp) if gp.current else _idle_embed()
                view  = MusicControls(self, guild_id)
                await msg.edit(embed=embed, view=view)
            except discord.NotFound:
                gp.dash_message_id = None
            except Exception as ex:
                logger.debug(f"Dashboard update: {ex}")

    @_update_task.before_loop
    async def _before_update(self):
        await self.bot.wait_until_ready()

    # ── 24/7 reconnect (every 30s) ──────────────────────────────────────────────
    @tasks.loop(seconds=30)
    async def _247_task(self):
        for guild_id, gp in list(self._players.items()):
            if not gp.mode_247 or not gp.vc_channel_id:
                continue
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            if guild.voice_client is None:
                ch = guild.get_channel(gp.vc_channel_id)
                if ch:
                    try:
                        await ch.connect()
                    except Exception as ex:
                        logger.debug(f"24/7 reconnect: {ex}")

    @_247_task.before_loop
    async def _before_247(self):
        await self.bot.wait_until_ready()

    # ── Voice join ──────────────────────────────────────────────────────────────
    async def _join_voice(self, guild, author, send_fn):
        if not hasattr(author, "voice") or author.voice is None:
            await send_fn("❌ Join a voice channel first.")
            return None
        vc = guild.voice_client
        if vc is None:
            vc = await author.voice.channel.connect()
        elif vc.channel != author.voice.channel:
            await vc.move_to(author.voice.channel)
        return vc

    # ── Fetch song ──────────────────────────────────────────────────────────────
    async def _fetch_song(self, query: str, requester) -> Song:
        if "spotify.com" in query:
            query = _spotify_to_search(query)
        is_url = query.startswith("http://") or query.startswith("https://")
        is_yt  = is_url and ("youtube.com" in query or "youtu.be" in query)
        loop   = asyncio.get_running_loop()
        data   = None
        if is_yt:
            data = await loop.run_in_executor(None, lambda: _yt_search(query, is_url=True))
        elif is_url and "soundcloud.com" in query:
            data = await loop.run_in_executor(None, lambda: _sc_search(query))
        else:
            data = await loop.run_in_executor(None, lambda: _sc_search(query))
            if not data:
                data = await loop.run_in_executor(None, lambda: _yt_search(query))
        if not data:
            return None
        s = Song(data, requester)
        return s if s.stream_url else None

    # ── Playback ────────────────────────────────────────────────────────────────
    def _play_next(self, channel, guild, gp: GuildPlayer):
        vc = guild.voice_client
        if vc is None:
            gp.vc_playing = False
            return

        # ── LOOP FIX: re-queue current song BEFORE clearing it ─────────────────
        # Only loop if queue is empty (so loop doesn't interfere with normal queue)
        if gp.loop and gp.current and not gp.queue:
            # Re-fetch the same song to get a fresh stream URL (URLs expire)
            last = gp.current
            gp.current = None
            gp.vc_playing = False
            asyncio.run_coroutine_threadsafe(
                self._loop_song(channel, guild, gp, last), self.bot.loop)
            return

        if not gp.queue:
            if gp.autoplay and gp.current:
                last = gp.current
                gp.current = None
                gp.vc_playing = False
                asyncio.run_coroutine_threadsafe(
                    self._autoplay(channel, guild, gp, last), self.bot.loop)
            else:
                gp.current = None
                gp.vc_playing = False
                if not gp.mode_247:
                    asyncio.run_coroutine_threadsafe(
                        channel.send("✅ Queue finished."), self.bot.loop)
            return

        song = gp.queue.popleft()
        self._start_song(channel, guild, gp, song)
    
    def _get_played_songs(self, gp: GuildPlayer) -> set:
        """Get set of already-played song titles to avoid repeats in autoplay."""
        if not hasattr(gp, '_played_songs'):
            gp._played_songs = set()
        return gp._played_songs

    def _start_song(self, channel, guild, gp: GuildPlayer, song: Song):
        vc = guild.voice_client
        if not vc:
            return
        song.started_at = time.time()
        gp.current = song
        gp.vc_playing = True
        try:
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(song.stream_url, **FFMPEG_OPTS),
                volume=gp.volume
            )
        except Exception as e:
            logger.error(f"FFmpeg error '{song.title}': {e}")
            gp.current = None
            self._play_next(channel, guild, gp)
            return

        def _after(error):
            if error:
                logger.error(f"Player error: {error}")
            self._play_next(channel, guild, gp)

        vc.play(source, after=_after)
        # Only send now-playing message if NOT in the dashboard channel
        if channel and gp.dash_channel_id and channel.id != gp.dash_channel_id:
            asyncio.run_coroutine_threadsafe(
                channel.send(embed=song.simple_embed()), self.bot.loop)

    async def _loop_song(self, channel, guild, gp: GuildPlayer, last: Song):
        """Re-fetch and replay the same song (stream URLs expire)."""
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, lambda: _sc_search(last.title) or _yt_search(last.title))
        if data:
            song = Song(data, last.requester)
            self._start_song(channel, guild, gp, song)
        else:
            # Fallback: try original stream URL
            self._start_song(channel, guild, gp, last)

    async def _autoplay(self, channel, guild, gp: GuildPlayer, last: Song):
        """Fetch language-aware recommendations and queue them (no repeats)."""
        loop = asyncio.get_running_loop()
        
        # Get played songs set
        played = self._get_played_songs(gp)
        played.add(last.title.lower())
        
        # Try to get recommendations that haven't been played
        max_attempts = 3
        songs_data = []
        for attempt in range(max_attempts):
            candidates = await loop.run_in_executor(
                None, lambda: _get_autoplay_songs(last.title, last.uploader, last.webpage, limit=5))
            
            # Filter out already-played songs
            for d in candidates:
                title = (d.get("title") or "").lower()
                if title not in played and d.get("url"):
                    songs_data.append(d)
                    played.add(title)
                    if len(songs_data) >= 3:
                        break
            
            if len(songs_data) >= 3:
                break
            await asyncio.sleep(0.5)

        if not songs_data:
            if not gp.mode_247:
                await channel.send("✅ Queue finished — no new recommendations found.")
            return

        songs = [Song(d, guild.me) for d in songs_data if d.get("url")]
        if not songs:
            return

        for s in songs:
            gp.queue.append(s)

        self._play_next(channel, guild, gp)

        lang = "🎵 Hindi/Desi" if _is_hindi(last.title) else "🎵 Similar"
        titles = "\n".join(f"• {s.title}" for s in songs)
        embed = discord.Embed(
            title=f"✨ Autoplay — {lang} Recommendations",
            description=f"Based on **{last.title}**:\n{titles}",
            color=0x1DB954
        )
        await channel.send(embed=embed, delete_after=30)

    # ── Dashboard setup ─────────────────────────────────────────────────────────
    async def _setup_dashboard(self, guild, text_ch: discord.TextChannel, gp: GuildPlayer):
        try:
            await text_ch.purge(limit=20, check=lambda m: m.author == guild.me)
        except Exception:
            pass
        msg = await text_ch.send(embed=_idle_embed(), view=MusicControls(self, guild.id))
        gp.dash_channel_id = text_ch.id
        gp.dash_message_id = msg.id
        await set_setting(guild.id, "music_dashboard", {
            "channel_id": text_ch.id, "message_id": msg.id})
        return msg

    # ── Slash commands ──────────────────────────────────────────────────────────

    @app_commands.command(name="music-setup",
                          description="🎵 Set up the music player in a voice channel")
    @app_commands.describe(
        voice_channel="Voice channel where the bot will play music",
        text_channel="Text channel for the player embed (leave blank = use existing #music or bot-commands)"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def music_setup(self, interaction: discord.Interaction,
                          voice_channel: discord.VoiceChannel,
                          text_channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=True)
        gp = self._get_player(interaction.guild.id)

        # ── Join the voice channel ────────────────────────────────────────────
        vc = interaction.guild.voice_client
        try:
            if vc is None:
                await voice_channel.connect()
            elif vc.channel != voice_channel:
                await vc.move_to(voice_channel)
            gp.vc_channel_id = voice_channel.id
        except Exception as e:
            await interaction.followup.send(f"❌ Could not join **{voice_channel.name}**: {e}", ephemeral=True)
            return

        # ── Find text channel — NEVER create one ─────────────────────────────
        if not text_channel:
            # Priority: existing music/bot channel, then the channel where command was used
            for name in ("music-player", "🎵・music-player", "music", "bot-commands", "bot-spam", "bots"):
                text_channel = discord.utils.get(interaction.guild.text_channels, name=name)
                if text_channel:
                    break
            # Fallback: use the channel where the command was run
            if not text_channel:
                text_channel = interaction.channel

        # ── Post the dashboard embed ──────────────────────────────────────────
        await self._setup_dashboard(interaction.guild, text_channel, gp)

        await interaction.followup.send(
            f"✅ Music player ready!\n"
            f"🔊 Voice: **{voice_channel.name}**\n"
            f"📋 Dashboard: {text_channel.mention}\n\n"
            f"Use `/play <song>` to start music!\n"
            f"Use `/247` to keep the bot in VC 24/7.",
            ephemeral=True
        )

    @app_commands.command(name="247", description="🌙 Toggle 24/7 mode — bot stays in VC forever")
    async def mode_247(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        gp.mode_247 = not gp.mode_247
        vc = interaction.guild.voice_client
        if gp.mode_247:
            if vc:
                gp.vc_channel_id = vc.channel.id
            elif interaction.user.voice:
                gp.vc_channel_id = interaction.user.voice.channel.id
                await interaction.user.voice.channel.connect()
            embed = discord.Embed(
                title="🌙 24/7 Mode ON",
                description="Bot stays in VC forever. Autoplay keeps music going non-stop.\nUse `/247` again to disable.",
                color=0x7c3aed)
        else:
            gp.vc_channel_id = None
            embed = discord.Embed(
                title="🌙 24/7 Mode OFF",
                description="Bot will leave when queue ends.",
                color=0x6b7280)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="play", description="🎵 Play a song — name, YouTube or Spotify URL")
    @app_commands.describe(query="Song name, YouTube URL, or Spotify URL")
    async def slash_play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = await self._join_voice(
            interaction.guild, interaction.user,
            lambda m: interaction.followup.send(m, ephemeral=True))
        if not vc:
            return
        gp = self._get_player(interaction.guild.id)
        if gp.mode_247:
            gp.vc_channel_id = vc.channel.id
        song = await self._fetch_song(query, interaction.user)
        if not song:
            await interaction.followup.send(
                "❌ Couldn't find that song. Try a more specific name or a direct URL.")
            return
        gp.queue.append(song)
        if not vc.is_playing() and not vc.is_paused():
            self._play_next(interaction.channel, interaction.guild, gp)
            await interaction.followup.send(f"▶️ Now playing: **{song.title}**")
        else:
            e = discord.Embed(title="➕ Added to Queue",
                              description=f"[{song.title}]({song.webpage})" if song.webpage else song.title,
                              color=0x1DB954)
            e.add_field(name="Duration", value=song.duration_str, inline=True)
            e.add_field(name="Position", value=f"#{len(gp.queue)}", inline=True)
            if song.thumbnail and song.thumbnail.startswith("http"):
                e.set_thumbnail(url=song.thumbnail)
            await interaction.followup.send(embed=e)

    @app_commands.command(name="skip", description="⏭ Skip the current song")
    async def slash_skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭ Skipped.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="stop", description="⏹ Stop music and clear queue")
    async def slash_stop(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        gp.queue.clear(); gp.loop = False; gp.vc_playing = False
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            if not gp.mode_247:
                await vc.disconnect()
        await interaction.response.send_message("⏹ Stopped.")

    @app_commands.command(name="pause", description="⏸ Pause the current song")
    async def slash_pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        gp = self._get_player(interaction.guild.id)
        if vc and vc.is_playing():
            vc.pause(); gp.vc_playing = False
            await interaction.response.send_message("⏸ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="▶️ Resume the paused song")
    async def slash_resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        gp = self._get_player(interaction.guild.id)
        if vc and vc.is_paused():
            vc.resume(); gp.vc_playing = True
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)

    @app_commands.command(name="volume", description="🔊 Set volume (1–100)")
    @app_commands.describe(level="Volume level 1–100")
    async def slash_volume(self, interaction: discord.Interaction, level: int):
        if not 1 <= level <= 100:
            return await interaction.response.send_message("❌ Volume must be 1–100.", ephemeral=True)
        gp = self._get_player(interaction.guild.id)
        gp.volume = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = gp.volume
        await interaction.response.send_message(f"🔊 Volume: **{level}%**")

    @app_commands.command(name="queue", description="📋 Show the music queue")
    async def slash_queue(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        if not gp.current and not gp.queue:
            return await interaction.response.send_message("📭 Queue is empty.", ephemeral=True)
        e = discord.Embed(title="🎵 Music Queue", color=0x1DB954)
        if gp.current:
            e.add_field(name="▶️ Now Playing",
                        value=f"[{gp.current.title}]({gp.current.webpage}) `{gp.current.duration_str}`",
                        inline=False)
        if gp.queue:
            lines = [f"`{i}.` [{s.title}]({s.webpage}) `{s.duration_str}`"
                     for i, s in enumerate(list(gp.queue)[:10], 1)]
            if len(gp.queue) > 10:
                lines.append(f"... and {len(gp.queue) - 10} more")
            e.add_field(name=f"Up Next ({len(gp.queue)})", value="\n".join(lines), inline=False)
        e.set_footer(text=f"Loop: {'on' if gp.loop else 'off'} • Vol: {int(gp.volume*100)}% • Autoplay: {'on' if gp.autoplay else 'off'} • 24/7: {'on' if gp.mode_247 else 'off'}")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="np", description="🎵 Show what's currently playing")
    async def slash_np(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        if not gp.current:
            return await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        await interaction.response.send_message(
            embed=gp.current.player_embed(gp), view=MusicControls(self, interaction.guild.id))

    @app_commands.command(name="shuffle", description="🔀 Shuffle the queue")
    async def slash_shuffle(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        if not gp.queue:
            return await interaction.response.send_message("❌ Queue is empty.", ephemeral=True)
        q = list(gp.queue); random.shuffle(q); gp.queue = deque(q)
        await interaction.response.send_message("🔀 Queue shuffled!")

    @app_commands.command(name="loop", description="🔁 Toggle loop for current song")
    async def slash_loop(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        gp.loop = not gp.loop
        await interaction.response.send_message(
            f"🔁 Loop {'**ON** — current song will repeat' if gp.loop else 'off'}")

    @app_commands.command(name="autoplay", description="✨ Toggle autoplay recommendations")
    async def slash_autoplay(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        gp.autoplay = not gp.autoplay
        embed = discord.Embed(
            title=f"✨ Autoplay {'on' if gp.autoplay else 'off'}",
            description="Plays similar songs when queue ends. Hindi songs → Hindi recommendations." if gp.autoplay else "Disabled.",
            color=0x1DB954 if gp.autoplay else 0x6b7280)
        await interaction.response.send_message(embed=embed)

    # ── Prefix aliases ──────────────────────────────────────────────────────────
    @commands.command(name="play", aliases=["p"])
    async def prefix_play(self, ctx, *, query: str):
        vc = await self._join_voice(ctx.guild, ctx.author, ctx.send)
        if not vc:
            return
        msg = await ctx.send(f"🔍 Searching **{query}**...")
        song = await self._fetch_song(query, ctx.author)
        if not song:
            return await msg.edit(content="❌ Couldn't find that song.")
        await msg.delete()
        gp = self._get_player(ctx.guild.id)
        gp.queue.append(song)
        if not vc.is_playing() and not vc.is_paused():
            self._play_next(ctx.channel, ctx.guild, gp)
        else:
            e = discord.Embed(title="➕ Added to Queue",
                              description=f"[{song.title}]({song.webpage})", color=0x1DB954)
            e.add_field(name="Duration", value=song.duration_str, inline=True)
            e.add_field(name="Position", value=f"#{len(gp.queue)}", inline=True)
            await ctx.send(embed=e)

    @commands.command(name="skip", aliases=["s"])
    async def prefix_skip(self, ctx):
        vc = ctx.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop(); await ctx.send("⏭ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="stop")
    async def prefix_stop(self, ctx):
        gp = self._get_player(ctx.guild.id)
        gp.queue.clear(); vc = ctx.guild.voice_client
        if vc:
            vc.stop()
            if not gp.mode_247:
                await vc.disconnect()
        await ctx.send("⏹ Stopped.")

    @commands.command(name="pause")
    async def prefix_pause(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause(); await ctx.send("⏸ Paused.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="resume", aliases=["r"])
    async def prefix_resume(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume(); await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("❌ Nothing is paused.")

    @commands.command(name="volume", aliases=["v", "vol"])
    async def prefix_volume(self, ctx, vol: int):
        if not 1 <= vol <= 100:
            return await ctx.send("❌ Volume must be 1–100.")
        gp = self._get_player(ctx.guild.id); gp.volume = vol / 100
        vc = ctx.guild.voice_client
        if vc and vc.source:
            vc.source.volume = gp.volume
        await ctx.send(f"🔊 Volume: **{vol}%**")

    @commands.command(name="queue", aliases=["q"])
    async def prefix_queue(self, ctx):
        gp = self._get_player(ctx.guild.id)
        if not gp.current and not gp.queue:
            return await ctx.send("📭 Queue is empty.")
        e = discord.Embed(title="🎵 Music Queue", color=0x1DB954)
        if gp.current:
            e.add_field(name="Now Playing",
                        value=f"[{gp.current.title}]({gp.current.webpage}) `{gp.current.duration_str}`",
                        inline=False)
        if gp.queue:
            lines = [f"`{i}.` [{s.title}]({s.webpage}) `{s.duration_str}`"
                     for i, s in enumerate(list(gp.queue)[:10], 1)]
            e.add_field(name=f"Up Next ({len(gp.queue)})", value="\n".join(lines), inline=False)
        await ctx.send(embed=e)

    @commands.command(name="nowplaying", aliases=["np"])
    async def prefix_np(self, ctx):
        gp = self._get_player(ctx.guild.id)
        if not gp.current:
            return await ctx.send("❌ Nothing is playing.")
        await ctx.send(embed=gp.current.player_embed(gp), view=MusicControls(self, ctx.guild.id))

    @commands.command(name="shuffle")
    async def prefix_shuffle(self, ctx):
        gp = self._get_player(ctx.guild.id)
        if not gp.queue:
            return await ctx.send("❌ Queue is empty.")
        q = list(gp.queue); random.shuffle(q); gp.queue = deque(q)
        await ctx.send("🔀 Queue shuffled!")

    @commands.command(name="loop", aliases=["l"])
    async def prefix_loop(self, ctx):
        gp = self._get_player(ctx.guild.id); gp.loop = not gp.loop
        await ctx.send(f"🔁 Loop {'on' if gp.loop else 'off'}")

    @commands.command(name="leave", aliases=["dc"])
    async def prefix_leave(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            gp = self._get_player(ctx.guild.id)
            gp.queue.clear(); gp.mode_247 = False
            await vc.disconnect(); await ctx.send("👋 Left.")
        else:
            await ctx.send("❌ Not in a voice channel.")

    @commands.command(name="remove")
    async def prefix_remove(self, ctx, index: int):
        gp = self._get_player(ctx.guild.id); q = list(gp.queue)
        if not 1 <= index <= len(q):
            return await ctx.send(f"❌ Invalid. Queue has {len(q)} songs.")
        removed = q.pop(index - 1); gp.queue = deque(q)
        await ctx.send(f"🗑️ Removed **{removed.title}**")

    @commands.command(name="clearqueue", aliases=["cq"])
    async def prefix_clearqueue(self, ctx):
        self._get_player(ctx.guild.id).queue.clear()
        await ctx.send("🗑️ Queue cleared.")


async def setup(bot):
    await bot.add_cog(Music(bot))
