"""Board state assembly — DB queries → ``BoardState`` dataclass.

Kept separate from ``board_renderer`` so the embed-building is pure and
the DB-touching assembly can be reused by both the slash command cog
and the web dashboard.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Player, Record, RecordScope
from stankbot.db.repositories import chains as chains_repo
from stankbot.db.repositories import events as events_repo
from stankbot.services.board_renderer import BoardState, PlayerRow
from stankbot.services.session_service import SessionService
from stankbot.services.settings_service import Keys, SettingsService
from stankbot.utils.time_utils import next_reset_at

if TYPE_CHECKING:
    from stankbot.db.models import Altar


async def _display_names(
    session: AsyncSession, guild_id: int, user_ids: list[int]
) -> dict[int, str]:
    if not user_ids:
        return {}
    stmt = select(Player.user_id, Player.display_name).where(
        Player.guild_id == guild_id,
        Player.user_id.in_(user_ids),
    )
    rows = (await session.execute(stmt)).all()
    return {int(uid): name or str(uid) for uid, name in rows}


async def build_board_state(
    session: AsyncSession,
    *,
    guild_id: int,
    guild_name: str,
    altar: Altar,
    now: datetime | None = None,
    stank_emoji_override: str | None = None,
) -> BoardState:
    now = now or datetime.now(tz=UTC)
    settings = SettingsService(session)
    session_svc = SessionService(session)
    session_id = await session_svc.current(guild_id)

    # Current chain
    current_chain = await chains_repo.current_chain(session, guild_id, altar.id)
    if current_chain is not None:
        current, current_unique = await chains_repo.chain_length_and_unique(
            session, current_chain.id
        )
    else:
        current = 0
        current_unique = 0

    # Records (cached)
    session_rec = await session.get(Record, (guild_id, altar.id, str(RecordScope.SESSION)))
    alltime_rec = await session.get(Record, (guild_id, altar.id, str(RecordScope.ALLTIME)))

    # Leaderboard for top-N display
    rows_limit = int(await settings.get(guild_id, Keys.STANK_RANKING_ROWS, 5))
    board_rows = await events_repo.leaderboard(
        session, guild_id, session_id=session_id, limit=max(rows_limit, 10)
    )
    user_ids = [uid for uid, _, _ in board_rows]

    # Chainbreaker (all-time PP leader)
    breaker_pair = await events_repo.top_pp_user(session, guild_id)
    if breaker_pair is not None:
        user_ids.append(breaker_pair[0])
    # Chain starter for the current chain
    starter_uid = current_chain.starter_user_id if current_chain else None
    if starter_uid is not None:
        user_ids.append(starter_uid)

    names = await _display_names(session, guild_id, user_ids)

    rankings = [
        PlayerRow(
            user_id=uid,
            display_name=names.get(uid, str(uid)),
            earned_sp=sp,
            punishments=pp,
        )
        for uid, sp, pp in board_rows
    ]

    starter_row: PlayerRow | None = None
    if starter_uid is not None:
        # Pull the starter's own SP/PP for display.
        sp, pp = await events_repo.sp_pp_totals(
            session, guild_id, starter_uid, session_id=session_id
        )
        starter_row = PlayerRow(
            user_id=starter_uid,
            display_name=names.get(starter_uid, str(starter_uid)),
            earned_sp=sp,
            punishments=pp,
        )

    breaker_row: PlayerRow | None = None
    if breaker_pair is not None:
        bid, pp = breaker_pair
        breaker_row = PlayerRow(
            user_id=bid,
            display_name=names.get(bid, str(bid)),
            earned_sp=0,
            punishments=pp,
        )

    # Next reset
    reset_hours = await settings.get(guild_id, Keys.RESET_HOURS_UTC, [7, 15, 23])
    next_reset = next_reset_at([int(h) for h in reset_hours], now=now)

    sticker_url = (
        f"https://cdn.discordapp.com/stickers/{altar.sticker_id}.png"
        if altar.sticker_id
        else ""
    )
    from stankbot.services.embed_builders import resolve_stank_emoji

    stank_emoji = resolve_stank_emoji(None, altar) or stank_emoji_override or ":Stank:"

    return BoardState(
        guild_name=guild_name,
        stank_emoji=stank_emoji,
        altar_sticker_url=sticker_url,
        current=current,
        current_unique=current_unique,
        record=session_rec.chain_length if session_rec else 0,
        record_unique=session_rec.unique_count if session_rec else 0,
        alltime_record=alltime_rec.chain_length if alltime_rec else 0,
        alltime_record_unique=alltime_rec.unique_count if alltime_rec else 0,
        next_reset_at=next_reset,
        now=now,
        stank_rows_limit=rows_limit,
        rankings=rankings[:rows_limit],
        chain_starter=starter_row,
        chainbreaker=breaker_row,
        extras={
            "altar_channel_id": altar.channel_id,
            "altar_channel_mention": f"<#{altar.channel_id}>" if altar.channel_id else "",
        },
    )
