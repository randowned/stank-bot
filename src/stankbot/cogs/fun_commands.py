"""Fun, low-stakes slash commands.

``/napkin`` (alias ``/tissue``) — grab a virtual tissue. Each use bumps
the caller's personal tally and posts an admin-editable embed to the
guild's announcement channels. A random action line keeps it fresh.

These are *not* part of the event-sourced scoring system — see
``db/repositories/tissue_counts.py``.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from stankbot.db.repositories import tissue_counts as tissue_counts_repo
from stankbot.services import announcement_service, default_templates
from stankbot.services import embed_builders as _eb

if TYPE_CHECKING:
    from stankbot.bot import StankBot

log = logging.getLogger(__name__)


class FunCommands(commands.Cog):
    """Top-level fun commands (``/napkin``, ``/tissue``)."""

    def __init__(self, bot: StankBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="napkin", description="Grab a virtual tissue. \U0001f9fb"
    )
    async def napkin(self, interaction: discord.Interaction) -> None:
        await self._tissue(interaction)

    @app_commands.command(
        name="tissue", description="Grab a virtual tissue. \U0001f9fb"
    )
    async def tissue(self, interaction: discord.Interaction) -> None:
        await self._tissue(interaction)

    async def _tissue(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command only works inside a server.", ephemeral=True
            )
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        async with self.bot.db() as session:
            count = await tissue_counts_repo.increment(
                session, guild_id=guild_id, user_id=user_id
            )
            board_url = _eb.board_url_for(
                self.bot.config.oauth_redirect_uri, guild_id
            )
            embed = await _eb.build_tissue_embed(
                target_display_name=interaction.user.display_name,
                tissue_action=random.choice(default_templates.TISSUE_ACTIONS),
                tissue_count=count,
                board_url=board_url,
                session=session,
                guild_id=guild_id,
            )
            sent_to = await announcement_service.broadcast_to_guild(
                session, self.bot, guild_id=guild_id, embed=embed
            )

        if sent_to:
            await interaction.response.send_message(
                "\U0001f9fb *Bless you!*", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "\U0001f9fb Counted! (No announcement channel is set, so "
                "nothing was posted publicly.)",
                ephemeral=True,
            )


async def setup(bot: StankBot) -> None:
    await bot.add_cog(FunCommands(bot))
