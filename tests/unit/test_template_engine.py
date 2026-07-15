"""Template engine: substitution, validation, embed rendering."""

from __future__ import annotations

import discord
import pytest

from stankbot.services.template_engine import (
    RenderContext,
    TemplateError,
    render_embed,
    strict_substitute,
    substitute,
    validate_template_variables,
)


def test_substitute_replaces_snake_case_tokens() -> None:
    ctx = RenderContext(variables={"current": 42, "record": 100})
    assert substitute("chain {current}/{record}", ctx) == "chain 42/100"


def test_substitute_leaves_unknown_tokens_verbatim() -> None:
    ctx = RenderContext(variables={"current": 1})
    assert substitute("{current} {unknown}", ctx) == "1 {unknown}"


def test_strict_substitute_raises_on_unknown_token() -> None:
    ctx = RenderContext(variables={"current": 1})
    with pytest.raises(TemplateError):
        strict_substitute("{current} {missing}", ctx)


def test_validate_rejects_camelcase() -> None:
    with pytest.raises(TemplateError):
        validate_template_variables("{alltimeRecord}")


def test_validate_rejects_kebab_case() -> None:
    with pytest.raises(TemplateError):
        validate_template_variables("{next-reset-in}")


def test_validate_accepts_snake_case_with_digits() -> None:
    assert validate_template_variables("{chain_1} {record_v2}") == ["chain_1", "record_v2"]


def test_render_embed_builds_fields_and_footer() -> None:
    template = {
        "title": "Board: {guild_name}",
        "color": "#ffd166",
        "description": "Chain: {current}",
        "fields": [
            {"name": "Record", "value": "{record}", "inline": True},
            {"name": "Unique", "value": "{record_unique}", "inline": True},
        ],
        "footer": "v{ver}",
    }
    ctx = RenderContext(
        variables={
            "guild_name": "Maphra",
            "current": 42,
            "record": 120,
            "record_unique": 15,
            "ver": "2.0.0",
        }
    )
    embed = render_embed(template, ctx)
    assert isinstance(embed, discord.Embed)
    assert embed.title == "Board: Maphra"
    assert embed.description == "Chain: 42"
    assert embed.color is not None
    assert embed.color.value == 0xFFD166
    assert len(embed.fields) == 2
    assert embed.fields[0].value == "120"
    assert embed.fields[1].inline is True
    assert embed.footer is not None
    assert embed.footer.text == "v2.0.0"


def test_render_embed_image_string() -> None:
    """Single string image works as before."""
    template = {"image": "{image_url}"}
    ctx = RenderContext(variables={"image_url": "https://example.com/img.png"})
    embed = render_embed(template, ctx)
    assert embed.image is not None
    assert embed.image.url == "https://example.com/img.png"


def test_render_embed_image_array_picks_one() -> None:
    """Array of images picks one at random."""
    template = {"image": ["https://example.com/a.png", "https://example.com/b.png"]}
    ctx = RenderContext(variables={})
    results: set[str] = set()
    for _ in range(40):
        embed = render_embed(template, ctx)
        assert embed.image is not None
        assert embed.image.url is not None
        results.add(embed.image.url)
    assert results == {"https://example.com/a.png", "https://example.com/b.png"}


def test_render_embed_image_array_single_element() -> None:
    """Array with one element always picks that one."""
    template = {"image": ["https://example.com/only.png"]}
    ctx = RenderContext(variables={})
    embed = render_embed(template, ctx)
    assert embed.image is not None
    assert embed.image.url == "https://example.com/only.png"


def test_render_embed_image_array_empty_is_noop() -> None:
    """Empty array is falsy — no image set."""
    template = {"image": []}
    ctx = RenderContext(variables={})
    embed = render_embed(template, ctx)
    assert embed.image is None or embed.image.url is None


def test_render_embed_image_array_with_variables() -> None:
    """Array elements are template strings — resolved after pick."""
    template = {"image": ["{a}", "{b}"]}
    ctx = RenderContext(variables={"a": "https://a.png", "b": "https://b.png"})
    results: set[str] = set()
    for _ in range(40):
        embed = render_embed(template, ctx)
        assert embed.image is not None
        assert embed.image.url is not None
        results.add(embed.image.url)
    assert results == {"https://a.png", "https://b.png"}
