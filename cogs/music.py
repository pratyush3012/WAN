"""
WAN Bot - Music Cog
24/7 mode: bot stays in voice forever, queue never ends (autoplay from history),
auto-rejoins on restart. No auto-disconnect.
"""
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import logging
import random
import json
import os
from collections import deque

logger = logging.getLogger('discord_bot.music')

PERSIST_FILE = 'music_247.json'

YTDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch5',
    'source_address': '0.0.0.0',
    'playlistend': 50,
}

YTDL_SINGLE = {**YTDL_OPTS, 'noplaylist': True, 'default_search': 'ytsearch'}

FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

AUTOPLAY_SEEDS = [
    "top hits 2024", "best pop songs", "chill vibes playlist",
    "hip hop hits", "lofi hip hop", "trending music 2024",
    "best rap songs", "workout music", "party hits",
]


def _ytdl_extract(query: str, single: bool = True) -> dict:
    opts = YTDL_SINGLE if single else YTDL_OPTS
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(query, download=False)


def _fmt(seconds) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class MusicQueue:
    def __init__(self):
        self.queue: deque = deque()
        self.current = None
        self.loop = False        # repeat current song
        self.loop_queue = False  # repeat whole queue
        self.history: deque = deque(maxlen=50)  # used for autoplay

    def add(self, song): self.queue.append(song)

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
        lst = list(self.queue); random.shuffle(lst); self.queue = deque(lst)

    def remove(self, idx: int):
        lst = list(self.queue)
        if 0 < idx <= len(lst):
            removed = lst.pop(idx - 1); self.queue = deque(lst); return removed.title
        return None

    def move(self, fr: int, to: int) -> bool:
        lst = list(self.queue)
        if not (0 < fr <= len(lst) and 0 < to <= len(lst)): return False
        song = lst.pop(fr - 1); lst.insert(to - 1, song); self.queue = deque(lst); return True


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
            loop.run_in_executor(None, lambda: _ytdl_extract(query, single=True)),
            timeout=30.0,
        )
        if 'entries' in data:
            data = data['entries'][0]
        src = discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTS)
        return cls(src, data=data, volume=volume)

    @classmethod
    async def search_results(cls, query: str, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: _ytdl_extract(query, single=False)),
                timeout=20.0,
            )
        except Exception:
            return []
        entries = data.get('entries', [data]) if 'entries' in data else [data]
        return [e for e in entries if e][:5]

    @classmethod
    async def from_playlist(cls, url: str, *, loop=None, volume=0.5):
        """Return list of YTDLSource objects from a playlist URL (up to 50)."""
        loop = loop or asyncio.get_event_loop()
        data = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _ytdl_extract(url, single=False)),
            timeout=60.0,
        )
        entries = data.get('entries', [data]) if 'entries' in data else [data]
        sources = []
        for entry in entries:
            if not entry:
                continue
            try:
                src = discord.FFmpegPCMAudio(entry['url'], **FFMPEG_OPTS)
                sources.append(cls(src, data=entry, volume=volume))
            except Exception:
                continue
        return sources


