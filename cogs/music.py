"""
WAN Bot - Music Cog
Plays audio from YouTube via yt-dlp with queue support
"""
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import logging
from collections import deque

logger = logging.getLogger('discord_bot.music')

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

def get_ytdl():
    return yt_dlp.YoutubeDL(YTDL_OPTIONS)


class MusicQueue:
    def __init__(self):
        self.queue: deque = deque()
        self.current = None
        self.loop = False

    def add(self, song):
        self.queue.append(song)

    def next(self):
        if self.loop and self.current:
            return self.current
        if self.queue:
            self.current = self.queue.popleft()
            return self.current
        self.current = None
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
    async def from_query(cls, query, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: get_ytdl().extract_info(query, download=False)),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            raise Exception("Search timed out — try a more specific query")

        if 'entries' in data:
            data = data['entries'][0]

        stream_url = data['url']
        source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
        return cls(source, data=data)

    def cleanup(self):
        try:
            self.original.cleanup()
        except Exception:
            pass


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues: dict[int, MusicQueue] = {}

    def get_queue(self, guild_id: int) -> MusicQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

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

    @app_commands.command(name="play", description="🎵 Play a song from YouTube")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Join a voice channel first.", ephemeral=True)

        await interaction.response.defer()

        vc = interaction.guild.voice_client
        if not vc:
            try:
                vc = await interaction.user.voice.channel.connect()
            except Exception as e:
                return await interaction.followup.send(f"❌ Could not connect: {e}", ephemeral=True)

        try:
            player = await YTDLSource.from_query(query, loop=self.bot.loop)
            player.requester = interaction.user
            queue = self.get_queue(interaction.guild.id)

            if vc.is_playing() or vc.is_paused():
                queue.add(player)
                embed = discord.Embed(title="➕ Added to Queue", description=f"**{player.title}**", color=0x5865f2)
                embed.set_footer(text=f"Position {len(queue.queue)} • Requested by {interaction.user.display_name}")
            else:
                queue.current = player
                def after(err):
                    if err:
                        logger.error(f"Playback error: {err}")
                    self._play_next(interaction.guild)
                vc.play(player, after=after)
                embed = discord.Embed(title="🎵 Now Playing", description=f"**{player.title}**", color=0x57f287)
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                embed.set_footer(text=f"Requested by {interaction.user.display_name}")

            # Broadcast to dashboard
            try:
                from web_dashboard_enhanced import broadcast_update
                broadcast_update('music_update', {
                    'guild_id': interaction.guild.id,
                    'action': 'now_playing',
                    'title': player.title,
                    'thumbnail': player.thumbnail,
                    'requester': interaction.user.display_name,
                    'queue_size': len(queue.queue)
                })
            except Exception:
                pass

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Play error: {e}")
            await interaction.followup.send(f"❌ Could not play: {e}", ephemeral=True)

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
        if vc and vc.is_playing():
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
            embed.add_field(name="🎵 Now Playing", value=f"**{queue.current.title}**", inline=False)
        if queue.queue:
            lines = [f"{i+1}. {s.title}" for i, s in enumerate(list(queue.queue)[:10])]
            embed.add_field(name="Up Next", value="\n".join(lines), inline=False)
        else:
            embed.description = "Queue is empty."
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="🎵 Show current song")
    async def nowplaying(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if not queue.current:
            return await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
        embed = discord.Embed(title="🎵 Now Playing", description=f"**{queue.current.title}**", color=0x57f287)
        if queue.current.thumbnail:
            embed.set_thumbnail(url=queue.current.thumbnail)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="🔊 Set volume (0-100)")
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]):
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = level / 100
            await interaction.response.send_message(f"🔊 Volume set to {level}%")
        else:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)

    @app_commands.command(name="loop", description="🔁 Toggle loop mode")
    async def loop(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        queue.loop = not queue.loop
        await interaction.response.send_message(f"🔁 Loop {'enabled' if queue.loop else 'disabled'}.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        if before.channel and self.bot.user in before.channel.members:
            humans = [m for m in before.channel.members if not m.bot]
            if not humans:
                await asyncio.sleep(60)
                guild = before.channel.guild
                if guild.voice_client and not any(not m.bot for m in guild.voice_client.channel.members):
                    await self.cleanup(guild.id)


async def setup(bot):
    await bot.add_cog(Music(bot))
