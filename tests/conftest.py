"""Shared pytest fixtures.

All fixtures use tmp_path (pytest's built-in temp directory) so tests
are fully isolated and leave no trace after they run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cliks.models import ALL_ROLES, Role, Voice, VoiceFile
from tests.helpers import make_minimal_wav


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Return an empty source directory."""
    d = tmp_path / "source"
    d.mkdir()
    return d


@pytest.fixture
def complete_voice_dir(source_dir: Path) -> Path:
    """A voice folder with all 4 role WAVs present."""
    folder = source_dir / "BELL - Classic Bell"
    folder.mkdir()
    for role in ALL_ROLES:
        wav_name = {
            Role.ACCENT: "Accent.wav",
            Role.FOURTHS: "4ths.wav",
            Role.EIGHTHS: "8ths.wav",
            Role.SIXTEENTHS: "16ths.wav",
        }[role]
        make_minimal_wav(folder / wav_name)
    return folder


@pytest.fixture
def incomplete_voice_dir(source_dir: Path) -> Path:
    """A voice folder missing the 8ths and 16ths roles."""
    folder = source_dir / "A1 - MPC x Ableton"
    folder.mkdir()
    make_minimal_wav(folder / "Accent.wav")
    make_minimal_wav(folder / "4ths.wav")
    return folder


@pytest.fixture
def complete_voice(complete_voice_dir: Path) -> Voice:
    """A fully-populated Voice object (all 4 roles)."""
    voice = Voice(
        folder_name="BELL - Classic Bell",
        source_dir=complete_voice_dir,
    )
    for role in ALL_ROLES:
        wav_name = {
            Role.ACCENT: "Accent.wav",
            Role.FOURTHS: "4ths.wav",
            Role.EIGHTHS: "8ths.wav",
            Role.SIXTEENTHS: "16ths.wav",
        }[role]
        voice.files[role] = VoiceFile(
            role=role,
            source_path=complete_voice_dir / wav_name,
        )
    return voice


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Return an empty output directory."""
    d = tmp_path / "output"
    d.mkdir()
    return d
