"""Assemble a complete parent Instrument Rack from per-voice chains.

Takes the rack shell (header + footer extracted from the parent rack template)
and a chain template (one InstrumentBranchPreset block), stamps out one chain
per voice with sample paths patched, and writes the assembled .adg.

The assembled rack has a Chain Selector with one slot per voice, allowing
you to switch voices by changing the selector value.

Template files (in templates/):
  rack_header.xml    -- Everything up to and including <BranchPresets>
  rack_footer.xml    -- From </BranchPresets> to end of file
  chain_template.xml -- One complete InstrumentBranchPreset block (BLIP)
"""

from __future__ import annotations

import gzip
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from cliks.models import Role, Voice
from cliks.patcher import _SLOT_ROLE_MAP, _SLOT_SUFFIX_MAP, _TEMPLATE_OUTER_NAME

log = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


@dataclass
class AssembleResult:
    output_path: Path
    voice_count: int
    success: bool
    error: str | None = None


def assemble_rack(
    voices: list[Voice],
    voice_pack_windows_root: str,
    output_path: Path,
    templates_dir: Path | None = None,
    dry_run: bool = False,
) -> AssembleResult:
    """Assemble a parent rack .adg containing one chain per complete voice.

    Args:
        voices:                  All discovered voices (incomplete ones are skipped).
        voice_pack_windows_root: Windows path to the VoicePacks root folder.
        output_path:             Where to write the assembled .adg file.
        templates_dir:           Directory containing rack_header.xml, rack_footer.xml,
                                 chain_template.xml. Defaults to project templates/ dir.
        dry_run:                 If True, log without writing.

    Returns an AssembleResult.
    """
    tdir = templates_dir or _TEMPLATES_DIR
    complete = [v for v in voices if v.is_complete]
    complete.sort(key=lambda v: v.slug)

    if not complete:
        return AssembleResult(
            output_path=output_path, voice_count=0, success=False,
            error="No complete voices to assemble",
        )

    try:
        header = (tdir / "rack_header.xml").read_text(encoding="utf-8")
        footer = (tdir / "rack_footer.xml").read_text(encoding="utf-8")
        chain_tpl = (tdir / "chain_template.xml").read_text(encoding="utf-8")
    except FileNotFoundError as e:
        return AssembleResult(
            output_path=output_path, voice_count=0, success=False,
            error=f"Template file not found: {e}",
        )

    chains: list[str] = []
    for idx, voice in enumerate(complete):
        patched = _patch_chain(chain_tpl, voice, voice_pack_windows_root, chain_id=idx)
        chains.append(patched)

    assembled = header + "\n".join(chains) + "\n" + footer

    if dry_run:
        log.info(
            "[dry-run] Would write assembled rack (%d voices): %s",
            len(complete), output_path,
        )
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(output_path, "wb") as f:
            f.write(assembled.encode("utf-8"))
        log.info("Wrote assembled rack (%d voices): %s", len(complete), output_path)

    return AssembleResult(
        output_path=output_path, voice_count=len(complete), success=True,
    )


def _patch_chain(
    chain_xml: str,
    voice: Voice,
    voice_pack_windows_root: str,
    chain_id: int,
) -> str:
    """Patch a single chain template for a voice.

    Replaces:
      - InstrumentBranchPreset Id
      - Chain Name
      - BranchSelectorRange (outer, the one with non-zero values)
      - All inner slot UserNames (BLIP-ACCENT -> CODE-ACCENT etc.)
      - All SampleRef Path and RelativePath entries
      - The outer chain UserName (template name -> voice folder_name)
    """
    result_lines: list[str] = []
    lines = chain_xml.splitlines()

    in_sample_ref = False
    current_role: Role | None = None

    for line in lines:
        stripped = line.strip()

        if "<SampleRef>" in stripped:
            in_sample_ref = True
        elif "</SampleRef>" in stripped:
            in_sample_ref = False
            current_role = None

        # Detect slot role from UserName
        m = re.search(r'<UserName Value="([^"]+)"', line)
        if m:
            slot_name = m.group(1)
            if slot_name in _SLOT_ROLE_MAP:
                current_role = _SLOT_ROLE_MAP[slot_name]

        # Patch sample paths inside SampleRef
        if in_sample_ref and current_role is not None:
            line = _patch_sample_line(line, voice, voice_pack_windows_root, current_role)

        result_lines.append(line)

    patched = "\n".join(result_lines)

    # Replace InstrumentBranchPreset Id
    patched = re.sub(
        r'<InstrumentBranchPreset Id="\d+"',
        f'<InstrumentBranchPreset Id="{chain_id}"',
        patched,
        count=1,
    )

    # Replace chain Name
    patched = re.sub(
        r'(<Name Value=")[^"]*(")',
        lambda m: f'{m.group(1)}{voice.code}{m.group(2)}',
        patched,
        count=1,
    )

    # Replace outer chain UserName (template name -> voice folder_name)
    patched = patched.replace(
        f'UserName Value="{_TEMPLATE_OUTER_NAME}"',
        f'UserName Value="{voice.folder_name}"',
    )

    # Replace inner slot UserNames
    code = voice.code
    for template_slot, suffix in _SLOT_SUFFIX_MAP.items():
        new_slot = f"{code}{suffix}"
        patched = patched.replace(
            f'UserName Value="{template_slot}"',
            f'UserName Value="{new_slot}"',
        )

    # Patch the outer BranchSelectorRange (the non-zero one).
    # In the template this has values like Min=2, Max=2 etc.
    # We find the BranchSelectorRange that has non-zero Min and replace it.
    patched = _patch_branch_selector_range(patched, chain_id)

    return patched


