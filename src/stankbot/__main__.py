from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

import uvicorn

from stankbot.bot import StankBot
from stankbot.config import AppConfig, ConfigError, load_config
from stankbot.logging_setup import configure_logging

log = logging.getLogger(__name__)


async def _run_web(bot: StankBot, config: AppConfig) -> None:
    """Serve the FastAPI dashboard on the bot's event loop."""
    from stankbot.web.app import build_app

    app = build_app(config, bot.engine, bot.session_factory, bot=bot)
    uvicorn_config = uvicorn.Config(
        app,
        host=config.web_host,
        port=config.web_port,
        log_level=config.log_level.lower(),
        lifespan="on",
    )
    server = uvicorn.Server(uvicorn_config)
    await server.serve()


async def run() -> None:
    import discord

    config = load_config()
    configure_logging(level=config.log_level, fmt=config.log_format)
    log.info("StankBot starting")

    bot = StankBot(config)
    async with bot:
        tasks: list[asyncio.Task[object]] = [
            asyncio.create_task(bot.start(config.discord_token.get_secret_value())),
        ]
        if config.enable_web:
            log.info("Web dashboard on http://%s", config.web_bind)
            tasks.append(asyncio.create_task(_run_web(bot, config)))
        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc is None:
                continue
            if isinstance(exc, discord.LoginFailure):
                raise ConfigError(
                    "Discord rejected the bot token (DISCORD_TOKEN). "
                    "Open the Developer Portal -> Bot -> Reset Token, then "
                    "paste the new token into .env.local and restart."
                ) from exc
            if isinstance(exc, discord.PrivilegedIntentsRequired):
                raise ConfigError(
                    "Discord rejected the bot's intents. Enable "
                    "'Message Content Intent' AND 'Server Members Intent' "
                    "under Developer Portal -> Bot -> Privileged Gateway Intents."
                ) from exc
            raise exc


def main() -> None:
    try:
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(run())
    except ConfigError as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
