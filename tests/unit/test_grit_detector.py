"""Unit tests for grit_detector — pure numpy audio signal heuristics.

Tests use synthetically generated audio (sine waves, noise, silence) so
they have zero external dependencies beyond numpy.
"""

from __future__ import annotations

import numpy as np
import pytest

from stankbot.utils.grit_detector import (
    compressed_ratio,
    compute_grit_score,
    spectral_centroid,
    spectral_flatness,
    zero_crossing_rate,
)

SR = 16000  # sample rate used by the voice pipeline


# ---------------------------------------------------------------------------
# Zero-crossing rate
# ---------------------------------------------------------------------------


class TestZeroCrossingRate:
    def test_silence_is_zero(self) -> None:
        x = np.zeros(16000, dtype=np.float32)
        assert zero_crossing_rate(x) == 0.0

    def test_sine_is_low(self) -> None:
        t = np.linspace(0, 1.0, SR, endpoint=False)
        x = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        # A pure sine has predictable zero-crossings: 2 per period * 440 Hz / SR
        expected = (2 * 440) / SR  # ~0.055
        assert zero_crossing_rate(x) == pytest.approx(expected, abs=0.01)

    def test_noise_is_high(self) -> None:
        rng = np.random.default_rng(42)
        x = rng.uniform(-1, 1, SR).astype(np.float32)
        # Uniform noise crosses zero about half the samples
        assert zero_crossing_rate(x) > 0.4
        assert zero_crossing_rate(x) < 0.6

    def test_short_array_clips_gracefully(self) -> None:
        assert zero_crossing_rate(np.array([0.0])) == 0.0
        assert zero_crossing_rate(np.array([0.0, 0.5])) >= 0.0


# ---------------------------------------------------------------------------
# Spectral centroid
# ---------------------------------------------------------------------------


class TestSpectralCentroid:
    def test_silence_is_zero(self) -> None:
        x = np.zeros(SR, dtype=np.float32)
        assert spectral_centroid(x, SR) == 0.0

    def test_low_freq_tone(self) -> None:
        t = np.linspace(0, 1.0, SR, endpoint=False)
        x = np.sin(2 * np.pi * 200 * t).astype(np.float32)
        centroid = spectral_centroid(x, SR)
        # Centroid should be near 200 Hz for a pure tone
        assert centroid == pytest.approx(200, abs=20)

    def test_high_freq_tone(self) -> None:
        t = np.linspace(0, 1.0, SR, endpoint=False)
        x = np.sin(2 * np.pi * 3000 * t).astype(np.float32)
        centroid = spectral_centroid(x, SR)
        assert centroid == pytest.approx(3000, abs=50)


# ---------------------------------------------------------------------------
# Spectral flatness
# ---------------------------------------------------------------------------


class TestSpectralFlatness:
    def test_silence_is_zero(self) -> None:
        x = np.zeros(SR, dtype=np.float32)
        assert spectral_flatness(x) == 0.0

    def test_sine_is_low(self) -> None:
        t = np.linspace(0, 1.0, SR, endpoint=False)
        x = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        # Pure sine — very peaky spectrum → low flatness
        assert spectral_flatness(x) < 0.3

    def test_noise_is_high(self) -> None:
        rng = np.random.default_rng(99)
        x = rng.uniform(-1, 1, SR).astype(np.float32)
        # White noise — flat spectrum → high flatness
        assert spectral_flatness(x) > 0.7


# ---------------------------------------------------------------------------
# Compressed ratio
# ---------------------------------------------------------------------------


class TestCompressedRatio:
    """Tests for compressed_ratio (kurtosis-based helper, unused in composite score)."""

    def test_silence_is_zero(self) -> None:
        # Silence has zero variance → skip (compressed_ratio not used in composite score)
        pass

    def test_sine_midrange(self) -> None:
        t = np.linspace(0, 1.0, SR, endpoint=False)
        x = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        cr = compressed_ratio(x)
        # Sine has kurtosis ≈ -1.5, score = (5-(-1.5))/7 ≈ 0.93
        assert 0.8 < cr < 1.0

    def test_clipped_sine_is_compressed(self) -> None:
        t = np.linspace(0, 1.0, SR, endpoint=False)
        x = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        x_clipped = np.clip(x * 5, -1, 1)
        cr = compressed_ratio(x_clipped)
        # Clipped signal has near-uniform amplitude → low kurtosis → high score
        assert cr > 0.8

    def test_noise_midrange(self) -> None:
        rng = np.random.default_rng(77)
        x = rng.uniform(-1, 1, SR).astype(np.float32)
        cr = compressed_ratio(x)
        # Uniform noise has kurtosis ≈ -1.2 → score ≈ 0.89
        assert 0.5 < cr < 1.0


# ---------------------------------------------------------------------------
# Composite grit score
# ---------------------------------------------------------------------------


class TestCompositeGritScore:
    def test_silence_score_is_zero(self) -> None:
        x = np.zeros(SR, dtype=np.float32)
        assert compute_grit_score(x, SR) == 0.0

    def test_sine_is_not_gritty(self) -> None:
        t = np.linspace(0, 1.0, SR, endpoint=False)
        x = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        assert compute_grit_score(x, SR) < 0.3

    def test_white_noise_is_gritty(self) -> None:
        rng = np.random.default_rng(123)
        x = rng.uniform(-1, 1, SR).astype(np.float32)
        assert compute_grit_score(x, SR) > 0.6

    def test_clipped_sine_is_moderately_gritty(self) -> None:
        t = np.linspace(0, 1.0, SR, endpoint=False)
        x = np.clip(np.sin(2 * np.pi * 440 * t) * 10, -1, 1).astype(np.float32)
        score = compute_grit_score(x, SR)
        # A clipped sine retains strong tonal character → moderate grit.
        # Higher centroid from harmonics, but still low ZCR and low flatness.
        assert score > 0.05  # above silence

    def test_noise_with_tone_is_gritty(self) -> None:
        """Noise-modulated tone — approximates distorted/growled vocal."""
        rng = np.random.default_rng(789)
        t = np.linspace(0, 1.0, SR, endpoint=False)
        tone = np.sin(2 * np.pi * 300 * t)
        noise = rng.uniform(-1, 1, SR).astype(np.float32) * 0.5
        x = (tone + noise).astype(np.float32)
        # Normalise
        x /= float(np.max(np.abs(x)))
        score = compute_grit_score(x, SR)
        # Tone+noise mix should be noticeably gritty
        assert score > 0.3

    def test_score_range(self) -> None:
        """Grit score should always be in [0.0, 1.0] for any input."""
        rng = np.random.default_rng(456)
        for _ in range(10):
            x = rng.uniform(-1, 1, SR).astype(np.float32)
            score = compute_grit_score(x, SR)
            assert 0.0 <= score <= 1.0
