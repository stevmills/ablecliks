"""Bootstrap a demo source directory from the existing 2-file sample packs.

Maps the two legacy filenames to the 4 expected role files:
  MetronomeUp.wav -> Accent.wav  (accented downbeat)
  Metronome.wav   -> 4ths.wav    (plain beat)
  Metronome.wav   -> 8ths.wav    (copy; pitch shifted via rack, not this tool)
  Metronome.wav   -> 16ths.wav   (copy; pitch shifted via rack, not this tool)

Usage:
  python scripts/bootstrap_demo.py [--source samples] [--dest samples-demo] [--voices N]

This is a one-time migration helper for the legacy 2-file format.
Future voices should already have 4 distinct files per the convention.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


LEGACY_ACCENT = "MetronomeUp.wav"
LEGACY_BEAT = "Metronome.wav"

ROLE_MAP = {
    "Accent.wav": LEGACY_ACCENT,
    "4ths.wav": LEGACY_BEAT,
    "8ths.wav": LEGACY_BEAT,
    "16ths.wav": LEGACY_BEAT,
}


def bootstrap(source_dir: Path, dest_dir: Path, max_voices: int | None = None) -> None:
    voice_folders = sorted(
        (p for p in source_dir.iterdir() if p.is_dir()),
        key=lambda p: p.name,
    )
    if max_voices is not None:
        voice_folders = voice_folders[:max_voices]

    dest_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    skipped = 0

    for folder in voice_folders:
        accent_src = folder / LEGACY_ACCENT
        beat_src = folder / LEGACY_BEAT

        if not accent_src.exists() or not beat_src.exists():
            print(f"  SKIP (missing legacy files): {folder.name}", file=sys.stderr)
            skipped += 1
            continue

        out_folder = dest_dir / folder.name
        out_folder.mkdir(exist_ok=True)

        for dest_name, src_file in ROLE_MAP.items():
            src = folder / src_file
            dst = out_folder / dest_name
            shutil.copy2(src, dst)

        print(f"  OK  {folder.name}")
        created += 1

    print(f"\nBootstrap complete: {created} voice(s) prepared, {skipped} skipped.")
    print(f"Output: {dest_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="samples", help="Source directory (default: samples)")
    parser.add_argument("--dest", default="samples-demo", help="Output directory (default: samples-demo)")
    parser.add_argument("--voices", type=int, default=None, help="Max voices to bootstrap (default: all)")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    source_dir = (repo_root / args.source).resolve()
    dest_dir = (repo_root / args.dest).resolve()

    if not source_dir.exists():
        print(f"Error: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Bootstrapping demo voices from: {source_dir}")
    print(f"Output to: {dest_dir}\n")
    bootstrap(source_dir, dest_dir, max_voices=args.voices)


if __name__ == "__main__":
    main()