def _patch_branch_selector_range(xml: str, chain_id: int) -> str:
    """Replace the outer BranchSelectorRange with the chain index.

    The chain template has two types of BranchSelectorRange:
      - Inner ones (all zeros) for the 5 Simpler slots -- leave alone
      - One outer one with non-zero values for the chain selector -- patch this

    We find the first BranchSelectorRange block where Min != 0 and replace it.
    If chain_id == 0 (first chain), we replace the last BranchSelectorRange block
    since all inner ones are already 0.
    """
    lines = xml.splitlines()
    result: list[str] = []
    found_outer = False

    i = 0
    while i < len(lines):
        if '<BranchSelectorRange>' in lines[i] and not found_outer:
            # Read the block
            block_start = i
            block_lines = [lines[i]]
            i += 1
            while i < len(lines) and '</BranchSelectorRange>' not in lines[i]:
                block_lines.append(lines[i])
                i += 1
            if i < len(lines):
                block_lines.append(lines[i])

            block_text = "\n".join(block_lines)
            # Check if any value is non-zero (this is the outer range)
            has_nonzero = bool(re.search(r'<Min Value="[1-9]', block_text))

            if has_nonzero:
                found_outer = True
                indent = lines[block_start].split('<')[0]
                inner = indent + '\t'
                result.append(f"{indent}<BranchSelectorRange>")
                result.append(f'{inner}<Min Value="{chain_id}" />')
                result.append(f'{inner}<Max Value="{chain_id}" />')
                result.append(f'{inner}<CrossfadeMin Value="{chain_id}" />')
                result.append(f'{inner}<CrossfadeMax Value="{chain_id}" />')
                result.append(f"{indent}</BranchSelectorRange>")
            else:
                result.extend(block_lines)
        else:
            result.append(lines[i])
        i += 1

    # If we never found a non-zero one (this would be the case if the template
    # used value "0"), we need to patch the LAST BranchSelectorRange instead.
    if not found_outer:
        return _patch_last_branch_selector(xml, chain_id)

    return "\n".join(result)


def _patch_last_branch_selector(xml: str, chain_id: int) -> str:
    """Fallback: patch the last BranchSelectorRange block in the XML."""
    lines = xml.splitlines()

    # Find all BranchSelectorRange block positions
    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        if '<BranchSelectorRange>' in lines[i]:
            start = i
            while i < len(lines) and '</BranchSelectorRange>' not in lines[i]:
                i += 1
            blocks.append((start, i))
        i += 1

    if not blocks:
        return xml

    last_start, last_end = blocks[-1]
    indent = lines[last_start].split('<')[0]
    inner = indent + '\t'

    replacement = [
        f"{indent}<BranchSelectorRange>",
        f'{inner}<Min Value="{chain_id}" />',
        f'{inner}<Max Value="{chain_id}" />',
        f'{inner}<CrossfadeMin Value="{chain_id}" />',
        f'{inner}<CrossfadeMax Value="{chain_id}" />',
        f"{indent}</BranchSelectorRange>",
    ]

    result = lines[:last_start] + replacement + lines[last_end + 1:]
    return "\n".join(result)


def _patch_sample_line(
    line: str,
    voice: Voice,
    voice_pack_windows_root: str,
    role: Role,
) -> str:
    """Replace sample-related attributes on a single line within a SampleRef."""
    slug = voice.slug
    filename = f"{slug}_{role.value}.wav"
    win_path = f"{voice_pack_windows_root}\\{slug}\\{filename}"

    if "<Path Value=" in line:
        repl = f'<Path Value="{win_path}"'
        return re.sub(r'<Path Value="[^"]*"', lambda _: repl, line)

    if "<RelativePath Value=" in line:
        return re.sub(r'<RelativePath Value="[^"]*"', lambda _: '<RelativePath Value=""', line)

    if "<RelativePathType Value=" in line:
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
