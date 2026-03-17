"""
WAN Bot — Music Cog
Based on user-provided architecture, improved and integrated as a proper cog.

- Uses cookies.txt for authenticated yt-dlp requests (no 403 errors)
- Per-guild queue using asyncio.Queue
- Smart autoplay: scores related videos by artist match + title similarity
- Avoids repeating last 20 tracks
- Slash commands (discord.py 2.x app_commands)
- No external tokens needed — uses DISCORD_TOKEN from .env
"""

import asyncio
import logging
import os
import re
from collections import deque
from typing import Optional

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger("discord_bot.music")

# ── Config ────────────────────────────────────────────────────────────────────

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "..", "cookies.txt")

def _ytdl_opts(extra: dict = {}) -> dict:
    opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "extractor_args": {"youtube": {"player_client": ["web", "android"]}},
        **extra,
    }
    if os.path.isfile(COOKIES_FILE):
        opts["cookiefile"] = os.path.abspath(COOKIES_FILE)
        logger.info("music: cookies.txt found and loaded")
    return opts

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


# ── Autoplay scoring helpers ──────────────────────────────────────────────────

# Mood keyword groups — prevents genre-jumping
_MOOD_GROUPS = {
    "soft":      ["lofi", "acoustic", "chill", "calm", "relax", "sleep", "study", "piano", "ambient", "slow", "soft"],
    "romantic":  ["romantic", "love", "sad", "emotional", "heartbreak", "ballad", "melancholy"],
    "energetic": ["edm", "dance", "party", "hype", "workout", "bass", "trap", "dubstep", "rave"],
    "rock":      ["rock", "metal", "punk", "grunge", "indie", "alternative", "guitar"],
    "hiphop":    ["rap", "hip hop", "hip-hop", "drill", "r&b", "rnb", "soul"],
    "classical": ["classical", "orchestra", "symphony", "opera", "baroque"],
    "hindi":     ["hindi", "bollywood", "punjabi", "bhajan", "ghazal", "arijit", "atif"],
    "kpop":      ["kpop", "k-pop", "bts", "blackpink", "twice"],
}

_INCOMPATIBLE = [
    ("soft", "energetic"), ("classical", "energetic"),
    ("classical", "hiphop"), ("hindi", "kpop"),
]


def _detect_mood(text: str) -> Optional[str]:
    t = text.lower()
    for mood, kws in _MOOD_GROUPS.items():
        if any(k in t for k in kws):
            return mood
    return None


