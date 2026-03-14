"""Tests for validator.py: validation rules engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from cliks.models import ALL_ROLES, Role, Voice, VoiceFile
from cliks.validator import Severity, validate
from tests.helpers import make_minimal_wav


def _make_voice(folder_name: str, source_dir: Path, roles: list[Role] | None = None) -> Voice:
    """Helper: create a Voice with the given roles populated (using real temp files)."""
    folder = source_dir / folder_name
    folder.mkdir(exist_ok=True)
    voice = Voice(folder_name=folder_name, source_dir=folder)
    if roles is None:
        roles = list(ALL_ROLES)
    wav_map = {
        Role.ACCENT: "Accent.wav",
        Role.FOURTHS: "4ths.wav",
        Role.EIGHTHS: "8ths.wav",
        Role.SIXTEENTHS: "16ths.wav",
    }
    for role in roles:
        path = folder / wav_map[role]
        make_minimal_wav(path)
        voice.files[role] = VoiceFile(role=role, source_path=path)
    return voice


class TestValidateMissingRoles:
    def test_complete_voice_has_no_errors(self, source_dir: Path, output_dir: Path):
        voice = _make_voice("BELL - Classic Bell", source_dir)
        result = validate([voice], output_dir=output_dir)
        assert result.is_valid

    def test_missing_role_is_an_error(self, source_dir: Path):
        voice = _make_voice("BELL - Classic Bell", source_dir, roles=[Role.ACCENT])
        result = validate([voice])
        assert result.has_errors
        error_messages = [i.message for i in result.errors]
        assert any("4ths" in m or "8ths" in m or "16ths" in m for m in error_messages)

    def test_all_missing_roles_reported(self, source_dir: Path):
        voice = _make_voice("BELL - Classic Bell", source_dir, roles=[])
        result = validate([voice])
        missing_errors = [i for i in result.errors if "Missing role" in i.message]
        assert len(missing_errors) == 4


class TestValidateSlugCollisions:
    def test_slug_collision_is_an_error(self, source_dir: Path):
        v1 = _make_voice("BELL - Classic Bell", source_dir)
        # Create a second folder that would slug to the same value.
        folder2 = source_dir / "bell-classic-bell"
        folder2.mkdir()
        v2 = Voice(folder_name="bell-classic-bell", source_dir=folder2)
        result = validate([v1, v2])
        collision_errors = [i for i in result.errors if "collision" in i.message.lower()]
        assert len(collision_errors) >= 1

    def test_no_collision_with_distinct_slugs(self, source_dir: Path):
        v1 = _make_voice("BELL - Classic Bell", source_dir)
        v2 = _make_voice("A1 - MPC x Ableton", source_dir)
        result = validate([v1, v2])
        collision_errors = [i for i in result.errors if "collision" in i.message.lower()]
        assert len(collision_errors) == 0


class TestValidateZeroByteFiles:
    def test_zero_byte_wav_is_an_error(self, source_dir: Path):
        folder = source_dir / "BELL - Classic Bell"
        folder.mkdir()
        zero_wav = folder / "Accent.wav"
        zero_wav.write_bytes(b"")  # 0 bytes
        voice = Voice(folder_name="BELL - Classic Bell", source_dir=folder)
        voice.files[Role.ACCENT] = VoiceFile(role=Role.ACCENT, source_path=zero_wav)
        result = validate([voice])
        size_errors = [i for i in result.errors if "empty" in i.message.lower() or "0 bytes" in i.message]
        assert len(size_errors) == 1


class TestValidateWarnings:
    def test_non_standard_folder_name_is_warning(self, source_dir: Path):
        voice = _make_voice("NakedName", source_dir)
        result = validate([voice])
        pattern_warnings = [i for i in result.warnings if "CODE - Description" in i.message]
        assert len(pattern_warnings) == 1

    def test_standard_folder_name_no_warning(self, source_dir: Path):
        voice = _make_voice("BELL - Classic Bell", source_dir)
        result = validate([voice])
        pattern_warnings = [i for i in result.warnings if "CODE - Description" in i.message]
        assert len(pattern_warnings) == 0

    def test_extra_wav_file_is_warning(self, source_dir: Path):
        voice = _make_voice("BELL - Classic Bell", source_dir)
        extra = voice.source_dir / "Metronome.wav"
        make_minimal_wav(extra)
        result = validate([voice])
        extra_warnings = [i for i in result.warnings if "Extra file" in i.message]
        assert len(extra_warnings) == 1

    def test_existing_output_folder_is_warning(self, source_dir: Path, output_dir: Path):
        voice = _make_voice("BELL - Classic Bell", source_dir)
        (output_dir / voice.slug).mkdir()
        result = validate([voice], output_dir=output_dir, overwrite=False)
        exist_warnings = [i for i in result.warnings if "already exists" in i.message]
        assert len(exist_warnings) == 1

    def test_force_suppresses_existing_folder_warning(self, source_dir: Path, output_dir: Path):
        voice = _make_voice("BELL - Classic Bell", source_dir)
        (output_dir / voice.slug).mkdir()
        result = validate([voice], output_dir=output_dir, overwrite=True)
        exist_warnings = [i for i in result.warnings if "already exists" in i.message]
        assert len(exist_warnings) == 0


class TestValidateInfo:
    def test_info_contains_discovery_count(self, source_dir: Path):
        v1 = _make_voice("BELL - Classic Bell", source_dir)
        v2 = _make_voice("A1 - MPC x Ableton", source_dir)
        result = validate([v1, v2])
        info_msgs = [i.message for i in result.infos]
        assert any("2 voice folder(s)" in m for m in info_msgs)
