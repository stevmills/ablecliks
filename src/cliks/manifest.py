"""Manifest schema and serialization.

The manifest.json file is the contract between the CLI and consumers
(Ableton Live file browser, future Max for Live devices).

Schema version "1.0" fields:
  schema_version  -- semver string for forward compatibility
  voice           -- identity fields: name, slug, code, source_folder
  roles           -- one entry per role with output filename
  built_at        -- ISO-8601 UTC timestamp
  built_from      -- absolute POSIX path of the source voice folder
  windows_path    -- Windows path of the output voice folder (None if not on /mnt/)

# TODO(m4l): In a future version, add audio metadata (sample_rate, bit_depth, channels)
#            to the per-role entry so M4L can validate samples before loading.
# TODO(m4l): Consider adding a rack_slot field to voice when pad mapping is implemented.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from cliks.models import ALL_ROLES, Voice
from cliks.paths import to_windows_path

SCHEMA_VERSION = "1.0"
MANIFEST_FILENAME = "manifest.json"


def build_manifest(
    voice: Voice,
    output_voice_dir: Path,
) -> dict:
    """Construct the manifest dictionary for a voice pack.

    Args:
        voice:            The Voice model (source-side).
        output_voice_dir: The absolute output directory for this voice pack.

    Returns a plain dict ready for json.dumps().

    Example:
        >>> manifest = build_manifest(voice, Path("/mnt/c/VoicePacks/bell-classic-bell"))
        >>> manifest["voice"]["slug"]
        'bell-classic-bell'
    """
    slug = voice.slug
    windows_path = to_windows_path(output_voice_dir)

    roles: dict[str, dict] = {}
    for role in ALL_ROLES:
        vf = voice.files.get(role)
        roles[role.value] = {
            "filename": vf.output_filename(slug) if vf else None,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "voice": {
            "name": voice.description,
            "slug": slug,
            "code": voice.code,
            "source_folder": voice.folder_name,
        },
        "roles": roles,
        "built_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "built_from": str(voice.source_dir),
        "windows_path": windows_path,
    }


def write_manifest(manifest: dict, output_voice_dir: Path) -> Path:
    """Write manifest.json to output_voice_dir.

    Returns the path to the written file.

    Example:
        >>> path = write_manifest(manifest, Path("/mnt/c/VoicePacks/bell-classic-bell"))
    """
    out_path = output_voice_dir / MANIFEST_FILENAME
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    return out_path
