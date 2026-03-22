"""
utils/settings.py — Persistent guild settings helper.
All cog settings go through here so they survive Render redeploys.
Uses the GuildSettings table (SQLite locally, PostgreSQL on Render).
"""
import logging
from sqlalchemy import select, delete
from utils.database import Database, GuildSettings

logger = logging.getLogger('discord_bot.settings')

_db = None

def _get_db():
    global _db
    if _db is None:
        _db = Database()
    return _db


async def get_setting(guild_id: int, key: str, default=None):
    """Get a setting value for a guild. Returns default if not set."""
    try:
        db = _get_db()
        async with db.async_session() as session:
            result = await session.execute(
                select(GuildSettings).where(
                    GuildSettings.guild_id == guild_id,
                    GuildSettings.key == key
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return default
            return row.value
    except Exception as e:
        logger.error(f"get_setting error guild={guild_id} key={key}: {e}")
        return default


async def set_setting(guild_id: int, key: str, value) -> bool:
    """Set a setting value for a guild. Creates or updates."""
    try:
        db = _get_db()
        async with db.async_session() as session:
            result = await session.execute(
                select(GuildSettings).where(
                    GuildSettings.guild_id == guild_id,
                    GuildSettings.key == key
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = GuildSettings(guild_id=guild_id, key=key, value=value)
                session.add(row)
            else:
                row.value = value
            await session.commit()
            return True
    except Exception as e:
        logger.error(f"set_setting error guild={guild_id} key={key}: {e}")
        return False


async def delete_setting(guild_id: int, key: str) -> bool:
    """Delete a setting for a guild."""
    try:
        db = _get_db()
        async with db.async_session() as session:
            await session.execute(
                delete(GuildSettings).where(
                    GuildSettings.guild_id == guild_id,
                    GuildSettings.key == key
                )
            )
            await session.commit()
            return True
    except Exception as e:
        logger.error(f"delete_setting error guild={guild_id} key={key}: {e}")
        return False


async def get_all_settings(guild_id: int) -> dict:
    """Get all settings for a guild as a dict."""
    try:
        db = _get_db()
        async with db.async_session() as session:
            result = await session.execute(
                select(GuildSettings).where(GuildSettings.guild_id == guild_id)
            )
            rows = result.scalars().all()
            return {row.key: row.value for row in rows}
    except Exception as e:
        logger.error(f"get_all_settings error guild={guild_id}: {e}")
        return {}
