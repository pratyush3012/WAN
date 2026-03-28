"""
WAN Bot - Music Cog
Slash: /play /skip /stop /pause /resume /volume /queue /np /shuffle /loop /join /leave /autoplay
Prefix: !play !skip etc.
Sources: SoundCloud (primary, works on Render) → YouTube fallback
Autoplay: when queue empties, fetches related tracks from SoundCloud
"""
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import yt_dlp
import logging
import random
import os
from collections import deque

logger = logging.getLogger("discord_bot.music")

# SoundCloud — primary source, not blocked on server IPs
SC_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
    "skip_download": True,
}

# SoundCloud related tracks — fetch up to 5 related songs
SC_RELATED_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "playlistend": 5,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
    "skip_download": True,
}

# YouTube — fallback, uses android_vr client (no JS runtime needed)
YT_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
    "skip_download": True,
    "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
    "geo_bypass": True,
    "geo_bypass_country": "US",
}

# FFmpeg — no single-quoted headers (breaks on Linux)
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

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
        logger.debug(f"Spotify resolve: {e}")
    return url


def _search_soundcloud(query: str) -> dict | None:
    """Search SoundCloud. Returns info dict or None."""
    ytdl = yt_dlp.YoutubeDL(SC_OPTS)
    try:
        info = ytdl.extract_info(f"scsearch:{query}", download=False)
        if not info or not info.get("entries"):
            return None
        entry = info["entries"][0]
        if not entry or not entry.get("url"):
            return None
        return entry
    except Exception as e:
        logger.warning(f"SoundCloud search failed for '{query}': {e}")
        return None


def _search_youtube(query: str, is_url: bool = False) -> dict | None:
    """Search or fetch from YouTube. Returns info dict or None."""
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
            # Re-extract to get stream URL
            video_url = entry.get("webpage_url") or entry.get("url")
            if not video_url:
                return None
            info = ytdl.extract_info(video_url, download=False)
        if not info or not info.get("url"):
            return None
        return info
    except Exception as e:
        logger.warning(f"YouTube search failed for '{query}': {e}")
        return None


def _get_related_songs(sc_url: str, requester, limit: int = 3) -> list:
    """Fetch related/recommended tracks from SoundCloud for a given track URL."""
    try:
        ytdl = yt_dlp.YoutubeDL(SC_RELATED_OPTS)
        # SoundCloud related tracks endpoint
        related_url = sc_url.rstrip("/") + "/recommended"
        info = ytdl.extract_info(related_url, download=False)
        if not info:
            return []
        entries = info.get("entries", [])
        songs = []
        for e in entries[:limit]:
            if e and e.get("url"):
                songs.append(Song(e, requester))
        return songs
    except Exception as e:
        logger.debug(f"Related tracks fetch failed: {e}")
        return []


def _search_related_by_title(title: str, uploader: str, requester, limit: int = 3) -> list:
    """Search SoundCloud for similar songs based on title/artist — fallback for autoplay."""
    try:
        ytdl = yt_dlp.YoutubeDL({**SC_OPTS, "noplaylist": False, "playlistend": limit + 2})
        # Search for songs by same artist or similar title
        query = f"scsearch{limit + 2}:{uploader} {title.split('-')[0].strip()}"
        info = ytdl.extract_info(query, download=False)
        if not info or not info.get("entries"):
            return []
        songs = []
        for e in info["entries"]:
            if e and e.get("url") and e.get("title") != title:
                songs.append(Song(e, requester))
                if len(songs) >= limit:
                    break
        return songs
    except Exception as e:
        logger.debug(f"Related search failed: {e}")
        return []
    def __init__(self, data: dict, requester):
        self.stream_url = data.get("url", "")
        self.title      = data.get("title", "Unknown")
        self.duration   = data.get("duration", 0)
        self.thumbnail  = data.get("thumbnail") or data.get("artwork_url")
        self.uploader   = data.get("uploader") or data.get("channel") or data.get("artist", "Unknown")
        self.webpage    = data.get("webpage_url") or data.get("permalink_url", "")
        self.requester  = requester

    @property
    def duration_str(self):
        if not self.duration:
            return "Live"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def embed(self, status="🎵 Now Playing"):
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


class GuildPlayer:
    def __init__(self):
        self.queue: deque = deque()
        self.current: Song = None
        self.volume: float = 0.5
        self.loop: bool = False
        self.autoplay: bool = True   # on by default


