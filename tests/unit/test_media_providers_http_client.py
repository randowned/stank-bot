"""Unit tests for shared HTTP client in media providers.

Verifies that YouTubeProvider and SpotifyProvider accept an injected
httpx.AsyncClient and use it instead of creating their own.
"""

from __future__ import annotations

import httpx

from stankbot.services.media_providers.spotify import SpotifyProvider
from stankbot.services.media_providers.youtube import YouTubeProvider


class TestYouTubeProviderHttpClient:
    def test_owns_client_when_none_provided(self) -> None:
        """When no http_client is passed, the provider creates and owns its own."""
        provider = YouTubeProvider(api_key="test-key")
        assert provider._owns_client is True
        assert provider._client is None

    def test_uses_injected_client(self) -> None:
        """When http_client is passed, the provider uses it and does not own it."""
        shared = httpx.AsyncClient()
        provider = YouTubeProvider(api_key="test-key", http_client=shared)
        assert provider._owns_client is False
        assert provider._client is shared

    def test_does_not_close_shared_client(self) -> None:
        """close() should not close an injected shared client."""
        shared = httpx.AsyncClient()
        provider = YouTubeProvider(api_key="test-key", http_client=shared)
        assert provider._owns_client is False
        assert provider._client is shared
        # _get_client should return the same shared instance
        client = provider._get_client()
        assert client is shared

    def test_get_client_creates_when_none(self) -> None:
        """_get_client creates a client when none was injected."""
        provider = YouTubeProvider(api_key="test-key")
        assert provider._client is None
        client = provider._get_client()
        assert client is not None
        assert provider._owns_client is True


class TestSpotifyProviderHttpClient:
    def test_owns_client_when_none_provided(self) -> None:
        """When no http_client is passed, the provider creates and owns its own."""
        provider = SpotifyProvider(client_id="test-id", client_secret="test-secret")
        assert provider._owns_client is True
        assert provider._client is None

    def test_uses_injected_client(self) -> None:
        """When http_client is passed, the provider uses it and does not own it."""
        shared = httpx.AsyncClient()
        provider = SpotifyProvider(
            client_id="test-id", client_secret="test-secret", http_client=shared,
        )
        assert provider._owns_client is False
        assert provider._client is shared

    def test_get_client_creates_when_none(self) -> None:
        """_get_client creates a client when none was injected."""
        provider = SpotifyProvider(client_id="test-id", client_secret="test-secret")
        assert provider._client is None
        client = provider._get_client()
        assert client is not None
        assert provider._owns_client is True
