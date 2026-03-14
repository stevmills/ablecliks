"""Tests for builder.py and manifest.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cliks.builder import build_all
from cliks.manifest import MANIFEST_FILENAME, SCHEMA_VERSION, build_manifest
from cliks.models import ALL_ROLES, Role


class TestBuildAll:
    def test_builds_complete_voice(self, complete_voice, output_dir: Path):
        result = build_all([complete_voice], output_dir)
        assert result.success
        assert "bell-classic-bell" in result.built

    def test_output_folder_created(self, complete_voice, output_dir: Path):
        build_all([complete_voice], output_dir)
        assert (output_dir / "bell-classic-bell").is_dir()

    def test_all_role_files_copied(self, complete_voice, output_dir: Path):
        build_all([complete_voice], output_dir)
        out = output_dir / "bell-classic-bell"
        expected = [
            "bell-classic-bell_accent.wav",
            "bell-classic-bell_4ths.wav",
            "bell-classic-bell_8ths.wav",
            "bell-classic-bell_16ths.wav",
        ]
        for name in expected:
            assert (out / name).exists(), f"Missing: {name}"

    def test_manifest_written(self, complete_voice, output_dir: Path):
        build_all([complete_voice], output_dir)
        manifest_path = output_dir / "bell-classic-bell" / MANIFEST_FILENAME
        assert manifest_path.exists()

    def test_manifest_content(self, complete_voice, output_dir: Path):
        build_all([complete_voice], output_dir)
        manifest_path = output_dir / "bell-classic-bell" / MANIFEST_FILENAME
        data = json.loads(manifest_path.read_text())
        assert data["schema_version"] == SCHEMA_VERSION
        assert data["voice"]["slug"] == "bell-classic-bell"
        assert data["voice"]["code"] == "BELL"
        assert data["voice"]["name"] == "Classic Bell"
        for role in ALL_ROLES:
            assert role.value in data["roles"]
            assert data["roles"][role.value]["filename"] is not None

    def test_incomplete_voice_skipped(self, incomplete_voice_dir: Path, output_dir: Path):
        from cliks.scanner import scan_source_dir

        voices = scan_source_dir(incomplete_voice_dir.parent)
        result = build_all(voices, output_dir)
        assert len(result.skipped) == 1
        assert len(result.built) == 0

    def test_dry_run_writes_nothing(self, complete_voice, output_dir: Path):
        result = build_all([complete_voice], output_dir, dry_run=True)
        assert result.built == ["bell-classic-bell"]
        assert not (output_dir / "bell-classic-bell").exists()

    def test_overwrite_replaces_existing(self, complete_voice, output_dir: Path):
        build_all([complete_voice], output_dir)
        stale_file = output_dir / "bell-classic-bell" / "stale.txt"
        stale_file.write_text("old")
        build_all([complete_voice], output_dir, overwrite=True)
        assert not stale_file.exists()

    def test_source_files_not_modified(self, complete_voice, output_dir: Path):
        source_paths = {role: vf.source_path for role, vf in complete_voice.files.items()}
        original_sizes = {role: p.stat().st_size for role, p in source_paths.items()}
        build_all([complete_voice], output_dir)
        for role, path in source_paths.items():
            assert path.stat().st_size == original_sizes[role]


class TestBuildManifest:
    def test_windows_path_set_for_mnt_path(self, complete_voice):
        fake_output = Path("/mnt/c/Users/testuser/VoicePacks/bell-classic-bell")
        manifest = build_manifest(complete_voice, fake_output)
        assert manifest["windows_path"] == "C:\\Users\\testuser\\VoicePacks\\bell-classic-bell"

    def test_windows_path_none_for_linux_path(self, complete_voice, output_dir: Path):
        manifest = build_manifest(complete_voice, output_dir / "bell-classic-bell")
        assert manifest["windows_path"] is None

    def test_built_from_is_source_dir(self, complete_voice, output_dir: Path):
        manifest = build_manifest(complete_voice, output_dir / "bell-classic-bell")
        assert manifest["built_from"] == str(complete_voice.source_dir)

    def test_schema_version_present(self, complete_voice, output_dir: Path):
        manifest = build_manifest(complete_voice, output_dir / "bell-classic-bell")
        assert manifest["schema_version"] == SCHEMA_VERSION
