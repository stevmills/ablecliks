"""Tests for models.py: slugify, parse_voice_code, Role, Voice."""

from __future__ import annotations

import pytest

from cliks.models import (
    ALL_ROLES,
    Role,
    Voice,
    VoiceFile,
    parse_voice_code,
    slugify,
)
from pathlib import Path


class TestSlugify:
    def test_basic_code_description(self):
        assert slugify("BELL - Classic Bell") == "bell-classic-bell"

    def test_mpc_x_notation(self):
        assert slugify("A1 - MPC x Ableton") == "a1-mpc-x-ableton"

    def test_dj_hyphen_code(self):
        assert slugify("DJ-PN - Pioneer Rekordbox") == "dj-pn-pioneer-rekordbox"

    def test_special_chars_collapsed(self):
        assert slugify("BELL -- double  dash") == "bell-double-dash"

    def test_leading_trailing_stripped(self):
        assert slugify("  spaces  ") == "spaces"

    def test_numbers_preserved(self):
        assert slugify("BP1 - Beep") == "bp1-beep"

    def test_all_upper(self):
        assert slugify("TICK") == "tick"


class TestParseVoiceCode:
    def test_standard_pattern(self):
        code, desc = parse_voice_code("BELL - Classic Bell")
        assert code == "BELL"
        assert desc == "Classic Bell"

    def test_numeric_code(self):
        code, desc = parse_voice_code("A1 - MPC x Ableton")
        assert code == "A1"
        assert desc == "MPC x Ableton"

    def test_hyphenated_code(self):
        code, desc = parse_voice_code("DJ-PN - Pioneer Rekordbox")
        assert code == "DJ-PN"
        assert desc == "Pioneer Rekordbox"

    def test_no_separator_returns_full(self):
        code, desc = parse_voice_code("SomeFolderName")
        assert code == "SomeFolderName"
        assert desc == "SomeFolderName"


class TestRole:
    def test_from_filename_accent(self):
        assert Role.from_filename("Accent.wav") == Role.ACCENT

    def test_from_filename_case_insensitive(self):
        assert Role.from_filename("ACCENT.wav") == Role.ACCENT
        assert Role.from_filename("accent.wav") == Role.ACCENT

    def test_from_filename_4ths(self):
        assert Role.from_filename("4ths.wav") == Role.FOURTHS

    def test_from_filename_8ths(self):
        assert Role.from_filename("8ths.wav") == Role.EIGHTHS

    def test_from_filename_16ths(self):
        assert Role.from_filename("16ths.wav") == Role.SIXTEENTHS

    def test_from_filename_unknown(self):
        assert Role.from_filename("Metronome.wav") is None
        assert Role.from_filename("MetronomeUp.wav") is None
        assert Role.from_filename("click.wav") is None

    def test_from_filename_no_extension(self):
        assert Role.from_filename("Accent") == Role.ACCENT


class TestVoiceFile:
    def test_output_filename(self):
        vf = VoiceFile(role=Role.ACCENT, source_path=Path("Accent.wav"))
        assert vf.output_filename("bell-classic-bell") == "bell-classic-bell_accent.wav"

    def test_output_filename_4ths(self):
        vf = VoiceFile(role=Role.FOURTHS, source_path=Path("4ths.wav"))
        assert vf.output_filename("my-voice") == "my-voice_4ths.wav"


class TestVoice:
    def test_slug(self):
        voice = Voice(folder_name="BELL - Classic Bell", source_dir=Path("/tmp/bell"))
        assert voice.slug == "bell-classic-bell"

    def test_code(self):
        voice = Voice(folder_name="BELL - Classic Bell", source_dir=Path("/tmp/bell"))
        assert voice.code == "BELL"

    def test_description(self):
        voice = Voice(folder_name="BELL - Classic Bell", source_dir=Path("/tmp/bell"))
        assert voice.description == "Classic Bell"

    def test_is_complete_false_when_empty(self):
        voice = Voice(folder_name="BELL - Classic Bell", source_dir=Path("/tmp/bell"))
        assert not voice.is_complete

    def test_is_complete_true_when_all_roles_present(self, complete_voice: Voice):
        assert complete_voice.is_complete

    def test_missing_roles(self):
        voice = Voice(folder_name="BELL - Classic Bell", source_dir=Path("/tmp/bell"))
        voice.files[Role.ACCENT] = VoiceFile(role=Role.ACCENT, source_path=Path("Accent.wav"))
        assert Role.FOURTHS in voice.missing_roles
        assert Role.ACCENT not in voice.missing_roles

    def test_matches_code_pattern_true(self):
        voice = Voice(folder_name="BELL - Classic Bell", source_dir=Path("/tmp"))
        assert voice.matches_code_pattern()

    def test_matches_code_pattern_false(self):
        voice = Voice(folder_name="NakedName", source_dir=Path("/tmp"))
        assert not voice.matches_code_pattern()
