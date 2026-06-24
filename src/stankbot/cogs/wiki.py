"""Wiki commands — forum-based wiki management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from stankbot.cogs._checks import requires_admin
from stankbot.db.repositories import wiki as wiki_repo
from stankbot.services import template_store
from stankbot.services.template_engine import RenderContext, render_embed
from stankbot.services.wiki_service import (
    archive_old_posts,
    build_wiki_tree,
    format_wiki_index,
    find_or_create_wiki_thread,
    update_wiki_message,
)

if TYPE_CHECKING:
    from stankbot.bot import StankBot

log = logging.getLogger(__name__)


class StankWiki(commands.GroupCog, name="stank-wiki"):
    """Wiki commands — gated by ``requires_admin``."""

    def __init__(self, bot: StankBot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name="build", description="Build and update the wiki index.")
    @requires_admin()
    async def wiki_build(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return

        await interaction.response.defer(ephemeral=True)

        async with self.bot.db() as session:
            wiki = await wiki_repo.for_guild(session, interaction.guild.id, enabled_only=True)

        if wiki is None:
            await interaction.followup.send(
                "Wiki not configured. Use the dashboard to set up a wiki channel.",
                ephemeral=True,
            )
            return

        try:
            channel = interaction.guild.get_channel(wiki.wiki_channel_id)
            if not isinstance(channel, discord.ForumChannel):
                await interaction.followup.send(
                    f"<#{wiki.wiki_channel_id}> is not a forum channel.",
                    ephemeral=True,
                )
                return

            log.info("Archiving old posts from all threads...")
            all_threads = [t async for t in channel.archived_threads()]
            log.info(f"Found {len(all_threads)} archived threads")
            all_threads.extend(channel.threads)
            log.info(f"Found {len(channel.threads)} active threads, total: {len(all_threads)}")

            for thread in all_threads:
                if isinstance(thread, discord.Thread):
                    if thread.name.startswith("archive-") or thread.name == "wiki-index":
                        log.info(f"Skipping {thread.id} ({thread.name})")
                        continue
                    log.info(f"Archiving thread {thread.id} ({thread.name})")
                    await archive_old_posts(channel, thread)
                else:
                    log.warning(f"Skipping non-Thread: {type(thread)}")

            posts = await build_wiki_tree(channel, interaction.guild.id)
            log.info(f"Wiki build: {len(posts)} root posts returned")

            wiki_index = format_wiki_index(posts)
            log.info(f"Formatted wiki_index:\n{wiki_index}")

            if not wiki_index:
                wiki_index = "*(No wiki posts yet)*"
                log.info("Wiki index was empty, using default message")

            thread, msg = await find_or_create_wiki_thread(channel, self.bot.user.id, self.bot.http)
            log.info(f"Wiki thread: {thread.id}, message: {msg.id}")

            async with self.bot.db() as session:
                template_dict = await template_store.load("wiki_index", session, interaction.guild.id)

            ctx = RenderContext(
                variables={
                    "wiki_index": wiki_index,
                    "wiki_url": thread.jump_url,
                    "thumbnail_url": "",
                    "board_url": self.bot.config.oauth_redirect_uri.rsplit("/", 2)[0] + "/",
                }
            )

            embed = render_embed(template_dict, ctx)
            log.info(f"Embed created, updating message...")
            await update_wiki_message(thread, msg, embeds=[embed])
            log.info(f"Message updated successfully")

            await interaction.followup.send(
                f"Wiki index updated in {channel.mention}.",
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.followup.send(
                f"No permission to access or manage {channel.mention}.",
                ephemeral=True,
            )
        except Exception as e:
            log.exception("wiki build error")
            await interaction.followup.send(
                f"Failed to build wiki index: {type(e).__name__}",
                ephemeral=True,
            )


async def setup(bot: StankBot) -> None:
    await bot.add_cog(StankWiki(bot))