class SearchView(discord.ui.View):
    def __init__(self, results, cog, interaction):
        super().__init__(timeout=60)
        self.results = results; self.cog = cog
        for i, entry in enumerate(results[:5]):
            title = (entry.get('title') or 'Unknown')[:50]
            btn = discord.ui.Button(label=f"{i+1}. {title}", style=discord.ButtonStyle.secondary, row=min(i, 4))
            btn.callback = self._cb(entry)
            self.add_item(btn)

    def _cb(self, entry):
        async def callback(interaction: discord.Interaction):
            self.stop()
            await interaction.response.defer()
            await self.cog._play_entry(interaction, entry)
        return callback


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues: dict[int, MusicQueue] = {}
        self._volumes: dict[int, float] = {}
        self._247: dict[int, int] = self._load_247()   # guild_id -> channel_id
        self._autoplay: dict[int, bool] = {}           # guild_id -> bool
        self._reconnect_task = bot.loop.create_task(self._reconnect_loop())

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
                json.dump(self._247, f)
        except Exception as e:
            logger.error(f"Save 24/7 failed: {e}")

    # ── 24/7 reconnect loop ───────────────────────────────────────────────

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
                        logger.info(f"24/7 reconnect → {channel.name} ({guild.name})")
                        await channel.connect()
                    elif vc.channel.id != channel_id:
                        await vc.move_to(channel)
                except Exception as e:
                    logger.warning(f"24/7 reconnect error guild {guild_id}: {e}")
            await asyncio.sleep(30)

    # ── Helpers ───────────────────────────────────────────────────────────

    def get_queue(self, guild_id: int) -> MusicQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    def get_volume(self, guild_id: int) -> float:
        return self._volumes.get(guild_id, 0.5)

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
        """Called after each song ends. Handles autoplay when queue is empty."""
        queue = self.get_queue(guild.id)
        next_song = queue.next()

        if next_song:
            self._start_playing(guild, next_song, queue)
            return

        # Queue is empty — trigger autoplay if enabled
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

    async def _autoplay_next(self, guild: discord.Guild):
        """Pick a related/random song and play it automatically."""
        queue = self.get_queue(guild.id)
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return
        if vc.is_playing():
            return  # something started already

        # Use last played song title as seed, else random seed
        seed = None
        if queue.history:
            seed = queue.history[-1].title
        if not seed:
            seed = random.choice(AUTOPLAY_SEEDS)

        try:
            vol = self.get_volume(guild.id)
            player = await YTDLSource.from_query(
                f"ytsearch:{seed} mix", loop=self.bot.loop, volume=vol
            )
            player.requester = None  # autoplay
            queue.current = player
            self._start_playing(guild, player, queue)
            logger.info(f"Autoplay: {player.title} in {guild.name}")
        except Exception as e:
            logger.warning(f"Autoplay failed: {e}")
            # Retry with a random seed after 5s
            await asyncio.sleep(5)
            await self._autoplay_next(guild)

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
    # COMMANDS
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

    @app_commands.command(name="playlist", description="📋 Queue an entire YouTube playlist")
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
                description=f"Added **{len(songs) + (1 if not vc.is_playing() else 0)}** songs to the queue.",
                color=0x5865f2)
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Playlist error: {e}")
            await interaction.followup.send(f"❌ Could not load playlist: {e}", ephemeral=True)

    @app_commands.command(name="search", description="🔍 Search YouTube and pick a result")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        results = await YTDLSource.search_results(query, loop=self.bot.loop)
        if not results:
            return await interaction.followup.send("❌ No results found.", ephemeral=True)
        embed = discord.Embed(title=f"🔍 Results for: {query}", color=0x5865f2)
        for i, r in enumerate(results):
            embed.add_field(name=f"{i+1}. {(r.get('title') or '?')[:60]}",
                value=f"`{_fmt(r.get('duration', 0))}`", inline=False)
        await interaction.followup.send(embed=embed, view=SearchView(results, self, interaction))

    @app_commands.command(name="247", description="🔴 Toggle 24/7 mode — bot stays in VC forever")
    async def cmd_247(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ You need Manage Server permission.", ephemeral=True)
        gid = interaction.guild.id
        if gid in self._247:
            del self._247[gid]
            self._save_247()
            await interaction.response.send_message("🔴 24/7 mode **disabled**. Bot will leave when queue ends.")
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
                f"Bot will stay here forever and autoplay music when the queue ends."
            )

    @app_commands.command(name="autoplay", description="🔀 Toggle autoplay when queue ends")
    async def autoplay(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        current = self._autoplay.get(gid, True)
        self._autoplay[gid] = not current
        state = "enabled" if not current else "disabled"
        await interaction.response.send_message(
            f"{'🟢' if not current else '🔴'} Autoplay **{state}**. "
            f"{'Bot will keep playing related songs when queue ends.' if not current else 'Bot will wait silently when queue ends.'}"
        )

    @app_commands.command(name="join", description="📥 Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Join a voice channel first.", ephemeral=True)
        ch = interaction.user.voice.channel
        vc = interaction.guild.voice_client
        if vc:
            await vc.move_to(ch)
        else:
            await ch.connect()
        await interaction.response.send_message(f"📥 Joined **{ch.name}**.")

    @app_commands.command(name="leave", description="📤 Leave voice channel (disables 24/7 for this session)")
    async def leave(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ You need Manage Server permission.", ephemeral=True)
        gid = interaction.guild.id
        # Temporarily remove from 24/7 so cleanup disconnects
        was_247 = gid in self._247
        if was_247:
            del self._247[gid]
            self._save_247()
        queue = self.get_queue(gid)
        queue.clear()
        if gid in self.queues:
            del self.queues[gid]
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect(force=True)
        msg = "📤 Left voice channel."
        if was_247:
            msg += " 24/7 mode disabled — use `/247` to re-enable."
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
            vc.stop()  # triggers after() → _play_next
            await interaction.response.send_message("⏭ Skipped.")
        else:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)

    @app_commands.command(name="stop", description="⏹ Stop music and clear queue (bot stays in VC)")
    async def stop(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        queue = self.get_queue(gid)
        queue.clear()
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
        embed.add_field(name="Requested by",
            value=getattr(p.requester, 'mention', '🤖 Autoplay'), inline=True)
        embed.add_field(name="Queue", value=f"{len(queue.queue)} song(s) up next", inline=True)
        is_247 = interaction.guild.id in self._247
        embed.set_footer(text=f"{'🟢 24/7 ON' if is_247 else '🔴 24/7 OFF'} • Autoplay: {'ON' if self._autoplay.get(interaction.guild.id, True) else 'OFF'}")
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
            ap = self._autoplay.get(interaction.guild.id, True)
            embed.add_field(name="Queue Empty",
                value="🤖 Autoplay will pick the next song." if ap else "Add songs with `/play`.",
                inline=False)
        loop_s = "🔁 Song" if queue.loop else ("🔁 Queue" if queue.loop_queue else "Off")
        is_247 = interaction.guild.id in self._247
        embed.set_footer(text=f"Loop: {loop_s} • {'🟢 24/7 ON' if is_247 else '🔴 24/7 OFF'}")
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

    @app_commands.command(name="remove", description="🗑 Remove a song from the queue by position")
    async def remove(self, interaction: discord.Interaction, position: app_commands.Range[int, 1, 100]):
        title = self.get_queue(interaction.guild.id).remove(position)
        if title:
            await interaction.response.send_message(f"🗑 Removed **{title}**.")
        else:
            await interaction.response.send_message("❌ Invalid position.", ephemeral=True)

    @app_commands.command(name="move", description="↕️ Move a song to a different queue position")
    async def move(self, interaction: discord.Interaction,
                   from_position: app_commands.Range[int, 1, 100],
                   to_position: app_commands.Range[int, 1, 100]):
        if self.get_queue(interaction.guild.id).move(from_position, to_position):
            await interaction.response.send_message(f"↕️ Moved #{from_position} → #{to_position}.")
        else:
            await interaction.response.send_message("❌ Invalid positions.", ephemeral=True)

    @app_commands.command(name="clearqueue", description="🗑 Clear the queue (keeps current song playing)")
    async def clearqueue(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        count = len(queue.queue)
        queue.queue.clear()
        await interaction.response.send_message(f"🗑 Cleared {count} song(s) from queue.")

    # ── No auto-disconnect listener — bot stays forever ───────────────────
    # The only way to remove the bot is /leave (requires Manage Server)


async def setup(bot):
    await bot.add_cog(Music(bot))
