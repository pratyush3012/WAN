"""
Music Autoplay / Recommendation Engine
=======================================
When the queue runs dry, this engine picks the next song intelligently:

Priority order:
  1. Same artist/channel                    (+50 pts)
  2. YouTube related videos (relatedToVideoId) (+30 pts base)
  3. Title keyword / mood similarity        (+20 pts)
  4. Similar duration                       (+10 pts)

Strict rules:
  - Never repeat a track from the last 20 played (history)
  - Never jump genres (e.g. EDM after soft acoustic)
  - Skip meme/short content (< 60 s)
  - Fallback: "<artist> similar songs" search if related API fails
"""

import asyncio
import logging
import os
import re
from typing import Optional

import aiohttp
import yt_dlp

logger = logging.getLogger("discord_bot.music.autoplay")

# ── Mood / keyword taxonomy ───────────────────────────────────────────────────

MOOD_GROUPS: dict[str, list[str]] = {
    "soft":       ["lofi", "acoustic", "chill", "calm", "relax", "sleep", "study",
                   "piano", "ambient", "slow", "soft", "gentle", "peaceful"],
    "romantic":   ["romantic", "love", "sad", "emotional", "heartbreak", "ballad",
                   "sentimental", "melancholy", "nostalgia"],
    "energetic":  ["edm", "dance", "party", "hype", "workout", "gym", "bass",
                   "trap", "dubstep", "electro", "rave", "club"],
    "rock":       ["rock", "metal", "punk", "grunge", "indie", "alternative",
                   "guitar", "band", "live"],
    "hip_hop":    ["rap", "hip hop", "hip-hop", "freestyle", "drill", "boom bap",
                   "r&b", "rnb", "soul"],
    "classical":  ["classical", "orchestra", "symphony", "opera", "baroque",
                   "concerto", "sonata", "quartet"],
    "jazz":       ["jazz", "blues", "swing", "bebop", "fusion", "saxophone"],
    "hindi":      ["hindi", "bollywood", "desi", "punjabi", "bhajan", "ghazal",
                   "filmi", "arijit", "atif", "shreya"],
    "kpop":       ["kpop", "k-pop", "bts", "blackpink", "twice", "exo", "got7",
                   "stray kids", "nct", "ive", "aespa"],
}

# Mood groups that should NOT cross-pollinate
_INCOMPATIBLE: list[tuple[str, str]] = [
    ("soft",      "energetic"),
    ("classical", "energetic"),
    ("classical", "hip_hop"),
    ("jazz",      "energetic"),
    ("hindi",     "kpop"),
]


def _detect_mood(text: str) -> Optional[str]:
    """Return the dominant mood group for a title/channel string, or None."""
    text_lower = text.lower()
    for mood, keywords in MOOD_GROUPS.items():
        if any(kw in text_lower for kw in keywords):
            return mood
    return None


def _moods_compatible(mood_a: Optional[str], mood_b: Optional[str]) -> bool:
    if mood_a is None or mood_b is None:
        return True  # unknown mood → allow
    if mood_a == mood_b:
        return True
    pair = (min(mood_a, mood_b), max(mood_a, mood_b))
    for a, b in _INCOMPATIBLE:
        if (min(a, b), max(a, b)) == pair:
            return False
    return True


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score_candidate(
    candidate: dict,
    last_title: str,
    last_channel: str,
    last_duration: Optional[int],
    last_mood: Optional[str],
) -> int:
    """
    Score a yt-dlp info dict against the last played track.
    Returns integer score (higher = better match).
    """
    score = 0
    title: str = candidate.get("title", "")
    channel: str = candidate.get("uploader") or candidate.get("channel", "")
    duration: Optional[int] = candidate.get("duration")

    # 1. Same artist / channel
    if channel and last_channel and channel.lower() == last_channel.lower():
        score += 50
        logger.debug(f"  +50 same artist: {channel!r}")

    # 2. Title keyword overlap
    last_words = set(re.findall(r"\w+", last_title.lower()))
    cand_words = set(re.findall(r"\w+", title.lower()))
    common = last_words & cand_words - {"the", "a", "an", "of", "in", "on", "at",
                                         "to", "and", "or", "is", "ft", "feat"}
    if common:
        pts = min(30, len(common) * 8)
        score += pts
        logger.debug(f"  +{pts} title overlap: {common}")

    # 3. Mood / keyword match
    cand_mood = _detect_mood(f"{title} {channel}")
    if not _moods_compatible(last_mood, cand_mood):
        logger.debug(f"  SKIP incompatible mood: {last_mood} vs {cand_mood}")
        return -999  # disqualify
    if cand_mood and cand_mood == last_mood:
        score += 20
        logger.debug(f"  +20 same mood: {cand_mood}")

    # 4. Similar duration (within 30 %)
    if duration and last_duration:
        ratio = min(duration, last_duration) / max(duration, last_duration)
        if ratio >= 0.7:
            score += 10
            logger.debug(f"  +10 similar duration ({duration}s vs {last_duration}s)")

    # Penalise very short clips (memes / shorts)
    if duration and duration < 60:
        logger.debug(f"  SKIP short content ({duration}s)")
        return -999

    return score


# ── Related video fetcher ─────────────────────────────────────────────────────

