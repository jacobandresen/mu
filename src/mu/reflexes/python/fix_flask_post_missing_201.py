import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_flask_post_missing_201(file_path: str) -> bool:
    """Add HTTP 201 status code to Flask POST route returns missing it.

    REST convention: POST endpoints that create a resource should return 201.
    When a model writes `return jsonify(...)` in a POST handler without a
    status code, Flask defaults to 200, but tests that check `r.status_code == 201`
    fail. This reflex adds `, 201` to bare `return jsonify(...)` calls inside
    POST route handlers.
    Generic: applies to any Flask app with POST routes.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    if "@app.route" not in text or "methods=['POST']" not in text and 'methods=["POST"]' not in text:
        return False
    lines = text.splitlines()
    in_post_handler = False
    changed = False
    out = []
    for i, line in enumerate(lines):
        # Detect @app.route with POST
        if re.search(r"@\w+\.route\([^)]*methods=[^\)]*'POST'", line) or \
           re.search(r'@\w+\.route\([^)]*methods=[^\)]*"POST"', line):
            in_post_handler = True
        elif line.startswith('@') and 'route' in line:
            in_post_handler = False  # different decorator
        elif re.match(r'^def \w+', line):
            # New function def — if we were in a post handler, keep flag until a return is seen
            pass
        elif in_post_handler and re.match(r'\s+return jsonify\(', line):
            # Check if already has a status code (comma after the closing paren)
            stripped = line.rstrip()
            if not re.search(r'\bstatus\b', stripped) and not re.search(r'jsonify\(.*\),\s*\d+', stripped):
                # No status code — add 201
                stripped = re.sub(r'(return jsonify\(.*\))$', r'\1, 201', stripped)
                line = stripped + '\n' if line.endswith('\n') else stripped
                changed = True
                in_post_handler = False  # only fix the first return in the handler
        out.append(line)
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(out))
    print(f"==> [mu-agent] Reflex: added 201 status to POST route jsonify return in {file_path}")
    return True
