import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls

from ._common import *  # noqa: F401,F403

def fix_rust_cargo_toml(file_path: str) -> bool:
    """Regenerate a corrupted Cargo.toml that has merged or duplicate sections.

    The repair model sometimes appends content to Cargo.toml without proper
    separation, producing artifacts like `authors = ["x"][package]` or multiple
    `[package]` headers. Detect these and replace with a minimal valid Cargo.toml.
    """
    if Path(file_path).name.lower() != 'cargo.toml':
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Corruption signals: inline '][', multiple [package] sections, [[package]]
    is_corrupt = (
        re.search(r'\]\[', text) is not None
        or text.count('\n[package]') > 1
        or '[[package]]' in text
        or text.count('[package]') > 1
    )
    if not is_corrupt:
        return False
    # Extract the project name if we can find it
    m = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    proj = m.group(1) if m else Path(file_path).parent.name or 'app'
    # Detect if there's a src/main.rs or main.rs to set up [[bin]]
    has_src_main = Path(Path(file_path).parent / 'src' / 'main.rs').exists()
    has_root_main = Path(Path(file_path).parent / 'main.rs').exists()
    clean = (
        '[package]\n'
        f'name = "{proj}"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n'
    )
    if has_root_main and not has_src_main:
        clean += f'\n[[bin]]\nname = "{proj}"\npath = "main.rs"\n'
    Path(file_path).write_text(clean)
    print(f"==> [mu-agent] Reflex: regenerated corrupted Cargo.toml in {file_path}")
    return True
