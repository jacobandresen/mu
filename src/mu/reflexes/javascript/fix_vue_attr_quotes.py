import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_vue_attr_quotes(file_path: str) -> bool:
    """Strip invalid characters from Vue HTML template attribute names.

    HTML attribute names cannot contain U+0022 ("), U+0027 ('), or U+003C (<).
    When the model writes `v-bind:"prop"=value`, the Vue compiler raises
    SyntaxError. This reflex strips those characters from attribute names
    (the text before `=`) inside the <template> section only.
    """
    if not file_path.lower().endswith('.vue'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    template_m = re.search(r'(<template(?:\s[^>]*)?>)(.*?)(</template>)', text, re.DOTALL)
    if not template_m:
        return False

    template = template_m.group(2)

    def fix_name(m: re.Match) -> str:
        name = m.group(1)
        clean = name.replace('"', '').replace("'", '').replace('<', '')
        return clean

    # Match an attribute name that contains at least one invalid char before '='.
    # The lookahead (?==) keeps the '=' unconsumed so the surrounding text is intact.
    new_template = re.sub(
        r"""(?<=[ \t\n])([\w:@$./-]*["'<][\w:@$./\"'<-]*)(?==)""",
        fix_name,
        template,
    )

    if new_template == template:
        return False

    new_text = text[:template_m.start(2)] + new_template + text[template_m.end(2):]
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: stripped invalid chars from Vue attribute names in {file_path}")
    return True
