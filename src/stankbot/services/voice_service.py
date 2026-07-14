"""Voice message pipeline — download, decode, transcribe, and grit-analyse.

Orchestrates the full pipeline for a single voice message:
  1. Decode Opus/Ogg → PCM float32 (via ffmpeg pipe, no temp files)
  2. Run faster-whisper transcription
  3. Run grit analysis on the same PCM audio
  4. Check transcription against altar keywords
  5. Award grit bonus SP if the delivery was sufficiently gritty

Lazy-loads the whisper model on first call to avoid loading it on guilds
that don't use voice detection. All CPU-heavy work runs in a
ThreadPoolExecutor so the event loop stays responsive.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from stankbot.db.models import Altar

log = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice")
_whisper_model: object | None = None


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------


def voice_available() -> tuple[bool, str]:
    """Check if voice detection dependencies are available at runtime.

    Returns
    -------
    tuple[bool, str]
        (True, "") if all deps are present, or (False, reason) with a
        user-facing explanation of what's missing.
    """
    try:
        import numpy  # noqa: F401
    except ImportError:
        return False, "numpy not installed (required by faster-whisper)"

    import shutil

    if shutil.which("ffmpeg") is None:
        return False, "ffmpeg not found on PATH (required for audio decoding)"

    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return (
            False,
            "faster-whisper not installed (install via `uv sync --group voice`)",
        )

    return True, ""


@dataclass(slots=True)
class VoiceResult:
    """Result of analysing a single voice message."""

    is_stank: bool
    text: str
    grit_score: float = 0.0
    bonus_sp: int = 0


# ---------------------------------------------------------------------------
# ffmpeg decode
# ---------------------------------------------------------------------------


def _decode_audio(ogg_bytes: bytes, sample_rate: int = 16000) -> np.ndarray:
    """Decode Opus/Ogg to mono float32 PCM at ``sample_rate`` Hz.

    Pipes the raw bytes through ``ffmpeg`` — no temp files written.
    Returns a 1-D float32 array normalised to [-1.0, 1.0].

    Raises ``subprocess.CalledProcessError`` if ffmpeg is missing or the
    input is corrupt.
    """
    proc = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "s16le",  # signed 16-bit little-endian PCM
            "-ac",
            "1",  # mono
            "-ar",
            str(sample_rate),
            "pipe:1",
        ],
        input=ogg_bytes,
        capture_output=True,
        check=True,
        timeout=30,
    )
    audio = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


# ---------------------------------------------------------------------------
# whisper transcription
# ---------------------------------------------------------------------------


def _load_whisper() -> object:
    """Lazy global whisper model (loaded once, kept for the bot's lifetime)."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    from faster_whisper import WhisperModel

    _whisper_model = WhisperModel(
        "tiny",
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        num_workers=1,
    )
    log.info("loaded faster-whisper tiny (cpu, int8)")
    return _whisper_model


def _transcribe(audio: np.ndarray) -> str:
    """Run whisper transcription on PCM audio. Returns the transcript text."""
    model = _load_whisper()
    segments, _info = model.transcribe(audio, beam_size=1, language="en")
    return " ".join(seg.text.strip() for seg in segments)


# ---------------------------------------------------------------------------
# grit analysis
# ---------------------------------------------------------------------------


def _analyze_grit(audio: np.ndarray, sample_rate: int) -> float:
    """Compute grit score for the audio. Pure numpy — fast."""
    # Late import so grit_detector doesn't need numpy at module level
    from stankbot.utils.grit_detector import compute_grit_score

    return compute_grit_score(audio, sample_rate)


# ---------------------------------------------------------------------------
# full pipeline
# ---------------------------------------------------------------------------


async def analyze(
    ogg_bytes: bytes,
    altar: Altar,
    *,
    keywords: list[str] | None = None,
    grit_threshold: float | None = None,
    grit_bonus: int = 0,
) -> VoiceResult:
    """Run the full voice analysis pipeline for a single voice message.

    Parameters
    ----------
    ogg_bytes : bytes
        Raw Opus/Ogg attachment bytes downloaded from Discord.
    altar : Altar
        The guild's altar configuration (provides defaults for voice settings).
    keywords : list[str] | None
        Keywords to match in the transcription. Falls back to
        ``altar.voice_keywords`` when None.
    grit_threshold : float | None
        Minimum grit score (0–1) for bonus eligibility. Falls back to
        ``altar.voice_grit_threshold`` when None.
    grit_bonus : int
        SP bonus awarded when grit threshold is met. Falls back to
        ``altar.voice_grit_bonus`` when None/0.

    Returns
    -------
    VoiceResult
    """
    if not ogg_bytes:
        return VoiceResult(is_stank=False, text="", grit_score=0.0)

    kw = keywords if keywords is not None else (altar.voice_keywords or [])
    if not kw:
        return VoiceResult(is_stank=False, text="", grit_score=0.0)

    thresh = grit_threshold if grit_threshold is not None else float(altar.voice_grit_threshold)
    bonus = grit_bonus if grit_bonus else (altar.voice_grit_bonus or 0)

    loop = asyncio.get_running_loop()

    def _run() -> VoiceResult:
        audio = _decode_audio(ogg_bytes)
        text = _transcribe(audio)
        grit = _analyze_grit(audio, 16000)
        text_lower = text.lower().strip()
        is_stank = any(k.lower().strip() in text_lower for k in kw)
        bsp = bonus if is_stank and grit >= thresh else 0
        return VoiceResult(is_stank=is_stank, text=text, grit_score=float(grit), bonus_sp=bsp)

    return await loop.run_in_executor(_EXECUTOR, _run)
