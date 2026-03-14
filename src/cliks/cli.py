"""CLI entry point for cliks.

Subcommands:
  scan      -- List discovered voices and their role completeness.
  validate  -- Run validation rules and report all issues.
  build     -- Validate then build voice packs to output_dir.
  report    -- Alias for validate with pretty-printed output.

Global flags:
  --config <path>   Path to cliks.toml (default: auto-discovered)
  --verbose / -v    Enable DEBUG logging
  --dry-run         (build only) Log planned operations without writing
  --force           (build only) Overwrite existing output folders

Exit codes:
  0  Success
  1  Validation errors found (build blocked)
  2  Runtime / system error
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from cliks import __version__
from cliks.assembler import assemble_rack
from cliks.builder import build_all
from cliks.config import CliksConfig, bundled_template_path
from cliks.models import ConfigError
from cliks.patcher import patch_all
from cliks.paths import resolve_output_dir, resolve_source_dir, to_windows_path
from cliks.report import print_assemble, print_build, print_patch, print_scan, print_validation
from cliks.scanner import scan_source_dir
from cliks.validator import validate

log = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cliks",
        description="Convert raw WAV files into standardized Ableton Drum Rack voice packs.",
    )
    parser.add_argument("--version", action="version", version=f"cliks {__version__}")
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to cliks.toml (default: auto-discovered from cwd upward)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # --- scan ---
    scan_p = sub.add_parser("scan", help="List discovered voices and role completeness")
    scan_p.add_argument(
        "source_dir",
        nargs="?",
        metavar="SOURCE_DIR",
        help="Directory containing voice folders (overrides config)",
    )

    # --- validate ---
    val_p = sub.add_parser("validate", help="Run validation rules and report issues")
    val_p.add_argument(
        "source_dir",
        nargs="?",
        metavar="SOURCE_DIR",
        help="Directory containing voice folders (overrides config)",
    )
    val_p.add_argument(
        "--output-dir",
        metavar="OUTPUT_DIR",
        help="Output directory to check for write access and existing folders",
    )

    # --- report (alias for validate with same options) ---
    rep_p = sub.add_parser("report", help="Pretty-print validation report (alias for validate)")
    rep_p.add_argument("source_dir", nargs="?", metavar="SOURCE_DIR")
    rep_p.add_argument("--output-dir", metavar="OUTPUT_DIR")

    # --- assemble ---
    asm_p = sub.add_parser(
        "assemble",
        help="Assemble a parent Instrument Rack .adg containing all voices",
    )
    asm_p.add_argument(
        "--output",
        metavar="PATH",
        help="Path for the assembled .adg file (default: presets_dir/CLIKS.adg)",
    )
    asm_p.add_argument(
        "--source-dir",
        metavar="PATH",
        help="Source directory of voice folders (overrides config)",
    )
    asm_p.add_argument(
        "--voice-pack-root",
        metavar="WIN_PATH",
        help="Windows path to VoicePacks root (overrides config)",
    )
    asm_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without writing any files",
    )

    # --- patch ---
    patch_p = sub.add_parser(
        "patch",
        help="Generate Ableton .adg presets from built voice packs",
    )
    patch_p.add_argument(
        "--template",
        metavar="PATH",
        help="Path to the .adg template file (overrides config)",
    )
    patch_p.add_argument(
        "--presets-dir",
        metavar="PATH",
        help="Directory to write .adg presets into (overrides config)",
    )
    patch_p.add_argument(
        "--voice-pack-root",
        metavar="WIN_PATH",
        help="Windows path to VoicePacks root, e.g. C:\\Users\\...\\VoicePacks (overrides config)",
    )
    patch_p.add_argument(
        "--source-dir",
        metavar="PATH",
        help="Source directory of voice folders (overrides config)",
    )
    patch_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without writing any files",
    )

    # --- build ---
    build_p = sub.add_parser("build", help="Build voice packs from source to output directory")
    build_p.add_argument(
        "source_dir",
        nargs="?",
        metavar="SOURCE_DIR",
        help="Directory containing voice folders (overrides config)",
    )
    build_p.add_argument(
        "output_dir",
        nargs="?",
        metavar="OUTPUT_DIR",
        help="Root output directory for voice packs (overrides config)",
    )
    build_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing any files",
    )
    build_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output voice folders",
    )

    return parser


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(levelname)s %(name)s: %(message)s",
        level=level,
        stream=sys.stderr,
    )


def _load_config(args: argparse.Namespace) -> CliksConfig:
    config_path = Path(args.config).expanduser() if args.config else None
    if config_path:
        return CliksConfig.load(config_path)
    return CliksConfig.find_and_load()


def _resolve_source(args: argparse.Namespace, cfg: CliksConfig) -> Path:
    raw = getattr(args, "source_dir", None) or cfg.paths.source_dir
    if not raw:
        print("Error: source_dir is required (pass as argument or set in cliks.toml)", file=sys.stderr)
        sys.exit(2)
    return resolve_source_dir(raw)


def _resolve_output(args: argparse.Namespace, cfg: CliksConfig) -> Path | None:
    raw = getattr(args, "output_dir", None) or cfg.paths.output_dir
    if not raw:
        return None
    return resolve_output_dir(raw)


def _resolve_win_root(args: argparse.Namespace, cfg: CliksConfig) -> str | None:
    """Resolve the Windows VoicePacks root path from args, config, or output_dir."""
    win_root = getattr(args, "voice_pack_root", None) or cfg.patch.voice_pack_windows_root
    if not win_root:
        output_raw = cfg.paths.output_dir
        if output_raw:
            output_path = resolve_output_dir(output_raw)
            win_root = to_windows_path(output_path)
    return win_root


def cmd_assemble(args: argparse.Namespace, cfg: CliksConfig) -> int:
    source_raw = getattr(args, "source_dir", None) or cfg.paths.source_dir
    if not source_raw:
        print("Error: source_dir required for assemble.", file=sys.stderr)
        return 2
    source_dir = resolve_source_dir(source_raw)

    win_root = _resolve_win_root(args, cfg)
    if not win_root:
        print(
            "Error: Cannot determine Windows path for voice packs.\n"
            "Set patch.voice_pack_windows_root in cliks.toml or pass --voice-pack-root.",
            file=sys.stderr,
        )
        return 2

    # Default output path
    output_raw = getattr(args, "output", None)
    if output_raw:
        output_path = Path(output_raw).expanduser().resolve()
    else:
        presets_raw = cfg.patch.presets_dir
        if presets_raw:
            output_path = Path(presets_raw).expanduser().resolve() / "CLIKS.adg"
        else:
            print(
                "Error: --output or patch.presets_dir required for assemble.",
                file=sys.stderr,
            )
            return 2

    dry_run = args.dry_run
    voices = scan_source_dir(source_dir)

    result = assemble_rack(
        voices,
        voice_pack_windows_root=str(win_root),
        output_path=output_path,
        dry_run=dry_run,
    )

    print_assemble(result, dry_run=dry_run)
    return 0 if result.success else 1


def cmd_patch(args: argparse.Namespace, cfg: CliksConfig) -> int:
    # Resolve template path (falls back to bundled template)
    template_raw = getattr(args, "template", None) or cfg.patch.template
    if template_raw:
        template_path = Path(template_raw).expanduser().resolve()
    else:
        template_path = bundled_template_path()
    if not template_path.exists():
        print(f"Error: template file not found: {template_path}", file=sys.stderr)
        return 2

    # Resolve presets output dir
    presets_raw = getattr(args, "presets_dir", None) or cfg.patch.presets_dir
    if not presets_raw:
        print(
            "Error: patch.presets_dir is required.\n"
            "Set it in cliks.toml [patch] section or pass --presets-dir PATH.",
            file=sys.stderr,
        )
        return 2
    presets_dir = Path(presets_raw).expanduser().resolve()

    # Resolve Windows voice pack root (for paths inside the .adg XML)
    win_root = _resolve_win_root(args, cfg)
    if not win_root:
        print(
            "Error: Cannot determine Windows path for voice packs.\n"
            "Set patch.voice_pack_windows_root in cliks.toml or pass --voice-pack-root.",
            file=sys.stderr,
        )
        return 2

    # Resolve source dir for scanning voices
    source_raw = getattr(args, "source_dir", None) or cfg.paths.source_dir
    source_dir = resolve_source_dir(source_raw) if source_raw else None
    if source_dir is None:
        print("Error: source_dir required for patch.", file=sys.stderr)
        return 2

    dry_run = args.dry_run
    voices = scan_source_dir(source_dir)
    complete = [v for v in voices if v.is_complete]

    log.info("Patching %d voice(s) -> %s", len(complete), presets_dir)

    results = patch_all(
        complete,
        template_path=template_path,
        output_dir=presets_dir,
        voice_pack_windows_root=str(win_root),
        dry_run=dry_run,
    )

    print_patch(results, dry_run=dry_run)

    failed = [r for r in results if not r.success]
    return 1 if failed else 0


def cmd_scan(args: argparse.Namespace, cfg: CliksConfig) -> int:
    source_dir = _resolve_source(args, cfg)
    voices = scan_source_dir(source_dir)
    print_scan(voices, source_dir)
    return 0


def cmd_validate(args: argparse.Namespace, cfg: CliksConfig) -> int:
    source_dir = _resolve_source(args, cfg)
    output_dir = _resolve_output(args, cfg)
    voices = scan_source_dir(source_dir)
    result = validate(voices, output_dir=output_dir)
    print_validation(result)
    return 1 if result.has_errors else 0


def cmd_build(args: argparse.Namespace, cfg: CliksConfig) -> int:
    source_dir = _resolve_source(args, cfg)
    output_dir = _resolve_output(args, cfg)

    if output_dir is None:
        print(
            "Error: output_dir is required for build "
            "(pass as argument or set [paths] output_dir in cliks.toml)",
            file=sys.stderr,
        )
        return 2

    overwrite = args.force or cfg.build.overwrite
    dry_run = args.dry_run

    voices = scan_source_dir(source_dir)
    result = validate(voices, output_dir=output_dir, overwrite=overwrite)
    print_validation(result)

    if result.has_errors:
        print("Build aborted: fix errors above before building.", file=sys.stderr)
        return 1

    build_result = build_all(voices, output_dir, overwrite=overwrite, dry_run=dry_run)
    print_build(build_result, dry_run=dry_run)

    return 0 if build_result.success else 1


def main(argv: list[str] | None = None) -> None:
    """Main entry point. Parses args, loads config, dispatches subcommand."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    try:
        cfg = _load_config(args)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(2)

    dispatch = {
        "scan": cmd_scan,
        "validate": cmd_validate,
        "report": cmd_validate,
        "build": cmd_build,
        "patch": cmd_patch,
        "assemble": cmd_assemble,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(2)

    try:
        exit_code = handler(args, cfg)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        log.debug("Unhandled exception", exc_info=True)
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)

    sys.exit(exit_code)
