"""
WAN Bot - Music Cog (Lara-style)
Commands: !play, !stop, !skip, !pause, !resume, !volume, !queue, !np, !join, !leave, !shuffle, !loop
Supports: song names, YouTube URLs, Spotify track/album/playlist URLs
Audio source: yt-dlp (YouTube search)
"""
import discord
from discord.ext import commands
import asyncio
import yt_dlp
import logging
import random
import os
from collections import deque

logger = logging.getLogger("discord_bot.music")

YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)


def _spotify_to_search(url: str) -> str:
    """Convert Spotify URL to a YouTube search query using spotipy if available."""
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
                artists = ", ".join(a["name"] for a in t["artists"])
                return f"{t['name']} {artists}"
            elif "/album/" in url:
                aid = url.split("/album/")[1].split("?")[0]
                a = sp.album(aid)
                return f"{a['name']} {a['artists'][0]['name']}"
            elif "/playlist/" in url:
                pid = url.split("/playlist/")[1].split("?")[0]
                p = sp.playlist(pid)
                return p["name"]
    except Exception:
        pass
    return url


class Song:
    def __init__(self, data: dict, requester: discord.Member):
        self.stream_url = data.get("url", "")
        self.title      = data.get("title", "Unknown")
        self.duration   = data.get("duration", 0)
        self.thumbnail  = data.get("thumbnail")
        self.uploader   = data.get("uploader") or data.get("channel", "Unknown")
        self.webpage    = data.get("webpage_url", "")
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
        e.add_field(name="Uploader", value=self.uploader, inline=True)
        e.add_field(name="Requested by", value=self.requester.mention, inline=True)
        if self.thumbnail:
            e.set_thumbnail(url=self.thumbnail)
        return e


