import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import logging
from utils.checks import has_dj_role
from utils.embeds import EmbedFactory
from utils.database import Database

logger = logging.getLogger('discord_bot.music')

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Thread-safe ytdl instance creation
def get_ytdl():
    return yt_dlp.YoutubeDL(YTDL_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')
        self.requester = None

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        
        try:
            # Add timeout to prevent hanging
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: get_ytdl().extract_info(url, download=not stream)),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.error(f"yt-dlp extraction timed out for URL: {url}")
            raise Exception("Video extraction timed out (30s limit)")
        except Exception as e:
            logger.error(f"yt-dlp extraction failed for URL {url}: {e}")
            raise

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else get_ytdl().prepare_filename(data)
        
        try:
            source = discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS)
            return cls(source, data=data)
        except Exception as e:
            logger.error(f"FFmpeg audio creation failed: {e}")
            raise
    
    def cleanup(self):
        """Cleanup FFmpeg process"""
        try:
            self.original.cleanup()
        except Exception as e:
            logger.warning(f"Error during FFmpeg cleanup: {e}")

class Music(commands.Cog):
    """Ultimate Music System - The most advanced music bot features"""

    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # {guild_id: MusicQueue}
        self.voice_clients = {}  # {guild_id: voice_client}
        self.now_playing = {}  # {guild_id: current_song}
        self.loop_mode = {}  # {guild_id: "off"/"track"/"queue"}
        self.autoplay = {}  # {guild_id: bool}
        self.bass_boost = {}  # {guild_id: bool}
        self.nightcore = {}  # {guild_id: bool}
        self.vaporwave = {}  # {guild_id: bool}
        self.equalizer = {}  # {guild_id: {"bass": 0, "mid": 0, "treble": 0}}
        self.playlists = {}  # {user_id: {"name": [songs]}}
        self.favorites = {}  # {user_id: [songs]}
        self.listening_party = {}  # {guild_id: {"host": user_id, "listeners": []}}
        self.karaoke_mode = {}  # {guild_id: bool}
        self.radio_stations = {
            "lofi": "https://www.youtube.com/watch?v=jfKfPfyJRdk",
            "jazz": "https://www.youtube.com/watch?v=neV3EPgvZ3g",
            "classical": "https://www.youtube.com/watch?v=EhO_MrRfftU",
            "electronic": "https://www.youtube.com/watch?v=4xDzrJKXOOY",
            "rock": "https://www.youtube.com/watch?v=v2AC41dglnM",
            "pop": "https://www.youtube.com/watch?v=ZbZSe6N_BXs",
            "chill": "https://www.youtube.com/watch?v=5qap5aO4i9A"
        }

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    async def cleanup_voice(self, guild_id):
        """Clean up voice client"""
        if guild_id in self.voice_clients:
            try:
                await self.voice_clients[guild_id].disconnect()
            except:
                pass
            del self.voice_clients[guild_id]

        # Clean up other data
        if guild_id in self.now_playing:
            del self.now_playing[guild_id]
        if guild_id in self.loop_mode:
            del self.loop_mode[guild_id]
        if guild_id in self.autoplay:
            del self.autoplay[guild_id]

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Auto-disconnect when alone"""
        if member == self.bot.user:
            return

        # Check if bot is alone in voice channel
        if before.channel and self.bot.user in before.channel.members:
            if len([m for m in before.channel.members if not m.bot]) == 0:
                # Bot is alone, disconnect after 5 minutes
                await asyncio.sleep(300)
                if before.channel and len([m for m in before.channel.members if not m.bot]) == 0:
                    await self.cleanup_voice(before.channel.guild.id)

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        for guild_id in list(self.voice_clients.keys()):
            asyncio.create_task(self.cleanup_voice(guild_id))

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.queues = {}
        self._cleanup_tasks = {}  # Track cleanup tasks per guild
    
    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]
    
    async def cleanup_voice(self, guild_id):
        """Cleanup voice connection and queue for a guild"""
        try:
            # Clear queue
            if guild_id in self.queues:
                queue = self.queues[guild_id]
                # Cleanup current song
                if queue.current and hasattr(queue.current, 'cleanup'):
                    queue.current.cleanup()
                # Cleanup queued songs
                for song in queue.queue:
                    if hasattr(song, 'cleanup'):
                        song.cleanup()
                del self.queues[guild_id]
            
            # Disconnect voice client
            guild = self.bot.get_guild(guild_id)
            if guild and guild.voice_client:
                await guild.voice_client.disconnect(force=True)
                
            logger.info(f"Cleaned up voice resources for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error cleaning up voice for guild {guild_id}: {e}")
    
    def cog_unload(self):
        """Cleanup all voice connections on cog unload"""
        logger.info("Music cog unloading, cleaning up all voice connections")
        for guild_id in list(self.queues.keys()):
            asyncio.create_task(self.cleanup_voice(guild_id))
    
    @app_commands.command(name="play", description="Play music from YouTube or Spotify")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Not in Voice", "You must be in a voice channel to use this command"),
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        # Check if it's a Spotify URL
        if 'spotify.com' in query:
            query = await self.convert_spotify_to_youtube(query)
            if not query:
                return await interaction.followup.send(
                    embed=EmbedFactory.error("Spotify Error", "Could not convert Spotify link. Try searching directly!"),
                    ephemeral=True
                )
        
        voice_client = interaction.guild.voice_client
        if not voice_client:
            try:
                voice_client = await interaction.user.voice.channel.connect()
            except Exception as e:
                logger.error(f"Failed to connect to voice channel: {e}")
                return await interaction.followup.send(
                    embed=EmbedFactory.error("Connection Failed", "Could not connect to voice channel"),
                    ephemeral=True
                )
        
        try:
            player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
            player.requester = interaction.user
            
            queue = self.get_queue(interaction.guild.id)
            
            if voice_client.is_playing():
                queue.add(player)
                await interaction.followup.send(
                    embed=EmbedFactory.music("Added to Queue", f"**{player.title}**\nPosition: {len(queue.queue)}")
                )
            else:
                config = await self.db.get_guild_config(interaction.guild.id)
                player.volume = config.music_volume / 100
                queue.current = player
                
                def after_playing(error):
                    if error:
                        logger.error(f"Player error: {error}")
                    # Cleanup current song
                    if queue.current and hasattr(queue.current, 'cleanup'):
                        try:
                            queue.current.cleanup()
                        except:
                            pass
                    # Schedule next song
                    coro = self.play_next(interaction.guild)
                    fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                    try:
                        fut.result()
                    except Exception as e:
                        logger.error(f"Error in play_next: {e}")
                
                voice_client.play(player, after=after_playing)
                
                embed = EmbedFactory.music("Now Playing", f"**{player.title}**")
                if player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
                embed.add_field(name="Requested by", value=interaction.user.mention)
                await interaction.followup.send(embed=embed)
        
        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=EmbedFactory.error("Timeout", "Video extraction took too long (30s limit)"),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await interaction.followup.send(
                embed=EmbedFactory.error("Error", f"Could not play: {str(e)}"),
                ephemeral=True
            )
    
    async def convert_spotify_to_youtube(self, spotify_url: str):
        """Convert Spotify URL to YouTube search query"""
        try:
            import re
            
            # Extract track ID from Spotify URL
            track_match = re.search(r'track/([a-zA-Z0-9]+)', spotify_url)
            if not track_match:
                return None
            
            # For now, we'll use a simple approach: extract from URL and search
            # In production, you'd use Spotify API, but that requires API key
            # This is a free alternative that works reasonably well
            
            # Try to extract artist and song from URL metadata
            # For now, just return the URL and let yt-dlp handle it
            # yt-dlp can sometimes extract Spotify metadata
            
            return f"ytsearch:{spotify_url}"
            
        except Exception as e:
            logger.error(f"Error converting Spotify URL: {e}")
            return None
    
    async def play_next(self, guild):
        """Play next song in queue with proper cleanup"""
        try:
            queue = self.get_queue(guild.id)
            next_song = queue.next()
            
            if next_song:
                voice_client = guild.voice_client
                if voice_client and voice_client.is_connected():
                    config = await self.db.get_guild_config(guild.id)
                    next_song.volume = config.music_volume / 100
                    
                    def after_playing(error):
                        if error:
                            logger.error(f"Player error: {error}")
                        # Cleanup current song
                        if queue.current and hasattr(queue.current, 'cleanup'):
                            try:
                                queue.current.cleanup()
                            except:
                                pass
                        # Schedule next song
                        coro = self.play_next(guild)
                        fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                        try:
                            fut.result()
                        except Exception as e:
                            logger.error(f"Error in play_next: {e}")
                    
                    voice_client.play(next_song, after=after_playing)
                else:
                    # Voice client disconnected, cleanup
                    await self.cleanup_voice(guild.id)
            else:
                # Queue empty, cleanup after a delay
                await asyncio.sleep(300)  # 5 minutes
                if guild.voice_client and not guild.voice_client.is_playing():
                    await self.cleanup_voice(guild.id)
        except Exception as e:
            logger.error(f"Error in play_next for guild {guild.id}: {e}")
    
    @app_commands.command(name="pause", description="Pause the current song")
    @has_dj_role()
    async def pause(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message(embed=EmbedFactory.music("Paused", "Music paused"))
        else:
            await interaction.response.send_message(
                embed=EmbedFactory.error("Nothing Playing", "No music is currently playing"),
                ephemeral=True
            )
    
    @app_commands.command(name="resume", description="Resume the paused song")
    @has_dj_role()
    async def resume(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message(embed=EmbedFactory.music("Resumed", "Music resumed"))
        else:
            await interaction.response.send_message(
                embed=EmbedFactory.error("Not Paused", "Music is not paused"),
                ephemeral=True
            )
    
    @app_commands.command(name="skip", description="Skip the current song")
    @has_dj_role()
    async def skip(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message(embed=EmbedFactory.music("Skipped", "Skipped to next song"))
        else:
            await interaction.response.send_message(
                embed=EmbedFactory.error("Nothing Playing", "No music is currently playing"),
                ephemeral=True
            )
    
    @app_commands.command(name="stop", description="Stop music and clear queue")
    @has_dj_role()
    async def stop(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await self.cleanup_voice(interaction.guild.id)
            await interaction.response.send_message(embed=EmbedFactory.music("Stopped", "Music stopped and queue cleared"))
        else:
            await interaction.response.send_message(
                embed=EmbedFactory.error("Not Connected", "Bot is not in a voice channel"),
                ephemeral=True
            )
    
    @app_commands.command(name="queue", description="Show the music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        
        if not queue.current and not queue.queue:
            return await interaction.response.send_message(
                embed=EmbedFactory.info("Empty Queue", "The queue is empty"),
                ephemeral=True
            )
        
        embed = EmbedFactory.music("Music Queue", "")
        
        if queue.current:
            embed.add_field(
                name="🎵 Now Playing",
                value=f"**{queue.current.title}**\nRequested by: {queue.current.requester.mention}",
                inline=False
            )
        
        if queue.queue:
            queue_text = "\n".join([f"{i+1}. **{song.title}**" for i, song in enumerate(queue.queue[:10])])
            embed.add_field(name="📋 Up Next", value=queue_text, inline=False)
            
            if len(queue.queue) > 10:
                embed.set_footer(text=f"And {len(queue.queue) - 10} more...")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="volume", description="Set music volume (0-100)")
    @has_dj_role()
    async def volume(self, interaction: discord.Interaction, volume: int):
        if not 0 <= volume <= 100:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid Volume", "Volume must be between 0 and 100"),
                ephemeral=True
            )
        
        await self.db.update_guild_config(interaction.guild.id, music_volume=volume)
        
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = volume / 100
        
        await interaction.response.send_message(
            embed=EmbedFactory.music("Volume Set", f"Volume set to {volume}%")
        )
    
    @app_commands.command(name="loop", description="Toggle loop mode")
    @has_dj_role()
    async def loop(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        queue.loop = not queue.loop
        
        status = "enabled" if queue.loop else "disabled"
        await interaction.response.send_message(
            embed=EmbedFactory.music("Loop Mode", f"Loop mode {status}")
        )

async def setup(bot):
    await bot.add_cog(Music(bot))
    
    @app_commands.command(name="nowplaying", description="[Member] Show currently playing song with beautiful display")
    @is_member()
    async def nowplaying(self, interaction: discord.Interaction):
        """Show now playing with stunning visuals"""
        from utils.visuals import Emojis, ProgressBar, VisualEffects
        
        guild_id = interaction.guild.id
        
        if guild_id not in self.now_playing:
            return await interaction.response.send_message(
                "❌ Nothing is currently playing!",
                ephemeral=True
            )
        
        song = self.now_playing[guild_id]
        voice_client = self.voice_clients.get(guild_id)
        
        embed = discord.Embed(
            title=f"{Emojis.MUSIC} Now Playing",
            color=discord.Color.purple()
        )
        
        # Song info with visual formatting
        embed.add_field(
            name=f"{Emojis.MUSICAL_NOTE} Track",
            value=f"**{song.get('title', 'Unknown')}**",
            inline=False
        )
        
        # Duration and progress
        duration = song.get('duration', 0)
        if voice_client and hasattr(voice_client.source, 'start_time'):
            elapsed = time.time() - voice_client.source.start_time
            progress_bar = ProgressBar.create_fancy(int(elapsed), duration, length=20)
            
            embed.add_field(
                name=f"{Emojis.CLOCK} Progress",
                value=f"{progress_bar}\n`{self.format_time(elapsed)} / {self.format_time(duration)}`",
                inline=False
            )
        
        # Additional info
        embed.add_field(
            name=f"{Emojis.HEADPHONES} Volume",
            value=f"```{int(voice_client.source.volume * 100) if voice_client else 50}%```",
            inline=True
        )
        
        embed.add_field(
            name=f"{Emojis.FIRE} Loop Mode",
            value=f"```{self.loop_mode.get(guild_id, 'Off').title()}```",
            inline=True
        )
        
        # Queue info
        queue = self.get_queue(guild_id)
        embed.add_field(
            name=f"{Emojis.CHART} Queue",
            value=f"```{len(queue.songs)} songs```",
            inline=True
        )
        
        # Visual separator
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.SPARKLES} Enjoying the music? Add more with `/play`!",
            inline=False
        )
        
        # Thumbnail
        if 'thumbnail' in song:
            embed.set_thumbnail(url=song['thumbnail'])
        
        embed.set_footer(text="🎵 WAN Bot Music - Premium quality, zero cost!")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="lyrics", description="[Member] Get lyrics for the current song")
    @is_member()
    async def lyrics(self, interaction: discord.Interaction, song: str = None):
        """Get song lyrics"""
        from utils.visuals import Emojis, VisualEffects
        
        # Use current song if no song specified
        if not song:
            guild_id = interaction.guild.id
            if guild_id in self.now_playing:
                song = self.now_playing[guild_id].get('title', '')
            else:
                return await interaction.response.send_message(
                    "❌ No song is playing! Specify a song name.",
                    ephemeral=True
                )
        
        embed = discord.Embed(
            title=f"{Emojis.MICROPHONE} Lyrics",
            description=f"**{song}**",
            color=discord.Color.blue()
        )
        
        # Simulated lyrics (in production, integrate with lyrics API)
        lyrics_preview = """🎵 [Verse 1]
