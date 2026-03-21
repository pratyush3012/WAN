"""
Shared Gemini AI utility with rate limiting and exponential backoff.
All cogs should use this instead of their own _gemini() functions.
"""
import asyncio
import json
import logging
import os
import time
import urllib.request
import urllib.error

logger = logging.getLogger("discord_bot.gemini")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Global rate limiter: max 1 request per 2 seconds to avoid 429s
_last_call_time: float = 0.0
_call_lock = None  # initialized lazily (needs running event loop)
_consecutive_429s: int = 0


def _get_lock():
    global _call_lock
    if _call_lock is None:
        _call_lock = asyncio.Lock()
    return _call_lock


async def gemini_call(
    prompt: str,
    max_tokens: int = 150,
    temperature: float = 0.9,
    retries: int = 3,
) -> str | None:
    """
    Call Gemini API with rate limiting and exponential backoff on 429.
    Returns the text response or None on failure.
    """
    global _last_call_time, _consecutive_429s

    if not GEMINI_API_KEY:
        return None

    async with _get_lock():
        # Enforce minimum 2s gap between calls
        now = time.monotonic()
        gap = now - _last_call_time
        if gap < 2.0:
            await asyncio.sleep(2.0 - gap)
        _last_call_time = time.monotonic()

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }).encode()
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )

    for attempt in range(retries):
        try:
            loop = asyncio.get_event_loop()

            def _call():
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read())

            data = await loop.run_in_executor(None, _call)
            _consecutive_429s = 0
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

        except urllib.error.HTTPError as e:
            if e.code == 429:
                _consecutive_429s += 1
                wait = min(2 ** (_consecutive_429s + attempt), 60)
                logger.warning(f"Gemini 429 — backing off {wait}s (attempt {attempt+1}/{retries})")
                await asyncio.sleep(wait)
            else:
                logger.warning(f"Gemini HTTP error {e.code}: {e}")
                return None
        except Exception as e:
            logger.warning(f"Gemini error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)

    return None
