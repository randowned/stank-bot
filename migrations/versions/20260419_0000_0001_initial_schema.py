"""Initial schema for StankBot.

Revision ID: 0001
Revises:
Create Date: 2026-04-19 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# SQLite requires INTEGER PRIMARY KEY for autoincrement; on Postgres we want BigInt.
_BIGINT_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guilds",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "guild_settings",
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("key", sa.String(length=80), primary_key=True),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "admin_roles",
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "channel_bindings",
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("channel_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("purpose", sa.String(length=32), primary_key=True),
    )

    op.create_table(
        "altars",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("sticker_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sp_flat_override", sa.Integer(), nullable=True),
        sa.Column("sp_position_bonus_override", sa.Integer(), nullable=True),
        sa.Column("sp_starter_bonus_override", sa.Integer(), nullable=True),
        sa.Column("sp_finish_bonus_override", sa.Integer(), nullable=True),
        sa.Column("sp_reaction_override", sa.Integer(), nullable=True),
        sa.Column("pp_break_base_override", sa.Integer(), nullable=True),
        sa.Column("pp_break_per_stank_override", sa.Integer(), nullable=True),
        sa.Column("cooldown_seconds_override", sa.Integer(), nullable=True),
        sa.Column("custom_event_key", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("guild_id", "channel_id", "sticker_id", name="uq_altar_triple"),
    )
    op.create_index("ix_altars_guild_enabled", "altars", ["guild_id", "enabled"])

    op.create_table(
        "players",
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "chains",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "altar_id",
            sa.Integer(),
            sa.ForeignKey("altars.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("broken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("starter_user_id", sa.BigInteger(), nullable=False),
        sa.Column("broken_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("final_length", sa.Integer(), nullable=True),
        sa.Column("final_unique", sa.Integer(), nullable=True),
    )
    op.create_index("ix_chains_guild_altar", "chains", ["guild_id", "altar_id"])
    op.create_index("ix_chains_guild_broken_at", "chains", ["guild_id", "broken_at"])

    op.create_table(
        "chain_messages",
        sa.Column(
            "chain_id",
            sa.Integer(),
            sa.ForeignKey("chains.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chain_messages_chain", "chain_messages", ["chain_id", "position"])

    op.create_table(
        "events",
        sa.Column("id", _BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "altar_id",
            sa.Integer(),
            sa.ForeignKey("altars.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "chain_id",
            sa.Integer(),
            sa.ForeignKey("chains.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("custom_event_key", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_events_guild_user", "events", ["guild_id", "user_id"])
    op.create_index("ix_events_guild_session", "events", ["guild_id", "session_id"])
    op.create_index("ix_events_guild_chain", "events", ["guild_id", "chain_id"])
    op.create_index(
        "ix_events_guild_type_created", "events", ["guild_id", "type", "created_at"]
    )
    op.create_index("ix_events_custom_key", "events", ["guild_id", "custom_event_key"])

    op.create_table(
        "reaction_awards",
        sa.Column("message_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("user_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("sticker_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chain_id",
            sa.Integer(),
            sa.ForeignKey("chains.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "awarded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "records",
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "altar_id",
            sa.Integer(),
            sa.ForeignKey("altars.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("scope", sa.String(length=16), primary_key=True),
        sa.Column("chain_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "chain_id",
            sa.Integer(),
            sa.ForeignKey("chains.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
    )

    op.create_table(
        "cooldowns",
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "altar_id",
            sa.Integer(),
            sa.ForeignKey("altars.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("last_valid_stank_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "player_totals",
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column(
            "session_id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=False,
            server_default="0",
        ),
        sa.Column("earned_sp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("punishments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "achievements",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("icon", sa.String(length=200), nullable=True),
        sa.Column("rule_json", sa.JSON(), nullable=False),
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "player_badges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "achievement_key",
            sa.String(length=64),
            sa.ForeignKey("achievements.key", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unlocked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "chain_id",
            sa.Integer(),
            sa.ForeignKey("chains.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint(
            "guild_id", "user_id", "achievement_key", name="uq_player_badge_unique"
        ),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", _BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_guild_created", "audit_log", ["guild_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_guild_created", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("player_badges")
    op.drop_table("achievements")
    op.drop_table("player_totals")
    op.drop_table("cooldowns")
    op.drop_table("records")
    op.drop_table("reaction_awards")
    op.drop_index("ix_events_custom_key", table_name="events")
    op.drop_index("ix_events_guild_type_created", table_name="events")
    op.drop_index("ix_events_guild_chain", table_name="events")
    op.drop_index("ix_events_guild_session", table_name="events")
    op.drop_index("ix_events_guild_user", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_chain_messages_chain", table_name="chain_messages")
    op.drop_table("chain_messages")
    op.drop_index("ix_chains_guild_broken_at", table_name="chains")
    op.drop_index("ix_chains_guild_altar", table_name="chains")
    op.drop_table("chains")
    op.drop_table("players")
    op.drop_index("ix_altars_guild_enabled", table_name="altars")
    op.drop_table("altars")
    op.drop_table("channel_bindings")
    op.drop_table("admin_roles")
    op.drop_table("guild_settings")
    op.drop_table("guilds")
