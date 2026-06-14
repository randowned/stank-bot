"""Tissue counter repo + the /napkin fun embed.

Locks in:
    * increment returns the new personal tally and isolates per (guild, user)
    * get_count reflects increments / defaults to 0
    * build_tissue_embed renders display name + count
    * tissue_embed is a registered, snake_case-clean template slot
"""

from __future__ import annotations

from typing import Any

from stankbot.db.repositories import tissue_counts as tissue_counts_repo
from stankbot.services import template_store
from stankbot.services.default_templates import TISSUE_ACTIONS, TISSUE_EMBED
from stankbot.services.embed_builders import build_tissue_embed
from stankbot.services.template_engine import validate_template_variables


class TestIncrement:
    async def test_first_use_returns_one(self, session: Any) -> None:
        assert await tissue_counts_repo.increment(session, guild_id=1, user_id=10) == 1

    async def test_increments_monotonically(self, session: Any) -> None:
        await tissue_counts_repo.increment(session, guild_id=1, user_id=10)
        assert await tissue_counts_repo.increment(session, guild_id=1, user_id=10) == 2
        assert await tissue_counts_repo.increment(session, guild_id=1, user_id=10) == 3

    async def test_isolated_per_user_and_guild(self, session: Any) -> None:
        await tissue_counts_repo.increment(session, guild_id=1, user_id=10)
        await tissue_counts_repo.increment(session, guild_id=1, user_id=10)
        # different user, same guild
        assert await tissue_counts_repo.increment(session, guild_id=1, user_id=11) == 1
        # same user, different guild
        assert await tissue_counts_repo.increment(session, guild_id=2, user_id=10) == 1

    async def test_get_count_default_and_after(self, session: Any) -> None:
        assert await tissue_counts_repo.get_count(session, guild_id=1, user_id=10) == 0
        await tissue_counts_repo.increment(session, guild_id=1, user_id=10)
        assert await tissue_counts_repo.get_count(session, guild_id=1, user_id=10) == 1


class TestTissueEmbed:
    async def test_renders_name_and_count(self, session: Any) -> None:
        embed = await build_tissue_embed(
            target_display_name="Alice",
            tissue_action="grabbed a tissue",
            tissue_count=7,
            session=session,
            guild_id=1,
        )
        assert embed.description is not None
        assert "Alice" in embed.description
        assert "grabbed a tissue" in embed.description
        assert "7" in embed.description

    def test_actions_non_empty(self) -> None:
        assert len(TISSUE_ACTIONS) >= 10
        assert all(isinstance(a, str) and a for a in TISSUE_ACTIONS)


class TestTemplateRegistration:
    def test_slot_registered(self) -> None:
        assert "tissue_embed" in template_store.all_keys()

    def test_template_vars_snake_case(self) -> None:
        # title / description / author values must all pass validation
        for value in (TISSUE_EMBED.get("title"), TISSUE_EMBED.get("description")):
            if isinstance(value, str):
                validate_template_variables(value)
        author = TISSUE_EMBED.get("author", {})
        if isinstance(author, dict):
            for v in author.values():
                if isinstance(v, str):
                    validate_template_variables(v)
