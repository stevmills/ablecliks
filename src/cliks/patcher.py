"""Ableton .adg preset patcher.

Reads a template Drum Rack preset (.adg = gzip-compressed XML), replaces
the 5 Simpler sample paths with paths from a built voice pack, and writes
a new ready-to-load .adg preset.

The template is a single Drum Rack chain .adg with 5 Simpler slots:
  BLIP-ACCENT     → accent role
  BLIP-NO ACCENT  → 4ths role  (the non-accented beat, same file as 4ths)
  BLIP-4TH'S      → 4ths role
  BLIP-8TH'S      → 8ths role
  BLIP 16TH'S     → 16ths role

Strategy:
  - Parse the XML line-by-line tracking state (inside SampleRef, current slot role).
  - Replace <Path>, <RelativePath>, <RelativePathType>, <OriginalFileSize>,
    <OriginalCrc> only when inside a SampleRef block.
  - Replace chain/slot UserName strings so the preset is identifiable in Ableton.
  - Never modify the template file; always write to a new path.

# TODO(m4l): When M4L can load presets programmatically, replace this file-based
#            approach with Live API calls to set SampleRef paths directly.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from cliks.models import Role, Voice
from cliks.paths import to_windows_path

log = logging.getLogger(__name__)

# Slot UserName values in the template (cliks-template.adg).
# These are the exact strings that appear in the template XML.
_TEMPLATE_OUTER_NAME = "CLIKS-TEMPLATE"

_SLOT_ROLE_MAP: dict[str, Role] = {
    "BLIP-ACCENT":    Role.ACCENT,
    "BLIP-NO ACCENT": Role.FOURTHS,   # no-accent slot plays the plain beat (4ths)
    "BLIP-4TH'S":     Role.FOURTHS,
    "BLIP-8TH'S":     Role.EIGHTHS,
    "BLIP 16TH'S":    Role.SIXTEENTHS,
}

# Output slot names use the voice CODE prefix.
# Template slot suffix is kept (e.g. "-ACCENT", " 16TH'S").
_SLOT_SUFFIX_MAP: dict[str, str] = {
    "BLIP-ACCENT":    "-ACCENT",
    "BLIP-NO ACCENT": "-NO ACCENT",
    "BLIP-4TH'S":     "-4TH'S",
    "BLIP-8TH'S":     "-8TH'S",
    "BLIP 16TH'S":    " 16TH'S",
}


@dataclass
class PatchResult:
    slug: str
    output_path: Path
    success: bool
    error: str | None = None


def patch_voice(
    voice: Voice,
    template_path: Path,
    output_dir: Path,
    voice_pack_windows_root: str,
    dry_run: bool = False,
) -> PatchResult:
    """Generate a patched .adg preset for a single voice.

    Args:
        voice:                   The Voice to patch in.
        template_path:           Path to the single-voice Drum Rack template .adg.
        output_dir:              Directory to write the output .adg into.
        voice_pack_windows_root: Windows path to the VoicePacks root folder,
                                 e.g. ``C:\\Users\\me\\Music\\Ableton\\VoicePacks``.
                                 Used to build the <Path> value for each sample.
        dry_run:                 If True, log what would happen but write nothing.

    Returns a PatchResult with the output path and success status.
    """
    slug = voice.slug
    output_path = output_dir / f"{slug}.adg"

    try:
        xml = _read_adg(template_path)
        patched = _patch_xml(xml, voice, voice_pack_windows_root)

        if dry_run:
            log.info("[dry-run] Would write preset: %s", output_path)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            _write_adg(patched, output_path)
            log.info("Wrote preset: %s", output_path.name)

        return PatchResult(slug=slug, output_path=output_path, success=True)

    except Exception as e:
        log.error("Failed to patch '%s': %s", slug, e)
        return PatchResult(slug=slug, output_path=output_path, success=False, error=str(e))


def patch_all(
    voices: list[Voice],
    template_path: Path,
    output_dir: Path,
    voice_pack_windows_root: str,
    dry_run: bool = False,
) -> list[PatchResult]:
    """Patch all complete voices and return a list of PatchResults.

    Incomplete voices (missing roles) are skipped.
    """
    results = []
    for voice in voices:
        if not voice.is_complete:
            log.warning("Skipping incomplete voice: %s", voice.slug)
            continue
        result = patch_voice(
            voice, template_path, output_dir, voice_pack_windows_root, dry_run=dry_run
        )
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_adg(path: Path) -> str:
    """Read and decompress a .adg file, returning the XML as a string."""
    with gzip.open(path, "rb") as f:
        return f.read().decode("utf-8")


def _write_adg(xml: str, path: Path) -> None:
    """Compress and write an XML string as a .adg file."""
    with gzip.open(path, "wb") as f:
        f.write(xml.encode("utf-8"))


def _patch_xml(xml: str, voice: Voice, voice_pack_windows_root: str) -> str:
    """Apply all substitutions to the template XML and return the patched string.

    Steps:
      1. Walk lines; track SampleRef scope and current slot role.
      2. Inside SampleRef: replace Path, RelativePath, RelativePathType,
         OriginalFileSize, OriginalCrc.
      3. Replace outer chain UserName and all inner slot UserNames.
    """
    lines = xml.splitlines()
    result: list[str] = []

    in_sample_ref = False
    current_role: Role | None = None

    for line in lines:
        stripped = line.strip()

        # Track SampleRef scope
        if "<SampleRef>" in stripped:
            in_sample_ref = True
        elif "</SampleRef>" in stripped:
            in_sample_ref = False
            current_role = None

        # Detect slot role from nearest preceding UserName
        m = re.search(r'<UserName Value="([^"]+)"', line)
        if m:
            slot_name = m.group(1)
            if slot_name in _SLOT_ROLE_MAP:
                current_role = _SLOT_ROLE_MAP[slot_name]

        # Patch inside SampleRef only
        if in_sample_ref and current_role is not None:
            line = _patch_sample_ref_line(line, voice, voice_pack_windows_root, current_role)

        result.append(line)

    patched = "\n".join(result)

    # Replace outer chain name
    patched = patched.replace(
        f'UserName Value="{_TEMPLATE_OUTER_NAME}"',
        f'UserName Value="{voice.folder_name}"',
    )

    # Replace inner slot names using voice CODE
    code = voice.code
    for template_slot, suffix in _SLOT_SUFFIX_MAP.items():
        new_slot = f"{code}{suffix}"
        patched = patched.replace(
            f'UserName Value="{template_slot}"',
            f'UserName Value="{new_slot}"',
        )

    return patched


def _patch_sample_ref_line(
    line: str,
    voice: Voice,
    voice_pack_windows_root: str,
    role: Role,
) -> str:
    """Replace sample-related XML attributes on a single line within a SampleRef."""
    slug = voice.slug
    filename = f"{slug}_{role.value}.wav"

    # Build the Windows path: root\slug\filename (backslashes)
    win_path = f"{voice_pack_windows_root}\\{slug}\\{filename}"

    # Use lambda replacements to prevent re.sub from interpreting backslashes
    # in Windows paths (e.g. C:\Users) as regex escape sequences.
    if "<Path Value=" in line:
        repl = f'<Path Value="{win_path}"'
        return re.sub(r'<Path Value="[^"]*"', lambda _: repl, line)

    if "<RelativePath Value=" in line:
        return re.sub(r'<RelativePath Value="[^"]*"', lambda _: '<RelativePath Value=""', line)

    if "<RelativePathType Value=" in line:
        # 0 = absolute path (not relative to Ableton User Library)
        return re.sub(
            r'<RelativePathType Value="[^"]*"',
            lambda _: '<RelativePathType Value="0"',
            line,
        )

    if "<OriginalFileSize Value=" in line:
        return re.sub(
            r'<OriginalFileSize Value="[^"]*"',
            lambda _: '<OriginalFileSize Value="0"',
            line,
        )

    if "<OriginalCrc Value=" in line:
        return re.sub(
            r'<OriginalCrc Value="[^"]*"',
            lambda _: '<OriginalCrc Value="0"',
            line,
        )

    return line
