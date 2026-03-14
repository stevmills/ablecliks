"""Structured output formatting for the CLI.

All report functions write to stdout. Log messages go through the logging
module. This separation means report output is always parseable/greppable
even when verbose logging is enabled.
"""

from __future__ import annotations

from pathlib import Path

from cliks.assembler import AssembleResult
from cliks.builder import BuildResult
from cliks.models import ALL_ROLES, Voice
from cliks.patcher import PatchResult
from cliks.validator import Severity, ValidationResult

_COL = 28  # column width for aligned output


def print_scan(voices: list[Voice], source_dir: Path) -> None:
    """Print a table of discovered voices and their role completeness.

    Example output::

        Source: samples/
        75 voice folder(s) found.

        SLUG                         FOLDER                        ACCENT  4THS  8THS  16THS
        bell-classic-bell            BELL - Classic Bell              ✓      ✓     ✓     ✓
        a1-mpc-x-ableton             A1 - MPC x Ableton               ✓      ✗     ✗     ✗
    """
    print(f"\nSource: {source_dir}")
    print(f"{len(voices)} voice folder(s) found.\n")

    header = f"{'SLUG':<{_COL}} {'FOLDER':<{_COL}} " + "  ".join(
        r.value.upper().ljust(6) for r in ALL_ROLES
    )
    print(header)
    print("-" * len(header))

    for voice in voices:
        role_cols = "  ".join(
            ("✓" if role in voice.files else "✗").ljust(6) for role in ALL_ROLES
        )
        print(f"{voice.slug:<{_COL}} {voice.folder_name:<{_COL}} {role_cols}")

    print()


def print_validation(result: ValidationResult) -> None:
    """Print all validation issues grouped by severity."""
    if not result.issues:
        print("No issues found.")
        return

    for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
        matching = [i for i in result.issues if i.severity == severity]
        if not matching:
            continue
        print(f"\n{severity.value}S ({len(matching)}):")
        for issue in matching:
            print(f"  {issue}")

    print()
    status = "FAIL" if result.has_errors else "OK"
    error_count = len(result.errors)
    warn_count = len(result.warnings)
    print(f"Result: {status}  |  {error_count} error(s), {warn_count} warning(s)")
    print()


def print_assemble(result: AssembleResult, dry_run: bool = False) -> None:
    """Print a summary of the assemble operation."""
    mode = " [dry-run]" if dry_run else ""
    if result.success:
        print(f"\nAssemble{mode} complete:")
        print(f"  Voices: {result.voice_count}")
        print(f"  Output: {result.output_path}")
    else:
        print(f"\nAssemble{mode} failed: {result.error}")
    print()


def print_patch(results: list[PatchResult], dry_run: bool = False) -> None:
    """Print a summary of the patch operation."""
    mode = " [dry-run]" if dry_run else ""
    succeeded = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    print(f"\nPatch{mode} complete:")
    print(f"  Generated: {len(succeeded)}")
    print(f"  Failed:    {len(failed)}")

    if failed:
        print("\nFailed:")
        for r in failed:
            print(f"  {r.slug}: {r.error}")

    print()


def print_build(result: BuildResult, dry_run: bool = False) -> None:
    """Print a summary of the build operation."""
    mode = " [dry-run]" if dry_run else ""
    print(f"\nBuild{mode} complete:")
    print(f"  Built:   {len(result.built)}")
    print(f"  Skipped: {len(result.skipped)}")
    print(f"  Failed:  {len(result.failed)}")

    if result.failed:
        print("\nFailed voices:")
        for slug in result.failed:
            print(f"  {slug}")

    print()
