"""Tests for the dashboard_url_for helper."""

from __future__ import annotations

import pytest

from stankbot.services.dashboard_urls import dashboard_url_for


BASE = "https://bot.example.com"


def test_board_legacy() -> None:
    assert dashboard_url_for("board", base_url=BASE) == f"{BASE}/"


def test_board_v2() -> None:
    assert dashboard_url_for("board", base_url=BASE, frontend="v2") == f"{BASE}/v2/"


def test_player_legacy() -> None:
    assert (
        dashboard_url_for("player", base_url=BASE, user_id=42)
        == f"{BASE}/player/42"
    )


def test_player_v2() -> None:
    assert (
        dashboard_url_for("player", base_url=BASE, frontend="v2", user_id=42)
        == f"{BASE}/v2/player/42"
    )


def test_chain_legacy() -> None:
    assert (
        dashboard_url_for("chain", base_url=BASE, chain_id=7)
        == f"{BASE}/history/chain/7"
    )


def test_chain_v2() -> None:
    assert (
        dashboard_url_for("chain", base_url=BASE, frontend="v2", chain_id=7)
        == f"{BASE}/v2/chain/7"
    )


def test_session_legacy() -> None:
    assert (
        dashboard_url_for("session", base_url=BASE, session_id=3)
        == f"{BASE}/history/session/3"
    )


def test_session_v2() -> None:
    assert (
        dashboard_url_for("session", base_url=BASE, frontend="v2", session_id=3)
        == f"{BASE}/v2/session/3"
    )


def test_admin_v2_prefix() -> None:
    assert (
        dashboard_url_for("admin_templates", base_url=BASE, frontend="v2")
        == f"{BASE}/v2/admin/templates"
    )


def test_admin_legacy_prefix() -> None:
    assert (
        dashboard_url_for("admin_templates", base_url=BASE, frontend="legacy")
        == f"{BASE}/admin/templates"
    )


def test_unknown_frontend_falls_back_to_legacy() -> None:
    # Typos in env vars should not break embeds — fall back to the legacy
    # URLs since that's currently the default and what's known-good.
    assert dashboard_url_for("board", base_url=BASE, frontend="typo") == f"{BASE}/"


def test_trailing_slash_normalized() -> None:
    assert (
        dashboard_url_for("board", base_url="https://x.com/", frontend="v2")
        == "https://x.com/v2/"
    )


def test_chain_requires_id() -> None:
    with pytest.raises(ValueError):
        dashboard_url_for("chain", base_url=BASE)


def test_unknown_kind_raises() -> None:
    with pytest.raises(ValueError):
        dashboard_url_for("nope", base_url=BASE)  # type: ignore[arg-type]
