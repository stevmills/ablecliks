"""Shared test helpers (not fixtures)."""

from __future__ import annotations

import struct
import wave
from pathlib import Path


def make_minimal_wav(path: Path) -> None:
    """Write a minimal valid WAV file (mono, 44100 Hz, 16-bit, 1 silent sample)."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(struct.pack("<h", 0))
