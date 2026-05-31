"""Research agent: web search + page fetch + LLM synthesis → Markdown report."""

import html as _html
import json
import re
import sys
import time
from pathlib import Path

from mu.client import chat_or_retry

# ── tool definitions ──────────────────────────────────────────────────────────

_SEARCH_TOOL = {
    'type': 'function',
    'function': {
        'name': 'Search',
        'description': 'Search the web and return titles, URLs, and snippets.',
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Search query'},
            },
            'required': ['query'],
        },
    },
}

_FETCH_TOOL = {
    'type': 'function',
    'function': {
        'name': 'Fetch',
        'description': 'Fetch the plain-text content of a web page.',
        'parameters': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'description': 'URL to retrieve'},
            },
            'required': ['url'],
        },
    },
}

_WRITE_TOOL = {
    'type': 'function',
    'function': {
        'name': 'Write',
        'description': 'Write content to a file.',
        'parameters': {
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': 'File path'},
                'content': {'type': 'string', 'description': 'File content'},
            },
            'required': ['path', 'content'],
        },
    },
}

_TOOLS = [_SEARCH_TOOL, _FETCH_TOOL, _WRITE_TOOL]

_UA = 'Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0'

_fetch_cache: dict[str, str] = {}
_search_cache: dict[str, str] = {}

# ── filename helper ───────────────────────────────────────────────────────────

def report_filename(topic: str) -> str:
    slug = re.sub(r'[^\w\s]', '', topic.lower().strip())
    slug = re.sub(r'\s+', '_', slug)
    slug = re.sub(r'_+', '_', slug).strip('_')
    return f"{slug}_report.md"


_EXT_LANG = {
    '.py': 'Python', '.go': 'Go', '.rs': 'Rust', '.js': 'JavaScript',
    '.ts': 'TypeScript', '.c': 'C', '.cpp': 'C++', '.rb': 'Ruby',
    '.java': 'Java', '.cs': 'C#', '.kt': 'Kotlin', '.swift': 'Swift',
    '.lua': 'Lua', '.zig': 'Zig', '.nim': 'Nim', '.pas': 'Pascal',
}

# ── web tools ─────────────────────────────────────────────────────────────────

