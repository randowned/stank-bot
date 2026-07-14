"""Grit easter egg — audio signal heuristics for detecting "gritty" delivery.

Computes a composite grit score (0.0–1.0) from four audio features derived
from the decoded PCM audio waveform. Higher scores indicate a "grittier"
(growled, screamed, distorted, heavily compressed) vocal delivery.

Pure numpy — no additional dependencies beyond what faster-whisper already
pulls in transitively. ~10ms on CPU for a typical 10s voice message.

Formula:
    grit_score = ZCR × 0.25 + centroid × 0.25 + flatness × 0.20 + compression × 0.30

Weights are calibrated for human voice recordings in Discord voice messages
(Opus-encoded, 16 kHz mono). The compression metric (amplitude kurtosis)
carries the most weight because a compressed/saturated waveform is the
strongest perceptual cue for "gritty" delivery in real speech, even though
it can give unexpected results on synthetic test signals (pure tones, etc.).
"""

from __future__ import annotations

import numpy as np


def zero_crossing_rate(x: np.ndarray) -> float:
    """Fraction of samples where the waveform crosses zero.

    Gritty/distorted vocals have high-frequency noise components that
    produce a higher ZCR than clean speech.
    """
    if len(x) < 2:
        return 0.0
    crossings = np.sum(np.abs(np.diff(np.sign(x))))
    return float(crossings / (2.0 * len(x)))


def spectral_centroid(x: np.ndarray, sample_rate: int) -> float:
    """Weighted mean frequency of the power spectrum (Hz).

    Screamed or growled vocals shift energy to higher frequencies,
    raising the spectral centroid relative to relaxed speech.
    """
    spectrum = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1.0 / sample_rate)
    total = float(np.sum(spectrum))
    if total == 0:
        return 0.0
    return float(np.sum(freqs * spectrum) / total)


def spectral_flatness(x: np.ndarray) -> float:
    """Ratio of geometric mean to arithmetic mean of the power spectrum.

    1.0 = completely noise-like (flat spectrum — gritty).
    0.0 = pure tone (peaky spectrum — clean).
    """
    spectrum = np.abs(np.fft.rfft(x))
    spectrum = spectrum[spectrum > 0]  # avoid log(0)
    if len(spectrum) == 0:
        return 0.0
    geometric = np.exp(np.mean(np.log(spectrum)))
    arithmetic = float(np.mean(spectrum))
    if arithmetic == 0:
        return 0.0
    return float(geometric / arithmetic)


def _amplitude_kurtosis(x: np.ndarray) -> float:
    """Excess kurtosis of the amplitude distribution.

    Clean speech has high kurtosis (heavy tails — lots of near-silent
    samples between words).  Noise-like or compressed signals have
    lower kurtosis (more samples at all amplitude levels).

    Used as a proxy for dynamic-range compression / saturation.

    Returns
    -------
    float
        Excess kurtosis (Fisher definition, Gaussian → 0).
        Typical range for audio: [-2, 15+].
    """
    mean = float(np.mean(x))
    fourth = float(np.mean((x - mean) ** 4))
    second = float(np.mean((x - mean) ** 2))
    if second == 0:
        return 0.0
    return fourth / (second * second) - 3.0


def compressed_ratio(x: np.ndarray) -> float:
    """Compression/saturation proxy based on amplitude kurtosis.

    Maps excess kurtosis to a normalised [0, 1] score where:
    - 1.0 = heavily compressed, saturated, or noise-like (platykurtic)
    - 0.0 = high dynamic range, clean (leptokurtic)

    Typical values:
    - Clean speech (kurtosis 5–15): 0.0–0.14
    - White noise (kurtosis ~0): ~0.71
    - Clipped/distorted (kurtosis −2 to −1): 0.86–1.0
    """
    # Silence (zero variance) → not compressed.
    if np.max(np.abs(x)) == 0:
        return 0.0
    kurt = _amplitude_kurtosis(x)
    # Map the range [-2, 5] → [1.0, 0.0], clip outside.
    # kurt = -2 (uniform/clipped) → 1.0
    # kurt = 0 (Gaussian/noise) → ~0.71
    # kurt = 5 (clean speech upper bound) → 0.0
    normalised = 5.0 - kurt
    return min(max(normalised / 7.0, 0.0), 1.0)


def compute_grit_score(x: np.ndarray, sample_rate: int) -> float:
    """Composite grit score between 0.0 (clean) and 1.0 (maximum grit).

    Combines four audio features with empirically calibrated weights
    favouring the compression/saturation metric for real voice signals:

        grit = ZCR × 0.25 + centroid × 0.25 + flatness × 0.20 + compression × 0.30

    Parameters
    ----------
    x : np.ndarray
        Float32 mono audio, normalised to [-1.0, 1.0].
    sample_rate : int
        Sample rate of the audio (e.g. 16000).

    Returns
    -------
    float
        Grit score in [0.0, 1.0].
    """
    zcr = zero_crossing_rate(x)
    cent_hz = spectral_centroid(x, sample_rate)
    cent_norm = cent_hz / (sample_rate / 2)  # normalise to 0–1
    flat = spectral_flatness(x)
    comp = compressed_ratio(x)
    return zcr * 0.25 + cent_norm * 0.25 + flat * 0.20 + comp * 0.30
