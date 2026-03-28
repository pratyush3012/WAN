"""
WAN Bot - Music Cog v3
Features:
- /play /skip /stop /pause /resume /volume /queue /np /shuffle /loop /autoplay
- /music-setup  — creates a dedicated #music channel with a live player embed
- /247          — toggle 24/7 mode (bot stays in VC, autoplay keeps music going)
- Live player embed updates every 15s with animated progress bar
- Autoplay: fetches related SoundCloud tracks when queue ends
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import yt_dlp
import logging
import random
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
SC_RELATED_OPTS = {
    "format": "bestaudio/best", "noplaylist": False, "playlistend": 5,
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

# ── Progress bar animation frames ──────────────────────────────────────────────
BAR_FILLED  = "▓"
BAR_EMPTY   = "░"
BAR_HEAD    = "🔘"

def _progress_bar(elapsed: int, total: int, length: int = 18) -> str:
    if not total:
        return BAR_FILLED * length
    pct = min(elapsed / total, 1.0)
    filled = int(pct * length)
    bar = BAR_FILLED * filled + BAR_HEAD + BAR_EMPTY * (length - filled)
    return bar

def _fmt_time(secs: int) -> str:
    if not secs:
        return "0:00"
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

# ── Spotify resolver ────────────────────────────────────────────────────────────
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

# ── Search helpers ──────────────────────────────────────────────────────────────
def _search_soundcloud(query: str) -> dict | None:
    ytdl = yt_dlp.YoutubeDL(SC_OPTS)
    try:
        info = ytdl.extract_info(f"scsearch:{query}", download=False)
        if not info or not info.get("entries"):
            return None
        e = info["entries"][0]
        return e if e and e.get("url") else None
    except Exception as ex:
        logger.warning(f"SC search '{query}': {ex}")
        return None

def _search_youtube(query: str, is_url: bool = False) -> dict | None:
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
            video_url = entry.get("webpage_url") or entry.get("url")
            if not video_url:
                return None
            info = ytdl.extract_info(video_url, download=False)
        return info if info and info.get("url") else None
    except Exception as ex:
        logger.warning(f"YT search '{query}': {ex}")
        return None

def _get_related_songs(sc_url: str, limit: int = 3) -> list:
    try:
        ytdl = yt_dlp.YoutubeDL(SC_RELATED_OPTS)
        info = ytdl.extract_info(sc_url.rstrip("/") + "/recommended", download=False)
        if not info:
            return []
        return [e for e in info.get("entries", [])[:limit] if e and e.get("url")]
    except Exception as ex:
        logger.debug(f"Related tracks: {ex}")
        return []

def _search_related_by_title(title: str, uploader: str, limit: int = 3) -> list:
    """Search SoundCloud for similar songs — language-aware using title/artist."""
    try:
        opts = {**SC_OPTS, "noplaylist": False, "playlistend": limit + 3}
        ytdl = yt_dlp.YoutubeDL(opts)
        # Use artist name as primary signal — keeps same language/genre
        queries = [
            f"scsearch{limit + 3}:{uploader}",           # same artist
            f"scsearch{limit + 3}:{title.split('-')[0].strip()} similar",  # similar to title
        ]
        results = []
        seen_titles = {title.lower()}
        for q in queries:
            if len(results) >= limit:
                break
            info = ytdl.extract_info(q, download=False)
            if not info or not info.get("entries"):
                continue
            for e in info["entries"]:
                if not e or not e.get("url"):
                    continue
                t = (e.get("title") or "").lower()
                if t in seen_titles:
                    continue
                seen_titles.add(t)
                results.append(e)
                if len(results) >= limit:
                    break
        return results
    except Exception as ex:
        logger.debug(f"Related by title: {ex}")
        return []


# ── Song ────────────────────────────────────────────────────────────────────────
class Song:
    def __init__(self, data: dict, requester):
        self.stream_url = data.get("url", "")
        self.title      = data.get("title", "Unknown")
        self.duration   = data.get("duration", 0)
        self.thumbnail  = data.get("thumbnail") or data.get("artwork_url")
        self.uploader   = data.get("uploader") or data.get("channel") or data.get("artist", "Unknown")
        self.webpage    = data.get("webpage_url") or data.get("permalink_url", "")
        self.requester  = requester
        self.started_at: float = 0.0   # set when playback begins

    @property
    def duration_str(self):
        if not self.duration:
            return "∞"
        return _fmt_time(self.duration)

    @property
    def elapsed(self) -> int:
        if not self.started_at:
            return 0
        return int(time.time() - self.started_at)

    def player_embed(self, gp) -> discord.Embed:
        """Rich now-playing embed with animated progress bar."""
        elapsed = self.elapsed
        total   = self.duration or 0
        bar     = _progress_bar(elapsed, total)
        pct     = int((elapsed / total * 100)) if total else 0

        # Status line
        status_icon = "▶️" if gp.vc_playing else "⏸"
        loop_icon   = "🔁" if gp.loop else ""
        ap_icon     = "✨" if gp.autoplay else ""
        flags       = " ".join(filter(None, [loop_icon, ap_icon]))

        e = discord.Embed(color=0x1DB954)
        e.set_author(name=f"{status_icon} Now Playing  {flags}")
        e.title = self.title[:200]
        if self.webpage:
            e.url = self.webpage
        e.description = (
            f"`{_fmt_time(elapsed)}` {bar} `{self.duration_str}`\n"
            f"{'━' * 22}\n"
        )
        e.add_field(name="🎤 Artist", value=self.uploader[:50], inline=True)
        e.add_field(name="🔊 Volume", value=f"{int(gp.volume * 100)}%", inline=True)
        e.add_field(name="📋 Queue", value=f"{len(gp.queue)} song{'s' if len(gp.queue) != 1 else ''}", inline=True)
        if self.requester:
            name = self.requester.mention if hasattr(self.requester, "mention") else str(self.requester)
            e.add_field(name="👤 Requested by", value=name, inline=True)
        if gp.queue:
            next_song = list(gp.queue)[0]
            e.add_field(name="⏭ Up Next", value=next_song.title[:50], inline=True)
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        e.set_footer(text="🎵 WAN Music  •  Use /play to add songs  •  Updates every 15s")
        return e

    def simple_embed(self, status="🎵 Now Playing"):
        e = discord.Embed(
            title=status,
            description=f"[{self.title}]({self.webpage})" if self.webpage else self.title,
            color=0x1DB954
        )
        e.add_field(name="Duration", value=self.duration_str, inline=True)
        e.add_field(name="Source", value=self.uploader, inline=True)
        if self.requester:
            name = self.requester.mention if hasattr(self.requester, "mention") else str(self.requester)
            e.add_field(name="Requested by", value=name, inline=True)
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        return e


# ── GuildPlayer ─────────────────────────────────────────────────────────────────
class GuildPlayer:
    def __init__(self):
        self.queue: deque   = deque()
        self.current: Song  = None
        self.volume: float  = 0.5
        self.loop: bool     = False
        self.autoplay: bool = True
        self.vc_playing: bool = False
        # 24/7 mode
        self.mode_247: bool = False
        self.vc_channel_id: int = None   # voice channel to stay in
        # Dashboard embed
        self.dashboard_channel_id: int = None   # text channel with live embed
        self.dashboard_message_id: int = None   # message to edit


# ── Controls View ───────────────────────────────────────────────────────────────
class MusicControls(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=None)   # persistent
        self.cog = cog
        self.guild_id = guild_id

    def _vc(self):
        guild = self.cog.bot.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    def _gp(self):
        return self.cog._get_player(self.guild_id)

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏮ No previous track (not supported yet)", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.primary, row=0)
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self._vc()
        gp = self._gp()
        if vc and vc.is_playing():
            vc.pause()
            gp.vc_playing = False
            button.emoji = "▶️"
            await interaction.response.send_message("⏸ Paused.", ephemeral=True, delete_after=3)
        elif vc and vc.is_paused():
            vc.resume()
            gp.vc_playing = True
            button.emoji = "⏸"
            await interaction.response.send_message("▶️ Resumed.", ephemeral=True, delete_after=3)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.primary, row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self._vc()
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭ Skipped.", ephemeral=True, delete_after=3)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, row=0)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp()
        gp.queue.clear()
        gp.loop = False
        gp.vc_playing = False
        vc = self._vc()
        if vc:
            vc.stop()
            if not gp.mode_247:
                await vc.disconnect()
        await interaction.response.send_message("⏹ Stopped.", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=1)
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp()
        q = list(gp.queue)
        random.shuffle(q)
        gp.queue = deque(q)
        await interaction.response.send_message("🔀 Shuffled!", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=1)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp()
        gp.loop = not gp.loop
        button.style = discord.ButtonStyle.success if gp.loop else discord.ButtonStyle.secondary
        await interaction.response.send_message(
            f"🔁 Loop {'on' if gp.loop else 'off'}", ephemeral=True, delete_after=3)

    @discord.ui.button(label="✨ Auto", style=discord.ButtonStyle.success, row=1)
    async def autoplay_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp()
        gp.autoplay = not gp.autoplay
        button.style = discord.ButtonStyle.success if gp.autoplay else discord.ButtonStyle.secondary
        await interaction.response.send_message(
            f"✨ Autoplay {'on' if gp.autoplay else 'off'}", ephemeral=True, delete_after=3)

    @discord.ui.button(label="🌙 24/7", style=discord.ButtonStyle.secondary, row=1)
    async def mode247_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp()
        gp.mode_247 = not gp.mode_247
        button.style = discord.ButtonStyle.success if gp.mode_247 else discord.ButtonStyle.secondary
        await interaction.response.send_message(
            f"🌙 24/7 mode {'on' if gp.mode_247 else 'off'}", ephemeral=True, delete_after=5)

    @discord.ui.button(label="🔉", style=discord.ButtonStyle.secondary, row=2)
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp()
        gp.volume = max(0.1, gp.volume - 0.1)
        vc = self._vc()
        if vc and vc.source:
            vc.source.volume = gp.volume
        await interaction.response.send_message(
            f"🔉 Volume: **{int(gp.volume * 100)}%**", ephemeral=True, delete_after=3)

    @discord.ui.button(label="🔊", style=discord.ButtonStyle.secondary, row=2)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self._gp()
        gp.volume = min(1.0, gp.volume + 0.1)
        vc = self._vc()
        if vc and vc.source:
            vc.source.volume = gp.volume
        await interaction.response.send_message(
            f"🔊 Volume: **{int(gp.volume * 100)}%**", ephemeral=True, delete_after=3)


# ── Idle embed (shown when nothing is playing) ──────────────────────────────────
def _idle_embed() -> discord.Embed:
    e = discord.Embed(
        title="🎵 WAN Music Player",
        description=(
            "```\n"
            "  ♪  Nothing is playing right now  ♪\n"
            "```\n"
            "Use `/play <song name>` to start listening!\n\n"
            "**Supported sources:**\n"
            "🎵 SoundCloud  •  📺 YouTube  •  🎧 Spotify URLs\n\n"
            "**Commands:**\n"
            "`/play` `/skip` `/queue` `/np` `/volume`\n"
            "`/loop` `/shuffle` `/autoplay` `/247`"
        ),
        color=0x1DB954
    )
    e.set_footer(text="🎵 WAN Music  •  24/7 Mode Available  •  Autoplay Enabled")
    return e


# ── Music Cog ───────────────────────────────────────────────────────────────────
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._players: dict = {}
        self._update_task.start()

    def cog_unload(self):
        self._update_task.cancel()

    def _get_player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer()
        return self._players[guild_id]

    # ── Live dashboard update task ──────────────────────────────────────────────

    @tasks.loop(seconds=15)
    async def _update_task(self):
        """Update the live player embed in every guild's music channel."""
        for guild_id, gp in list(self._players.items()):
            if not gp.dashboard_channel_id or not gp.dashboard_message_id:
                continue
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            ch = guild.get_channel(gp.dashboard_channel_id)
            if not ch:
                continue
            try:
                msg = await ch.fetch_message(gp.dashboard_message_id)
                if gp.current:
                    embed = gp.current.player_embed(gp)
                else:
                    embed = _idle_embed()
                await msg.edit(embed=embed, view=MusicControls(self, guild_id))
            except discord.NotFound:
                gp.dashboard_message_id = None
            except Exception as ex:
                logger.debug(f"Dashboard update error: {ex}")

    @_update_task.before_loop
    async def _before_update(self):
        await self.bot.wait_until_ready()

    # ── 24/7 reconnect task ─────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _247_task(self):
        """Reconnect to VC if 24/7 mode is on and bot got disconnected."""
        for guild_id, gp in list(self._players.items()):
            if not gp.mode_247 or not gp.vc_channel_id:
                continue
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            vc = guild.voice_client
            if vc is None:
                ch = guild.get_channel(gp.vc_channel_id)
                if ch:
                    try:
                        await ch.connect()
                        logger.info(f"24/7: Reconnected to {ch.name} in {guild.name}")
                    except Exception as ex:
                        logger.debug(f"24/7 reconnect failed: {ex}")

    @_247_task.before_loop
    async def _before_247(self):
        await self.bot.wait_until_ready()

    # ── Voice helpers ───────────────────────────────────────────────────────────

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

    async def _fetch_song(self, query: str, requester) -> Song:
        if "spotify.com" in query:
            query = _spotify_to_search(query)
        is_url = query.startswith("http://") or query.startswith("https://")
        is_yt  = is_url and ("youtube.com" in query or "youtu.be" in query)
        is_sc  = is_url and "soundcloud.com" in query
        loop   = asyncio.get_running_loop()
        data   = None
        if is_yt:
            data = await loop.run_in_executor(None, lambda: _search_youtube(query, is_url=True))
        elif is_sc:
            data = await loop.run_in_executor(None, lambda: _search_soundcloud(query))
        else:
            data = await loop.run_in_executor(None, lambda: _search_soundcloud(query))
            if not data:
                data = await loop.run_in_executor(None, lambda: _search_youtube(query, is_url=False))
        if not data:
            return None
        song = Song(data, requester)
        return song if song.stream_url else None

    # ── Playback ────────────────────────────────────────────────────────────────

    def _play_next(self, channel, guild, gp: GuildPlayer):
        vc = guild.voice_client
        if vc is None:
            gp.vc_playing = False
            return
        if gp.loop and gp.current:
            gp.queue.appendleft(gp.current)
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
                        channel.send("✅ Queue finished. Use `/play` to add more songs."),
                        self.bot.loop)
            return
        song = gp.queue.popleft()
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
            self._play_next(channel, guild, gp)
            return

        def _after(error):
            if error:
                logger.error(f"Player error: {error}")
            self._play_next(channel, guild, gp)

        vc.play(source, after=_after)
        # Send now-playing to the text channel (not the dashboard channel)
        if channel and (not gp.dashboard_channel_id or channel.id != gp.dashboard_channel_id):
            asyncio.run_coroutine_threadsafe(
                channel.send(embed=song.simple_embed()), self.bot.loop)

    async def _autoplay(self, channel, guild, gp: GuildPlayer, last_song: Song):
        loop = asyncio.get_running_loop()
        songs_data = []
        if last_song.webpage and "soundcloud.com" in last_song.webpage:
            songs_data = await loop.run_in_executor(
                None, lambda: _get_related_songs(last_song.webpage, limit=3))
        if not songs_data:
            songs_data = await loop.run_in_executor(
                None, lambda: _search_related_by_title(last_song.title, last_song.uploader, limit=3))
        if not songs_data:
            if not gp.mode_247:
                await channel.send("✅ Queue finished — no recommendations found.")
            return
        songs = [Song(d, guild.me) for d in songs_data if d.get("url")]
        for s in songs:
            gp.queue.append(s)
        self._play_next(channel, guild, gp)
        titles = "\n".join(f"• {s.title}" for s in songs)
        await channel.send(embed=discord.Embed(
            title="✨ Autoplay — Recommended",
            description=f"Added **{len(songs)}** similar songs:\n{titles}",
            color=0x1DB954
        ))

    # ── Dashboard setup ─────────────────────────────────────────────────────────

    async def _setup_dashboard(self, guild, channel: discord.TextChannel, gp: GuildPlayer):
        """Post or update the live player embed in the music channel."""
        # Clear old messages in channel (keep last 10 for context)
        try:
            await channel.purge(limit=50, check=lambda m: m.author == guild.me)
        except Exception:
            pass
        embed = _idle_embed()
        view  = MusicControls(self, guild.id)
        msg   = await channel.send(embed=embed, view=view)
        gp.dashboard_channel_id = channel.id
        gp.dashboard_message_id = msg.id
        # Persist
        await set_setting(guild.id, "music_dashboard", {
            "channel_id": channel.id,
            "message_id": msg.id,
        })
        return msg

    # ── Slash commands ──────────────────────────────────────────────────────────

    @app_commands.command(name="music-setup", description="🎵 Create a dedicated music channel with live player")
    @app_commands.describe(
        text_channel="Text channel for the player embed (leave blank to create #music-player)",
        voice_channel="Voice channel for the bot to join (leave blank to use your current VC)"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def music_setup(self, interaction: discord.Interaction,
                          text_channel: discord.TextChannel = None,
                          voice_channel: discord.VoiceChannel = None):
        await interaction.response.defer(ephemeral=True)
        gp = self._get_player(interaction.guild.id)

        # ── Text channel ──────────────────────────────────────────────────────
        if not text_channel:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(
                    send_messages=False, read_messages=True, add_reactions=False),
                interaction.guild.me: discord.PermissionOverwrite(
                    send_messages=True, manage_messages=True, embed_links=True),
            }
            text_channel = await interaction.guild.create_text_channel(
                "🎵・music-player",
                overwrites=overwrites,
                topic="WAN Music Player — Use /play to add songs"
            )

        # ── Voice channel ─────────────────────────────────────────────────────
        if not voice_channel:
            # Use user's current VC, or find one named music/lounge/general
            if interaction.user.voice:
                voice_channel = interaction.user.voice.channel
            else:
                for name in ("music", "lounge", "general", "voice"):
                    voice_channel = discord.utils.get(interaction.guild.voice_channels, name=name)
                    if voice_channel:
                        break
                if not voice_channel and interaction.guild.voice_channels:
                    voice_channel = interaction.guild.voice_channels[0]

        # Join voice channel
        if voice_channel:
            vc = interaction.guild.voice_client
            try:
                if vc is None:
                    await voice_channel.connect()
                elif vc.channel != voice_channel:
                    await vc.move_to(voice_channel)
                gp.vc_channel_id = voice_channel.id
            except Exception as e:
                logger.warning(f"Could not join voice channel: {e}")

        # ── Post player embed ─────────────────────────────────────────────────
        await self._setup_dashboard(interaction.guild, text_channel, gp)

        vc_info = f" and joined **{voice_channel.name}**" if voice_channel else ""
        await interaction.followup.send(
            f"✅ Music player set up in {text_channel.mention}{vc_info}!\n"
            f"The embed updates every 15 seconds. Use `/play` to start music.\n"
            f"Use `/247` to keep the bot in VC 24/7.",
            ephemeral=True
        )

    @app_commands.command(name="247", description="🌙 Toggle 24/7 mode — bot stays in VC forever")
    async def mode_247(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        gp.mode_247 = not gp.mode_247
        vc = interaction.guild.voice_client
        if gp.mode_247:
            # Store current VC or user's VC
            if vc:
                gp.vc_channel_id = vc.channel.id
            elif interaction.user.voice:
                gp.vc_channel_id = interaction.user.voice.channel.id
                vc = await interaction.user.voice.channel.connect()
            if not self._247_task.is_running():
                self._247_task.start()
            embed = discord.Embed(
                title="🌙 24/7 Mode ON",
                description=(
                    "Bot will stay in the voice channel forever.\n"
                    "Autoplay will keep music going non-stop.\n"
                    "Use `/247` again to disable."
                ),
                color=0x7c3aed
            )
        else:
            gp.vc_channel_id = None
            embed = discord.Embed(
                title="🌙 24/7 Mode OFF",
                description="Bot will leave the voice channel when the queue ends.",
                color=0x6b7280
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="play", description="🎵 Play a song — name, YouTube or Spotify URL")
    @app_commands.describe(query="Song name, YouTube URL, or Spotify URL")
    async def slash_play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = await self._join_voice(
            interaction.guild, interaction.user,
            lambda m: interaction.followup.send(m, ephemeral=True)
        )
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
            if song.thumbnail:
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
        gp.queue.clear()
        gp.loop = False
        gp.vc_playing = False
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
            vc.pause()
            gp.vc_playing = False
            await interaction.response.send_message("⏸ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="▶️ Resume the paused song")
    async def slash_resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        gp = self._get_player(interaction.guild.id)
        if vc and vc.is_paused():
            vc.resume()
            gp.vc_playing = True
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
            e.add_field(name=f"Up Next ({len(gp.queue)} songs)", value="\n".join(lines), inline=False)
        e.set_footer(text=f"Loop: {'on' if gp.loop else 'off'} • Vol: {int(gp.volume*100)}% • Autoplay: {'on ✨' if gp.autoplay else 'off'} • 24/7: {'on 🌙' if gp.mode_247 else 'off'}")
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
        q = list(gp.queue)
        random.shuffle(q)
        gp.queue = deque(q)
        await interaction.response.send_message("🔀 Queue shuffled!")

    @app_commands.command(name="loop", description="🔁 Toggle loop for current song")
    async def slash_loop(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        gp.loop = not gp.loop
        await interaction.response.send_message(f"🔁 Loop {'on' if gp.loop else 'off'}")

    @app_commands.command(name="autoplay", description="✨ Toggle autoplay — plays similar songs when queue ends")
    async def slash_autoplay(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        gp.autoplay = not gp.autoplay
        embed = discord.Embed(
            title=f"✨ Autoplay {'on' if gp.autoplay else 'off'}",
            description=(
                "When the queue runs out, I'll automatically play similar songs."
                if gp.autoplay else "Autoplay disabled."
            ),
            color=0x1DB954 if gp.autoplay else 0x6b7280
        )
        await interaction.response.send_message(embed=embed)

    # /join and /leave removed to stay under 100 slash command limit
    # /play auto-joins your voice channel; use /stop to disconnect

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
            if song.thumbnail:
                e.set_thumbnail(url=song.thumbnail)
            await ctx.send(embed=e)

    @commands.command(name="skip", aliases=["s"])
    async def prefix_skip(self, ctx):
        vc = ctx.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await ctx.send("⏭ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="stop")
    async def prefix_stop(self, ctx):
        gp = self._get_player(ctx.guild.id)
        gp.queue.clear()
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
            if not gp.mode_247:
                await vc.disconnect()
        await ctx.send("⏹ Stopped.")

    @commands.command(name="pause")
    async def prefix_pause(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸ Paused.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="resume", aliases=["r"])
    async def prefix_resume(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("❌ Nothing is paused.")

    @commands.command(name="volume", aliases=["v", "vol"])
    async def prefix_volume(self, ctx, vol: int):
        if not 1 <= vol <= 100:
            return await ctx.send("❌ Volume must be 1–100.")
        gp = self._get_player(ctx.guild.id)
        gp.volume = vol / 100
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
            if len(gp.queue) > 10:
                lines.append(f"... and {len(gp.queue) - 10} more")
            e.add_field(name=f"Up Next ({len(gp.queue)} songs)", value="\n".join(lines), inline=False)
        e.set_footer(text=f"Loop: {'on' if gp.loop else 'off'} • Vol: {int(gp.volume*100)}%")
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
        q = list(gp.queue)
        random.shuffle(q)
        gp.queue = deque(q)
        await ctx.send("🔀 Queue shuffled!")

    @commands.command(name="loop", aliases=["l"])
    async def prefix_loop(self, ctx):
        gp = self._get_player(ctx.guild.id)
        gp.loop = not gp.loop
        await ctx.send(f"🔁 Loop {'on' if gp.loop else 'off'}")

    @commands.command(name="leave", aliases=["dc"])
    async def prefix_leave(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            gp = self._get_player(ctx.guild.id)
            gp.queue.clear()
            gp.mode_247 = False
            await vc.disconnect()
            await ctx.send("👋 Left.")
        else:
            await ctx.send("❌ Not in a voice channel.")

    @commands.command(name="remove")
    async def prefix_remove(self, ctx, index: int):
        gp = self._get_player(ctx.guild.id)
        q = list(gp.queue)
        if not 1 <= index <= len(q):
            return await ctx.send(f"❌ Invalid. Queue has {len(q)} songs.")
        removed = q.pop(index - 1)
        gp.queue = deque(q)
        await ctx.send(f"🗑️ Removed **{removed.title}**")

    @commands.command(name="clearqueue", aliases=["cq"])
    async def prefix_clearqueue(self, ctx):
        self._get_player(ctx.guild.id).queue.clear()
        await ctx.send("🗑️ Queue cleared.")


async def setup(bot):
    await bot.add_cog(Music(bot))
