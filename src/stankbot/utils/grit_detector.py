"""Grit easter egg — audio signal heuristics for detecting "gritty" delivery.

Computes a composite grit score (0.0–1.0) from three audio features.
Higher scores indicate a "grittier" (growled, screamed, distorted) delivery.

Pure numpy — no additional dependencies beyond what faster-whisper already
pulls in transitively. ~10ms on CPU for a typical 10s voice message.

Formula:
    grit_score = ZCR × 0.35 + centroid × 0.35 + flatness × 0.30

Design rationale:
    - ZCR (zero-crossing rate) catches high-frequency noise from distortion.
    - Spectral centroid catches bright/shrieky sounds (screamed vocals).
    - Spectral flatness catches unstructured noise (growl, breath distortion).
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


def compute_grit_score(x: np.ndarray, sample_rate: int) -> float:
    """Composite grit score between 0.0 (clean) and 1.0 (maximum grit).

    Combines three audio features with empirically calibrated weights:

        grit = ZCR × 0.35 + centroid × 0.35 + flatness × 0.30

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
    return zcr * 0.35 + cent_norm * 0.35 + flat * 0.30
