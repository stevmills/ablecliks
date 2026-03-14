"""Core data models for voice packs.

All models are pure dataclasses with no I/O or side effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Role(str, Enum):
    """The four rhythmic roles every voice must provide.

    Values are the canonical lowercase output suffixes used in filenames
    and manifest keys.
    """

    ACCENT = "accent"
    FOURTHS = "4ths"
    EIGHTHS = "8ths"
    SIXTEENTHS = "16ths"

    @classmethod
    def from_filename(cls, name: str) -> "Role | None":
        """Match a bare filename stem (case-insensitive) to a Role.

        Example:
            >>> Role.from_filename("Accent")
            <Role.ACCENT: 'accent'>
            >>> Role.from_filename("4ths")
            <Role.FOURTHS: '4ths'>
            >>> Role.from_filename("unknown")
        """
        stem = Path(name).stem.lower()
        mapping = {
            "accent": cls.ACCENT,
            "4ths": cls.FOURTHS,
            "8ths": cls.EIGHTHS,
            "16ths": cls.SIXTEENTHS,
        }
        return mapping.get(stem)


# Ordered list for consistent reporting and iteration.
ALL_ROLES: tuple[Role, ...] = (
    Role.ACCENT,
    Role.FOURTHS,
    Role.EIGHTHS,
    Role.SIXTEENTHS,
)

# Expected input filenames for each role (case-insensitive match used at scan time).
ROLE_INPUT_FILENAMES: dict[Role, str] = {
    Role.ACCENT: "Accent.wav",
    Role.FOURTHS: "4ths.wav",
    Role.EIGHTHS: "8ths.wav",
    Role.SIXTEENTHS: "16ths.wav",
}


def slugify(text: str, separator: str = "-") -> str:
    """Convert a folder name to a normalized slug.

    Lowercases the string, replaces non-alphanumeric runs with the separator,
    and strips leading/trailing separators.

    Example:
        >>> slugify("BELL - Classic Bell")
        'bell-classic-bell'
        >>> slugify("A1 - MPC x Ableton")
        'a1-mpc-x-ableton'
        >>> slugify("DJ-PN - Pioneer Rekordbox")
        'dj-pn-pioneer-rekordbox'
    """
    lowered = text.lower()
    # Replace any sequence of non-alphanumeric chars (except the separator) with separator.
    slug = re.sub(r"[^a-z0-9]+", separator, lowered)
    return slug.strip(separator)


def parse_voice_code(folder_name: str) -> tuple[str, str]:
    """Parse CODE and description from a folder name following 'CODE - Description' pattern.

    Returns (code, description). If the pattern is not matched, code == slugified folder_name
    and description == folder_name.

    Example:
        >>> parse_voice_code("BELL - Classic Bell")
        ('BELL', 'Classic Bell')
        >>> parse_voice_code("UnknownFormat")
        ('UnknownFormat', 'UnknownFormat')
    """
    match = re.match(r"^([A-Z0-9\-]+)\s+-\s+(.+)$", folder_name)
    if match:
        return match.group(1), match.group(2).strip()
    return folder_name, folder_name


@dataclass
class VoiceFile:
    """A single WAV file associated with a role."""

    role: Role
    source_path: Path

    def output_filename(self, slug: str) -> str:
        """Return the standardized output filename for this file.

        Example:
            >>> vf = VoiceFile(role=Role.ACCENT, source_path=Path("Accent.wav"))
            >>> vf.output_filename("bell-classic-bell")
            'bell-classic-bell_accent.wav'
        """
        return f"{slug}_{self.role.value}.wav"


@dataclass
class Voice:
    """A single named voice with its source folder and discovered role files.

    A voice may be complete (all 4 roles present) or incomplete (validation will flag).
    """

    folder_name: str
    source_dir: Path
    files: dict[Role, VoiceFile] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        """Normalized slug derived from folder_name."""
        return slugify(self.folder_name)

    @property
    def code(self) -> str:
        """Short code extracted from folder_name (e.g. 'BELL' from 'BELL - Classic Bell')."""
        code, _ = parse_voice_code(self.folder_name)
        return code

    @property
    def description(self) -> str:
        """Human-readable description from folder_name."""
        _, desc = parse_voice_code(self.folder_name)
        return desc

    @property
    def is_complete(self) -> bool:
        """True when all four roles are present."""
        return all(role in self.files for role in ALL_ROLES)

    @property
    def missing_roles(self) -> list[Role]:
        """Roles with no corresponding file."""
        return [role for role in ALL_ROLES if role not in self.files]

    @property
    def extra_files(self) -> list[Path]:
        """WAV files in source_dir that don't map to any role."""
        known = {vf.source_path for vf in self.files.values()}
        return [
            p
            for p in self.source_dir.iterdir()
            if p.suffix.lower() == ".wav" and p not in known
        ]

    def matches_code_pattern(self) -> bool:
        """True when folder_name follows the 'CODE - Description' convention."""
        code, desc = parse_voice_code(self.folder_name)
        return code != self.folder_name  # parse succeeded


@dataclass
class CliksError(Exception):
    """Base exception for all cliks errors."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class ConfigError(CliksError):
    """Raised when configuration is invalid or missing."""


@dataclass
class BuildError(CliksError):
    """Raised when a build operation fails (e.g. disk full, permission denied)."""