def _search(query: str) -> str:
    if query in _search_cache:
        return _search_cache[query]
    try:
        import httpx
        r = httpx.get(
            'https://html.duckduckgo.com/html/',
            params={'q': query},
            headers={'User-Agent': _UA},
            timeout=15.0,
            follow_redirects=True,
        )
        r.raise_for_status()
        text = r.text

        title_re = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL)
        snippet_re = re.compile(
            r'class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL)

        titles = title_re.findall(text)
        snippets = [
            _html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
            for m in snippet_re.finditer(text)
        ]

        results = []
        for i, (url, raw_title) in enumerate(titles[:8]):
            title = _html.unescape(re.sub(r'<[^>]+>', '', raw_title)).strip()
            snippet = snippets[i] if i < len(snippets) else ''
            results.append(f"{i + 1}. {title}\n   URL: {url}\n   {snippet}")

        result = '\n\n'.join(results) if results else 'No results found.'
        _search_cache[query] = result
        return result
    except Exception as e:
        return f"Search error: {e}"


def _fetch(url: str, max_chars: int = 6000) -> str:
    if url in _fetch_cache:
        return _fetch_cache[url]
    try:
        import httpx
        r = httpx.get(url, headers={'User-Agent': _UA}, timeout=15.0,
                      follow_redirects=True)
        r.raise_for_status()
        text = r.text
        for tag in ('script', 'style', 'nav', 'header', 'footer', 'aside'):
            text = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', ' ', text,
                          flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = _html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + f'\n\n[truncated at {max_chars} chars]'
        _fetch_cache[url] = text
        return text
    except Exception as e:
        return f"Fetch error: {e}"


def _write(path: str, content: str) -> str:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(content)
        return f"wrote {path} ({len(content)} bytes)"
    except Exception as e:
        return f"error writing file: {e}"


def _dispatch(name: str, raw_args) -> str:
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
    except Exception:
        args = {}
    if name == 'Search':
        return _search(args.get('query', ''))
    if name == 'Fetch':
        return _fetch(args.get('url', ''))
    if name == 'Write':
        return _write(args.get('path', ''), args.get('content', ''))
    return f"unknown tool: {name}"


def _log_call(name: str, raw_args) -> None:
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
    except Exception:
        args = {}
    label = args.get('query') or args.get('url') or args.get('path', '')
    cached = (
        (name == 'Fetch' and args.get('url', '') in _fetch_cache) or
        (name == 'Search' and args.get('query', '') in _search_cache)
    )
    suffix = ' [cached]' if cached else ''
    print(f"==> [mu-research] {name}({label!r}){suffix}", flush=True)

# ── research loop ─────────────────────────────────────────────────────────────

def research(topic: str, output_file: str, model: str,
             max_turns: int = 20, timeout: float = 300.0) -> int:
    system = (
        f'You are a research agent. Research the topic: "{topic}".\n\n'
        'PROTOCOL:\n'
        '1. Call Search one or more times to find relevant pages.\n'
        '2. Call Fetch on the most relevant URLs to read their content.\n'
        '3. After reading at least 3 sources, call Write to save a factual, '
        f'well-structured Markdown report to `{output_file}`.\n'
        '4. Report must be factual — no speculation, no opinion.\n'
        '5. End the report with a ## Sources section listing every URL you fetched.\n'
        '6. Stop immediately after calling Write.'
    )
    msgs: list[dict] = [
        {'role': 'system', 'content': system},
        {'role': 'user',
         'content': f'Research "{topic}" and write the report to `{output_file}`.'},
    ]

    print(f"  Researching: {topic}", flush=True)
    deadline = time.time() + timeout
    wrote_this_run = False

    for turn in range(max_turns):
        if time.time() >= deadline:
            print("mu-research: timeout", file=sys.stderr)
            return 1
        try:
            msg, stats = chat_or_retry(model, msgs, _TOOLS, deadline)
        except Exception as e:
            print(f"mu-research: {e}", file=sys.stderr)
            return 1
        msgs.append(msg)

        if not msg.get('tool_calls'):
            if wrote_this_run and Path(output_file).exists():
                return 0
            if turn < max_turns - 1:
                msgs.append({'role': 'user',
                             'content': (f'Call Write now to save the report to '
                                         f'`{output_file}`. Do not write prose.')})
            continue

        for tc in msg['tool_calls']:
            name = tc['function']['name']
            raw = tc['function']['arguments']
            _log_call(name, raw)
            result = _dispatch(name, raw)
            msgs.append({'role': 'tool', 'content': result,
                         'tool_call_id': tc.get('id', '')})
            if name == 'Write' and Path(output_file).exists():
                wrote_this_run = True
                return 0

    print("mu-research: max turns reached without writing report", file=sys.stderr)
    return 1


# ── deep research ─────────────────────────────────────────────────────────────

def _compose_topic(goal: str, task, plan_context: str) -> str:
    """Build a specific research query from task context + plan context.

    Combines the overall goal, task purpose, language, and dependencies so
    searches are targeted rather than generic (e.g. not just "Makefile").
    """
    ext = Path(task.file_path).suffix.lower()
    lang = _EXT_LANG.get(ext, '')

    # Pull dependency list from the ## Dependencies section
    deps = ''
    in_deps = False
    for line in plan_context.splitlines():
        if re.match(r'^##\s+Dependencies', line):
            in_deps = True
            continue
        if in_deps:
            if line.startswith('## '):
                break
            stripped = line.strip()
            if stripped:
                deps = stripped
                break

    parts: list[str] = []
    desc_lower = (task.description or '').lower()
    if lang and lang.lower() not in desc_lower:
        parts.append(lang)
    if task.description:
        parts.append(task.description)
    if goal:
        parts.append(f'for {goal}')
    elif deps:
        parts.append(f'using {deps}')

    return ' '.join(parts) if parts else task.file_path


def _summarize_report(report_path: str, task, model: str, goal: str) -> str:
    """Distill a research report into 3-5 actionable implementation bullets."""
    try:
        content = Path(report_path).read_text()
    except OSError:
        return ''
    system = (
        'You are a senior software engineer. Given a research report, extract '
        '3-5 concrete, actionable bullet points that directly guide implementing '
        'a specific file. Focus on: APIs to use, patterns to follow, gotchas to avoid, '
        'and best practices. Output ONLY bullet points starting with "- ". No headers, no preamble.'
    )
    prompt = f'File: `{task.file_path}`\nPurpose: {task.description}\n'
    if goal:
        prompt += f'Project goal: {goal}\n'
    prompt += f'\nResearch report:\n\n{content[:8000]}\n\nExtract implementation guidance:'
    msgs = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': prompt},
    ]
    try:
        msg, _ = chat_or_retry(model, msgs, [], time.time() + 120.0)
        return (msg.get('content') or '').strip()
    except Exception as e:
        print(f"  summarize error: {e}", file=sys.stderr)
        return ''


def _extract_research_notes(plan_text: str) -> dict[str, str]:
    """Parse existing ## Research Notes section → {file_path: bullets}."""
    header = '## Research Notes'
    if header not in plan_text:
        return {}
    section = plan_text[plan_text.index(header) + len(header):]
    end_match = re.search(r'\n## ', section)
    if end_match:
        section = section[:end_match.start()]
    result: dict[str, str] = {}
    current_file: str | None = None
    current_lines: list[str] = []
    for line in section.splitlines():
        m = re.match(r'^### (.+)$', line)
        if m:
            if current_file and current_lines:
                result[current_file] = '\n'.join(current_lines).strip()
            current_file = m.group(1).strip()
            current_lines = []
        elif current_file:
            current_lines.append(line)
    if current_file and current_lines:
        result[current_file] = '\n'.join(current_lines).strip()
    return result


