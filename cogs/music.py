"""
WAN Bot - Music Cog
Plays audio from YouTube via yt-dlp with queue, shuffle, seek, and volume support.
"""
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import logging
import random
from collections import deque

logger = logging.getLogger('discord_bot.music')

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch5',   # return 5 results for /search
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}


def _run_ytdl(query: str) -> dict:
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
        return ydl.extract_info(query, download=False)


class MusicQueue:
    def __init__(self):
        self.queue: deque = deque()
        self.current = None
        self.loop = False          # loop current song
        self.loop_queue = False    # loop entire queue
        self._history: deque = deque(maxlen=20)

    def add(self, song):
        self.queue.append(song)

    def next(self):
        if self.loop and self.current:
            return self.current
        if self.current:
            self._history.append(self.current)
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

    def remove(self, index: int) -> str | None:
        """Remove song at 1-based index from queue. Returns title or None."""
        lst = list(self.queue)
        if 0 < index <= len(lst):
            removed = lst.pop(index - 1)
            self.queue = deque(lst)
            return removed.title
        return None

    def move(self, from_idx: int, to_idx: int) -> bool:
        lst = list(self.queue)
        if not (0 < from_idx <= len(lst) and 0 < to_idx <= len(lst)):
            return False
        song = lst.pop(from_idx - 1)
        lst.insert(to_idx - 1, song)
        self.queue = deque(lst)
        return True


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
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: _run_ytdl(query)),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            raise Exception("Search timed out — try a more specific query")

        if 'entries' in data:
            data = data['entries'][0]

        source = discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS)
        return cls(source, data=data, volume=volume)

    @classmethod
    async def search(cls, query: str, *, loop=None):
        """Return up to 5 search results without creating a source."""
        loop = loop or asyncio.get_event_loop()
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: _run_ytdl(query)),
                timeout=20.0,
            )
        except asyncio.TimeoutError:
            return []
        entries = data.get('entries', [data]) if 'entries' in data else [data]
        return entries[:5]

    def cleanup(self):
        try:
            self.original.cleanup()
        except Exception:
            pass


