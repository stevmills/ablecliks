"""Tests for paths.py: WSL/Windows path conversion."""

from __future__ import annotations

from pathlib import Path

import pytest

from cliks.paths import (
    is_windows_accessible,
    resolve_output_dir,
    resolve_source_dir,
    to_windows_path,
)


class TestToWindowsPath:
    def test_c_drive(self):
        result = to_windows_path(Path("/mnt/c/Users/testuser/Music"))
        assert result == "C:\\Users\\testuser\\Music"

    def test_d_drive(self):
        result = to_windows_path(Path("/mnt/d/Projects"))
        assert result == "D:\\Projects"

    def test_drive_root(self):
        result = to_windows_path(Path("/mnt/c"))
        assert result == "C:\\"

    def test_uppercase_drive_letter(self):
        result = to_windows_path(Path("/mnt/C/Users"))
        assert result == "C:\\Users"

    def test_non_mnt_path_returns_none(self):
        assert to_windows_path(Path("/home/testuser/dev")) is None

    def test_mnt_without_drive_returns_none(self):
        assert to_windows_path(Path("/mnt/longname/foo")) is None

    def test_root_path_returns_none(self):
        assert to_windows_path(Path("/")) is None

    def test_deeply_nested(self):
        result = to_windows_path(Path("/mnt/c/Users/testuser/Music/Ableton/VoicePacks/bell-classic-bell"))
        assert result == "C:\\Users\\testuser\\Music\\Ableton\\VoicePacks\\bell-classic-bell"

    def test_spaces_in_path(self):
        result = to_windows_path(Path("/mnt/c/Users/testuser/My Music"))
        assert result == "C:\\Users\\testuser\\My Music"


class TestIsWindowsAccessible:
    def test_mnt_path_is_accessible(self):
        assert is_windows_accessible(Path("/mnt/c/Users")) is True

    def test_home_path_is_not_accessible(self):
        assert is_windows_accessible(Path("/home/testuser")) is False


class TestResolveSourceDir:
    def test_absolute_path_unchanged(self):
        result = resolve_source_dir("/home/testuser/dev/samples")
        assert result == Path("/home/testuser/dev/samples")

    def test_relative_path_resolved_against_cwd(self, tmp_path: Path):
        result = resolve_source_dir("samples", cwd=tmp_path)
        assert result == tmp_path / "samples"

    def test_tilde_expanded(self):
        result = resolve_source_dir("~/dev")
        assert not str(result).startswith("~")
        assert result.is_absolute()
