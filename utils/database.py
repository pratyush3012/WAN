from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, BigInteger, String, Integer, Boolean, DateTime, JSON, Index, UniqueConstraint
import datetime
from datetime import timezone
import os
import logging


def _utcnow():
    return datetime.datetime.now(timezone.utc)

logger = logging.getLogger('discord_bot.database')

Base = declarative_base()

class GuildConfig(Base):
    __tablename__ = 'guild_config'
    
    guild_id = Column(BigInteger, primary_key=True)
    prefix = Column(String, default='!')
    welcome_channel = Column(BigInteger, nullable=True)
    log_channel = Column(BigInteger, nullable=True)
    mod_role = Column(BigInteger, nullable=True)
    dj_role = Column(BigInteger, nullable=True)
    mute_role = Column(BigInteger, nullable=True)
    auto_role = Column(BigInteger, nullable=True)
    translation_enabled = Column(Boolean, default=True)
    music_volume = Column(Integer, default=50)
    xp_enabled = Column(Boolean, default=True)
    anti_spam = Column(Boolean, default=True)
    anti_raid = Column(Boolean, default=True)
    youtube_channels = Column(JSON, default=list)
    disabled_modules = Column(JSON, default=list)

class UserXP(Base):
    __tablename__ = 'user_xp'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    voice_time = Column(Integer, default=0)
    last_xp_time = Column(DateTime, default=_utcnow)
    
    __table_args__ = (
        UniqueConstraint('guild_id', 'user_id', name='uix_guild_user'),
        Index('idx_guild_xp', 'guild_id', 'xp'),
        Index('idx_guild_user', 'guild_id', 'user_id'),
    )

class ModAction(Base):
    __tablename__ = 'mod_actions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    moderator_id = Column(BigInteger, nullable=False)
    action_type = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    timestamp = Column(DateTime, default=_utcnow)
    
    __table_args__ = (
        Index('idx_guild_timestamp', 'guild_id', 'timestamp'),
        Index('idx_user_actions', 'user_id', 'guild_id'),
    )


class GuildSettings(Base):
    """Generic key-value settings store — persists all cog settings across deploys."""
    __tablename__ = 'guild_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    key = Column(String, nullable=False)
    value = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint('guild_id', 'key', name='uix_guild_key'),
        Index('idx_guild_settings', 'guild_id', 'key'),
    )

class Database:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        db_url = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///bot.db')
        # Render PostgreSQL URLs use postgres:// but SQLAlchemy needs postgresql+asyncpg://
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql+asyncpg://', 1)
        elif db_url.startswith('postgresql://') and '+asyncpg' not in db_url:
            db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://', 1)

        # If asyncpg not installed, fall back to SQLite regardless of DATABASE_URL
        if 'asyncpg' in db_url:
            try:
                import asyncpg  # noqa: F401
            except ImportError:
                logger.warning("asyncpg not installed — falling back to SQLite")
                db_url = 'sqlite+aiosqlite:///bot.db'
        
        # Connection pooling configuration
        pool_config = {
            'pool_size': 10,
            'max_overflow': 20,
            'pool_timeout': 30,
            'pool_recycle': 3600,
            'pool_pre_ping': True,
        }
        
        try:
            if 'sqlite' in db_url:
                self.engine = create_async_engine(
                    db_url,
                    echo=False,
                    connect_args={'check_same_thread': False}
                )
            else:
                self.engine = create_async_engine(db_url, echo=False, **pool_config)
        except (ImportError, ModuleNotFoundError, OSError) as e:
            logger.warning(
                "PostgreSQL async engine init failed (%s) — falling back to SQLite",
                e,
            )
            db_url = 'sqlite+aiosqlite:///bot.db'
            self.engine = create_async_engine(
                db_url,
                echo=False,
                connect_args={'check_same_thread': False}
            )

        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        self._initialized = True
        logger.info(f"Database initialized with URL: {db_url.split('@')[-1] if '@' in db_url else 'sqlite'}")
    
    async def init_db(self):
        """Initialize database tables"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def get_guild_config(self, guild_id: int):
        """Get guild configuration with proper session management"""
        try:
            async with self.async_session() as session:
                result = await session.get(GuildConfig, guild_id)
                if not result:
                    result = GuildConfig(guild_id=guild_id)
                    session.add(result)
                    await session.commit()
                    await session.refresh(result)
                return result
        except Exception as e:
            logger.error(f"Error getting guild config for {guild_id}: {e}")
            # Return default config on error
            return GuildConfig(guild_id=guild_id)
    
    async def update_guild_config(self, guild_id: int, **kwargs):
        """Update guild configuration"""
        try:
            async with self.async_session() as session:
                config = await session.get(GuildConfig, guild_id)
                if not config:
                    config = GuildConfig(guild_id=guild_id)
                    session.add(config)
                
                for key, value in kwargs.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                
                await session.commit()
        except Exception as e:
            logger.error(f"Error updating guild config for {guild_id}: {e}")
            raise
    
    async def close(self):
        """Close database connections"""
        await self.engine.dispose()
        logger.info("Database connections closed")
