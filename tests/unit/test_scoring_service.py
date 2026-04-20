"""Direct tests of the v1 → v2 scoring port."""

from __future__ import annotations

import pytest

from stankbot.services.scoring_service import (
    ScoringConfig,
    break_pp,
    finish_bonus_recipient,
    stank_sp,
)


def test_stank_sp_starter_gets_base_plus_starter_bonus() -> None:
    cfg = ScoringConfig()
    # Position 1: SP_FLAT (10) + 0 position bonus + SP_STARTER_BONUS (15) = 25
    assert stank_sp(1, cfg) == 25


def test_stank_sp_position_bonus_scales_linearly() -> None:
    cfg = ScoringConfig()
    # v1: SP_FLAT + (position-1)*SP_POSITION_BONUS
    assert stank_sp(2, cfg) == 10 + 1
    assert stank_sp(5, cfg) == 10 + 4
    assert stank_sp(100, cfg) == 10 + 99


def test_stank_sp_respects_overrides() -> None:
    cfg = ScoringConfig(sp_flat=20, sp_position_bonus=3, sp_starter_bonus=50)
    assert stank_sp(1, cfg) == 20 + 0 + 50
    assert stank_sp(4, cfg) == 20 + 9


def test_stank_sp_rejects_non_positive_position() -> None:
    with pytest.raises(ValueError):
        stank_sp(0, ScoringConfig())


def test_break_pp_matches_v1_formula() -> None:
    cfg = ScoringConfig()
    # v1: PP_BREAK_BASE (25) + length * PP_BREAK_PER_STANK (2)
    assert break_pp(0, cfg) == 25
    assert break_pp(10, cfg) == 45
    assert break_pp(100, cfg) == 225


def test_finish_bonus_skips_the_breaker() -> None:
    # chain: [A, B, C, D], breaker = D → last non-breaker is C.
    assert finish_bonus_recipient([1, 2, 3, 4], breaker_user_id=4) == 3


def test_finish_bonus_walks_back_past_consecutive_breakers() -> None:
    # chain: [A, B, D, D], breaker = D → last non-breaker is B.
    assert finish_bonus_recipient([1, 2, 4, 4], breaker_user_id=4) == 2


def test_finish_bonus_none_if_only_breaker_in_chain() -> None:
    assert finish_bonus_recipient([4], breaker_user_id=4) is None
    assert finish_bonus_recipient([], breaker_user_id=4) is None


def test_finish_bonus_when_no_breaker_id() -> None:
    # Break triggered by a user the system doesn't know — any last contributor is fine.
    assert finish_bonus_recipient([1, 2, 3], breaker_user_id=None) == 3
