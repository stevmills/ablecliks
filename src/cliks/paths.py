"""WSL and Windows path conversion utilities.

All internal logic uses pathlib.Path (POSIX). Windows path conversion is a
leaf operation: it only happens when writing manifest.json for Ableton consumption.

Design constraints:
- Pure string manipulation -- no subprocess calls (no wslpath dependency).
- Returns None gracefully when the path is not Windows-accessible.
- Fully deterministic and testable.

# TODO(m4l): If M4L ever needs to call back into WSL, add wsl_to_unc() here.
"""

from __future__ import annotations

from pathlib import Path


_WSL_MOUNT_ROOT = "/mnt"
_DRIVE_LETTER_LEN = 1


def to_windows_path(posix_path: Path) -> str | None:
    """Convert a WSL /mnt/<drive>/... path to a Windows drive path.

    Returns the Windows-style path string (e.g. ``C:\\Users\\me\\Music``),
    or None if the path is not under /mnt/ with a single-letter drive component.

    This path is stored in manifest.json so that Ableton Live (on Windows)
    and future Max for Live devices can reference the file without knowing
    about WSL mount points.

    Example:
        >>> to_windows_path(Path("/mnt/c/Users/me/Music"))
        'C:\\\\Users\\\\me\\\\Music'
        >>> to_windows_path(Path("/home/me/dev/project"))
        >>> to_windows_path(Path("/mnt/c"))
        'C:\\\\'
    """
    parts = posix_path.parts
    # Expect: ('/', 'mnt', '<drive_letter>', ...)
    if (
        len(parts) >= 3
        and parts[0] == "/"
        and parts[1] == "mnt"
        and len(parts[2]) == _DRIVE_LETTER_LEN
        and parts[2].isalpha()
    ):
        drive = parts[2].upper()
        rest = "\\".join(parts[3:])
        return f"{drive}:\\{rest}"
    return None


def is_windows_accessible(path: Path) -> bool:
    """Return True when the path is under a WSL Windows mount point (/mnt/<letter>/).

    Example:
        >>> is_windows_accessible(Path("/mnt/c/Users/me"))
        True
        >>> is_windows_accessible(Path("/home/me/dev"))
        False
    """
    return to_windows_path(path) is not None


def resolve_source_dir(raw: str, cwd: Path | None = None) -> Path:
    """Resolve a source directory string to an absolute Path.

    Relative paths are resolved against cwd (defaults to Path.cwd()).
    Tildes are expanded.

    Example:
        >>> resolve_source_dir("samples", cwd=Path("/home/me/dev/ablecliks"))
        PosixPath('/home/me/dev/ablecliks/samples')
    """
    base = cwd or Path.cwd()
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = base / p
    return p.resolve()


def resolve_output_dir(raw: str, cwd: Path | None = None) -> Path:
    """Resolve an output directory string to an absolute Path.

    Same logic as resolve_source_dir; kept separate for clarity and future divergence.

    Example:
        >>> resolve_output_dir("/mnt/c/Users/me/Music/Ableton/VoicePacks")
        PosixPath('/mnt/c/Users/me/Music/Ableton/VoicePacks')
    """
    return resolve_source_dir(raw, cwd)
