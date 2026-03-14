"""Voice discovery: scan a source directory for voice folders.

The scanner is a pure function from a filesystem path to a list of Voice
objects. It performs no validation beyond what is necessary to construct
the model -- missing roles are recorded, not rejected, so the validator
can produce complete error reports.

Convention:
  source_dir/
    VOICE_NAME/
      Accent.wav   (case-insensitive match)
      4ths.wav
      8ths.wav
      16ths.wav

Non-WAV files (e.g. .asd, :Zone.Identifier) are silently ignored at scan time.
WAV files that don't match a role are recorded as extra_files (reported by validator).
"""

from __future__ import annotations

import logging
from pathlib import Path

from cliks.models import Role, Voice, VoiceFile

log = logging.getLogger(__name__)


def scan_source_dir(source_dir: Path) -> list[Voice]:
    """Discover all voice folders under source_dir.

    Each immediate subdirectory is treated as a potential voice. Files are
    matched to roles by their stem (case-insensitive). Subdirectories are
    not recursed into.

    Returns a list of Voice objects (may be incomplete; validator checks completeness).

    Raises FileNotFoundError if source_dir does not exist.
    Raises NotADirectoryError if source_dir is not a directory.

    Example:
        >>> voices = scan_source_dir(Path("samples"))
        >>> voices[0].folder_name
        'BELL - Classic Bell'
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

    voices: list[Voice] = []

    candidates = sorted(
        (p for p in source_dir.iterdir() if p.is_dir()),
        key=lambda p: p.name,
    )

    log.debug("Scanning %d subdirectories in %s", len(candidates), source_dir)

    for folder in candidates:
        voice = _scan_voice_folder(folder)
        voices.append(voice)
        log.debug(
            "Found voice '%s': %d/%d roles present",
            voice.folder_name,
            len(voice.files),
            4,
        )

    log.info("Scan complete: %d voice folders found in %s", len(voices), source_dir)
    return voices


def _scan_voice_folder(folder: Path) -> Voice:
    """Build a Voice from a single folder, matching WAV files to roles.

    Files with extensions other than .wav are skipped entirely.
    """
    voice = Voice(folder_name=folder.name, source_dir=folder)

    wav_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".wav"]

    for wav in wav_files:
        role = Role.from_filename(wav.name)
        if role is not None:
            voice.files[role] = VoiceFile(role=role, source_path=wav)
            log.debug("  Matched %s -> %s", wav.name, role.value)
        else:
            log.debug("  Unmatched WAV (not a role file): %s", wav.name)

    return voice
