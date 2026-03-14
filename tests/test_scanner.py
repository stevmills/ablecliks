"""Tests for scanner.py: voice folder discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from cliks.models import Role
from cliks.scanner import scan_source_dir
from tests.helpers import make_minimal_wav


class TestScanSourceDir:
    def test_discovers_complete_voice(self, complete_voice_dir: Path, source_dir: Path):
        voices = scan_source_dir(source_dir)
        assert len(voices) == 1
        assert voices[0].folder_name == "BELL - Classic Bell"
        assert voices[0].is_complete

    def test_discovers_incomplete_voice(self, incomplete_voice_dir: Path, source_dir: Path):
        voices = scan_source_dir(source_dir)
        assert len(voices) == 1
        assert not voices[0].is_complete
        assert Role.ACCENT in voices[0].files
        assert Role.FOURTHS in voices[0].files
        assert Role.EIGHTHS not in voices[0].files

    def test_multiple_voices_returned_sorted(self, source_dir: Path):
        for name in ["Z - Zeta", "A - Alpha", "M - Middle"]:
            d = source_dir / name
            d.mkdir()
        voices = scan_source_dir(source_dir)
        assert [v.folder_name for v in voices] == ["A - Alpha", "M - Middle", "Z - Zeta"]

    def test_case_insensitive_role_matching(self, source_dir: Path):
        folder = source_dir / "TEST - Case"
        folder.mkdir()
        make_minimal_wav(folder / "ACCENT.WAV")
        make_minimal_wav(folder / "4THS.WAV")
        make_minimal_wav(folder / "8THS.WAV")
        make_minimal_wav(folder / "16THS.WAV")
        voices = scan_source_dir(source_dir)
        assert voices[0].is_complete

    def test_non_wav_files_ignored(self, source_dir: Path):
        folder = source_dir / "TICK - Tick Track"
        folder.mkdir()
        make_minimal_wav(folder / "Accent.wav")
        (folder / "Accent.wav.asd").write_bytes(b"fake asd")
        (folder / "Accent.wav:Zone.Identifier").write_text("fake zone")
        voices = scan_source_dir(source_dir)
        assert len(voices[0].files) == 1

    def test_extra_wav_files_not_in_files_dict(self, source_dir: Path):
        folder = source_dir / "TICK - Tick Track"
        folder.mkdir()
        make_minimal_wav(folder / "Accent.wav")
        make_minimal_wav(folder / "Metronome.wav")  # extra file
        voices = scan_source_dir(source_dir)
        assert len(voices[0].files) == 1  # only Accent matched
        assert len(voices[0].extra_files) == 1

    def test_empty_source_dir_returns_empty_list(self, source_dir: Path):
        voices = scan_source_dir(source_dir)
        assert voices == []

    def test_missing_source_dir_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            scan_source_dir(tmp_path / "nonexistent")

    def test_file_as_source_dir_raises(self, tmp_path: Path):
        f = tmp_path / "not_a_dir.txt"
        f.write_text("hello")
        with pytest.raises(NotADirectoryError):
            scan_source_dir(f)
