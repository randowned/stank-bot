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
        self.wiki_keywords_cache: dict[int, list[str]] = {}
        self.wiki_config_cache: dict[int, dict] = {}
        self.wiki_threads_cache: dict[int, list[dict]] = {}
        super().__init__()
        log.info("=== StankWiki cog initialized ===")

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

            log.info(f"Refreshing wiki threads cache...")
            await self.load_wiki_threads_cache(interaction.guild.id, channel)
            log.info(f"Wiki threads cache refreshed")

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


    async def load_wiki_threads_cache(self, guild_id: int, wiki_channel: discord.ForumChannel) -> None:
        """Load and cache all wiki thread info."""
        log.info(f"Loading wiki threads cache for guild {guild_id}")
        threads_info: list[dict] = []

        async for thread in wiki_channel.archived_threads():
            if not thread.name.startswith("archive-") and thread.name != "wiki-index":
                try:
                    async for msg in thread.history(limit=1, oldest_first=True):
                        threads_info.append({
                            "name": thread.name,
                            "thread_id": thread.id,
                            "url": msg.jump_url,
                            "content": msg.content[:1024] if msg.content else "(no content)",
                        })
                        log.info(f"  Cached archived thread: {thread.name}")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        for thread in wiki_channel.threads:
            if not thread.name.startswith("archive-") and thread.name != "wiki-index":
                try:
                    async for msg in thread.history(limit=1, oldest_first=True):
                        threads_info.append({
                            "name": thread.name,
                            "thread_id": thread.id,
                            "url": msg.jump_url,
                            "content": msg.content[:1024] if msg.content else "(no content)",
                        })
                        log.info(f"  Cached active thread: {thread.name}")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        self.wiki_threads_cache[guild_id] = threads_info
        log.info(f"Wiki threads cache loaded: {len(threads_info)} threads")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.info("=== StankWiki cog ready - loading wiki caches ===")

        # Load wiki caches for all guilds
        for guild in self.bot.guilds:
            try:
                async with self.bot.db() as session:
                    wiki = await wiki_repo.for_guild(session, guild.id, enabled_only=True)

                if wiki:
                    wiki_channel = guild.get_channel(wiki.wiki_channel_id)
                    if isinstance(wiki_channel, discord.ForumChannel):
                        log.info(f"Loading cache for guild {guild.id}")
                        await self.load_wiki_threads_cache(guild.id, wiki_channel)
                    else:
                        log.warning(f"Guild {guild.id} wiki channel is not a forum")
            except Exception as e:
                log.error(f"Failed to load wiki cache for guild {guild.id}: {type(e).__name__}: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listen for keywords in messages and add info reaction if matches found."""
        log.warning(f"=== on_message TRIGGERED ===")
        log.warning(f"Guild: {message.guild}, Channel: {message.channel.id}, Author: {message.author}, Bot: {message.author.bot}, Content: {message.content[:50]}")

        if message.author.bot or not message.guild:
            return

        wiki_config = self.wiki_config_cache.get(message.guild.id)
        if wiki_config is None:
            log.info(f"Loading wiki config for guild {message.guild.id}")
            async with self.bot.db() as session:
                wiki = await wiki_repo.for_guild(session, message.guild.id, enabled_only=True)

            if not wiki:
                log.info(f"No wiki configured for guild {message.guild.id}")
                return

            wiki_config = {
                "wiki_channel_id": wiki.wiki_channel_id,
                "watch_channel_ids": wiki.wiki_watch_channel_ids or [],
            }
            self.wiki_config_cache[message.guild.id] = wiki_config
            log.info(f"Cached wiki config: {wiki_config}")
        else:
            log.info(f"Using cached wiki config: {wiki_config}")

        watch_channel_ids = wiki_config.get("watch_channel_ids", [])
        watch_channel_ids_int = [int(ch) if isinstance(ch, str) else ch for ch in watch_channel_ids]
        log.info(f"Watch channels (int): {watch_channel_ids_int}, message channel: {message.channel.id}")

        if message.channel.id not in watch_channel_ids_int:
            log.info(f"Message channel {message.channel.id} not in watch list {watch_channel_ids_int}")
            return

        wiki_channel = message.guild.get_channel(wiki_config["wiki_channel_id"])
        log.info(f"Wiki channel: {wiki_channel}, is ForumChannel: {isinstance(wiki_channel, discord.ForumChannel)}")
        if not isinstance(wiki_channel, discord.ForumChannel):
            log.info("Wiki channel is not a ForumChannel")
            return

        keywords = self.wiki_keywords_cache.get(message.guild.id)
        if keywords is None:
            log.info("Building keywords cache...")
            keywords = []
            async for thread in wiki_channel.archived_threads():
                if not thread.name.startswith("archive-") and thread.name != "wiki-index":
                    keywords.append(thread.name.lower())
                    log.info(f"  Added keyword: {thread.name.lower()}")
            for thread in wiki_channel.threads:
                if not thread.name.startswith("archive-") and thread.name != "wiki-index":
                    keywords.append(thread.name.lower())
                    log.info(f"  Added keyword: {thread.name.lower()}")
            self.wiki_keywords_cache[message.guild.id] = keywords
            log.info(f"Keywords cache built: {keywords}")
        else:
            log.info(f"Using cached keywords: {keywords}")

        message_lower = message.content.lower()
        log.info(f"Message content: '{message.content}'")
        log.info(f"Message lower: '{message_lower}'")
        has_match = any(keyword in message_lower for keyword in keywords)
        log.info(f"Has match: {has_match}")

        if has_match:
            try:
                await message.add_reaction("ℹ️")
                log.info(f"Added info reaction to message {message.id}")
            except (discord.Forbidden, discord.HTTPException) as e:
                log.warning(f"Failed to add reaction: {type(e).__name__}: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User) -> None:
        """Handle info reaction clicks - send wiki entry to user via DM."""
        log.warning(f"=== on_reaction_add TRIGGERED ===")
        log.warning(f"Emoji: {reaction.emoji}, User: {user}, IsBot: {user.bot}")

        if user.bot or reaction.emoji != "ℹ️":
            log.warning(f"Skipping: bot={user.bot}, emoji={reaction.emoji}")
            return

        message = reaction.message
        log.warning(f"Message guild: {message.guild}, Channel type: {type(message.channel).__name__}, Channel ID: {message.channel.id}")
        if not message.guild:
            log.warning("Skipping: no guild")
            return

        async with self.bot.db() as session:
            wiki = await wiki_repo.for_guild(session, message.guild.id, enabled_only=True)

        log.warning(f"Wiki: {wiki}")
        if not wiki:
            log.warning("Skipping: no wiki")
            return

        watch_channel_ids = wiki.wiki_watch_channel_ids or []
        watch_channel_ids_int = [int(ch) if isinstance(ch, str) else ch for ch in watch_channel_ids]
        log.warning(f"Watch channels: {watch_channel_ids_int}, Message channel: {message.channel.id}")
        if message.channel.id not in watch_channel_ids_int:
            log.warning("Skipping: message not in watch channel")
            return

        wiki_channel = message.guild.get_channel(wiki.wiki_channel_id)
        if not isinstance(wiki_channel, discord.ForumChannel):
            log.warning("Skipping: wiki channel is not a forum")
            return

        message_lower = message.content.lower()
        log.warning(f"Searching cached threads for keywords in message: '{message.content}'")

        cached_threads = self.wiki_threads_cache.get(message.guild.id, [])
        log.warning(f"Using cached {len(cached_threads)} threads")

        matching_threads = [t for t in cached_threads if t["name"].lower() in message_lower]
        log.warning(f"Found {len(matching_threads)} matching threads")

        if not matching_threads:
            log.warning("No matching threads found, not sending DM")
            return

        embed = discord.Embed(title="📚 Wiki Entries", color=discord.Color.gold())
        embed.description = f"Found {len(matching_threads)} matching wiki entr{'ies' if len(matching_threads) > 1 else 'y'}:"

        for thread_info in matching_threads[:5]:
            embed.add_field(
                name=thread_info["name"],
                value=thread_info["content"],
                inline=False
            )

        try:
            log.warning(f"Sending DM to user {user.id} with {len(matching_threads)} entries")
            await user.send(embed=embed)
            log.warning(f"Successfully sent wiki info to user {user.id}")
        except (discord.Forbidden, discord.HTTPException) as e:
            log.error(f"Failed to send DM to user {user.id}: {type(e).__name__}: {e}")


async def setup(bot: StankBot) -> None:
    await bot.add_cog(StankWiki(bot))