async def _fetch_related_ids(video_id: str, session: aiohttp.ClientSession) -> list[str]:
    """
    Scrape YouTube's watch page for related video IDs.
    Returns up to 10 video IDs.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                logger.warning(f"Related fetch HTTP {resp.status} for {video_id}")
                return []
            html = await resp.text()
    except Exception as e:
        logger.warning(f"Related fetch error: {e}")
        return []

    # Extract video IDs from the initial data JSON embedded in the page
    # Pattern: "videoId":"<11-char-id>"
    ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html)
    # Deduplicate, exclude the source video itself
    seen: set[str] = {video_id}
    result: list[str] = []
    for vid in ids:
        if vid not in seen:
            seen.add(vid)
            result.append(vid)
        if len(result) >= 10:
            break
    logger.debug(f"Related IDs for {video_id}: {result}")
    return result


# ── yt-dlp metadata fetch (lightweight) ──────────────────────────────────────

def _build_ytdl_opts_meta() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "source_address": "0.0.0.0",
        "extractor_args": {
            "youtube": {"player_client": ["web", "android"]}
        },
    }
    cookies_path = os.path.join(os.path.dirname(__file__), "..", "cookies.txt")
    if os.path.isfile(cookies_path):
        opts["cookiefile"] = os.path.abspath(cookies_path)
    return opts


_YTDL_META_OPTS = _build_ytdl_opts_meta()


async def _fetch_metadata(video_id: str, loop: asyncio.AbstractEventLoop) -> Optional[dict]:
    """Fetch lightweight metadata for a video ID via yt-dlp."""
    ytdl = yt_dlp.YoutubeDL(_YTDL_META_OPTS)
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        data = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False)),
            timeout=15.0,
        )
        return data
    except Exception as e:
        logger.debug(f"Metadata fetch failed for {video_id}: {e}")
        return None


async def _search_fallback(query: str, loop: asyncio.AbstractEventLoop) -> list[dict]:
    """Search YouTube and return up to 5 result metadata dicts."""
    opts = dict(_YTDL_META_OPTS)
    opts["default_search"] = "ytsearch5"
    ytdl = yt_dlp.YoutubeDL(opts)
    try:
        data = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False)),
            timeout=20.0,
        )
        if data and "entries" in data:
            return [e for e in data["entries"] if e]
        return []
    except Exception as e:
        logger.warning(f"Fallback search failed for {query!r}: {e}")
        return []


# ── AutoplayEngine ────────────────────────────────────────────────────────────

class AutoplayEngine:
    """
    Stateless engine — all state is passed in per call.
    Call AutoplayEngine.get_next(...) to get the next recommended Track.
    """

    @staticmethod
    async def get_next(
        last_track,          # utils.music_player.Track
        history: list[str],  # list of recently played video IDs
        loop: asyncio.AbstractEventLoop,
    ):
        """
        Returns a Track (or None) for the next autoplay song.

        Strategy:
          1. Scrape related video IDs from YouTube watch page
          2. Fetch metadata for each candidate
          3. Score each candidate
          4. Pick highest-scoring track not in history
          5. Fallback: search "<artist> similar songs"
        """
        from utils.music_player import Track  # local import to avoid circular

        last_title: str = last_track.title or ""
        last_channel: str = last_track.channel or ""
        last_duration: Optional[int] = last_track.duration
        last_mood = _detect_mood(f"{last_title} {last_channel}")
        history_set = set(history)

        logger.info(
            f"[Autoplay] Base track: {last_title!r} | "
            f"channel: {last_channel!r} | mood: {last_mood}"
        )

        candidates: list[tuple[int, dict]] = []  # (score, data)

        # ── Step 1: Related video IDs ──────────────────────────────────────
        related_ids: list[str] = []
        if last_track.video_id:
            async with aiohttp.ClientSession() as session:
                related_ids = await _fetch_related_ids(last_track.video_id, session)

        logger.info(f"[Autoplay] Found {len(related_ids)} related video IDs")

        # ── Step 2: Fetch metadata + score ────────────────────────────────
        meta_tasks = [
            _fetch_metadata(vid, loop)
            for vid in related_ids
            if vid not in history_set
        ]
        results = await asyncio.gather(*meta_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception) or result is None:
                continue
            score = _score_candidate(
                result, last_title, last_channel, last_duration, last_mood
            )
            if score > -999:
                candidates.append((score, result))
                logger.debug(
                    f"[Autoplay] Candidate: {result.get('title')!r} "
                    f"score={score}"
                )

        # ── Step 3: Sort and pick best ────────────────────────────────────
        candidates.sort(key=lambda x: x[0], reverse=True)

        for score, data in candidates:
            vid_id = data.get("id")
            if vid_id and vid_id in history_set:
                continue
            logger.info(
                f"[Autoplay] ✅ Selected: {data.get('title')!r} "
                f"(score={score}, channel={data.get('uploader')!r})"
            )
            return Track(data)

        # ── Step 4: Fallback search ───────────────────────────────────────
        logger.warning(
            f"[Autoplay] No related candidates passed scoring. "
            f"Falling back to search."
        )
        fallback_query = (
            f"{last_channel} similar songs"
            if last_channel and last_channel.lower() not in ("unknown", "")
            else f"{last_title} similar"
        )
        logger.info(f"[Autoplay] Fallback query: {fallback_query!r}")

        fallback_results = await _search_fallback(fallback_query, loop)
        for data in fallback_results:
            vid_id = data.get("id")
            if vid_id and vid_id in history_set:
                continue
            score = _score_candidate(
                data, last_title, last_channel, last_duration, last_mood
            )
            if score > -999:
                logger.info(
                    f"[Autoplay] ✅ Fallback selected: {data.get('title')!r} "
                    f"(score={score})"
                )
                return Track(data)

        logger.error("[Autoplay] All candidates exhausted — no track found.")
        return None
