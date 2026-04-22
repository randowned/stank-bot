from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from stankbot.config import AppConfig
from stankbot.db.engine import build_engine, build_sessionmaker, session_scope
from stankbot.discord_mock.models import MockGuild, MockMember, MockTextChannel
from stankbot.scheduling.session_scheduler import SessionScheduler

log = logging.getLogger(__name__)


# Cogs loaded at startup (same as StankBot).
_COG_MODULES: tuple[str, ...] = (
    "stankbot.cogs.chain_listener",
    "stankbot.cogs.stank_commands",
    "stankbot.cogs.preview",
)


class MockBot:
    """Drop-in replacement for StankBot in dev mode.

    Has no Discord Gateway connection, but satisfies the attributes the web
    layer and cogs expect (engine, session_factory, get_guild, etc.).
    """

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    _bot_guilds: list[dict[str, object]]
    _guilds_loaded: asyncio.Event
    _cogs: dict[str, object]

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.engine = build_engine(config.database_url)
        self.session_factory = build_sessionmaker(self.engine)
        self.scheduler = SessionScheduler(self)
        self._bot_guilds = []
        self._guilds_loaded = asyncio.Event()
        self._cogs = {}

        # Create a default mock guild from config.
        guild_id = config.mock_default_guild_id or 123456789
        guild = MockGuild(
            id=guild_id,
            name=config.mock_default_guild_name,
            members={},
        )
        # Add default users as guild members so web auth checks pass.
        for uid, uname in [
            (config.mock_default_user_id, config.mock_default_user_name),
            (1001, "Alice"),
            (1002, "Bob"),
            (1003, "Charlie"),
            (1004, "Diana"),
            (1005, "Eve"),
        ]:
            guild.members[uid] = MockMember(
                id=uid,
                name=uname,
                display_name=uname,
            )
        # Add a default text channel so cogs have something to resolve.
        channel = MockTextChannel(id=1, name="altar", guild=guild)
        guild.channels[channel.id] = channel
        self._mock_guilds: dict[int, MockGuild] = {guild_id: guild}

        # Bot's own user identity.
        self.user = MockMember(
            id=config.discord_app_id,
            name="StankBot",
            display_name="StankBot",
            bot=True,
        )

        self._bot_guilds = [
            {
                "id": guild_id,
                "name": config.mock_default_guild_name,
                "icon": None,
            }
        ]

    @asynccontextmanager
    async def db(self) -> AsyncIterator[AsyncSession]:
        """Open a transactional session scope."""
        async with session_scope(self.session_factory) as session:
            yield session

    async def send_embed_to(self, channel_id: int, embed) -> None:
        """Log instead of sending to Discord."""
        log.info("send_embed_to channel=%d title=%s", channel_id, getattr(embed, "title", ""))

    def get_guild(self, guild_id: int) -> MockGuild | None:
        return self._mock_guilds.get(guild_id)

    async def fetch_channel(self, channel_id: int):
        for guild in self._mock_guilds.values():
            if channel_id in guild.channels:
                return guild.channels[channel_id]
        return None

    def get_channel(self, channel_id: int):
        return self.run_sync(self.fetch_channel, channel_id)

    def run_sync(self, coro, *args):
        """Synchronous wrapper for async methods (discord.py compat)."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # Can't run in running loop; return a mock-like object or None.
                # The web layer only calls get_guild/get_channel.
                return None
        except RuntimeError:
            pass
        return asyncio.run(coro(*args))

    async def setup_hook(self) -> None:
        # Ensure schema exists for the dev DB.
        from stankbot.db.models import Base

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("Ensured DB schema exists")

        for module in _COG_MODULES:
            try:
                mod = __import__(module, fromlist=["setup"])
                setup = getattr(mod, "setup", None)
                if setup is not None:
                    await setup(self)
                else:
                    # Some cogs may use discord.py extension loading.
                    # Load them manually if they expose a class.
                    cog_cls = getattr(mod, "ChainListener", None) or \
                              getattr(mod, "StankCommands", None) or \
                              getattr(mod, "Preview", None)
                    if cog_cls is not None:
                        await self.add_cog(cog_cls(self))
            except Exception:
                log.exception("Failed to load cog %s", module)
        log.info("Loaded cogs in mock mode")

        await self.scheduler.start()
        self._guilds_loaded.set()

    async def add_cog(self, cog) -> None:
        name = getattr(cog, "__cog_name__", None) or type(cog).__name__
        self._cogs[name] = cog

    def get_cog(self, name: str):
        return self._cogs.get(name)

    async def __aenter__(self):
        await self.setup_hook()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self) -> None:
        await self.scheduler.shutdown()
        await self.engine.dispose()
