# cliks

A Python CLI for converting raw WAV click/percussion samples into standardized
voice packs for Ableton Live Drum Rack template workflows.

Designed for WSL development with Ableton Live on Windows. Outputs voice packs,
per-voice `.adg` presets, and a master Instrument Rack — ready to load in Ableton.

---

## Requirements

- Python 3.11+
- WSL (Ubuntu or similar) — if using a Linux/Windows split workflow
- Ableton Live (for loading the generated presets)

No third-party runtime dependencies.

---

## Quick Start

```bash
git clone <REPO_URL> && cd ablecliks

# Create a virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Copy the example config and edit paths for your system
cp cliks.toml.example cliks.toml

# Run the CLI
cliks --help
```

---

## Getting the samples

Put your source WAVs in a folder (by default `samples/` in the project root). You can use any path and set `source_dir` in `cliks.toml`.

**Using the Ableton Live Metronome Expansion Pack (recommended):**

1. Download the [release zip](https://github.com/TroyMetrics/Ableton-Live-Metronome-Expansion-Pack/releases) and extract it.
2. The pack uses two files per voice (`Metronome.wav`, `MetronomeUp.wav`). Copy the extracted voice folders into `samples/` so you have one subfolder per voice, each containing those two WAVs.
3. Run the bootstrap script to convert them to the 4-role layout cliks expects:
   ```bash
   python scripts/bootstrap_demo.py --source samples --dest samples
   ```
   This creates the required `Accent.wav`, `4ths.wav`, `8ths.wav`, and `16ths.wav` in each voice folder (overwriting or creating as needed).

If you already have 4 WAVs per voice in the convention below, skip the bootstrap step and point cliks at that folder.

---

## Voice Pack Convention

Each voice is a subdirectory containing exactly 4 WAV files:

```
samples/
  BELL - Classic Bell/
    Accent.wav
    4ths.wav
    8ths.wav
    16ths.wav
```

Folder names should follow the `CODE - Description` pattern (e.g. `BELL - Classic Bell`).
Role filenames are matched case-insensitively.

---

## Output Structure

```
output_dir/
  bell-classic-bell/
    bell-classic-bell_accent.wav
    bell-classic-bell_4ths.wav
    bell-classic-bell_8ths.wav
    bell-classic-bell_16ths.wav
    manifest.json
```

The `manifest.json` contains the slug, source paths, role filenames, and a
Windows-style path for use by Ableton or a future Max for Live device.

---

## CLI Commands

### `scan` — Discover voices and show completeness

```bash
cliks scan samples/
cliks scan                    # uses source_dir from cliks.toml
```

### `validate` — Run all validation rules

```bash
cliks validate samples/
cliks validate samples/ --output-dir /mnt/c/Users/$USER/Music/Ableton/VoicePacks
```

### `report` — Alias for validate with pretty output

```bash
cliks report samples/
```

### `build` — Build voice packs

```bash
cliks build samples/ /mnt/c/Users/$USER/Music/Ableton/VoicePacks

# Dry run (shows what would happen, writes nothing)
cliks build --dry-run

# Overwrite existing output folders
cliks build --force
```

### `patch` — Generate per-voice .adg presets

```bash
# Uses bundled template by default; writes to [patch] presets_dir
cliks patch

# Override template or output directory
cliks patch --template /path/to/template.adg --presets-dir /path/to/output
```

### `assemble` — Build a master Instrument Rack

```bash
# Combines all patched voices into one .adg with Chain Selector
cliks assemble --output CLIKS.adg
```

### Global flags

| Flag | Description |
|------|-------------|
| `--config PATH` | Path to `cliks.toml` (auto-discovered from cwd by default) |
| `-v / --verbose` | Enable debug logging to stderr |
| `--dry-run` | Log operations without writing files |
| `--force` | Overwrite existing output folders |

---

## Configuration (`cliks.toml`)

Copy `cliks.toml.example` to `cliks.toml` and fill in paths for your system.
The config file is auto-discovered from the current directory upward.

```toml
[paths]
source_dir = "samples"
output_dir = "/mnt/c/Users/YOUR_USERNAME/Music/Ableton/VoicePacks"

[naming]
slug_separator = "-"

[build]
overwrite = false

[patch]
# Leave empty to use the bundled cliks-template.adg
template = ""
presets_dir = "/mnt/c/Users/YOUR_USERNAME/.../Instrument Rack/Cliks"
voice_pack_windows_root = ""
```

Precedence: CLI flag > cliks.toml > built-in default.

---

## Bundled Templates

The `templates/` directory includes the Ableton preset fragments used by `patch`
and `assemble`:

| File | Purpose |
|------|---------|
| `cliks-template.adg` | Single-voice Drum Rack preset (the patch template) |
| `chain_template.xml` | One `InstrumentBranchPreset` block for assembly |
| `rack_header.xml` | XML before `<BranchPresets>` in the master rack |
| `rack_footer.xml` | XML after `</BranchPresets>` in the master rack |

The `.adg` template includes macro assignments for pitch control on 4ths, 8ths,
and 16ths — these are preserved automatically during patching and assembly.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation errors found (build blocked) |
| 2 | Runtime / system error |

---

## Running Tests

```bash
pip install pytest
pytest
```

---

## WSL / Windows Path Notes

- The CLI runs entirely in WSL (Linux).
- All internal paths use `pathlib.Path` (POSIX).
- When `output_dir` is under `/mnt/<drive>/`, the `manifest.json` for each
  voice pack includes a `windows_path` field (e.g. `C:\Users\you\...`).
- Ableton Live on Windows reads files via the Windows path.
- No symlinks are used; files are always physically copied.

---

## Max for Live Integration (Future)

The `manifest.json` in each voice pack folder is the contract for future
Max for Live integration:

- M4L device discovers voice packs by scanning for `manifest.json` in subdirectories.
- Each manifest contains `windows_path`, role filenames, and `schema_version`.
- Code integration points are marked with `# TODO(m4l):` comments in the source.

---

## Folder Structure

```
ablecliks/
  pyproject.toml
  cliks.toml.example        # copy to cliks.toml and edit
  README.md
  templates/
    cliks-template.adg       # single-voice Drum Rack preset template
    chain_template.xml       # chain fragment for rack assembly
    rack_header.xml          # master rack header
    rack_footer.xml          # master rack footer
  src/cliks/
    __init__.py              # version
    __main__.py              # python -m cliks entry point
    cli.py                   # argparse wiring
    models.py                # Voice, Role, dataclasses
    scanner.py               # discover voices from source dir
    validator.py             # validation rules engine
    builder.py               # copy/rename files, build output
    manifest.py              # manifest schema + serialization
    paths.py                 # WSL/Windows path conversion
    config.py                # TOML config loading
    patcher.py               # .adg preset generation per voice
    assembler.py             # master rack assembly
    report.py                # formatted output
  scripts/
    bootstrap_demo.py        # convert legacy 2-file packs to 4-role format
  tests/
    conftest.py
    helpers.py
    test_models.py
    test_scanner.py
    test_validator.py
    test_builder.py
    test_paths.py
  samples/                   # raw WAV source files (not tracked in git)
```

---

## Credits

The sample packs used with this tool (for testing and as the initial source of 4-role voices) come from the [Ableton Live Metronome Expansion Pack](https://github.com/TroyMetrics/Ableton-Live-Metronome-Expansion-Pack) by [TroyMetrics](https://github.com/TroyMetrics) — 85 high-quality metronome sounds, distributed via the pack’s [release zip](https://github.com/TroyMetrics/Ableton-Live-Metronome-Expansion-Pack/releases). Thank you for making these samples available!

---

## License

MIT
