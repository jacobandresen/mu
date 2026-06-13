import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_js_program_parse_guard(file_path: str) -> bool:
    """Wrap `program.parse(process.argv)` with require.main === module guard.

    CLI apps built with commander call program.parse(process.argv) at module
    level. When Jest imports the module, this call runs commander's argument
    parser, which exits with code 1 (no matching command). Jest catches the
    process.exit and marks the test suite as failed.

    Fix: wrap the bare program.parse() call in `if (require.main === module)`
    so it only runs when executed directly, not when required by tests.
    General pattern: applies to any JS file using commander-style program.parse.
    """
    if Path(file_path).suffix.lower() not in ('.js', '.mjs', '.jsx'):
        return False
    basename = Path(file_path).name
    if basename.startswith('test') or 'test' in basename or 'spec' in basename:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    # Already guarded
    if 'require.main === module' in text or 'require.main == module' in text:
        return False

    # Match bare program.parse(process.argv) or program.parse(process.argv.slice(2))
    # at top indentation level (not inside a function or if block)
    m = re.search(
        r'^(program\.parseAsync?|program\.parse)\s*\(process\.argv',
        text, re.MULTILINE,
    )
    if not m:
        return False

    # Wrap the entire line(s) ending with ;
    line_start = text.rfind('\n', 0, m.start()) + 1
    # Find end of statement (could span multiple lines for async)
    stmt_end = text.find('\n', m.end())
    if stmt_end == -1:
        stmt_end = len(text)
    else:
        stmt_end += 1  # include the newline

    original = text[line_start:stmt_end]
    indent = re.match(r'^(\s*)', original).group(1)
    inner = original.rstrip('\n')
    wrapped = f'{indent}if (require.main === module) {{\n{indent}  {inner.strip()}\n{indent}}}\n'
    new_text = text[:line_start] + wrapped + text[stmt_end:]
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: wrapped program.parse with require.main guard in {file_path}")
    return True