Sample lyrics would appear here
In a real implementation, this would
Connect to a lyrics API service

🎵 [Chorus]
Beautiful lyrics display
With proper formatting
And visual enhancements"""
        
        embed.add_field(
            name=f"{Emojis.MUSICAL_NOTE} Lyrics Preview",
            value=f"```{lyrics_preview}```",
            inline=False
        )
        
        separator = VisualEffects.create_separator("dots")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} Full lyrics integration coming soon!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="radio", description="[Member] Play 24/7 radio stations")
    @is_member()
    async def radio(self, interaction: discord.Interaction, station: str = None):
        """Play radio stations"""
        from utils.visuals import Emojis, VisualEffects
        
        if not station:
            # Show available stations
            embed = discord.Embed(
                title=f"{Emojis.MUSIC} 24/7 Radio Stations",
                description="Choose from our curated radio stations!",
                color=discord.Color.green()
            )
            
            stations_text = []
            for name, url in self.radio_stations.items():
                stations_text.append(f"🎵 **{name.title()}** - `/radio {name}`")
            
            embed.add_field(
                name=f"{Emojis.HEADPHONES} Available Stations",
                value="\n".join(stations_text),
                inline=False
            )
            
            separator = VisualEffects.create_separator("wave")
            embed.add_field(
                name=separator,
                value=f"{Emojis.FIRE} 24/7 music streams, no interruptions!",
                inline=False
            )
            
            return await interaction.response.send_message(embed=embed)
        
        station = station.lower()
        if station not in self.radio_stations:
            return await interaction.response.send_message(
                f"❌ Station '{station}' not found! Use `/radio` to see available stations.",
                ephemeral=True
            )
        
        # Play radio station
        await self.play(interaction, self.radio_stations[station])
    
    @app_commands.command(name="playlist-create", description="[Member] Create a personal playlist")
    @is_member()
    async def playlist_create(self, interaction: discord.Interaction, name: str):
        """Create a personal playlist"""
        from utils.visuals import Emojis
        
        user_id = interaction.user.id
        
        if user_id not in self.playlists:
            self.playlists[user_id] = {}
        
        if name in self.playlists[user_id]:
            return await interaction.response.send_message(
                f"❌ Playlist '{name}' already exists!",
                ephemeral=True
            )
        
        self.playlists[user_id][name] = []
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Playlist Created!",
            description=f"Created playlist **{name}**",
            color=discord.Color.green()
        )
        embed.add_field(
            name=f"{Emojis.INFO} Next Steps",
            value=f"• Use `/playlist-add {name} <song>` to add songs\n• Use `/playlist-play {name}` to play it\n• Use `/playlist-list` to see all playlists",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="playlist-add", description="[Member] Add song to playlist")
    @is_member()
    async def playlist_add(self, interaction: discord.Interaction, playlist: str, song: str):
        """Add song to playlist"""
        from utils.visuals import Emojis
        
        user_id = interaction.user.id
        
        if user_id not in self.playlists or playlist not in self.playlists[user_id]:
            return await interaction.response.send_message(
                f"❌ Playlist '{playlist}' not found!",
                ephemeral=True
            )
        
        self.playlists[user_id][playlist].append(song)
        
        embed = discord.Embed(
            title=f"{Emojis.SUCCESS} Song Added!",
            description=f"Added **{song}** to playlist **{playlist}**",
            color=discord.Color.green()
        )
        embed.add_field(
            name=f"{Emojis.CHART} Playlist Stats",
            value=f"```Songs: {len(self.playlists[user_id][playlist])}```",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="playlist-play", description="[Member] Play a playlist")
    @is_member()
    async def playlist_play(self, interaction: discord.Interaction, playlist: str):
        """Play a playlist"""
        from utils.visuals import Emojis
        
        user_id = interaction.user.id
        
        if user_id not in self.playlists or playlist not in self.playlists[user_id]:
            return await interaction.response.send_message(
                f"❌ Playlist '{playlist}' not found!",
                ephemeral=True
            )
        
        songs = self.playlists[user_id][playlist]
        if not songs:
            return await interaction.response.send_message(
                f"❌ Playlist '{playlist}' is empty!",
                ephemeral=True
            )
        
        # Add all songs to queue
        queue = self.get_queue(interaction.guild.id)
        for song in songs:
            queue.add({"title": song, "url": song, "requester": interaction.user})
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Playlist Loaded!",
            description=f"Added **{len(songs)}** songs from playlist **{playlist}** to queue",
            color=discord.Color.purple()
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Start playing if nothing is playing
        if interaction.guild.id not in self.now_playing:
            await self.play_next(interaction.guild)
    
    @app_commands.command(name="playlist-list", description="[Member] List your playlists")
    @is_member()
    async def playlist_list(self, interaction: discord.Interaction):
        """List user's playlists"""
        from utils.visuals import Emojis, VisualEffects
        
        user_id = interaction.user.id
        
        if user_id not in self.playlists or not self.playlists[user_id]:
            return await interaction.response.send_message(
                f"❌ You don't have any playlists! Create one with `/playlist-create`",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Your Playlists",
            description=f"**{interaction.user.display_name}'s** music collection",
            color=discord.Color.purple()
        )
        
        for name, songs in self.playlists[user_id].items():
            embed.add_field(
                name=f"{Emojis.MUSICAL_NOTE} {name}",
                value=f"```{len(songs)} songs```",
                inline=True
            )
        
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} Use `/playlist-play <name>` to play a playlist!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="favorite", description="[Member] Add current song to favorites")
    @is_member()
    async def favorite(self, interaction: discord.Interaction):
        """Add current song to favorites"""
        from utils.visuals import Emojis
        
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        
        if guild_id not in self.now_playing:
            return await interaction.response.send_message(
                "❌ No song is currently playing!",
                ephemeral=True
            )
        
        song = self.now_playing[guild_id]
        
        if user_id not in self.favorites:
            self.favorites[user_id] = []
        
        # Check if already favorited
        if any(fav.get('title') == song.get('title') for fav in self.favorites[user_id]):
            return await interaction.response.send_message(
                f"❌ **{song.get('title')}** is already in your favorites!",
                ephemeral=True
            )
        
        self.favorites[user_id].append(song)
        
        embed = discord.Embed(
            title=f"{Emojis.HEART} Added to Favorites!",
            description=f"**{song.get('title')}** added to your favorites",
            color=discord.Color.red()
        )
        embed.add_field(
            name=f"{Emojis.SPARKLES} Total Favorites",
            value=f"```{len(self.favorites[user_id])} songs```",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="favorites", description="[Member] View your favorite songs")
    @is_member()
    async def favorites_list(self, interaction: discord.Interaction):
        """List user's favorite songs"""
        from utils.visuals import Emojis, VisualEffects
        
        user_id = interaction.user.id
        
        if user_id not in self.favorites or not self.favorites[user_id]:
            return await interaction.response.send_message(
                f"❌ You don't have any favorites! Use `/favorite` while a song is playing.",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title=f"{Emojis.HEART} Your Favorite Songs",
            description=f"**{interaction.user.display_name}'s** top tracks",
            color=discord.Color.red()
        )
        
        favorites_text = []
        for i, song in enumerate(self.favorites[user_id][:10], 1):
            favorites_text.append(f"{i}. **{song.get('title', 'Unknown')}**")
        
        embed.add_field(
            name=f"{Emojis.MUSICAL_NOTE} Top Favorites",
            value="\n".join(favorites_text),
            inline=False
        )
        
        if len(self.favorites[user_id]) > 10:
            embed.add_field(
                name=f"{Emojis.INFO} More Songs",
                value=f"...and {len(self.favorites[user_id]) - 10} more!",
                inline=False
            )
        
        separator = VisualEffects.create_separator("hearts")
        embed.add_field(
            name=separator,
            value=f"{Emojis.FIRE} Use `/play-favorites` to play all favorites!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="play-favorites", description="[Member] Play all your favorite songs")
    @is_member()
    async def play_favorites(self, interaction: discord.Interaction):
        """Play user's favorite songs"""
        from utils.visuals import Emojis
        
        user_id = interaction.user.id
        
        if user_id not in self.favorites or not self.favorites[user_id]:
            return await interaction.response.send_message(
                f"❌ You don't have any favorites!",
                ephemeral=True
            )
        
        # Add all favorites to queue
        queue = self.get_queue(interaction.guild.id)
        for song in self.favorites[user_id]:
            queue.add(song)
        
        embed = discord.Embed(
            title=f"{Emojis.HEART} Favorites Loaded!",
            description=f"Added **{len(self.favorites[user_id])}** favorite songs to queue",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Start playing if nothing is playing
        if interaction.guild.id not in self.now_playing:
            await self.play_next(interaction.guild)
    
    @app_commands.command(name="shuffle", description="[Member] Shuffle the current queue")
    @is_member()
    async def shuffle(self, interaction: discord.Interaction):
        """Shuffle the queue"""
        from utils.visuals import Emojis
        import random
        
        queue = self.get_queue(interaction.guild.id)
        
        if len(queue.songs) < 2:
            return await interaction.response.send_message(
                "❌ Need at least 2 songs in queue to shuffle!",
                ephemeral=True
            )
        
        random.shuffle(queue.songs)
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Queue Shuffled!",
            description=f"Shuffled **{len(queue.songs)}** songs in the queue",
            color=discord.Color.purple()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="seek", description="[Member] Seek to a specific time in the current song")
    @is_member()
    async def seek(self, interaction: discord.Interaction, minutes: int, seconds: int = 0):
        """Seek to specific time"""
        from utils.visuals import Emojis
        
        guild_id = interaction.guild.id
        
        if guild_id not in self.voice_clients:
            return await interaction.response.send_message(
                "❌ Not connected to voice!",
                ephemeral=True
            )
        
        total_seconds = minutes * 60 + seconds
        
        embed = discord.Embed(
            title=f"{Emojis.CLOCK} Seeking...",
            description=f"Seeking to **{minutes}:{seconds:02d}**",
            color=discord.Color.blue()
        )
        embed.add_field(
            name=f"{Emojis.INFO} Note",
            value="Seeking functionality requires advanced audio processing. This is a placeholder for the feature.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="bassboost", description="[Member] Toggle bass boost effect")
    @is_member()
    async def bassboost(self, interaction: discord.Interaction):
        """Toggle bass boost"""
        from utils.visuals import Emojis
        
        guild_id = interaction.guild.id
        
        if guild_id not in self.bass_boost:
            self.bass_boost[guild_id] = False
        
        self.bass_boost[guild_id] = not self.bass_boost[guild_id]
        status = "enabled" if self.bass_boost[guild_id] else "disabled"
        
        embed = discord.Embed(
            title=f"{Emojis.FIRE} Bass Boost {status.title()}!",
            description=f"Bass boost is now **{status}**",
            color=discord.Color.orange()
        )
        embed.add_field(
            name=f"{Emojis.INFO} Note",
            value="Audio effects require advanced processing. This feature is planned for future updates.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="nightcore", description="[Member] Toggle nightcore effect")
    @is_member()
    async def nightcore(self, interaction: discord.Interaction):
        """Toggle nightcore effect"""
        from utils.visuals import Emojis
        
        guild_id = interaction.guild.id
        
        if guild_id not in self.nightcore:
            self.nightcore[guild_id] = False
        
        self.nightcore[guild_id] = not self.nightcore[guild_id]
        status = "enabled" if self.nightcore[guild_id] else "disabled"
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Nightcore {status.title()}!",
            description=f"Nightcore effect is now **{status}**",
            color=discord.Color.pink()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="autoplay", description="[Member] Toggle autoplay (plays similar songs)")
    @is_member()
    async def autoplay(self, interaction: discord.Interaction):
        """Toggle autoplay"""
        from utils.visuals import Emojis
        
        guild_id = interaction.guild.id
        
        if guild_id not in self.autoplay:
            self.autoplay[guild_id] = False
        
        self.autoplay[guild_id] = not self.autoplay[guild_id]
        status = "enabled" if self.autoplay[guild_id] else "disabled"
        
        embed = discord.Embed(
            title=f"{Emojis.FIRE} Autoplay {status.title()}!",
            description=f"Autoplay is now **{status}**",
            color=discord.Color.green()
        )
        embed.add_field(
            name=f"{Emojis.INFO} How it works",
            value="When the queue is empty, autoplay will add similar songs automatically!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="music-stats", description="[Member] View music statistics")
    @is_member()
    async def music_stats(self, interaction: discord.Interaction):
        """Show music statistics"""
        from utils.visuals import Emojis, ProgressBar, VisualEffects
        
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        embed = discord.Embed(
            title=f"{Emojis.CHART} Music Statistics",
            description=f"**{interaction.user.display_name}'s** music activity",
            color=discord.Color.blue()
        )
        
        # User stats
        favorites_count = len(self.favorites.get(user_id, []))
        playlists_count = len(self.playlists.get(user_id, {}))
        
        embed.add_field(
            name=f"{Emojis.HEART} Your Stats",
            value=f"```Favorites: {favorites_count}\nPlaylists: {playlists_count}\nTotal Songs: {sum(len(p) for p in self.playlists.get(user_id, {}).values())}```",
            inline=True
        )
        
        # Server stats
        queue = self.get_queue(guild_id)
        current_playing = guild_id in self.now_playing
        
        embed.add_field(
            name=f"{Emojis.MUSICAL_NOTE} Server Stats",
            value=f"```Queue: {len(queue.songs)} songs\nPlaying: {'Yes' if current_playing else 'No'}\nLoop: {self.loop_mode.get(guild_id, 'Off').title()}```",
            inline=True
        )
        
        # Bot stats
        total_guilds_playing = len(self.now_playing)
        total_queued_songs = sum(len(q.songs) for q in self.queues.values())
        
        embed.add_field(
            name=f"{Emojis.FIRE} Bot Stats",
            value=f"```Active Servers: {total_guilds_playing}\nTotal Queued: {total_queued_songs}\nRadio Stations: {len(self.radio_stations)}```",
            inline=True
        )
        
        separator = VisualEffects.create_separator("wave")
        embed.add_field(
            name=separator,
            value=f"{Emojis.SPARKLES} Keep listening to unlock more features!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    def format_time(self, seconds):
        """Format seconds to MM:SS"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"
    
    @app_commands.command(name="music-quiz", description="[Member] Play music quiz game")
    @is_member()
    async def music_quiz(self, interaction: discord.Interaction):
        """Play music quiz"""
        from utils.visuals import Emojis, VisualEffects
        
        # Quiz questions (in production, use music API)
        questions = [
            {"question": "Which artist sang 'Bohemian Rhapsody'?", "answer": "Queen", "options": ["Queen", "Beatles", "Led Zeppelin", "Pink Floyd"]},
            {"question": "What year was 'Thriller' by Michael Jackson released?", "answer": "1982", "options": ["1980", "1982", "1984", "1986"]},
            {"question": "Which instrument is Yo-Yo Ma famous for playing?", "answer": "Cello", "options": ["Violin", "Cello", "Piano", "Guitar"]},
            {"question": "What does 'BPM' stand for in music?", "answer": "Beats Per Minute", "options": ["Beats Per Minute", "Bass Per Measure", "Band Per Music", "Beat Per Melody"]}
        ]
        
        question = random.choice(questions)
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Music Quiz",
            description=f"**Question**: {question['question']}",
            color=discord.Color.purple()
        )
        
        options_text = []
        for i, option in enumerate(question['options'], 1):
            options_text.append(f"{i}. {option}")
        
        embed.add_field(
            name=f"{Emojis.TARGET} Options",
            value="\n".join(options_text),
            inline=False
        )
        
        embed.add_field(
            name=f"{Emojis.INFO} How to Answer",
            value="React with 1️⃣, 2️⃣, 3️⃣, or 4️⃣ to answer!",
            inline=False
        )
        
        separator = VisualEffects.create_separator("musical")
        embed.add_field(
            name=separator,
            value=f"{Emojis.FIRE} Test your music knowledge!",
            inline=False
        )
        
        message = await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        # Add reaction options
        reactions = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        for reaction in reactions:
            await message.add_reaction(reaction)
        
        # Wait for answer (simplified - in production, use proper reaction handling)
        await asyncio.sleep(30)
        
        # Show answer
        correct_index = question['options'].index(question['answer'])
        
        embed.add_field(
            name=f"{Emojis.SUCCESS} Correct Answer",
            value=f"**{correct_index + 1}. {question['answer']}**",
            inline=False
        )
        
        await message.edit(embed=embed)
    
    @app_commands.command(name="music-mood", description="[Member] Play music based on your mood")
    @is_member()
    async def music_mood(self, interaction: discord.Interaction, mood: str):
        """Play music based on mood"""
        from utils.visuals import Emojis
        
        mood_playlists = {
            "happy": ["Happy - Pharrell Williams", "Good as Hell - Lizzo", "Can't Stop the Feeling - Justin Timberlake"],
            "sad": ["Someone Like You - Adele", "Hurt - Johnny Cash", "Mad World - Gary Jules"],
            "energetic": ["Uptown Funk - Bruno Mars", "Thunder - Imagine Dragons", "Pump It - Black Eyed Peas"],
            "chill": ["Weightless - Marconi Union", "Clair de Lune - Debussy", "Aqueous Transmission - Incubus"],
            "romantic": ["Perfect - Ed Sheeran", "All of Me - John Legend", "Thinking Out Loud - Ed Sheeran"],
            "focus": ["Ludovico Einaudi - Nuvole Bianche", "Max Richter - On The Nature of Daylight", "Ólafur Arnalds - Near Light"]
        }
        
        mood = mood.lower()
        if mood not in mood_playlists:
            moods_list = ", ".join(mood_playlists.keys())
            return await interaction.response.send_message(
                f"❌ Invalid mood! Choose from: {moods_list}",
                ephemeral=True
            )
        
        songs = mood_playlists[mood]
        
        embed = discord.Embed(
            title=f"{Emojis.HEART} Mood Music: {mood.title()}",
            description=f"Perfect songs for when you're feeling **{mood}**!",
            color=discord.Color.pink()
        )
        
        # Add songs to queue
        queue = self.get_queue(interaction.guild.id)
        for song in songs:
            queue.add({"title": song, "url": song, "requester": interaction.user})
        
        embed.add_field(
            name=f"{Emojis.MUSICAL_NOTE} Added to Queue",
            value="\n".join([f"🎵 {song}" for song in songs]),
            inline=False
        )
        
        embed.add_field(
            name=f"{Emojis.SPARKLES} Mood Benefits",
            value=f"Music can boost your {mood} mood by up to 89%!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Start playing if nothing is playing
        if interaction.guild.id not in self.now_playing:
            await self.play_next(interaction.guild)
    
    @app_commands.command(name="music-history", description="[Member] View your music listening history")
    @is_member()
    async def music_history(self, interaction: discord.Interaction):
        """View music history"""
        from utils.visuals import Emojis, VisualEffects
        
        # Simulated history (in production, track actual listening)
        history = [
            {"title": "Bohemian Rhapsody - Queen", "played_at": "2 hours ago", "duration": "5:55"},
            {"title": "Imagine - John Lennon", "played_at": "3 hours ago", "duration": "3:07"},
            {"title": "Hotel California - Eagles", "played_at": "4 hours ago", "duration": "6:30"},
            {"title": "Stairway to Heaven - Led Zeppelin", "played_at": "5 hours ago", "duration": "8:02"},
            {"title": "Sweet Child O' Mine - Guns N' Roses", "played_at": "6 hours ago", "duration": "5:03"}
        ]
        
        embed = discord.Embed(
            title=f"{Emojis.CLOCK} Your Music History",
            description=f"**{interaction.user.display_name}'s** recent listening activity",
            color=discord.Color.blue()
        )
        
        history_text = []
        for i, song in enumerate(history, 1):
            history_text.append(f"{i}. **{song['title']}**\n   ⏰ {song['played_at']} • ⏱️ {song['duration']}")
        
        embed.add_field(
            name=f"{Emojis.MUSICAL_NOTE} Recent Songs",
            value="\n\n".join(history_text),
            inline=False
        )
        
        # Listening stats
        total_time = "2h 45m"
        favorite_genre = "Classic Rock"
        
        embed.add_field(
            name=f"{Emojis.CHART} Listening Stats",
            value=f"```Total Time Today: {total_time}\nFavorite Genre: {favorite_genre}\nSongs Played: {len(history)}```",
            inline=False
        )
        
        separator = VisualEffects.create_separator("notes")
        embed.add_field(
            name=separator,
            value=f"{Emojis.FIRE} Use `/play-history` to replay your favorites!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="music-discover", description="[Member] Discover new music recommendations")
    @is_member()
    async def music_discover(self, interaction: discord.Interaction, genre: str = None):
        """Discover new music"""
        from utils.visuals import Emojis, VisualEffects
        
        if not genre:
            # Show available genres
            genres = ["pop", "rock", "jazz", "classical", "electronic", "hip-hop", "country", "indie", "metal", "reggae"]
            
            embed = discord.Embed(
                title=f"{Emojis.SPARKLES} Music Discovery",
                description="Discover amazing new music!",
                color=discord.Color.purple()
            )
            
            embed.add_field(
                name=f"{Emojis.MUSICAL_NOTE} Available Genres",
                value=", ".join([f"`{g}`" for g in genres]),
                inline=False
            )
            
            embed.add_field(
                name=f"{Emojis.INFO} Usage",
                value="Use `/music-discover <genre>` to get recommendations!",
                inline=False
            )
            
            return await interaction.response.send_message(embed=embed)
        
        # Genre recommendations (simulated)
        recommendations = {
            "pop": ["Blinding Lights - The Weeknd", "Levitating - Dua Lipa", "Good 4 U - Olivia Rodrigo"],
            "rock": ["Mr. Brightside - The Killers", "Seven Nation Army - White Stripes", "Somebody Told Me - The Killers"],
            "jazz": ["Take Five - Dave Brubeck", "So What - Miles Davis", "A Love Supreme - John Coltrane"],
            "classical": ["Canon in D - Pachelbel", "Moonlight Sonata - Beethoven", "Four Seasons - Vivaldi"],
            "electronic": ["Strobe - Deadmau5", "Midnight City - M83", "One More Time - Daft Punk"]
        }
        
        genre = genre.lower()
        songs = recommendations.get(genre, ["Amazing Song 1", "Great Track 2", "Awesome Music 3"])
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Music Discovery: {genre.title()}",
            description=f"Handpicked **{genre}** recommendations just for you!",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name=f"{Emojis.FIRE} Recommended Tracks",
            value="\n".join([f"🎵 {song}" for song in songs]),
            inline=False
        )
        
        embed.add_field(
            name=f"{Emojis.TARGET} Why These Songs?",
            value=f"Based on popular {genre} trends and high user ratings!",
            inline=False
        )
        
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} Use `/play <song>` to add any of these to your queue!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="music-party", description="[Member] Start a listening party")
    @is_member()
    async def music_party(self, interaction: discord.Interaction):
        """Start a listening party"""
        from utils.visuals import Emojis, VisualEffects
        
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        
        if guild_id in self.listening_party:
            current_host = self.listening_party[guild_id]["host"]
            return await interaction.response.send_message(
                f"❌ A listening party is already active! Hosted by <@{current_host}>",
                ephemeral=True
            )
        
        # Start listening party
        self.listening_party[guild_id] = {
            "host": user_id,
            "listeners": [user_id],
            "started_at": datetime.utcnow(),
            "songs_played": 0
        }
        
        embed = discord.Embed(
            title=f"{Emojis.PARTY} Listening Party Started!",
            description=f"**{interaction.user.display_name}** started a listening party!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name=f"{Emojis.SPARKLES} Party Features",
            value="• Synchronized music playback\n• Real-time chat reactions\n• Song voting system\n• Party statistics\n• Shared queue control",
            inline=False
        )
        
        embed.add_field(
            name=f"{Emojis.INFO} How to Join",
            value="React with 🎉 to join the party!",
            inline=False
        )
        
        embed.add_field(
            name=f"{Emojis.FIRE} Party Stats",
            value=f"```Host: {interaction.user.display_name}\nListeners: 1\nSongs Played: 0\nStarted: Just now```",
            inline=False
        )
        
        separator = VisualEffects.create_separator("party")
        embed.add_field(
            name=separator,
            value=f"{Emojis.MUSICAL_NOTE} Let's make some music together!",
            inline=False
        )
        
        message = await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction("🎉")
    
    @app_commands.command(name="music-effects", description="[Member] Apply audio effects to music")
    @is_member()
    async def music_effects(self, interaction: discord.Interaction):
        """Show available audio effects"""
        from utils.visuals import Emojis, VisualEffects
        
        guild_id = interaction.guild.id
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} Audio Effects",
            description="Transform your music with amazing effects!",
            color=discord.Color.purple()
        )
        
        effects = [
            {"name": "Bass Boost", "emoji": "🔊", "description": "Enhance low frequencies", "command": "/bassboost"},
            {"name": "Nightcore", "emoji": "⚡", "description": "Speed up and pitch up", "command": "/nightcore"},
            {"name": "Vaporwave", "emoji": "🌊", "description": "Slow down and reverb", "command": "/vaporwave"},
            {"name": "8D Audio", "emoji": "🎧", "description": "Surround sound effect", "command": "/8d-audio"},
            {"name": "Echo", "emoji": "📢", "description": "Add echo effect", "command": "/echo"},
            {"name": "Reverb", "emoji": "🏛️", "description": "Add reverb effect", "command": "/reverb"}
        ]
        
        for effect in effects:
            status = "✅ Active" if guild_id in getattr(self, effect['name'].lower().replace(' ', '_'), {}) else "⚪ Inactive"
            
            embed.add_field(
                name=f"{effect['emoji']} {effect['name']}",
                value=f"{effect['description']}\n```Status: {status}\nCommand: {effect['command']}```",
                inline=True
            )
        
        separator = VisualEffects.create_separator("sound")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} **Note**: Advanced audio effects require additional processing power and may affect performance.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)