def _moods_ok(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b or a == b:
        return True
    pair = tuple(sorted([a, b]))
    return pair not in [tuple(sorted(x)) for x in _INCOMPATIBLE]


def _score(candidate: dict, last: dict) -> int:
    """Score a candidate track against the last played track."""
    score = 0
    title = candidate.get("title", "")
    channel = candidate.get("uploader") or candidate.get("channel", "")
    dur = candidate.get("duration")
    last_title = last.get("title", "")
    last_channel = last.get("uploader") or last.get("channel", "")
    last_dur = last.get("duration")

    # Reject shorts / memes
    if dur and dur < 60:
        return -999

    # +50 same artist
    if channel and last_channel and channel.lower() == last_channel.lower():
        score += 50

    # +30 title word overlap
    stop = {"the", "a", "an", "of", "in", "on", "ft", "feat", "and", "or"}
    lw = set(re.findall(r"\w+", last_title.lower())) - stop
    cw = set(re.findall(r"\w+", title.lower())) - stop
    overlap = len(lw & cw)
    if overlap:
        score += min(30, overlap * 8)

    # +20 same mood
    last_mood = _detect_mood(f"{last_title} {last_channel}")
    cand_mood = _detect_mood(f"{title} {channel}")
    if not _moods_ok(last_mood, cand_mood):
        return -999
    if last_mood and last_mood == cand_mood:
        score += 20

    # +10 similar duration
    if dur and last_dur:
        ratio = min(dur, last_dur) / max(dur, last_dur)
        if ratio >= 0.7:
            score += 10

    return score


# ── Per-guild state ───────────────────────────────────────────────────────────

class GuildMusicState:
    """Holds all music state for one guild."""

    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.history: deque = deque(maxlen=20)   # last 20 video IDs
        self.current: Optional[dict] = None       # currently playing track info
        self.volume: float = 0.5
        self.autoplay: bool = False
        self._player_task: Optional[asyncio.Task] = None
        self._skip_event = asyncio.Event()

    def reset(self):
        # Drain queue
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.current = None


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    """Music system — play, queue, skip, pause, resume, stop, autoplay."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, GuildMusicState] = {}
        self._watchdog.start()

    def cog_unload(self):
        self._watchdog.cancel()
        for state in self._states.values():
            if state._player_task:
                state._player_task.cancel()

    def _state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildMusicState()
        return self._states[guild_id]

    # ── yt-dlp helpers (run in executor to avoid blocking) ────────────────

    async def _extract(self, query: str, *, search: bool = True) -> Optional[dict]:
        """Resolve a URL or search query to a track info dict."""
        opts = _ytdl_opts({"default_search": "ytsearch" if search else "auto"})
        ytdl = yt_dlp.YoutubeDL(opts)
        loop = self.bot.loop
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False)),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.error(f"[extract] Timed out: {query}")
            return None
        except Exception as e:
            logger.error(f"[extract] Failed: {e}")
            return None

        if not data:
            return None
        if "entries" in data:
            entries = [e for e in data["entries"] if e]
            return entries[0] if entries else None
        return data

    async def _get_related(self, last: dict) -> Optional[dict]:
        """
        Fetch related videos for last track, score them, return best match.
        Falls back to '<artist> similar songs' search if scraping fails.
        """
        vid_id = last.get("id")
        history_ids = set(self.bot.get_guild(0) and [] or [])  # placeholder — passed in caller
        return None  # implemented inline in _player_loop for access to state

    # ── Player loop ───────────────────────────────────────────────────────

    async def _player_loop(self, guild: discord.Guild):
        """Main playback loop for a guild. Runs as a background task."""
        state = self._state(guild.id)
        vc: discord.VoiceClient = guild.voice_client

        logger.info(f"[{guild.name}] Player loop started")

        while True:
            # Reconnect if dropped
            if not vc or not vc.is_connected():
                vc = guild.voice_client
                if not vc or not vc.is_connected():
                    await asyncio.sleep(3)
                    vc = guild.voice_client
                    if not vc or not vc.is_connected():
                        logger.warning(f"[{guild.name}] VC gone — stopping loop")
                        break

            # If queue empty, try autoplay
            if state.queue.empty():
                if state.autoplay and state.current:
                    next_track = await self._autoplay_next(state)
                    if next_track:
                        await state.queue.put(next_track)
                        logger.info(f"[{guild.name}] Autoplay queued: {next_track.get('title')}")
                    else:
                        await asyncio.sleep(5)
                        continue
                else:
                    await asyncio.sleep(2)
                    continue

            # Get next track
            try:
                track = await asyncio.wait_for(state.queue.get(), timeout=10.0)
            except asyncio.TimeoutError:
                continue

            state.current = track
            if track.get("id"):
                state.history.append(track["id"])

            # Build audio source
            stream_url = track.get("url")
            if not stream_url:
                logger.warning(f"[{guild.name}] No stream URL for {track.get('title')} — skipping")
                continue

            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTS),
                volume=state.volume,
            )

            # Play
            done_event = asyncio.Event()

            def _after(err):
                if err:
                    logger.error(f"[{guild.name}] Playback error: {err}")
                self.bot.loop.call_soon_threadsafe(done_event.set)

            try:
                vc.play(source, after=_after)
            except Exception as e:
                logger.error(f"[{guild.name}] vc.play failed: {e}")
                continue

            logger.info(f"[{guild.name}] ▶ {track.get('title')} — {track.get('uploader', '?')}")

            # Wait until track ends or skip is triggered
            await done_event.wait()

        logger.info(f"[{guild.name}] Player loop ended")
        state._player_task = None

    async def _autoplay_next(self, state: GuildMusicState) -> Optional[dict]:
        """Score and return the best related track for autoplay."""
        last = state.current
        if not last or not last.get("id"):
            return None

        history_ids = set(state.history)
        vid_id = last["id"]

        # Scrape related IDs from YouTube watch page
        import aiohttp
        related_ids = []
        try:
            url = f"https://www.youtube.com/watch?v={vid_id}"
            headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html)
                        seen = {vid_id}
                        for i in ids:
                            if i not in seen and i not in history_ids:
                                seen.add(i)
                                related_ids.append(i)
                            if len(related_ids) >= 8:
                                break
        except Exception as e:
            logger.warning(f"[autoplay] Scrape failed: {e}")

        logger.info(f"[autoplay] {len(related_ids)} related IDs found for {last.get('title')!r}")

        # Fetch metadata + score candidates
        best_score = -1
        best_track = None

        async def _fetch_and_score(vid):
            info = await self._extract(f"https://www.youtube.com/watch?v={vid}", search=False)
            if not info:
                return
            nonlocal best_score, best_track
            s = _score(info, last)
            logger.debug(f"[autoplay] {info.get('title')!r} score={s}")
            if s > best_score:
                best_score = s
                best_track = info

        tasks = [_fetch_and_score(i) for i in related_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        if best_track and best_score >= 0:
            logger.info(f"[autoplay] ✅ Selected: {best_track.get('title')!r} (score={best_score})")
            return best_track

        # Fallback: search "<artist> similar songs"
        artist = last.get("uploader") or last.get("channel", "")
        fallback_q = f"{artist} similar songs" if artist else f"{last.get('title', '')} similar"
        logger.info(f"[autoplay] Fallback search: {fallback_q!r}")
        result = await self._extract(fallback_q)
        if result and result.get("id") not in history_ids:
            return result

        logger.warning("[autoplay] No suitable track found")
        return None


    # ── Watchdog: auto-reconnect ──────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _watchdog(self):
        for guild_id, state in list(self._states.items()):
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            vc = guild.voice_client
            # Restart dead player task if queue has items or autoplay is on
            task_dead = not state._player_task or state._player_task.done()
            has_work = not state.queue.empty() or (state.autoplay and state.current)
            if task_dead and has_work and vc and vc.is_connected():
                logger.info(f"[watchdog] Restarting player loop for {guild.name}")
                state._player_task = self.bot.loop.create_task(self._player_loop(guild))

    @_watchdog.before_loop
    async def _before_watchdog(self):
        await self.bot.wait_until_ready()

    # ── Voice state: auto-pause when channel empties ──────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return
        humans = [m for m in vc.channel.members if not m.bot]
        if not humans and vc.is_playing():
            vc.pause()
            logger.info(f"[{guild.name}] Auto-paused — channel empty")

    # ── Slash Commands ────────────────────────────────────────────────────

    @app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            await vc.move_to(interaction.user.voice.channel)
        else:
            vc = await interaction.user.voice.channel.connect()
        await interaction.response.send_message(f"✅ Joined **{interaction.user.voice.channel.name}**")

    @app_commands.command(name="play", description="Play a song — YouTube URL or search query")
    @app_commands.describe(query="YouTube URL or search terms")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)

        await interaction.response.defer()

        # Connect if needed
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            try:
                vc = await interaction.user.voice.channel.connect()
            except Exception as e:
                return await interaction.followup.send(f"❌ Could not connect: {e}", ephemeral=True)

        # Extract track info
        info = await self._extract(query)
        if not info:
            return await interaction.followup.send("❌ Could not find that track.", ephemeral=True)

        state = self._state(interaction.guild.id)
        await state.queue.put(info)

        # Start player loop if not running
        if not state._player_task or state._player_task.done():
            state._player_task = self.bot.loop.create_task(
                self._player_loop(interaction.guild)
            )

        embed = discord.Embed(color=0x7C3AED)
        if state.current and (vc.is_playing() or vc.is_paused()):
            embed.title = "📋 Added to Queue"
            embed.description = f"**{info.get('title', 'Unknown')}**"
            embed.set_footer(text=f"By {info.get('uploader', '?')}")
        else:
            embed.title = "▶ Playing Soon"
            embed.description = f"**{info.get('title', 'Unknown')}**"
            if info.get("thumbnail"):
                embed.set_thumbnail(url=info["thumbnail"])

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭ Skipped.")
        else:
            await interaction.response.send_message("❌ Nothing to skip.", ephemeral=True)

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶ Resumed.")
        else:
            await interaction.response.send_message("❌ Not paused.", ephemeral=True)

    @app_commands.command(name="stop", description="Stop music and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        state.reset()
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
        if state._player_task:
            state._player_task.cancel()
        await interaction.response.send_message("⏹ Stopped and disconnected.")

    @app_commands.command(name="queue", description="Show the music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        items = list(state.queue._queue)
        embed = discord.Embed(title="🎵 Music Queue", color=0x7C3AED)
        if state.current:
            embed.add_field(
                name="Now Playing",
                value=f"**{state.current.get('title', '?')}** — {state.current.get('uploader', '?')}",
                inline=False,
            )
        if items:
            lines = "\n".join(f"`{i+1}.` {t.get('title', '?')}" for i, t in enumerate(items[:10]))
            embed.add_field(name="Up Next", value=lines, inline=False)
            if len(items) > 10:
                embed.set_footer(text=f"...and {len(items)-10} more")
        else:
            embed.add_field(name="Queue", value="Empty", inline=False)
        embed.set_footer(text=f"Autoplay: {'on' if state.autoplay else 'off'}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        if not state.current:
            return await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        t = state.current
        embed = discord.Embed(
            title="▶ Now Playing",
            description=f"**{t.get('title', '?')}**",
            color=0x10B981,
        )
        if t.get("thumbnail"):
            embed.set_thumbnail(url=t["thumbnail"])
        embed.add_field(name="Channel", value=t.get("uploader", "?"), inline=True)
        dur = t.get("duration")
        if dur:
            m, s = divmod(int(dur), 60)
            embed.add_field(name="Duration", value=f"{m}:{s:02d}", inline=True)
        embed.add_field(name="Queue", value=f"{state.queue.qsize()} track(s) up next", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set volume (0–100)")
    @app_commands.describe(level="Volume from 0 to 100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            return await interaction.response.send_message("❌ Must be 0–100.", ephemeral=True)
        state = self._state(interaction.guild.id)
        state.volume = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = state.volume
        icon = "🔇" if level == 0 else "🔉" if level < 50 else "🔊"
        await interaction.response.send_message(f"{icon} Volume: **{level}%**")

    @app_commands.command(name="autoplay", description="Toggle smart autoplay when queue ends")
    async def autoplay(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        state.autoplay = not state.autoplay
        icon = "🤖" if state.autoplay else "🔕"
        status = "on" if state.autoplay else "off"
        await interaction.response.send_message(f"{icon} Autoplay: **{status}**")

    @app_commands.command(name="leave", description="Disconnect the bot from voice")
    async def leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("❌ Not in a voice channel.", ephemeral=True)
        state = self._state(interaction.guild.id)
        state.reset()
        if state._player_task:
            state._player_task.cancel()
        await vc.disconnect()
        await interaction.response.send_message("👋 Disconnected.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
