"""Validation rules engine for voice packs.

validate() is a pure function: it takes a list of Voice objects and an
optional output Path, and returns a ValidationResult with typed issues.

Error levels:
  ERROR   -- blocks the build
  WARNING -- reported but does not block
  INFO    -- informational only

Errors:
  - Missing required role file(s)
  - Slug collision between two voices
  - WAV file is zero bytes (likely corrupt)
  - Output directory is not writable (only checked when output_dir is given)

Warnings:
  - Extra WAV files in voice folder (don't match any role)
  - Voice folder doesn't follow 'CODE - Description' naming pattern
  - Output voice folder already exists (and overwrite is False)

Info:
  - Total voices discovered
  - Incomplete voices (will be skipped)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from cliks.models import ALL_ROLES, Voice

log = logging.getLogger(__name__)


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Issue:
    """A single validation issue associated with a voice (or global)."""

    severity: Severity
    message: str
    voice_slug: str | None = None  # None means global/cross-voice issue

    def __str__(self) -> str:
        prefix = f"[{self.severity.value}]"
        context = f" ({self.voice_slug})" if self.voice_slug else ""
        return f"{prefix}{context} {self.message}"


@dataclass
class ValidationResult:
    """The outcome of running validate() on a set of voices."""

    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def infos(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.INFO]

    @property
    def has_errors(self) -> bool:
        return any(i.severity == Severity.ERROR for i in self.issues)

    @property
    def is_valid(self) -> bool:
        return not self.has_errors

    def add(
        self,
        severity: Severity,
        message: str,
        voice_slug: str | None = None,
    ) -> None:
        self.issues.append(Issue(severity=severity, message=message, voice_slug=voice_slug))


def validate(
    voices: list[Voice],
    output_dir: Path | None = None,
    overwrite: bool = False,
) -> ValidationResult:
    """Run all validation rules against a list of Voice objects.

    Args:
        voices:     Voices discovered by the scanner.
        output_dir: If provided, check writability and existing-folder conflicts.
        overwrite:  If True, existing output folders are not flagged as warnings.

    Returns a ValidationResult containing all issues found.

    Example:
        >>> result = validate(voices, output_dir=Path("/mnt/c/VoicePacks"))
        >>> result.is_valid
        True
    """
    result = ValidationResult()

    result.add(Severity.INFO, f"{len(voices)} voice folder(s) discovered")

    _check_slug_collisions(voices, result)
    _check_output_dir(output_dir, result)

    for voice in voices:
        _check_voice(voice, result, output_dir=output_dir, overwrite=overwrite)

    incomplete = [v for v in voices if not v.is_complete]
    if incomplete:
        result.add(
            Severity.INFO,
            f"{len(incomplete)} incomplete voice(s) will be skipped: "
            + ", ".join(v.slug for v in incomplete),
        )

    return result


def _check_slug_collisions(voices: list[Voice], result: ValidationResult) -> None:
    seen: dict[str, str] = {}
    for voice in voices:
        slug = voice.slug
        if slug in seen:
            result.add(
                Severity.ERROR,
                f"Slug collision: '{slug}' produced by both "
                f"'{seen[slug]}' and '{voice.folder_name}'",
            )
        else:
            seen[slug] = voice.folder_name


def _check_output_dir(output_dir: Path | None, result: ValidationResult) -> None:
    if output_dir is None:
        return
    if output_dir.exists() and not output_dir.is_dir():
        result.add(
            Severity.ERROR,
            f"Output path exists but is not a directory: {output_dir}",
        )
        return
    # Check writability by attempting to resolve the nearest existing ancestor.
    check_path = output_dir
    while not check_path.exists() and check_path.parent != check_path:
        check_path = check_path.parent
    if check_path.exists() and not _is_writable(check_path):
        result.add(Severity.ERROR, f"Output directory is not writable: {output_dir}")


def _is_writable(path: Path) -> bool:
    import os

    return os.access(path, os.W_OK)


def _check_voice(
    voice: Voice,
    result: ValidationResult,
    output_dir: Path | None,
    overwrite: bool,
) -> None:
    slug = voice.slug

    # Missing roles (ERROR)
    for role in voice.missing_roles:
        result.add(
            Severity.ERROR,
            f"Missing role file: expected '{role.value}.wav' (or similar casing)",
            voice_slug=slug,
        )

    # Zero-byte files (ERROR)
    for role, vf in voice.files.items():
        try:
            size = vf.source_path.stat().st_size
        except OSError:
            result.add(
                Severity.ERROR,
                f"Cannot stat file: {vf.source_path}",
                voice_slug=slug,
            )
            continue
        if size == 0:
            result.add(
                Severity.ERROR,
                f"Role file is empty (0 bytes): {vf.source_path.name}",
                voice_slug=slug,
            )

    # Extra WAV files (WARNING)
    for extra in voice.extra_files:
        result.add(
            Severity.WARNING,
            f"Extra file in voice folder (not a role file): {extra.name}",
            voice_slug=slug,
        )

    # Non-standard folder name (WARNING)
    if not voice.matches_code_pattern():
        result.add(
            Severity.WARNING,
            f"Folder name does not match 'CODE - Description' pattern: '{voice.folder_name}'",
            voice_slug=slug,
        )

    # Output folder already exists (WARNING)
    if output_dir is not None and not overwrite:
        out_voice_dir = output_dir / slug
        if out_voice_dir.exists():
            result.add(
                Severity.WARNING,
                f"Output folder already exists (use --force to overwrite): {out_voice_dir}",
                voice_slug=slug,
            )