class MusicControls(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild_id = guild_id

    def _vc(self):
        guild = self.cog.bot.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.secondary)
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self._vc()
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸ Paused.", ephemeral=True, delete_after=3)
        elif vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.", ephemeral=True, delete_after=3)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self._vc()
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭ Skipped.", ephemeral=True, delete_after=3)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self.cog._get_player(self.guild_id)
        gp.queue.clear()
        gp.loop = False
        vc = self._vc()
        if vc:
            vc.stop()
            await vc.disconnect()
        await interaction.response.send_message("⏹ Stopped.", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary)
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self.cog._get_player(self.guild_id)
        q = list(gp.queue)
        random.shuffle(q)
        gp.queue = deque(q)
        await interaction.response.send_message("🔀 Shuffled!", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self.cog._get_player(self.guild_id)
        gp.loop = not gp.loop
        await interaction.response.send_message(
            f"🔁 Loop {'on' if gp.loop else 'off'}", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="✨", style=discord.ButtonStyle.secondary, label="Auto")
    async def autoplay_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gp = self.cog._get_player(self.guild_id)
        gp.autoplay = not gp.autoplay
        status = "on ✨" if gp.autoplay else "off"
        button.style = discord.ButtonStyle.success if gp.autoplay else discord.ButtonStyle.secondary
        await interaction.response.send_message(
            f"✨ Autoplay {status}", ephemeral=True, delete_after=5)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._players: dict = {}

    def _get_player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer()
        return self._players[guild_id]

    async def _join_voice(self, guild: discord.Guild, author, send_fn) -> discord.VoiceClient:
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
        """Resolve query → Song. SoundCloud first, YouTube fallback."""
        # Resolve Spotify URLs
        if "spotify.com" in query:
            query = _spotify_to_search(query)

        is_url = query.startswith("http://") or query.startswith("https://")
        is_yt  = is_url and ("youtube.com" in query or "youtu.be" in query)
        is_sc  = is_url and "soundcloud.com" in query

        loop = asyncio.get_running_loop()
        data = None

        if is_yt:
            # Direct YouTube URL — try YouTube only
            data = await loop.run_in_executor(None, lambda: _search_youtube(query, is_url=True))
        elif is_sc:
            # Direct SoundCloud URL
            data = await loop.run_in_executor(None, lambda: _search_soundcloud(query))
        else:
            # Song name search — SoundCloud first (reliable on Render), then YouTube
            data = await loop.run_in_executor(None, lambda: _search_soundcloud(query))
            if not data:
                logger.info(f"SoundCloud miss, trying YouTube for: '{query}'")
                data = await loop.run_in_executor(None, lambda: _search_youtube(query, is_url=False))

        if not data:
            logger.warning(f"No results for: '{query}'")
            return None

        song = Song(data, requester)
        if not song.stream_url:
            logger.warning(f"No stream URL for: '{song.title}'")
            return None
        return song

    def _play_next(self, channel, guild: discord.Guild, gp: GuildPlayer):
        vc = guild.voice_client
        if vc is None:
            return
        if gp.loop and gp.current:
            gp.queue.appendleft(gp.current)
        if not gp.queue:
            # Autoplay — fetch related songs in background
            if gp.autoplay and gp.current:
                last = gp.current
                gp.current = None
                asyncio.run_coroutine_threadsafe(
                    self._autoplay(channel, guild, gp, last), self.bot.loop)
            else:
                gp.current = None
                asyncio.run_coroutine_threadsafe(
                    channel.send("✅ Queue finished. Use `/autoplay` to toggle autoplay."),
                    self.bot.loop)
            return
        song = gp.queue.popleft()
        gp.current = song
        try:
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(song.stream_url, **FFMPEG_OPTS),
                volume=gp.volume
            )
        except Exception as e:
            logger.error(f"FFmpeg error for '{song.title}': {e}")
            self._play_next(channel, guild, gp)
            return

        def _after(error):
            if error:
                logger.error(f"Player error: {error}")
            self._play_next(channel, guild, gp)

        vc.play(source, after=_after)
        asyncio.run_coroutine_threadsafe(
            channel.send(embed=song.embed(), view=MusicControls(self, guild.id)),
            self.bot.loop
        )

    async def _autoplay(self, channel, guild: discord.Guild, gp: GuildPlayer, last_song: Song):
        """Fetch and queue related songs when queue runs out."""
        loop = asyncio.get_running_loop()
        await channel.send(
            f"🎵 Queue empty — fetching recommendations based on **{last_song.title}**...",
            delete_after=10
        )
        # Try SoundCloud related tracks first
        songs = []
        if last_song.webpage and "soundcloud.com" in last_song.webpage:
            songs = await loop.run_in_executor(
                None, lambda: _get_related_songs(last_song.webpage, guild.me, limit=3))
        # Fallback: search by artist/title
        if not songs:
            songs = await loop.run_in_executor(
                None, lambda: _search_related_by_title(
                    last_song.title, last_song.uploader, guild.me, limit=3))
        if not songs:
            await channel.send("✅ Queue finished — couldn't find recommendations.")
            return
        for s in songs:
            gp.queue.append(s)
        # Start playing
        self._play_next(channel, guild, gp)
        titles = "\n".join(f"• {s.title}" for s in songs)
        await channel.send(
            embed=discord.Embed(
                title="🎵 Autoplay — Recommended Songs",
                description=f"Added **{len(songs)}** similar songs:\n{titles}",
                color=0x1DB954
            )
        )

    # ── Slash commands ─────────────────────────────────────────────────────────

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
        song = await self._fetch_song(query, interaction.user)
        if not song:
            await interaction.followup.send(
                "❌ Couldn't find that song. Try a more specific name or a direct YouTube/SoundCloud URL.")
            return
        gp = self._get_player(interaction.guild.id)
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

    @app_commands.command(name="stop", description="⏹ Stop music and disconnect")
    async def slash_stop(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        gp.queue.clear()
        gp.loop = False
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
        await interaction.response.send_message("⏹ Stopped and disconnected.")

    @app_commands.command(name="pause", description="⏸ Pause the current song")
    async def slash_pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="▶️ Resume the paused song")
    async def slash_resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)

    @app_commands.command(name="volume", description="🔊 Set volume (1–100)")
    @app_commands.describe(level="Volume level between 1 and 100")
    async def slash_volume(self, interaction: discord.Interaction, level: int):
        if not 1 <= level <= 100:
            return await interaction.response.send_message("❌ Volume must be 1–100.", ephemeral=True)
        gp = self._get_player(interaction.guild.id)
        gp.volume = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = gp.volume
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**")

    @app_commands.command(name="queue", description="📋 Show the music queue")
    async def slash_queue(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        if not gp.current and not gp.queue:
            return await interaction.response.send_message("📭 Queue is empty.", ephemeral=True)
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
        e.set_footer(text=f"Loop: {'on' if gp.loop else 'off'} • Volume: {int(gp.volume * 100)}% • Autoplay: {'on ✨' if gp.autoplay else 'off'}")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="np", description="🎵 Show what's currently playing")
    async def slash_np(self, interaction: discord.Interaction):
        gp = self._get_player(interaction.guild.id)
        if not gp.current:
            return await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        await interaction.response.send_message(
            embed=gp.current.embed(), view=MusicControls(self, interaction.guild.id))

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
        status = "on ✨" if gp.autoplay else "off"
        embed = discord.Embed(
            title=f"✨ Autoplay {status}",
            description=(
                "When the queue runs out, I'll automatically play similar songs based on what you were listening to."
                if gp.autoplay else
                "Autoplay disabled. Queue will stop when empty."
            ),
            color=0x1DB954 if gp.autoplay else 0x6b7280
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="join", description="🎤 Join your voice channel")
    async def slash_join(self, interaction: discord.Interaction):
        vc = await self._join_voice(
            interaction.guild, interaction.user,
            lambda m: interaction.response.send_message(m, ephemeral=True)
        )
        if vc:
            await interaction.response.send_message(f"✅ Joined **{vc.channel.name}**")

    @app_commands.command(name="leave", description="👋 Leave the voice channel")
    async def slash_leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            self._get_player(interaction.guild.id).queue.clear()
            await vc.disconnect()
            await interaction.response.send_message("👋 Left the voice channel.")
        else:
            await interaction.response.send_message("❌ Not in a voice channel.", ephemeral=True)

    # ── Prefix aliases ─────────────────────────────────────────────────────────

    @commands.command(name="play", aliases=["p"])
    async def prefix_play(self, ctx, *, query: str):
        vc = await self._join_voice(ctx.guild, ctx.author, ctx.send)
        if not vc:
            return
        msg = await ctx.send(f"🔍 Searching for **{query}**...")
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
        gp.loop = False
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
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
        await ctx.send(f"🔊 Volume set to **{vol}%**")

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
        e.set_footer(text=f"Loop: {'on' if gp.loop else 'off'} • Volume: {int(gp.volume * 100)}%")
        await ctx.send(embed=e)

    @commands.command(name="nowplaying", aliases=["np"])
    async def prefix_np(self, ctx):
        gp = self._get_player(ctx.guild.id)
        if not gp.current:
            return await ctx.send("❌ Nothing is playing.")
        await ctx.send(embed=gp.current.embed(), view=MusicControls(self, ctx.guild.id))

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
            self._get_player(ctx.guild.id).queue.clear()
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
