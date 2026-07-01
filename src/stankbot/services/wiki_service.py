"""Wiki service — build and manage forum-based wikis."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import discord
from discord.http import Route

log = logging.getLogger(__name__)


URL_LINK_PATTERN = re.compile(
    r"https?://(?:www\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)(?:/(\d+))?"
)
CHANNEL_MENTION_PATTERN = re.compile(r"<#(\d+)>")


@dataclass(frozen=True)
class WikiPost:
    """A post in the wiki with optional children."""

    thread_id: int
    message_id: int
    title: str
    url: str
    children: list[WikiPost] = field(default_factory=list)


def extract_message_links(content: str) -> list[tuple[int, int]]:
    """Extract thread references from content. Returns list of (guild_id, thread_id).

    Handles:
    - Full URL link: https://discord.com/channels/{guild_id}/{thread_id}/{message_id}
    - Thread URL link: https://discord.com/channels/{guild_id}/{thread_id}
    - Channel mention: <#{thread_id}>
    """
    links: list[tuple[int, int]] = []

    url_matches = URL_LINK_PATTERN.findall(content)
    for g, t, _ in url_matches:
        links.append((int(g), int(t)))

    mention_matches = CHANNEL_MENTION_PATTERN.findall(content)
    for thread_id in mention_matches:
        links.append((0, int(thread_id)))

    return links


async def build_wiki_tree(
    channel: discord.ForumChannel, guild_id: int
) -> list[WikiPost]:
    """Build a tree of posts from forum threads.

    A post (A) has post (B) as a child if (A)'s message contains a link
    to any message in the thread containing (B).

    Message links in forum threads use the format:
    https://discord.com/channels/{guild_id}/{thread_id}/{message_id}

    Returns root-level posts (those with no parent in the forum).
    """
    log.info("=== WIKI BUILD START ===")

    archived = [t async for t in channel.archived_threads()]
    log.info(f"Found {len(archived)} archived threads")

    active = channel.threads
    log.info(f"Found {len(active)} active threads")

    threads = archived + active
    log.info(f"Total threads to process: {len(threads)}")
    for t in threads:
        log.info(f"  - Thread: {t.id} ({t.name})")

    post_map: dict[int, WikiPost] = {}
    thread_to_last_msg: dict[int, discord.Message] = {}

    for thread in threads:
        if not isinstance(thread, discord.Thread):
            log.warning(f"Skipping non-Thread object: {type(thread)}")
            continue

        if thread.name.startswith("archive-") or thread.name == "wiki-index":
            log.info(f"Skipping archive/wiki thread: {thread.id} ({thread.name})")
            continue

        log.info(f"Processing thread {thread.id} ({thread.name})")

        last_msg = None
        try:
            last_msg_id = thread.last_message_id
            if last_msg_id is None:
                log.info(f"  - No last_message_id")
                continue
            last_msg = await thread.fetch_message(last_msg_id)
        except (discord.NotFound, discord.Forbidden, AttributeError) as e:
            log.warning(f"  - Failed to fetch last message {last_msg_id}: {type(e).__name__}")
            log.info(f"  - Searching for valid message in thread history...")
            try:
                async for msg in thread.history(limit=100):
                    if msg.author.id != channel.guild.me.id:
                        last_msg = msg
                        log.info(f"  - Found valid message: {msg.id} by {msg.author.name}")
                        break
            except (discord.Forbidden, discord.HTTPException) as he:
                log.warning(f"  - Failed to fetch thread history: {type(he).__name__}")
                continue

        if last_msg is None:
            log.info(f"  - No valid message found in thread")
            continue

        if last_msg.author.id == channel.guild.me.id:
            log.info(f"  - Skipping (bot message)")
            continue

        post = WikiPost(
            thread_id=thread.id,
            message_id=last_msg.id,
            title=thread.name,
            url=last_msg.jump_url,
        )
        post_map[thread.id] = post
        thread_to_last_msg[thread.id] = last_msg
        log.info(f"  - Added post: {thread.id} -> {thread.name}")

    log.info(f"Total posts in post_map: {len(post_map)}")

    children_map: dict[int, list[WikiPost]] = {}
    parent_threads: set[int] = set()

    for thread_id, last_msg in thread_to_last_msg.items():
        log.info(f"Thread {thread_id} ({post_map[thread_id].title}) message content:")
        log.info(f"  Content: {last_msg.content}")
        links = extract_message_links(last_msg.content)
        log.info(f"  Found {len(links)} links")
        for guild_id, linked_thread_id in links:
            log.info(f"    - Link to guild {guild_id}, thread {linked_thread_id}")
            if linked_thread_id in post_map and linked_thread_id != thread_id:
                if thread_id not in children_map:
                    children_map[thread_id] = []
                child_post = post_map[linked_thread_id]
                if child_post not in children_map[thread_id]:
                    children_map[thread_id].append(child_post)
                    parent_threads.add(linked_thread_id)
                    log.info(f"    - Created parent-child: {thread_id} -> {linked_thread_id}")

    log.info(f"Parent threads (will be excluded from root): {parent_threads}")

    root_posts: list[WikiPost] = []
    for thread_id, post in post_map.items():
        if thread_id in parent_threads:
            log.info(f"Excluding {thread_id} from root (has parent)")
            continue
        children = children_map.get(thread_id, [])
        post_with_children = WikiPost(
            thread_id=post.thread_id,
            message_id=post.message_id,
            title=post.title,
            url=post.url,
            children=children,
        )
        root_posts.append(post_with_children)
        log.info(f"Added root post: {thread_id} ({post.title}) with {len(children)} children")
        if children:
            for child in children:
                log.info(f"  - Child: {child.thread_id} ({child.title})")

    log.info(f"=== WIKI BUILD END: {len(root_posts)} root posts ===")
    return root_posts


def format_wiki_index(posts: list[WikiPost]) -> str:
    """Format root posts as a flat clickable markdown index (no tree structure)."""
    lines: list[str] = []
    for post in posts:
        lines.append(f"• [{post.title}]({post.url})")
    return "\n".join(lines)


async def find_or_create_wiki_thread(
    channel: discord.ForumChannel, bot_id: int, http_client: object | None = None
) -> tuple[discord.Thread, discord.Message]:
    """Find or create the bot's wiki index thread.

    Returns (thread, first_message).
    """
    wiki_thread_name = "wiki-index"

    for thread in channel.threads:
        if thread.name == wiki_thread_name:
            async for msg in thread.history(limit=1, oldest_first=True):
                return thread, msg

    async for thread in channel.archived_threads(limit=100):
        if thread.name == wiki_thread_name:
            async for msg in thread.history(limit=1, oldest_first=True):
                return thread, msg

    log.info(f"Creating new wiki-index thread in forum {channel.id}")
    initial_msg = await channel.create_thread(
        name=wiki_thread_name,
        content="*Wiki index loading...*",
    )

    first_msg = initial_msg.message
    thread = initial_msg.thread
    log.info(f"Created thread {thread.id}, first message {first_msg.id}")

    if http_client:
        try:
            guild = thread.guild
            bot_member = guild.me
            perms = channel.permissions_for(bot_member)
            log.info(f"Bot permissions in forum channel {channel.id}:")
            log.info(f"  - manage_threads: {perms.manage_threads}")
            log.info(f"  - manage_channels: {perms.manage_channels}")
            log.info(f"  - moderate_members: {perms.moderate_members}")

            log.info(f"Unpinning thread {thread.id} first (if pinned)")
            try:
                route = Route("PATCH", f"/channels/{thread.id}")
                await http_client.request(route, json={"pinned": False})
                log.info(f"Thread unpinned")
            except discord.HTTPException as e:
                log.info(f"Unpin failed or thread wasn't pinned: {e}")

            log.info(f"Now pinning thread {thread.id}")
            route = Route("PATCH", f"/channels/{thread.id}")
            await http_client.request(route, json={"pinned": True})
            log.info(f"Successfully pinned thread")
        except discord.Forbidden as e:
            log.error(f"Permission denied pinning thread (403): {e}")
            log.error(f"Bot needs 'Manage Threads' permission in the forum channel")
        except discord.HTTPException as e:
            log.error(f"HTTP error pinning thread: {e.status} {e.code} - {e}")
        except Exception as e:
            log.error(f"Unexpected error pinning thread: {type(e).__name__}: {e}")
    else:
        log.info("No http_client provided, cannot pin thread")

    return thread, first_msg


async def archive_old_posts(
    channel: discord.ForumChannel, thread: discord.Thread
) -> None:
    """Archive all but the last post in a thread to an archive thread."""
    log.info(f"=== ARCHIVING THREAD {thread.id} ({thread.name}) ===")
    archive_thread_name = f"archive-{thread.name}"

    messages_to_archive: list[discord.Message] = []

    try:
        async for msg in thread.history(limit=None, oldest_first=True):
            messages_to_archive.append(msg)
        log.info(f"Fetched {len(messages_to_archive)} messages from thread history")
    except (discord.Forbidden, discord.HTTPException) as e:
        log.error(f"Failed to fetch history for thread {thread.id}: {type(e).__name__}: {e}")
        return

    if len(messages_to_archive) <= 1:
        log.info(f"Thread {thread.id} has only {len(messages_to_archive)} message(s), nothing to archive")
        return

    messages_to_delete = messages_to_archive[:-1]
    log.info(f"Archiving {len(messages_to_delete)} message(s) from thread {thread.id} ({thread.name})")

    archive_thread_exists = False
    archive_thread = None

    for t in channel.threads:
        if t.name == archive_thread_name:
            archive_thread = t
            archive_thread_exists = True
            break

    if not archive_thread_exists:
        async for t in channel.archived_threads():
            if t.name == archive_thread_name:
                archive_thread = t
                archive_thread_exists = True
                break

    if not archive_thread:
        try:
            archive_msg = await channel.create_thread(
                name=archive_thread_name,
                content=f"Archive of messages from [{thread.name}]({thread.jump_url})"
            )
            archive_thread = archive_msg.thread
            log.info(f"Created archive thread {archive_thread.id}")
        except (discord.Forbidden, discord.HTTPException) as e:
            log.error(f"Failed to create archive thread: {type(e).__name__}: {e}")
            return

    for msg in messages_to_delete:
        try:
            log.info(f"Archiving message {msg.id} to archive thread")
            await archive_thread.send(
                f"**[{msg.author.name}]** {msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n{msg.content}"
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning(f"Failed to archive message {msg.id}: {type(e).__name__}")

    for msg in messages_to_delete:
        try:
            await msg.delete()
            log.info(f"Deleted message {msg.id}")
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning(f"Failed to delete message {msg.id}: {type(e).__name__}")


async def update_wiki_message(
    thread: discord.Thread, msg: discord.Message, embeds: list[discord.Embed] | None = None
) -> None:
    """Update wiki message in thread and pin it."""
    log.info(f"Updating message {msg.id} in thread {thread.id}")
    try:
        await msg.edit(content=None, embeds=embeds or [])
        log.info(f"Message updated successfully")
    except (discord.Forbidden, discord.HTTPException) as e:
        log.error(f"Failed to update message: {type(e).__name__}: {e}")
        return

    try:
        guild = thread.guild
        channel = thread.parent
        if channel:
            bot_member = guild.me
            perms = channel.permissions_for(bot_member)
            log.info(f"Bot permissions in forum channel {channel.id}:")
            log.info(f"  - manage_threads: {perms.manage_threads}")
            log.info(f"  - manage_channels: {perms.manage_channels}")
            log.info(f"  - moderate_members: {perms.moderate_members}")

        log.info(f"Unpinning thread {thread.id} first (if pinned)")
        try:
            await thread.edit(pinned=False)
            log.info(f"Thread unpinned")
        except discord.HTTPException as e:
            log.info(f"Unpin failed or thread wasn't pinned: {e}")

        log.info(f"Now pinning thread {thread.id}")
        await thread.edit(pinned=True)
        log.info(f"Thread pinned successfully")
    except discord.Forbidden as e:
        log.error(f"Permission denied pinning thread: {e}")
        log.error(f"Bot needs 'Manage Threads' permission in the forum channel")
    except discord.HTTPException as e:
        log.error(f"HTTP error pinning thread: {e.status} {e.code} - {e}")
    except Exception as e:
        log.error(f"Unexpected error pinning thread: {type(e).__name__}: {e}")
