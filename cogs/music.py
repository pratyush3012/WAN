"""
WAN Bot — Music Cog (v4)
========================
New in v4:
  - 24/7 Smart Radio: no idle disconnect, lofi fallback when channel empty
  - Per-user taste profiles: mood, language, artist remembered per user
  - Profile learning: updated every time a user plays a song
  - Interactive UI: join → button → modal input box
  - Personalized autoplay: uses active user's profile for fallback query
  - Priority: last joined user controls the vibe

All v3 fixes retained:
  - asyncio.Lock on _advance (race condition)
  - Stale VC guard in _play_song
  - Memory cleanup for idle states
  - Semaphore on autoplay fetches
  - Single YTDL instance
  - ytsearch5 instead of HTML scraping
"""

import asyncio
import json
import logging
import os
import random
import re
import time
from collections import deque
from typing import Optional

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger("discord_bot.music")

# ── Config ────────────────────────────────────────────────────────────────────

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "..", "cookies.txt")


def _build_opts(extra: dict = {}) -> dict:
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
    return opts


# Single reused instance — avoids re-init overhead on every search
YTDL = yt_dlp.YoutubeDL(_build_opts())

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

# Rotating lofi fallbacks — keeps 24/7 mode feeling alive
_LOFI_FALLBACKS = [
    "lofi chill beats",
    "ambient study music",
    "soft piano music",
    "chill instrumental beats",
    "lofi hip hop radio",
]


# ── Song ──────────────────────────────────────────────────────────────────────

class Song:
    """
    Wraps a yt-dlp info dict.
    Imported by web_dashboard_enhanced.py — attributes must stay stable.
    """
    __slots__ = ("title", "url", "stream_url", "thumbnail", "duration",
                 "channel", "video_id", "requester")

    def __init__(self, data: dict, requester=None):
        self.title: str      = data.get("title", "Unknown")
        self.url: str        = data.get("webpage_url") or data.get("url", "")
        self.stream_url: str = data.get("url", "")
        self.thumbnail       = data.get("thumbnail")
        self.duration        = data.get("duration")
        self.channel: str    = data.get("uploader") or data.get("channel", "Unknown")
        self.video_id        = data.get("id")
        self.requester       = requester

    @property
    def duration_str(self) -> str:
        if not self.duration:
            return "?"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def build_source(self, volume: float = 0.5) -> discord.PCMVolumeTransformer:
        return discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(self.stream_url, **FFMPEG_OPTS),
            volume=volume,
        )


# ── _fetch — dashboard imports this ──────────────────────────────────────────

def _fetch(query: str) -> Optional[dict]:
    """Sync yt-dlp extract. Called via run_in_executor from the dashboard."""
    try:
        data = YTDL.extract_info(query, download=False)
    except Exception as e:
        logger.error(f"[_fetch] {e}")
        return None
    if not data:
        return None
    if "entries" in data:
        entries = [e for e in data["entries"] if e]
        return entries[0] if entries else None
    return data


# ── Mood / language detection ─────────────────────────────────────────────────

