"""Voice pack builder: copy and rename WAV files, write manifest.

The builder is the only module (besides cli.py) that performs filesystem writes.
It validates first and refuses to build if any errors are present, unless the
caller explicitly filters to complete voices only.

Design:
  - All-or-nothing: voices are built only after full validation passes.
  - Dry-run support: when dry_run=True, log what would happen but write nothing.
  - shutil.copy2 preserves file metadata (timestamps, etc.).
  - Output folder is created with exist_ok=True when overwrite=True.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from cliks.manifest import build_manifest, write_manifest
from cliks.models import ALL_ROLES, BuildError, Voice

log = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Summary of a build operation."""

    built: list[str] = None  # slugs successfully built
    skipped: list[str] = None  # slugs skipped (incomplete)
    failed: list[str] = None  # slugs that encountered a build error

    def __post_init__(self) -> None:
        if self.built is None:
            self.built = []
        if self.skipped is None:
            self.skipped = []
        if self.failed is None:
            self.failed = []

    @property
    def success(self) -> bool:
        return len(self.failed) == 0


def build_all(
    voices: list[Voice],
    output_dir: Path,
    overwrite: bool = False,
    dry_run: bool = False,
) -> BuildResult:
    """Build voice packs for all complete voices.

    Incomplete voices (missing roles) are skipped without error.
    A BuildError is raised immediately if a system-level failure occurs
    (e.g. permission denied, disk full).

    Args:
        voices:     List of Voice objects from the scanner.
        output_dir: Root output directory. Voice subfolders are created inside.
        overwrite:  If True, existing voice output folders are deleted and rebuilt.
        dry_run:    If True, log planned operations but write nothing.

    Returns a BuildResult summarizing what happened.

    Example:
        >>> result = build_all(voices, Path("/mnt/c/VoicePacks"), dry_run=True)
        >>> result.built
        []
    """
    result = BuildResult()

    complete = [v for v in voices if v.is_complete]
    incomplete = [v for v in voices if not v.is_complete]

    for voice in incomplete:
        log.warning("Skipping '%s': missing roles %s", voice.slug, voice.missing_roles)
        result.skipped.append(voice.slug)

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    for voice in complete:
        try:
            _build_voice(voice, output_dir, overwrite=overwrite, dry_run=dry_run)
            result.built.append(voice.slug)
        except BuildError as e:
            log.error("Failed to build '%s': %s", voice.slug, e)
            result.failed.append(voice.slug)

    return result


def _build_voice(
    voice: Voice,
    output_dir: Path,
    overwrite: bool,
    dry_run: bool,
) -> None:
    """Build a single voice pack directory.

    Steps:
      1. Prepare output folder (create or clear if overwrite).
      2. Copy and rename each role WAV.
      3. Write manifest.json.
    """
    slug = voice.slug
    out_dir = output_dir / slug

    if out_dir.exists():
        if overwrite:
            if dry_run:
                log.info("[dry-run] Would remove existing: %s", out_dir)
            else:
                log.debug("Removing existing output folder: %s", out_dir)
                shutil.rmtree(out_dir)
        else:
            # Validator should have warned; builder proceeds to avoid surprises.
            log.debug("Output folder exists, writing into it (use --force to clean first): %s", out_dir)

    if dry_run:
        log.info("[dry-run] Would create: %s", out_dir)
    else:
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise BuildError(message=f"Cannot create output directory {out_dir}: {e}") from e

    for role in ALL_ROLES:
        vf = voice.files[role]
        dest_name = vf.output_filename(slug)
        dest_path = out_dir / dest_name

        if dry_run:
            log.info("[dry-run] Would copy: %s -> %s", vf.source_path, dest_path)
        else:
            log.debug("Copying: %s -> %s", vf.source_path.name, dest_path.name)
            try:
                shutil.copy2(vf.source_path, dest_path)
            except OSError as e:
                raise BuildError(
                    message=f"Failed to copy {vf.source_path} to {dest_path}: {e}"
                ) from e

    manifest = build_manifest(voice, out_dir)
    if dry_run:
        log.info("[dry-run] Would write: %s/manifest.json", out_dir)
    else:
        try:
            written = write_manifest(manifest, out_dir)
            log.debug("Wrote manifest: %s", written)
        except OSError as e:
            raise BuildError(message=f"Failed to write manifest for '{slug}': {e}") from e

    log.info("Built voice pack: %s", slug)