def _fmt_duration(seconds: int) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class SearchView(discord.ui.View):
    """Shows up to 5 search results as buttons."""
    def __init__(self, results: list, cog, interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.results = results
        self.cog = cog
        self.original_interaction = interaction
        for i, entry in enumerate(results[:5]):
            title = entry.get('title', 'Unknown')[:50]
            btn = discord.ui.Button(label=f"{i+1}. {title}", style=discord.ButtonStyle.secondary, row=i)
            btn.callback = self._make_callback(entry)
            self.add_item(btn)

    def _make_callback(self, entry):
        async def callback(interaction: discord.Interaction):
            self.stop()
            await interaction.response.defer()
            await self.cog._play_entry(interaction, entry)
        return callback


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues: dict[int, MusicQueue] = {}
        self._volumes: dict[int, float] = {}   # per-guild volume

    def get_queue(self, guild_id: int) -> MusicQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    def get_volume(self, guild_id: int) -> float:
        return self._volumes.get(guild_id, 0.5)

    async def cleanup(self, guild_id: int):
        if guild_id in self.queues:
            del self.queues[guild_id]
        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client:
            await guild.voice_client.disconnect(force=True)

    def _play_next(self, guild: discord.Guild):
        queue = self.get_queue(guild.id)
        next_song = queue.next()
        if next_song and guild.voice_client and guild.voice_client.is_connected():
            def after(err):
                if err:
                    logger.error(f"Playback error: {err}")
                self._play_next(guild)
            guild.voice_client.play(next_song, after=after)
            self._broadcast_now_playing(guild, next_song, queue)

    def _broadcast_now_playing(self, guild, player, queue):
        try:
            from web_dashboard_enhanced import broadcast_update
            broadcast_update('music_update', {
                'guild_id': guild.id,
                'action': 'now_playing',
                'title': player.title,
                'thumbnail': player.thumbnail,
                'duration': player.duration,
                'requester': getattr(player.requester, 'display_name', 'Dashboard'),
                'queue_size': len(queue.queue),
            })
        except Exception:
            pass

    async def _ensure_voice(self, interaction: discord.Interaction):
        """Connect to user's voice channel or return existing vc. Returns None on failure."""
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

    async def _play_entry(self, interaction: discord.Interaction, entry: dict):
        """Play a pre-fetched yt-dlp entry dict."""
        vc = await self._ensure_voice(interaction)
        if not vc:
            return
        try:
            vol = self.get_volume(interaction.guild.id)
            source = discord.FFmpegPCMAudio(entry['url'], **FFMPEG_OPTIONS)
            player = YTDLSource(source, data=entry, volume=vol)
            player.requester = interaction.user
            queue = self.get_queue(interaction.guild.id)

            if vc.is_playing() or vc.is_paused():
                queue.add(player)
                embed = discord.Embed(
                    title="➕ Added to Queue",
                    description=f"**[{player.title}]({player.url})**",
                    color=0x5865f2,
                )
                embed.set_footer(text=f"Position #{len(queue.queue)} • {_fmt_duration(player.duration)}")
            else:
                queue.current = player
                def after(err):
                    if err:
                        logger.error(f"Playback error: {err}")
                    self._play_next(interaction.guild)
                vc.play(player, after=after)
                embed = discord.Embed(
                    title="🎵 Now Playing",
                    description=f"**[{player.title}]({player.url})**",
                    color=0x57f287,
                )
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                embed.add_field(name="Duration", value=_fmt_duration(player.duration), inline=True)
                embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
                self._broadcast_now_playing(interaction.guild, player, queue)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Play entry error: {e}")
            await interaction.followup.send(f"❌ Could not play: {e}", ephemeral=True)

    # ── Commands ──────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="🎵 Play a song from YouTube (name or URL)")
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
                embed = discord.Embed(
                    title="➕ Added to Queue",
                    description=f"**[{player.title}]({player.url})**",
                    color=0x5865f2,
                )
                embed.set_footer(text=f"Position #{len(queue.queue)} • {_fmt_duration(player.duration)}")
            else:
                queue.current = player
                def after(err):
                    if err:
                        logger.error(f"Playback error: {err}")
                    self._play_next(interaction.guild)
                vc.play(player, after=after)
                embed = discord.Embed(
                    title="🎵 Now Playing",
                    description=f"**[{player.title}]({player.url})**",
                    color=0x57f287,
                )
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                embed.add_field(name="Duration", value=_fmt_duration(player.duration), inline=True)
                embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
                self._broadcast_now_playing(interaction.guild, player, queue)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Play error: {e}")
            await interaction.followup.send(f"❌ Could not play: {e}", ephemeral=True)

    @app_commands.command(name="search", description="🔍 Search YouTube and pick a result")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        results = await YTDLSource.search(query, loop=self.bot.loop)
        if not results:
            return await interaction.followup.send("❌ No results found.", ephemeral=True)
        embed = discord.Embed(title=f"🔍 Search: {query}", color=0x5865f2)
        for i, r in enumerate(results):
            embed.add_field(
                name=f"{i+1}. {r.get('title','?')[:60]}",
                value=f"`{_fmt_duration(r.get('duration',0))}`",
                inline=False,
            )
        view = SearchView(results, self, interaction)
        await interaction.followup.send(embed=embed, view=view)

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

    @app_commands.command(name="stop", description="⏹ Stop music and clear queue")
    async def stop(self, interaction: discord.Interaction):
        await self.cleanup(interaction.guild.id)
        await interaction.response.send_message("⏹ Stopped and cleared queue.")

    @app_commands.command(name="queue", description="📋 Show the music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        embed = discord.Embed(title="📋 Music Queue", color=0x5865f2)
        if queue.current:
            embed.add_field(
                name="🎵 Now Playing",
                value=f"**{queue.current.title}** `{_fmt_duration(queue.current.duration)}`",
                inline=False,
            )
        if queue.queue:
            lines = [
                f"`{i+1}.` {s.title} `{_fmt_duration(s.duration)}`"
                for i, s in enumerate(list(queue.queue)[:15])
            ]
            if len(queue.queue) > 15:
                lines.append(f"*...and {len(queue.queue)-15} more*")
            embed.add_field(name=f"Up Next ({len(queue.queue)} songs)", value="\n".join(lines), inline=False)
        else:
            embed.description = "Queue is empty."
        loop_status = "🔁 Song" if queue.loop else ("🔁 Queue" if queue.loop_queue else "Off")
        embed.set_footer(text=f"Loop: {loop_status}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="🎵 Show current song info")
    async def nowplaying(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if not queue.current:
            return await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
        p = queue.current
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**[{p.title}]({p.url})**",
            color=0x57f287,
        )
        if p.thumbnail:
            embed.set_thumbnail(url=p.thumbnail)
        embed.add_field(name="Duration", value=_fmt_duration(p.duration), inline=True)
        embed.add_field(name="Requested by", value=getattr(p.requester, 'mention', 'Unknown'), inline=True)
        embed.add_field(name="Queue", value=f"{len(queue.queue)} song(s) up next", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="🔊 Set volume (0–100)")
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]):
        self._volumes[interaction.guild.id] = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = level / 100
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**")

    @app_commands.command(name="loop", description="🔁 Toggle loop mode (song / queue / off)")
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
        queue = self.get_queue(interaction.guild.id)
        title = queue.remove(position)
        if title:
            await interaction.response.send_message(f"🗑 Removed **{title}** from queue.")
        else:
            await interaction.response.send_message("❌ Invalid position.", ephemeral=True)

    @app_commands.command(name="move", description="↕️ Move a song to a different queue position")
    async def move(self, interaction: discord.Interaction,
                   from_position: app_commands.Range[int, 1, 100],
                   to_position: app_commands.Range[int, 1, 100]):
        queue = self.get_queue(interaction.guild.id)
        if queue.move(from_position, to_position):
            await interaction.response.send_message(f"↕️ Moved song from position {from_position} to {to_position}.")
        else:
            await interaction.response.send_message("❌ Invalid positions.", ephemeral=True)

    @app_commands.command(name="clearqueue", description="🗑 Clear the entire queue (keeps current song)")
    async def clearqueue(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        count = len(queue.queue)
        queue.queue.clear()
        await interaction.response.send_message(f"🗑 Cleared {count} song(s) from queue.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        """Auto-disconnect when bot is alone in voice channel for 60 seconds."""
        if member.bot:
            return
        guild = member.guild
        vc = guild.voice_client
        if not vc:
            return
        # Check if bot is now alone
        humans = [m for m in vc.channel.members if not m.bot]
        if not humans:
            await asyncio.sleep(60)
            # Re-check after sleep
            vc = guild.voice_client
            if vc and not any(not m.bot for m in vc.channel.members):
                await self.cleanup(guild.id)


async def setup(bot):
    await bot.add_cog(Music(bot))