class GuildPlayer:
    def __init__(self):
        self.queue: deque = deque()
        self.current: Song = None
        self.volume: float = 0.5
        self.loop: bool = False


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
        status = "on" if gp.loop else "off"
        await interaction.response.send_message(f"🔁 Loop {status}", ephemeral=True, delete_after=3)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._players: dict = {}

    def _get_player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer()
        return self._players[guild_id]

    async def _ensure_voice(self, ctx) -> discord.VoiceClient:
        if ctx.author.voice is None:
            await ctx.send("❌ Join a voice channel first.")
            return None
        vc = ctx.guild.voice_client
        if vc is None:
            vc = await ctx.author.voice.channel.connect()
        elif vc.channel != ctx.author.voice.channel:
            await vc.move_to(ctx.author.voice.channel)
        return vc

    async def _fetch_song(self, query: str, requester: discord.Member) -> Song:
        loop = asyncio.get_event_loop()
        if "spotify.com" in query:
            query = _spotify_to_search(query)
        if not query.startswith("http"):
            query = f"ytsearch:{query}"
        try:
            data = await loop.run_in_executor(
                None, lambda: ytdl.extract_info(query, download=False)
            )
            if "entries" in data:
                data = data["entries"][0]
            return Song(data, requester)
        except Exception as e:
            logger.error(f"yt-dlp fetch error: {e}")
            return None

    def _play_next(self, ctx, gp: GuildPlayer):
        vc = ctx.guild.voice_client
        if vc is None:
            return
        if gp.loop and gp.current:
            gp.queue.appendleft(gp.current)
        if not gp.queue:
            gp.current = None
            asyncio.run_coroutine_threadsafe(
                ctx.send("✅ Queue finished."),
                self.bot.loop
            )
            return
        song = gp.queue.popleft()
        gp.current = song
        source = discord.FFmpegPCMAudio(song.stream_url, **FFMPEG_OPTS)
        source = discord.PCMVolumeTransformer(source, volume=gp.volume)
        vc.play(source, after=lambda e: self._play_next(ctx, gp))
        asyncio.run_coroutine_threadsafe(
            ctx.send(embed=song.embed(), view=MusicControls(self, ctx.guild.id)),
            self.bot.loop
        )

    @commands.command(name="join", aliases=["j"])
    async def join(self, ctx):
        vc = await self._ensure_voice(ctx)
        if vc:
            await ctx.send(f"✅ Joined **{vc.channel.name}**")

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx, *, query: str):
        vc = await self._ensure_voice(ctx)
        if not vc:
            return
        gp = self._get_player(ctx.guild.id)
        msg = await ctx.send("🔍 Searching...")
        song = await self._fetch_song(query, ctx.author)
        if not song:
            return await msg.edit(content="❌ Couldn't find that song. Try a different name or URL.")
        await msg.delete()
        gp.queue.append(song)
        if not vc.is_playing() and not vc.is_paused():
            self._play_next(ctx, gp)
        else:
            e = discord.Embed(
                title="➕ Added to Queue",
                description=f"[{song.title}]({song.webpage})" if song.webpage else song.title,
                color=0x1DB954
            )
            e.add_field(name="Duration", value=song.duration_str, inline=True)
            e.add_field(name="Position", value=f"#{len(gp.queue)}", inline=True)
            if song.thumbnail:
                e.set_thumbnail(url=song.thumbnail)
            await ctx.send(embed=e)

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx):
        vc = ctx.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await ctx.send("⏭ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="stop")
    async def stop(self, ctx):
        gp = self._get_player(ctx.guild.id)
        gp.queue.clear()
        gp.loop = False
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
        await ctx.send("⏹ Stopped and disconnected.")

    @commands.command(name="pause")
    async def pause(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸ Paused.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="resume", aliases=["r"])
    async def resume(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("❌ Nothing is paused.")

    @commands.command(name="volume", aliases=["v", "vol"])
    async def volume(self, ctx, vol: int):
        if not 1 <= vol <= 100:
            return await ctx.send("❌ Volume must be 1–100.")
        gp = self._get_player(ctx.guild.id)
        gp.volume = vol / 100
        vc = ctx.guild.voice_client
        if vc and vc.source:
            vc.source.volume = gp.volume
        await ctx.send(f"🔊 Volume set to **{vol}%**")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx):
        gp = self._get_player(ctx.guild.id)
        if not gp.current and not gp.queue:
            return await ctx.send("📭 Queue is empty.")
        e = discord.Embed(title="🎵 Music Queue", color=0x1DB954)
        if gp.current:
            e.add_field(
                name="Now Playing",
                value=f"[{gp.current.title}]({gp.current.webpage}) `{gp.current.duration_str}`",
                inline=False
            )
        if gp.queue:
            lines = []
            for i, s in enumerate(list(gp.queue)[:10], 1):
                lines.append(f"`{i}.` [{s.title}]({s.webpage}) `{s.duration_str}`")
            if len(gp.queue) > 10:
                lines.append(f"... and {len(gp.queue) - 10} more")
            e.add_field(name=f"Up Next ({len(gp.queue)} songs)", value="\n".join(lines), inline=False)
        e.set_footer(text=f"Loop: {'on' if gp.loop else 'off'} • Volume: {int(gp.volume * 100)}%")
        await ctx.send(embed=e)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx):
        gp = self._get_player(ctx.guild.id)
        if not gp.current:
            return await ctx.send("❌ Nothing is playing.")
        await ctx.send(embed=gp.current.embed(), view=MusicControls(self, ctx.guild.id))

    @commands.command(name="shuffle")
    async def shuffle(self, ctx):
        gp = self._get_player(ctx.guild.id)
        if not gp.queue:
            return await ctx.send("❌ Queue is empty.")
        q = list(gp.queue)
        random.shuffle(q)
        gp.queue = deque(q)
        await ctx.send("🔀 Queue shuffled!")

    @commands.command(name="loop", aliases=["l"])
    async def loop(self, ctx):
        gp = self._get_player(ctx.guild.id)
        gp.loop = not gp.loop
        await ctx.send(f"🔁 Loop {'on' if gp.loop else 'off'}")

    @commands.command(name="leave", aliases=["dc", "disconnect"])
    async def leave(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            self._get_player(ctx.guild.id).queue.clear()
            await vc.disconnect()
            await ctx.send("👋 Left the voice channel.")
        else:
            await ctx.send("❌ Not in a voice channel.")

    @commands.command(name="remove")
    async def remove(self, ctx, index: int):
        gp = self._get_player(ctx.guild.id)
        q = list(gp.queue)
        if not 1 <= index <= len(q):
            return await ctx.send(f"❌ Invalid position. Queue has {len(q)} songs.")
        removed = q.pop(index - 1)
        gp.queue = deque(q)
        await ctx.send(f"🗑️ Removed **{removed.title}**")

    @commands.command(name="clearqueue", aliases=["cq"])
    async def clear_queue(self, ctx):
        self._get_player(ctx.guild.id).queue.clear()
        await ctx.send("🗑️ Queue cleared.")


async def setup(bot):
    await bot.add_cog(Music(bot))