_MOOD_GROUPS = {
    "soft":      ["lofi", "acoustic", "chill", "calm", "relax", "sleep", "study",
                  "piano", "ambient", "slow", "soft"],
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


def _detect_lang(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["hindi", "bollywood", "arijit", "atif", "punjabi", "bhajan", "ghazal"]):
        return "hindi"
    if any(k in t for k in ["kpop", "k-pop", "bts", "blackpink", "twice", "exo"]):
        return "kpop"
    return "global"


def _moods_ok(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b or a == b:
        return True
    pair = tuple(sorted([a, b]))
    return pair not in [tuple(sorted(x)) for x in _INCOMPATIBLE]


def _score(candidate: dict, last: dict) -> int:
    score = 0
    title      = candidate.get("title", "")
    channel    = candidate.get("uploader") or candidate.get("channel", "")
    dur        = candidate.get("duration")
    last_title = last.get("title", "")
    last_ch    = last.get("uploader") or last.get("channel", "")
    last_dur   = last.get("duration")

    if dur and dur < 60:          # reject shorts/memes
        return -999

    if channel and last_ch and channel.lower() == last_ch.lower():
        score += 50               # same artist

    if "vevo" in channel.lower():
        score += 5                # verified artist boost

    stop = {"the", "a", "an", "of", "in", "on", "ft", "feat", "and", "or"}
    lw = set(re.findall(r"\w+", last_title.lower())) - stop
    cw = set(re.findall(r"\w+", title.lower())) - stop
    overlap = len(lw & cw)
    if overlap:
        score += min(30, overlap * 8)

    if "remix" in title.lower() and "remix" not in last_title.lower():
        score -= 10               # remix mismatch penalty

    last_mood = _detect_mood(f"{last_title} {last_ch}")
    cand_mood = _detect_mood(f"{title} {channel}")
    if not _moods_ok(last_mood, cand_mood):
        return -999               # incompatible genre
    if last_mood and last_mood == cand_mood:
        score += 20

    if dur and last_dur:
        ratio = min(dur, last_dur) / max(dur, last_dur)
        if ratio >= 0.7:
            score += 10

    return score


# ── Per-guild state ───────────────────────────────────────────────────────────

class GuildMusicState:
    """All music state for one guild."""

    def __init__(self):
        self._q: list[Song]           = []
        self.current: Optional[Song]  = None
        self.volume: float            = 0.5
        self.autoplay: bool           = True   # on by default for 24/7 mode
        self.loop_song: bool          = False
        self.loop_queue: bool         = False
        self._history: deque          = deque(maxlen=20)
        self._player_task: Optional[asyncio.Task] = None
        self._lock: asyncio.Lock      = asyncio.Lock()

    def empty(self) -> bool:
        return len(self._q) == 0

    def add(self, song: Song):
        self._q.append(song)

    def clear(self):
        self._q.clear()
        self.current = None

    def reset(self):
        self.clear()

    def __len__(self) -> int:
        return len(self._q)


# ── Interactive UI ────────────────────────────────────────────────────────────

class SongRequestModal(discord.ui.Modal, title="🎵 Request a Song"):
    query = discord.ui.TextInput(
        label="What do you want to hear?",
        placeholder="Song name, artist, or YouTube link...",
        required=True,
        max_length=200,
    )

    def __init__(self, cog: "Music", guild: discord.Guild):
        super().__init__()
        self.cog   = cog
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        song = await self.cog._extract(self.query.value)
        if not song:
            return await interaction.followup.send("❌ Song not found.", ephemeral=True)

        song.requester = interaction.user

        # Save user profile
        self.cog._update_profile(interaction.user.id, song)
        self.cog._track_activity(self.guild.id, interaction.user.id)

        state = self.cog._state(self.guild.id)
        state._q.append(song)

        vc = self.guild.voice_client
        if vc and not vc.is_playing() and not vc.is_paused():
            await self.cog._advance(self.guild)

        if not state._player_task or state._player_task.done():
            state._player_task = self.cog.bot.loop.create_task(
                self.cog._player_loop(self.guild)
            )

        embed = discord.Embed(
            title="▶ Added to Queue",
            description=f"**{song.title}** `{song.duration_str}`",
            color=0x10B981,
        )
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        embed.set_footer(text=f"By {song.channel} • Requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)


class MusicPromptView(discord.ui.View):
    def __init__(self, cog: "Music", guild: discord.Guild):
        super().__init__(timeout=120)
        self.cog   = cog
        self.guild = guild

    @discord.ui.button(label="🎵 Request a Song", style=discord.ButtonStyle.green)
    async def request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SongRequestModal(self.cog, self.guild))


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    """24/7 smart music — personalized per user, always playing."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, GuildMusicState] = {}

        # Per-user taste profiles  {user_id: {moods, languages, artists, last_query}}
        self._user_profiles: dict[int, dict] = {}

        # Active user per guild  {guild_id: user_id}
        self._active_user: dict[int, int] = {}

        # Activity score per guild  {guild_id: {user_id: count}}  — dominant user detection
        self._user_activity: dict[int, dict] = {}

        # Prompt cooldown per guild  {guild_id: timestamp}
        self._last_prompt_time: dict[int, float] = {}

        self.load_profiles()
        self._watchdog.start()

    def cog_unload(self):
        self._watchdog.cancel()
        for state in self._states.values():
            if state._player_task:
                state._player_task.cancel()

    # ── State helpers ─────────────────────────────────────────────────────

    def _state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildMusicState()
        return self._states[guild_id]

    def _cleanup(self, guild_id: int):
        state = self._states.get(guild_id)
        if state and state.empty() and not state.current:
            self._states.pop(guild_id, None)

    # ── Dashboard API ─────────────────────────────────────────────────────

    def _q(self, guild_id: int) -> GuildMusicState:
        return self._state(guild_id)

    async def _start(self, guild: discord.Guild, vc: discord.VoiceClient, song: Song):
        state = self._state(guild.id)
        state.current = song
        if vc.is_playing():
            vc.stop()
        self._play_song(guild, vc, song, state)
        if not state._player_task or state._player_task.done():
            state._player_task = self.bot.loop.create_task(self._player_loop(guild))

    # ── User profile ──────────────────────────────────────────────────────

    def _analyze_song(self, song: Song) -> dict:
        """Extract taste data from a song (used internally by _update_profile)."""
        text = f"{song.title} {song.channel}".lower()
        return {
            "mood":     _detect_mood(text),
            "language": _detect_lang(text),
            "query":    song.title,
            "channel":  song.channel,
        }

    def _update_profile(self, user_id: int, song: Song):
        """Update frequency-based taste profile for a user."""
        data = self._analyze_song(song)
        profile = self._user_profiles.setdefault(user_id, {
            "moods": {}, "languages": {}, "artists": {}, "last_query": ""
        })
        if data["mood"]:
            profile["moods"][data["mood"]] = profile["moods"].get(data["mood"], 0) + 1
        lang = data["language"]
        profile["languages"][lang] = profile["languages"].get(lang, 0) + 1
        artist = data["channel"]
        if artist and artist != "Unknown":
            profile["artists"][artist] = profile["artists"].get(artist, 0) + 1
        profile["last_query"] = data["query"]
        self.save_profiles()

    def _track_activity(self, guild_id: int, user_id: int):
        """Increment activity score for a user in a guild."""
        guild_activity = self._user_activity.setdefault(guild_id, {})
        guild_activity[user_id] = guild_activity.get(user_id, 0) + 1
        # Update active user to most engaged, not just last join
        self._active_user[guild_id] = max(guild_activity, key=guild_activity.get)

    # ── Profile persistence ───────────────────────────────────────────────

    def save_profiles(self):
        try:
            with open("profiles.json", "w") as f:
                json.dump(self._user_profiles, f)
        except Exception as e:
            logger.warning(f"[profiles] Save failed: {e}")

    def load_profiles(self):
        if os.path.exists("profiles.json"):
            try:
                with open("profiles.json") as f:
                    # JSON keys are strings — convert back to int
                    raw = json.load(f)
                    self._user_profiles = {int(k): v for k, v in raw.items()}
                logger.info(f"[profiles] Loaded {len(self._user_profiles)} user profiles")
            except Exception as e:
                logger.warning(f"[profiles] Load failed: {e}")

    # ── Extraction ────────────────────────────────────────────────────────

    async def _extract(self, query: str) -> Optional[Song]:
        try:
            data = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, lambda: _fetch(query)),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.error(f"[extract] Timed out: {query}")
            return None
        return Song(data) if data else None

    # ── Playback core ─────────────────────────────────────────────────────

    def _play_song(self, guild: discord.Guild, vc: discord.VoiceClient,
                   song: Song, state: GuildMusicState):
        if not vc or not vc.is_connected():
            logger.warning(f"[{guild.name}] VC not connected, skipping play")
            return

        source = song.build_source(state.volume)

        def _after(err):
            if err:
                logger.error(f"[{guild.name}] Playback error: {err}")
            asyncio.run_coroutine_threadsafe(self._advance(guild), self.bot.loop)

        vc.play(source, after=_after)
        logger.info(f"[{guild.name}] ▶ {song.title} — {song.channel}")

    async def _advance(self, guild: discord.Guild):
        """Advance to next track. Lock prevents race conditions."""
        state = self._state(guild.id)

        async with state._lock:
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                return

            if state.loop_song and state.current:
                self._play_song(guild, vc, state.current, state)
                return

            if state.loop_queue and state.current:
                state._q.append(state.current)

            if state._q:
                song = state._q.pop(0)
                state.current = song
                if song.video_id:
                    state._history.append(song.video_id)
                self._play_song(guild, vc, song, state)
                return

            # Queue empty — smart autoplay
            if state.autoplay:
                song = await self._autoplay_next(state, guild.id)
                if song:
                    state.current = song
                    if song.video_id:
                        state._history.append(song.video_id)
                    self._play_song(guild, vc, song, state)
                    return

            # Absolute fallback — rotating lofi 24/7
            logger.info(f"[{guild.name}] Falling back to lofi radio")
            song = await self._extract(random.choice(_LOFI_FALLBACKS))
            if song:
                state.current = song
                self._play_song(guild, vc, song, state)
            else:
                state.current = None
                self._cleanup(guild.id)

    async def _player_loop(self, guild: discord.Guild):
        state = self._state(guild.id)
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return

        if not vc.is_playing() and not vc.is_paused() and state._q:
            async with state._lock:
                if state._q:
                    song = state._q.pop(0)
                    state.current = song
                    if song.video_id:
                        state._history.append(song.video_id)
                    self._play_song(guild, vc, song, state)

        while True:
            await asyncio.sleep(2)
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                break
            if not vc.is_playing() and not vc.is_paused() and state._q:
                await self._advance(guild)

        state._player_task = None
        logger.info(f"[{guild.name}] Player loop ended")

    # ── Smart autoplay (personalized) ────────────────────────────────────

    async def _autoplay_next(self, state: GuildMusicState, guild_id: int) -> Optional[Song]:
        last = state.current
        history_ids = set(state._history)

        # Build search query from dominant user taste
        active_uid = self._active_user.get(guild_id)
        profile    = self._user_profiles.get(active_uid) if active_uid else None

        if profile:
            top_mood   = max(profile["moods"],     key=profile["moods"].get)     if profile.get("moods")     else None
            top_lang   = max(profile["languages"], key=profile["languages"].get) if profile.get("languages") else "global"
            top_artist = max(profile["artists"],   key=profile["artists"].get)   if profile.get("artists")   else None

            q = top_artist or profile.get("last_query", "")
            if top_mood:
                q += f" {top_mood}"
            if top_lang == "hindi":
                q += " hindi songs"
            elif top_lang == "kpop":
                q += " kpop"
            search_query = f"ytsearch5:{q}"
            logger.info(f"[autoplay] Personalized (dominant taste) for {active_uid}: {search_query!r}")
        elif last:
            search_query = (
                f"ytsearch5:{last.channel} {last.title}"
                if last.channel and last.channel.lower() not in ("unknown", "")
                else f"ytsearch5:{last.title} similar"
            )
            logger.info(f"[autoplay] Last-track based: {search_query!r}")
        else:
            return await self._extract(random.choice(_LOFI_FALLBACKS))

        last_dict = {
            "title": last.title if last else "",
            "uploader": last.channel if last else "",
            "duration": last.duration if last else None,
        }

        try:
            raw = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, lambda: YTDL.extract_info(search_query, download=False)),
                timeout=20.0,
            )
        except Exception as e:
            logger.warning(f"[autoplay] Search failed: {e}")
            return await self._extract("lofi chill beats")

        candidates = [e for e in (raw.get("entries") or []) if e and e.get("id") not in history_ids]

        sem = asyncio.Semaphore(3)
        best_score = -1
        best_entry: Optional[dict] = None

        async def _score_entry(entry: dict):
            nonlocal best_score, best_entry
            async with sem:
                info_dict = {
                    "title":    entry.get("title", ""),
                    "uploader": entry.get("uploader") or entry.get("channel", ""),
                    "duration": entry.get("duration"),
                    "id":       entry.get("id"),
                }
                s = _score(info_dict, last_dict)
                logger.debug(f"[autoplay] {info_dict['title']!r} score={s}")
                if s > best_score:
                    best_score = s
                    best_entry = entry

        await asyncio.gather(*[_score_entry(e) for e in candidates], return_exceptions=True)

        if best_entry and best_score >= 0:
            full = await self._extract(f"https://www.youtube.com/watch?v={best_entry.get('id')}")
            if full:
                logger.info(f"[autoplay] ✅ {full.title!r} (score={best_score})")
                return full

        # Fallback: rotating lofi
        logger.warning("[autoplay] No match — falling back to lofi")
        return await self._extract(random.choice(_LOFI_FALLBACKS))

    # ── 24/7 lofi fallback helpers ────────────────────────────────────────

    async def _play_lofi(self, guild: discord.Guild):
        """Play a random lofi track if nothing is currently playing."""
        state = self._state(guild.id)
        vc = guild.voice_client
        if not vc or not vc.is_connected() or vc.is_playing():
            return
        song = await self._extract(random.choice(_LOFI_FALLBACKS))
        if song:
            state.current = song
            self._play_song(guild, vc, song, state)

    async def _play_user_pref(self, guild: discord.Guild, profile: dict):
        """Switch to a user's preferred music style using dominant taste."""
        vc = guild.voice_client
        state = self._state(guild.id)
        if not vc or not vc.is_connected():
            return

        # Build query from dominant taste (not just last song)
        top_mood   = max(profile["moods"],     key=profile["moods"].get)     if profile.get("moods")     else None
        top_lang   = max(profile["languages"], key=profile["languages"].get) if profile.get("languages") else "global"
        top_artist = max(profile["artists"],   key=profile["artists"].get)   if profile.get("artists")   else None

        q = top_artist or profile.get("last_query", "")
        if top_mood:
            q += f" {top_mood}"
        if top_lang == "hindi":
            q += " hindi songs"
        elif top_lang == "kpop":
            q += " kpop"

        song = await self._extract(q)
        if song:
            # FIX #5: clear queue + null current BEFORE stop to prevent _advance race
            state._q.clear()
            state.current = None
            if vc.is_playing():
                vc.stop()
            state.current = song
            if song.video_id:
                state._history.append(song.video_id)
            self._play_song(guild, vc, song, state)
            logger.info(f"[{guild.name}] Switched to user profile: {q!r}")

    async def _send_prompt(self, channel: discord.VoiceChannel):
        """Send welcome embed with song request button. 30s cooldown per guild."""
        guild = channel.guild
        now   = time.time()
        if now - self._last_prompt_time.get(guild.id, 0) < 30:
            return                                          # cooldown — don't spam
        self._last_prompt_time[guild.id] = now

        text_ch = discord.utils.find(
            lambda c: isinstance(c, discord.TextChannel) and c.permissions_for(guild.me).send_messages,
            guild.text_channels,
        )
        if not text_ch:
            return
        embed = discord.Embed(
            title="🎧 Welcome!",
            description=f"You joined **{channel.name}**.\nClick below to request a song 👇",
            color=0x7C3AED,
        )
        await text_ch.send(embed=embed, view=MusicPromptView(self, guild))

    # ── Watchdog ──────────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _watchdog(self):
        for guild_id, state in list(self._states.items()):
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            vc = guild.voice_client

            # Restart dead player task
            has_work = not state.empty() or state.autoplay or state.current
            task_dead = not state._player_task or state._player_task.done()
            if task_dead and has_work and vc and vc.is_connected():
                logger.info(f"[watchdog] Restarting player for {guild.name}")
                state._player_task = self.bot.loop.create_task(self._player_loop(guild))

            # 24/7: if connected but silent, kick off lofi
            if vc and vc.is_connected() and not vc.is_playing() and not vc.is_paused():
                await self._play_lofi(guild)

    @_watchdog.before_loop
    async def _before_watchdog(self):
        await self.bot.wait_until_ready()

    # ── Voice state: personalized join / lofi on empty ────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                    before: discord.VoiceState,
                                    after: discord.VoiceState):
        if member.bot:
            return

        guild = member.guild
        vc    = guild.voice_client
        if not vc or not vc.is_connected():
            return

        humans = [m for m in vc.channel.members if not m.bot]

        # ── No humans left → lofi radio mode ─────────────────────────────
        if not humans:
            state = self._state(guild.id)
            state.autoplay = True
            state._q.clear()
            state.current = None
            logger.info(f"[{guild.name}] Channel empty — switching to lofi radio")
            await self._play_lofi(guild)
            return

        # ── Someone joined the bot's channel ─────────────────────────────
        if after.channel and after.channel == vc.channel:
            self._track_activity(guild.id, member.id)
            profile = self._user_profiles.get(member.id)

            if profile:
                # Known user — switch to their vibe
                logger.info(f"[{guild.name}] {member.display_name} joined — switching to their profile")
                await self._play_user_pref(guild, profile)
            else:
                # New user — send prompt
                await self._send_prompt(after.channel)


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

        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            try:
                vc = await interaction.user.voice.channel.connect()
            except Exception as e:
                return await interaction.followup.send(f"❌ Could not connect: {e}", ephemeral=True)

        song = await self._extract(query)
        if not song:
            return await interaction.followup.send("❌ Could not find that track.", ephemeral=True)

        song.requester = interaction.user

        # Save user profile + track activity (dominant user detection)
        self._update_profile(interaction.user.id, song)
        self._track_activity(interaction.guild.id, interaction.user.id)

        state = self._state(interaction.guild.id)
        state._q.append(song)

        if not state._player_task or state._player_task.done():
            state._player_task = self.bot.loop.create_task(self._player_loop(interaction.guild))

        embed = discord.Embed(color=0x7C3AED)
        if state.current and (vc.is_playing() or vc.is_paused()):
            embed.title = "📋 Added to Queue"
            embed.description = f"**{song.title}** `{song.duration_str}`"
            embed.set_footer(text=f"By {song.channel} • Requested by {interaction.user.display_name}")
        else:
            embed.title = "▶ Playing Soon"
            embed.description = f"**{song.title}** `{song.duration_str}`"
            if song.thumbnail:
                embed.set_thumbnail(url=song.thumbnail)
            embed.set_footer(text=f"By {song.channel}")
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
            state._player_task = None
        self._cleanup(interaction.guild.id)
        await interaction.response.send_message("⏹ Stopped and disconnected.")

    @app_commands.command(name="queue", description="Show the music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        items = list(state._q)
        embed = discord.Embed(title="🎵 Music Queue", color=0x7C3AED)
        if state.current:
            vc = interaction.guild.voice_client
            status = "▶" if (vc and vc.is_playing()) else "⏸"
            embed.add_field(
                name=f"{status} Now Playing",
                value=f"**{state.current.title}** `{state.current.duration_str}` — {state.current.channel}",
                inline=False,
            )
        if items:
            lines = "\n".join(f"`{i+1}.` {s.title} `{s.duration_str}`" for i, s in enumerate(items[:10]))
            embed.add_field(name="Up Next", value=lines, inline=False)
            extra = f"...and {len(items)-10} more  |  " if len(items) > 10 else ""
            embed.set_footer(text=f"{extra}Autoplay: {'on' if state.autoplay else 'off'}  |  Loop: {'song' if state.loop_song else 'queue' if state.loop_queue else 'off'}")
        else:
            embed.add_field(name="Queue", value="Empty — autoplay will keep music going", inline=False)
            embed.set_footer(text=f"Autoplay: {'on' if state.autoplay else 'off'}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        if not state.current:
            return await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        t  = state.current
        vc = interaction.guild.voice_client
        embed = discord.Embed(title="▶ Now Playing", description=f"**{t.title}**", color=0x10B981)
        if t.thumbnail:
            embed.set_thumbnail(url=t.thumbnail)
        embed.add_field(name="Channel",  value=t.channel or "?", inline=True)
        embed.add_field(name="Duration", value=t.duration_str,   inline=True)
        embed.add_field(name="Status",   value="▶ Playing" if (vc and vc.is_playing()) else "⏸ Paused", inline=True)
        embed.add_field(name="Queue",    value=f"{len(state._q)} up next", inline=True)
        embed.add_field(name="Loop",     value="song" if state.loop_song else "queue" if state.loop_queue else "off", inline=True)

        # Show active user profile
        active_uid = self._active_user.get(interaction.guild.id)
        profile    = self._user_profiles.get(active_uid) if active_uid else None
        if profile:
            active_member = interaction.guild.get_member(active_uid)
            name = active_member.display_name if active_member else "Unknown"
            def _top(d: dict): return max(d, key=d.get) if d else "mixed"
            embed.add_field(
                name="🎧 Active Vibe",
                value=f"{name} — {_top(profile.get('moods', {}))} / {_top(profile.get('languages', {}))}",
                inline=False,
            )
        if t.requester:
            embed.set_footer(text=f"Requested by {t.requester.display_name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="loop", description="Set loop mode: song / queue / off")
    @app_commands.choices(mode=[
        app_commands.Choice(name="song",  value="song"),
        app_commands.Choice(name="queue", value="queue"),
        app_commands.Choice(name="off",   value="off"),
    ])
    async def loop(self, interaction: discord.Interaction, mode: str):
        state = self._state(interaction.guild.id)
        state.loop_song  = (mode == "song")
        state.loop_queue = (mode == "queue")
        icons = {"song": "🔂", "queue": "🔁", "off": "➡"}
        await interaction.response.send_message(f"{icons[mode]} Loop: **{mode}**")

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

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        import random
        state = self._state(interaction.guild.id)
        if len(state._q) < 2:
            return await interaction.response.send_message("❌ Need at least 2 songs to shuffle.", ephemeral=True)
        random.shuffle(state._q)
        await interaction.response.send_message(f"🔀 Shuffled {len(state._q)} songs.")

    @app_commands.command(name="remove", description="Remove a song from the queue by position")
    @app_commands.describe(position="Position in queue (1 = next song)")
    async def remove(self, interaction: discord.Interaction, position: int):
        state = self._state(interaction.guild.id)
        if not 1 <= position <= len(state._q):
            return await interaction.response.send_message(
                f"❌ Invalid position. Queue has {len(state._q)} track(s).", ephemeral=True
            )
        removed = state._q.pop(position - 1)
        await interaction.response.send_message(f"🗑 Removed: **{removed.title}**")

    @app_commands.command(name="autoplay", description="Toggle smart autoplay")
    async def autoplay(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        state.autoplay = not state.autoplay
        icon = "🤖" if state.autoplay else "🔕"
        await interaction.response.send_message(f"{icon} Autoplay: **{'on' if state.autoplay else 'off'}**")

    @app_commands.command(name="vibe", description="Show your saved music taste profile")
    async def vibe(self, interaction: discord.Interaction):
        profile = self._user_profiles.get(interaction.user.id)
        if not profile:
            return await interaction.response.send_message(
                "No profile yet — play a song first and I'll learn your taste!", ephemeral=True
            )
        def _top(d: dict): return max(d, key=d.get) if d else "?"
        embed = discord.Embed(title=f"🎧 {interaction.user.display_name}'s Vibe", color=0x7C3AED)
        embed.add_field(name="Top Mood",     value=_top(profile.get("moods", {})),     inline=True)
        embed.add_field(name="Top Language", value=_top(profile.get("languages", {})), inline=True)
        embed.add_field(name="Top Artist",   value=_top(profile.get("artists", {})),   inline=True)
        embed.add_field(name="Last Song",    value=profile.get("last_query", "?"),     inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="request", description="Open the song request box")
    async def request(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            try:
                vc = await interaction.user.voice.channel.connect()
            except Exception as e:
                return await interaction.response.send_message(f"❌ Could not connect: {e}", ephemeral=True)
        await interaction.response.send_modal(SongRequestModal(self, interaction.guild))

    @app_commands.command(name="leave", description="Disconnect the bot from voice")
    async def leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("❌ Not in a voice channel.", ephemeral=True)
        state = self._state(interaction.guild.id)
        state.reset()
        if state._player_task:
            state._player_task.cancel()
            state._player_task = None
        await vc.disconnect()
        self._cleanup(interaction.guild.id)
        await interaction.response.send_message("👋 Disconnected.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
