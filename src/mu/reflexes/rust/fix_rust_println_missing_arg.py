import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls

from ._common import *  # noqa: F401,F403

def fix_rust_println_missing_arg(file_path: str) -> bool:
    """Fix println!/print! calls whose placeholder count doesn't match argument count.

    Models write format strings like `println!("{}")` or `println!("Fib({}) = {}")`
    with too few arguments. When inside a `for var in ...` loop, fills missing args
    with the loop variable (repeated if needed). Generic: any mismatch between `{}`
    count and argument count is a compile error in Rust.
    """
    if not file_path.endswith('.rs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    changed = False
    result = []
    loop_var_stack: list[str] = []

    for line in lines:
        stripped = line.strip()
        m = re.match(r'for\s+(\w+)\s+in\b', stripped)
        if m:
            loop_var_stack.append(m.group(1))

        # Match println!("...") or print!("...") — capture format string and args
        macro_m = re.search(r'\b(println|print)!\s*\(("(?:[^"\\]|\\.)*")(.*)\)', line)
        if macro_m:
            fmt_str = macro_m.group(2)  # includes surrounding quotes
            rest = macro_m.group(3)     # ', arg1, arg2, ...' or ''
            n_placeholders = fmt_str.count('{}')
            existing_args = [a.strip() for a in rest.lstrip(',').split(',') if a.strip()]
            if n_placeholders > len(existing_args) and loop_var_stack:
                var = loop_var_stack[-1]
                all_args = existing_args + [var] * (n_placeholders - len(existing_args))
                new_call = f'{macro_m.group(1)}!({fmt_str}, {", ".join(all_args)})'
                line = line.replace(macro_m.group(0), new_call, 1)
                changed = True

        if stripped == '}' and loop_var_stack:
            loop_var_stack.pop()
        result.append(line)

    if not changed:
        return False
    Path(file_path).write_text('\n'.join(result) + '\n')
    print(f"==> [mu-agent] Reflex: fixed println! missing arg(s) in {file_path}")
    return True
