"""Configuration loading for cliks.

Loads settings from a TOML file (cliks.toml by default) using the stdlib
tomllib module (Python 3.11+). All values are optional; CLI flags take
precedence over config file values, which take precedence over defaults.

Precedence: CLI flag > cliks.toml > hardcoded default.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from cliks.models import ConfigError


_DEFAULT_CONFIG_FILENAME = "cliks.toml"

# Bundled template .adg shipped with the repo in templates/.
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
_DEFAULT_TEMPLATE_FILENAME = "cliks-template.adg"


def bundled_template_path() -> Path:
    """Return the path to the bundled single-voice Drum Rack template."""
    return _TEMPLATES_DIR / _DEFAULT_TEMPLATE_FILENAME


@dataclass
class PathsConfig:
    source_dir: str = "samples"
    output_dir: str = ""


@dataclass
class NamingConfig:
    slug_separator: str = "-"


@dataclass
class BuildConfig:
    overwrite: bool = False


@dataclass
class PatchConfig:
    # Absolute path (WSL) to the single-voice Drum Rack template .adg.
    template: str = ""
    # Directory where generated .adg presets are written (WSL path).
    presets_dir: str = ""
    # Windows path to the VoicePacks root (for <Path> inside each preset).
    # Derived from paths.output_dir if not set explicitly.
    voice_pack_windows_root: str = ""


@dataclass
class CliksConfig:
    """Full configuration for a cliks session.

    All fields have defaults so the tool works with zero config.
    """

    paths: PathsConfig = field(default_factory=PathsConfig)
    naming: NamingConfig = field(default_factory=NamingConfig)
    build: BuildConfig = field(default_factory=BuildConfig)
    patch: PatchConfig = field(default_factory=PatchConfig)

    @classmethod
    def load(cls, config_path: Path) -> "CliksConfig":
        """Load configuration from a TOML file.

        Raises ConfigError if the file exists but cannot be parsed.
        Returns a default CliksConfig if the file does not exist.

        Example:
            >>> cfg = CliksConfig.load(Path("cliks.toml"))
        """
        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(message=f"Failed to parse config file {config_path}: {e}") from e
        except OSError as e:
            raise ConfigError(message=f"Cannot read config file {config_path}: {e}") from e

        paths_data = data.get("paths", {})
        naming_data = data.get("naming", {})
        build_data = data.get("build", {})

        patch_data = data.get("patch", {})

        return cls(
            paths=PathsConfig(
                source_dir=paths_data.get("source_dir", PathsConfig.source_dir),
                output_dir=paths_data.get("output_dir", PathsConfig.output_dir),
            ),
            naming=NamingConfig(
                slug_separator=naming_data.get("slug_separator", NamingConfig.slug_separator),
            ),
            build=BuildConfig(
                overwrite=build_data.get("overwrite", BuildConfig.overwrite),
            ),
            patch=PatchConfig(
                template=patch_data.get("template", PatchConfig.template),
                presets_dir=patch_data.get("presets_dir", PatchConfig.presets_dir),
                voice_pack_windows_root=patch_data.get(
                    "voice_pack_windows_root", PatchConfig.voice_pack_windows_root
                ),
            ),
        )

    @classmethod
    def find_and_load(cls, start_dir: Path | None = None) -> "CliksConfig":
        """Search for cliks.toml starting from start_dir (default: cwd).

        Walks up the directory tree until the file is found or the filesystem
        root is reached. Returns a default config if none is found.
        """
        directory = (start_dir or Path.cwd()).resolve()
        for candidate in [directory, *directory.parents]:
            config_file = candidate / _DEFAULT_CONFIG_FILENAME
            if config_file.exists():
                return cls.load(config_file)
        return cls()
