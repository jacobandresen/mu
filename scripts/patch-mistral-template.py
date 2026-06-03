#!/usr/bin/env python3
"""Patch Mistral 7B Instruct v0.3 GGUF files to support the system role.

The GGUF files for this model ship with a jinja template that raises an
exception on any message with role 'system'. mu sends a system prompt on
every request, so the model returns HTTP 400 until the template is fixed.

Fix: replace the template in-place with an equal-length version that
prepends system-message content to the first user turn. No bytes shift —
the replacement is padded to the exact original length with a jinja comment.

Usage:
    python3 scripts/patch-mistral-template.py            # auto-finds all copies
    python3 scripts/patch-mistral-template.py /path/to/model.gguf
"""

import sys
import glob
import os

try:
    import gguf
except ImportError:
    sys.exit("gguf package not found — run: pip install gguf")

# Template that supports system role by prepending it to the first user turn.
# Variables set/unset pattern avoids jinja2 namespace issues with older renderers.
_SYSTEM_CORE = (
    "{% set sys='' %}"
    "{% for m in messages %}"
    "{% if m['role']=='system' %}{% set sys=m['content']+'\\n\\n' %}"
    "{% elif m['role']=='user' %}{{ '[INST] '+sys+m['content']+' [/INST]' }}{% set sys='' %}"
    "{% elif m['role']=='assistant' %}{{ m['content']+eos_token }}"
    "{% endif %}{% endfor %}"
)


def _build_replacement(old_template: str) -> str | None:
    """Return a same-length replacement for old_template, or None if not applicable."""
    # Detect known broken patterns
    if "raise_exception('Only user and assistant roles are supported!')" not in old_template:
        return None  # already fixed or unrecognised

    # Preserve the bos_token prefix (varies slightly between uploads: '{{' vs '{{ ')
    if old_template.startswith("{{ bos_token }}"):
        prefix = "{{ bos_token }}"
    elif old_template.startswith("{{bos_token}}"):
        prefix = "{{bos_token}}"
    else:
        prefix = old_template.split("{%")[0]  # grab whatever precedes first block

    core = prefix + _SYSTEM_CORE
    pad = len(old_template) - len(core)
    if pad < 4:
        # Not enough room for a jinja comment — shouldn't happen with known templates
        return None
    return core + "{#" + "x" * (pad - 4) + "#}"


def patch_file(path: str) -> bool:
    """Patch a single GGUF file. Returns True if patched, False if skipped."""
    reader = gguf.GGUFReader(path)
    old_template = None
    for field in reader.fields.values():
        if "chat_template" in field.name:
            old_template = bytes(field.parts[-1]).decode("utf-8")
            break

    if old_template is None:
        print(f"  skip  {path}  (no chat_template field)")
        return False

    new_template = _build_replacement(old_template)
    if new_template is None:
        print(f"  skip  {path}  (already patched or unrecognised template)")
        return False

    assert len(new_template) == len(old_template), "BUG: replacement length mismatch"

    old_bytes = old_template.encode("utf-8")
    new_bytes = new_template.encode("utf-8")

    with open(path, "rb") as f:
        content = f.read()

    pos = content.find(old_bytes)
    if pos == -1:
        print(f"  skip  {path}  (template bytes not found — file may be compressed)")
        return False

    with open(path, "r+b") as f:
        f.seek(pos)
        f.write(new_bytes)

    print(f"  patch {path}  ({len(old_template)} bytes @ offset {pos})")
    return True


def find_mistral_ggufs() -> list[str]:
    base = os.path.expanduser("~/.lmstudio/models")
    pattern = os.path.join(base, "**", "*[Mm]istral*7[Bb]*[Ii]nstruct*v0.3*.gguf")
    return sorted(glob.glob(pattern, recursive=True))


def main() -> None:
    paths = sys.argv[1:] if len(sys.argv) > 1 else find_mistral_ggufs()

    if not paths:
        sys.exit("No Mistral 7B Instruct v0.3 GGUFs found under ~/.lmstudio/models")

    patched = 0
    for p in paths:
        if patch_file(p):
            patched += 1

    print(f"\n{patched}/{len(paths)} file(s) patched.")
    if patched:
        print("Reload the model in LM Studio (or run: mu model load <id>) to apply.")


if __name__ == "__main__":
    main()