def _set_research_notes(plan_text: str, notes: dict[str, str]) -> str:
    """Replace or append the ## Research Notes section in plan_text."""
    body = '\n\n'.join(f'### {fp}\n{bullets}' for fp, bullets in notes.items()) + '\n'
    if '## Research Notes' in plan_text:
        start = plan_text.index('## Research Notes')
        tail = plan_text[start + len('## Research Notes'):]
        end_match = re.search(r'\n## ', tail)
        if end_match:
            return plan_text[:start] + '## Research Notes\n\n' + body + tail[end_match.start():]
        return plan_text[:start] + '## Research Notes\n\n' + body
    return plan_text.rstrip('\n') + '\n\n## Research Notes\n\n' + body


def _update_sketch(file_path: str, bullets: str, goal: str, task) -> bool:
    """Replace the comment block in a sketch stub with research-informed notes."""
    from mu.plan import _sketch_comment  # type: ignore[attr-defined]
    try:
        content = Path(file_path).read_text()
    except OSError:
        return False
    if 'PLAN:' not in content:
        return False
    ext = Path(file_path).suffix.lower()
    lines: list[str] = [f'PLAN: {file_path}']
    if goal:
        lines.append(f'GOAL: {goal}')
    if task.description:
        lines.append(f'PURPOSE: {task.description}')
    lines.append('')
    lines.append('IMPLEMENTATION NOTES:')
    for bullet in bullets.splitlines():
        if bullet.strip():
            lines.append(bullet.strip())
    try:
        Path(file_path).write_text(_sketch_comment(ext, lines))
        return True
    except OSError:
        return False


def deep(plan_path: str, model: str, goal: str = '') -> int:
    """Research each pending task in PLAN.md and annotate with actionable context."""
    from mu.plan import parse, is_build_file
    p = parse(plan_path)
    if not p.tasks:
        print(f"No tasks found in {plan_path}", file=sys.stderr)
        return 1
    try:
        plan_text = Path(plan_path).read_text()
    except OSError:
        print(f"Cannot read {plan_path}", file=sys.stderr)
        return 1

    existing = _extract_research_notes(plan_text)
    research_dir = Path('.mu') / 'research'
    research_dir.mkdir(parents=True, exist_ok=True)

    all_notes: dict[str, str] = dict(existing)
    pending = [t for t in p.tasks if not t.done and not is_build_file(t.file_path)]

    for task in pending:
        topic = _compose_topic(goal, task, p.plan_context)
        slug = re.sub(r'\W+', '_', task.file_path).strip('_')
        output_file = str(research_dir / f'{slug}.md')

        if task.file_path in existing:
            # Second pass: research a more specific angle and append new bullets.
            print(f"  Deepening (cached): {task.file_path}", flush=True)
            deeper_topic = topic + ' advanced patterns pitfalls'
            deeper_file = str(research_dir / f'{slug}_deep.md')
            if research(deeper_topic, deeper_file, model) != 0:
                print(f"  WARNING: deep research failed for {task.file_path}", file=sys.stderr)
                continue
            print(f"  Summarizing deeper: {task.file_path}", flush=True)
            new_bullets = _summarize_report(deeper_file, task, model, goal)
            if not new_bullets:
                print(f"  WARNING: empty deeper summary for {task.file_path}", file=sys.stderr)
                continue
            existing_lines = [l for l in existing[task.file_path].splitlines() if l.strip()]
            added = [l for l in new_bullets.splitlines()
                     if l.strip() and l.strip() not in existing_lines]
            if not added:
                print(f"  No new bullets (deeper): {task.file_path}", flush=True)
                continue
            combined = '\n'.join(existing_lines + added)
            all_notes[task.file_path] = combined
            if _update_sketch(task.file_path, combined, goal, task):
                print(f"  Updated sketch (deeper): {task.file_path}", flush=True)
            continue

        print(f"  Researching ({task.file_path}): {topic}", flush=True)
        if research(topic, output_file, model) != 0:
            print(f"  WARNING: research failed for {task.file_path}", file=sys.stderr)
            continue

        print(f"  Summarizing: {task.file_path}", flush=True)
        bullets = _summarize_report(output_file, task, model, goal)
        if not bullets:
            print(f"  WARNING: empty summary for {task.file_path}", file=sys.stderr)
            continue
        all_notes[task.file_path] = bullets

        if _update_sketch(task.file_path, bullets, goal, task):
            print(f"  Updated sketch: {task.file_path}", flush=True)

    if all_notes == existing:
        print("No new research — plan already up to date.")
        return 0

    updated = _set_research_notes(plan_text, all_notes)
    try:
        Path(plan_path).write_text(updated)
    except OSError as e:
        print(f"Cannot write {plan_path}: {e}", file=sys.stderr)
        return 1

    new_count = len(all_notes) - len(existing)
    print(f"Updated {plan_path}: {new_count} new + {len(existing)} cached = {len(all_notes)} task(s).")
    return 0
