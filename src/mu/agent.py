"""Agent program and control architecture.

In AIMA terms this module is the top-level **agent program** — it composes all
four learning-agent components into the plan → write → repair → archive loop:

* **Planner** (``_run_planner``, ``_run_planning_phase``) — goal-based: turns a
  natural-language goal into a ``PLAN.md`` action sequence (the agent's plan).
* **Performance element** (``_run_writer`` → ``Session.run``) — executes the
  plan through the Write/Edit actuators.
* **Critic** (lint gate + test gate + ``Session.repair_loop``) — judges each
  action against the fixed performance standard (tests exit 0) and drives the
  repair loop.
* **Learning element** (``reflect``, ``enrich``) — distills the critic's
  feedback across episodes into the knowledge base (``CHALLENGES.md``).

``run()`` is the main entry point; ``plan()`` is the planner-only subcommand.
"""

import importlib.util
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

from mu import tools
from mu.archive import AgentSession
from mu.client import (chat, list_downloaded_llm_paths, list_models, load_catalog,
                        load_model, recommended_model)
from mu.plan import (Plan, check_goal_alignment, clear_challenges,
                     drop_minority_languages,
                     drop_runtime_artifacts,
                     extract_plan_content, get_challenges, ground_plan,
                     has_pending_build_file,
                     is_build_file, is_test_file, mark_task_done, next_task,
                     normalize_embedded_files,
                     normalize_test_command, parse, parse_content,
                     pending_source_files,
                     plan_languages, record_challenge, record_failed_repair,
                     relevant_files_context,
                     repair_history, strip_thinking_artifacts, tasks_remaining,
                     write_sketches)
from mu.reflexes import (apply_go_reflexes, apply_makefile_reflexes,
                         fix_missing_close_paren, fix_multiline_single_quote,
                         fix_test_import_module, py_autofix)
from mu.session import Session

LOG_DIR = ".mu"

_LIB_RE = re.compile(
    r'(?i)SDL2|OpenGL|ncurses|dotnet|C#|csharp|tensorflow|pytorch|'
    r'django|flask|opencv|wxwidgets|express|gin|cargo')
_HARD_LIB_RE = re.compile(r'(?i)pytest|jest|xunit|nunit|rspec|cargo\s+test')
_COMPLEXITY_PLANNER = {'trivial': 120, 'simple': 200, 'complex': 360, 'hard': 480}
_COMPLEXITY_WRITER = {'trivial': 90, 'simple': 220, 'complex': 300, 'hard': 400}
_REPAIR_MAX_ITERS = 6
_REPAIR_LOOP_RULES = """REPAIR RULES — follow exactly:
1. You are fixing failing tests. Each turn, make ONE targeted change: call Edit, or Write to replace a whole file.
2. Do NOT run any commands. The test is run for you after each edit and the new output is shown to you.
3. Only modify files that already exist. Do not create new files. Do not touch PLAN.md.
4. Call the tool immediately — no prose, no explanation. Stop after one tool call."""


def detect_complexity(goal: str) -> str:
    has_lib = bool(_LIB_RE.search(goal))
    if has_lib and _HARD_LIB_RE.search(goal):
        return 'hard'
    if has_lib:
        return 'complex'
    return 'trivial' if len(goal.split()) <= 4 else 'simple'

# ---------- Minimal stub generator ----------

def _default_stub(ext: str, path: str) -> str:
    """Return a minimal syntactically valid stub for the given file extension.

    Used when the model writes a near‑empty file (< 100 bytes). The stub is
    generic for the language class, satisfying the prime‑directive rule.
    """
    if ext == ".rs":
        return "fn main() {\n    println!(\"Hello, world!\");\n}\n"
    if ext in {".c", ".h"}:
        return "int main(void) {\n    return 0;\n}\n"
    if ext == ".go":
        return "package main\n\nimport \"fmt\"\n\nfunc main() {\n    fmt.Println(\"hello\")\n}\n"
    if ext == ".py":
        return "def main():\n    pass\n\nif __name__ == \"__main__\":\n    main()\n"
    # fallback: a simple comment indicating a stub
    return f"// {Path(path).name} stub\n"


def _is_effectively_empty(path: str) -> bool:
    """True when a written file contains no actual code — empty, all-whitespace,
    or comment-only.

    Replaces a raw byte-size threshold, which is the wrong tool: a valid minimal
    program is tiny in every dojo language (C hello-world ~77 B, Go ~73 B,
    Rust ~30 B, ``print("hi")`` 11 B), so a size cutoff destroys correct work.
    A line counts as code unless it is blank or begins with a common comment
    marker — language-class generic, never problem-specific.
    """
    try:
        text = Path(path).read_text()
    except OSError:
        return False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line[0] in ('#', '*') or line.startswith(('//', '/*', '--', '<!--')):
            continue
        return False
    return True


def log(msg: str, *args) -> None:
    if args:
        msg = msg % args
    print(f"==> [mu-agent] {msg}", flush=True)


def _match_loaded(loaded: list[str], target: str) -> str:
    """Return the loaded model id matching the catalog id `target`, or ''.

    LM Studio sometimes serves a model under a slightly different id than the
    catalog uses (org prefix differences), so fall back to a bare-name match.
    """
    if not target:
        return ''
    bare = target.split('/')[-1]
    for m in loaded:
        if m == target or m.split('/')[-1] == bare:
            return m
    return ''


def _select_model() -> str:
    """Pick the model for the agent: prefer the recommended one, loading it if
    needed; otherwise fall back to whatever is already loaded. Returns '' on
    failure (caller should abort)."""
    loaded = list_models()
    recommended = recommended_model()
    match = _match_loaded(loaded, recommended)
    if match:
        log("Using recommended model: %s", match)
        return match
    # If another catalog model is already loaded, prefer it over loading a
    # non-installed recommended model (avoids a confusing load error).
    catalog_bare = {
        spec['id'].split('/')[-1]
        for spec in load_catalog()
        if spec.get('id')
    }
    for m in loaded:
        bare = m.split('/')[-1].split('@')[0]
        if bare in catalog_bare:
            log("Using loaded catalog model: %s", m)
            return m
    if recommended:
        log("Recommended model %s not loaded — loading via LM Studio...", recommended)
        if load_model(recommended):
            loaded = list_models()
            model = _match_loaded(loaded, recommended) or recommended
            log("Using recommended model: %s", model)
            return model
        log("Could not load recommended model — falling back.")
    # Try any downloaded catalog model before giving up.
    catalog_ids = {spec['id'] for spec in load_catalog() if spec.get('id')}
    catalog_bare = {cid.split('/')[-1] for cid in catalog_ids}
    for path in list_downloaded_llm_paths():
        bare = path.split('/')[-1].split('@')[0]
        if path in catalog_ids or bare in catalog_bare:
            log("Loading downloaded catalog model: %s", path)
            if load_model(path):
                loaded = list_models()
                model = _match_loaded(loaded, path) or path
                log("Using downloaded catalog model: %s", model)
                return model
    if loaded:
        log("Using LM Studio model: %s", loaded[0])
        return loaded[0]
    print("mu-agent: no model loaded in LM Studio — load a model first",
          file=sys.stderr)
    return ''


def split(goal: str = '', model: str = '', target_dir: str = '') -> int:
    """Rewrite PLAN.md so pending tasks are split into smaller, more actionable files."""
    import time
    if not model:
        model = os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        model = _select_model()
        if not model:
            return 1

    if target_dir:
        os.chdir(target_dir)
    if not Path('PLAN.md').exists():
        print("mu-split: no PLAN.md found — run `mu plan` first", file=sys.stderr)
        return 1

    original = Path('PLAN.md').read_text()
    p = parse('PLAN.md')
    pending = [t for t in p.tasks if not t.done and not t.in_progress]
    if not pending:
        log("No pending tasks — nothing to split.")
        return 0

    timeout = _COMPLEXITY_PLANNER['simple']
    log("Splitting %d pending task(s) (timeout=%ds)", len(pending), timeout)

    system = (
        "You refine PLAN.md by splitting broad or vague pending tasks into smaller, "
        "more actionable file-level tasks. Output ONLY the raw PLAN.md markdown — "
        "no preamble, no explanation, no code fences."
    )
    rules = (
        "Rules:\n"
        "- Keep every `- [x]` (done) task exactly as-is, in the same position.\n"
        "- For each `- [ ]` task that is broad, multi-purpose, or vague, split it\n"
        "  into 2-4 concrete files, each with a single clear responsibility.\n"
        "- If a task is already narrow and single-purpose, leave it unchanged.\n"
        "- Use the exact format: `- [ ] path/to/file.ext — short purpose`.\n"
        "- Stay in the dominant language already used in the plan.\n"
        "- Preserve `## Summary`, `## Test Command`, `## Dependencies`, and all other sections verbatim.\n"
        "- Do NOT write code, prose, or file contents — only the task checklist."
    )
    user = (
        f"Current PLAN.md:\n\n{original}\n\n{rules}\n\n"
        + (f"GOAL: {goal}\n\n" if goal else "")
        + "Output the revised PLAN.md now. Preserve ## Summary if present, then ## Files."
    )

    msgs = [{'role': 'system', 'content': system},
            {'role': 'user', 'content': user}]
    print("  Splitting...", flush=True)
    t0 = time.time()
    try:
        msg, stats = chat(model, msgs, None, float(timeout))
    except Exception as e:
        log("Split error: %s", e)
        return 1
    elapsed = time.time() - t0
    log("chat: prompt=%d gen=%d time=%.1fs",
        stats.prompt_tokens, stats.generated_tokens, elapsed)

    content = extract_plan_content(msg.get('content') or '')
    if not content or not re.search(r'(?m)^- \[([ x])\] ', content):
        log("Split: response had no valid task checklist — leaving PLAN.md unchanged.")
        return 1

    new_p = parse_content(content)
    new_pending = [t for t in new_p.tasks if not t.done and not t.in_progress]
    if len(new_pending) <= len(pending):
        log("Split: no new tasks produced (%d -> %d pending) — leaving PLAN.md unchanged.",
            len(pending), len(new_pending))
        return 0

    os.makedirs(LOG_DIR, exist_ok=True)
    backup = os.path.join(LOG_DIR, 'PLAN-before-split.md')
    Path(backup).write_text(original)
    Path('PLAN.md').write_text(content)
    log("Split: %d -> %d pending tasks. Backup saved to %s.",
        len(pending), len(new_pending), backup)
    print()
    print(content, flush=True)
    return 0


def flow(goal: str = '', model: str = '', target_dir: str = '') -> int:
    """Reorganize PLAN.md so each write step is immediately followed by a testable step."""
    import time
    if not model:
        model = os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        model = _select_model()
        if not model:
            return 1

    if target_dir:
        os.chdir(target_dir)
    if not Path('PLAN.md').exists():
        print("mu-flow: no PLAN.md found — run `mu plan` first", file=sys.stderr)
        return 1

    original = Path('PLAN.md').read_text()
    p = parse('PLAN.md')
    pending = [t for t in p.tasks if not t.done and not t.in_progress]
    if not pending:
        log("No pending tasks — nothing to flow.")
        return 0

    timeout = _COMPLEXITY_PLANNER['simple']
    log("Flowing %d pending task(s) into write+test pairs (timeout=%ds)", len(pending), timeout)

    system = (
        "You reorganize PLAN.md so every source file task is immediately followed by a "
        "testable step that exercises it. Output ONLY the raw PLAN.md markdown — "
        "no preamble, no explanation, no code fences."
    )
    rules = (
        "Rules:\n"
        "- Keep every `- [x]` (done) task exactly as-is, in the same position.\n"
        "- Build files (Makefile, Cargo.toml, go.mod, pyproject.toml, package.json, "
        "  CMakeLists.txt, etc.) stay at the top in their current order; no test pair needed.\n"
        "- Config-only files (.toml, .json, .yaml, .lock, requirements.txt, .mod, .sum) "
        "  need no test pair unless they ARE the build artifact.\n"
        "- For each pending source file (non-build, non-config, non-test), ensure the very "
        "  next task is a test or verification file that directly exercises it.\n"
        "  - If a test file for that source already exists in the plan, move it to immediately "
        "    follow the source file.\n"
        "  - If no test file exists, add a new task right after the source file using the "
        "    naming convention appropriate for the language (e.g. test_X.py for Python, "
        "    X_test.go for Go, X.test.ts for TypeScript, X_spec.rb for Ruby). "
        "    Give it a description like 'verify <source file>'.\n"
        "- Test files that are already paired must stay paired; do not scatter them.\n"
        "- Use the exact format: `- [ ] path/to/file.ext — short purpose`.\n"
        "- Preserve `## Summary`, `## Test Command`, `## Dependencies`, and all other sections verbatim.\n"
        "- Do NOT write code, prose, or file contents — only the task checklist."
    )
    user = (
        f"Current PLAN.md:\n\n{original}\n\n{rules}\n\n"
        + (f"GOAL: {goal}\n\n" if goal else "")
        + "Output the revised PLAN.md now. Preserve ## Summary if present, then ## Files."
    )

    msgs = [{'role': 'system', 'content': system},
            {'role': 'user', 'content': user}]
    print("  Flowing...", flush=True)
    t0 = time.time()
    try:
        msg, stats = chat(model, msgs, None, float(timeout))
    except Exception as e:
        log("Flow error: %s", e)
        return 1
    elapsed = time.time() - t0
    log("chat: prompt=%d gen=%d time=%.1fs",
        stats.prompt_tokens, stats.generated_tokens, elapsed)

    content = extract_plan_content(msg.get('content') or '')
    if not content or not re.search(r'(?m)^- \[([ x])\] ', content):
        log("Flow: response had no valid task checklist — leaving PLAN.md unchanged.")
        return 1

    new_p = parse_content(content)
    new_pending = [t for t in new_p.tasks if not t.done and not t.in_progress]
    if len(new_pending) < len(pending):
        log("Flow: pending count decreased (%d -> %d) — leaving PLAN.md unchanged.",
            len(pending), len(new_pending))
        return 1

    os.makedirs(LOG_DIR, exist_ok=True)
    backup = os.path.join(LOG_DIR, 'PLAN-before-flow.md')
    Path(backup).write_text(original)
    Path('PLAN.md').write_text(content)
    log("Flow: %d -> %d pending tasks. Backup saved to %s.",
        len(pending), len(new_pending), backup)
    print()
    print(content, flush=True)
    return 0


def assess(goal: str = '', model: str = '', target_dir: str = '') -> int:
    """Assess each plan step for goal alignment; revise or skip deviating tasks."""
    import time
    if not model:
        model = os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        model = _select_model()
        if not model:
            return 1

    if target_dir:
        os.chdir(target_dir)
    if not Path('PLAN.md').exists():
        print("mu-assess: no PLAN.md found — run `mu plan` first", file=sys.stderr)
        return 1

    original = Path('PLAN.md').read_text()
    p = parse('PLAN.md')
    pending = [t for t in p.tasks if not t.done and not t.in_progress]
    if not pending:
        log("No pending tasks — nothing to assess.")
        return 0

    timeout = _COMPLEXITY_PLANNER['simple']
    log("Assessing %d pending task(s) for goal alignment (timeout=%ds)",
        len(pending), timeout)

    system = (
        "You are a strict plan reviewer. Your job is to ensure every pending task "
        "directly serves the stated GOAL — removing or revising tasks that deviate, "
        "and enriching descriptions so each task has what the implementer needs. "
        "Output ONLY the raw PLAN.md markdown — no preamble, no explanation, no code fences."
    )
    rules = (
        "Rules:\n"
        "- Keep every `- [x]` (done) task exactly as-is, in the same position.\n"
        "- For each `- [ ]` pending task, ask: does this task directly contribute to the GOAL?\n"
        "  - If YES and description is sufficient: keep it unchanged.\n"
        "  - If YES but the description lacks needed context (interface, data structure, "
        "    function signature): enrich the description (after `—`) with that contract.\n"
        "  - If the task can be REVISED to better align with the GOAL: update its description.\n"
        "  - If the task clearly DEVIATES from the GOAL and cannot be salvaged: remove it entirely.\n"
        "- Only the description part (after `—`) of a kept task may change. The file path "
        "  (before `—`) must remain byte-for-byte identical.\n"
        "- Do NOT add new tasks.\n"
        "- Preserve the relative order of kept tasks.\n"
        "- Use the exact format: `- [ ] path/to/file.ext — description`.\n"
        "- Preserve `## Summary`, `## Test Command`, `## Dependencies`, and all other sections verbatim.\n"
        "- Do NOT write code, prose outside descriptions, or file contents."
    )
    goal_line = f"GOAL: {goal}\n\n" if goal else ""
    user = (
        f"{goal_line}Current PLAN.md:\n\n{original}\n\n{rules}\n\n"
        "Output the assessed PLAN.md now. Preserve ## Summary if present, then ## Files."
    )

    msgs = [{'role': 'system', 'content': system},
            {'role': 'user', 'content': user}]
    print("  Assessing...", flush=True)
    t0 = time.time()
    try:
        msg, stats = chat(model, msgs, None, float(timeout))
    except Exception as e:
        log("Assess error: %s", e)
        return 1
    elapsed = time.time() - t0
    log("chat: prompt=%d gen=%d time=%.1fs",
        stats.prompt_tokens, stats.generated_tokens, elapsed)

    content = extract_plan_content(msg.get('content') or '')
    if not content or not re.search(r'(?m)^- \[([ x])\] ', content):
        log("Assess: response had no valid task checklist — leaving PLAN.md unchanged.")
        return 1

    new_p = parse_content(content)
    orig_paths = {t.file_path for t in p.tasks}
    new_paths = [t.file_path for t in new_p.tasks]

    # All kept paths must be from the original set (no new tasks added)
    added = [fp for fp in new_paths if fp not in orig_paths]
    if added:
        log("Assess: response added new tasks (%s) — leaving PLAN.md unchanged.",
            ', '.join(added))
        return 1

    # Done tasks must all be preserved
    orig_done = [t.file_path for t in p.tasks if t.done]
    new_done = [t.file_path for t in new_p.tasks if t.done]
    if orig_done != new_done:
        log("Assess: done tasks were altered — leaving PLAN.md unchanged.")
        return 1

    orig_pending_paths = [t.file_path for t in p.tasks if not t.done]
    new_pending_paths = [t.file_path for t in new_p.tasks if not t.done]
    skipped = [fp for fp in orig_pending_paths if fp not in new_pending_paths]
    if skipped:
        log("Assess: skipped %d off-goal task(s): %s", len(skipped), ', '.join(skipped))

    merged = _merge_header_pairs(content)
    if merged != content:
        merged_paths = {t.file_path for t in parse_content(merged).tasks}
        header_merged = [fp for fp in new_pending_paths if fp not in merged_paths]
        log("Assess: merged %d header/impl pair(s): %s",
            len(header_merged), ', '.join(sorted(header_merged)))

    os.makedirs(LOG_DIR, exist_ok=True)
    backup = os.path.join(LOG_DIR, 'PLAN-before-assess.md')
    Path(backup).write_text(original)
    Path('PLAN.md').write_text(merged)
    log("Assess: plan updated (%d pending -> %d pending). Backup saved to %s.",
        len(orig_pending_paths), len(new_pending_paths), backup)
    print()
    print(merged, flush=True)
    return 0


def iterate(goal: str = '', model: str = '', target_dir: str = '',
            max_iter: int = 10) -> int:
    """Continue executing an existing PLAN.md without re-planning."""
    if target_dir:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        os.chdir(target_dir)
    if not Path('PLAN.md').exists():
        print("mu-iterate: no PLAN.md found — run `mu plan` or `mu agent` first",
              file=sys.stderr)
        return 1
    plan_text = Path('PLAN.md').read_text()
    reset_text = re.sub(r'^(- \[)~(\] )', r'\1 \2', plan_text, flags=re.MULTILINE)
    reset_count = plan_text.count('- [~]')
    if reset_count:
        Path('PLAN.md').write_text(reset_text)
        log("Reset %d in-progress task(s) to pending.", reset_count)
    if not goal:
        p = parse('PLAN.md')
        goal = p.plan_context[:120].strip() or 'implement the plan'

    challenges = get_challenges()
    if challenges:
        mit_model = model or os.environ.get('MU_AGENT_MODEL', '') or _select_model()
        if mit_model:
            _run_mitigation_pass(mit_model, parse('PLAN.md'), challenges, goal)
        clear_challenges()
        log("Cleared challenges section after mitigation pass.")

    return run(goal=goal, model=model, target_dir='', max_iter=max_iter, force=True,
               show_result=True)


def plan(goal: str, model: str = '', target_dir: str = '', force: bool = False) -> int:
    """Generate PLAN.md and write sketch stubs for each planned file."""
    if not model:
        model = os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        model = _select_model()
        if not model:
            return 1

    if target_dir:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        os.chdir(target_dir)

    err = _check_standalone(force)
    if err:
        print(err, file=sys.stderr)
        return 1

    complexity = detect_complexity(goal)
    planner_timeout = _COMPLEXITY_PLANNER[complexity]

    if Path('PLAN.md').exists():
        log("PLAN.md already exists — skipping task-planner.")
        err = _validate_existing_plan()
        if err:
            print(f"mu-plan: {err}", file=sys.stderr)
            return 1
    else:
        if not _run_planning_phase(goal, model, planner_timeout, complexity):
            return 1

    if strip_thinking_artifacts('PLAN.md'):
        log("WARNING: thinking artifact tokens stripped from PLAN.md")
    extracted = normalize_embedded_files('PLAN.md')
    if extracted:
        log("Extracted embedded files: %s", ', '.join(extracted))
    if normalize_test_command('PLAN.md'):
        log("Normalized test command for portability.")

    if os.environ.get('MU_LINT_PLAN') == '1':
        _lint_critique_pass('PLAN.md', goal, model, planner_timeout)

    if os.environ.get('MU_ENRICH_LESSONS') == '1':
        _inject_lessons_section('PLAN.md', goal)

    p = parse('PLAN.md')

    dropped = drop_runtime_artifacts('PLAN.md', p)
    if dropped:
        log("Dropped runtime artifact tasks: %s", ', '.join(dropped))
        p = parse('PLAN.md')

    minority = drop_minority_languages('PLAN.md', p)
    if minority:
        langs = plan_languages(parse('PLAN.md'))
        dominant = next(iter(langs)) if langs else '?'
        log("Dropped minority-language files (keeping %s): %s", dominant, ', '.join(minority))
        p = parse('PLAN.md')

    grounded = ground_plan('PLAN.md', p)
    if grounded:
        for change in grounded:
            log("Grounded plan against toolchain — %s", change)
        p = parse('PLAN.md')

    ok, missing = check_goal_alignment(p, goal)
    if not ok:
        log("WARNING: PLAN.md contains none of the goal keywords.")
    elif missing:
        log("NOTE: PLAN.md missing some goal terms: %s", ', '.join(missing))

    sketched = write_sketches(p, goal)
    if sketched:
        log("Sketched %d file(s): %s", len(sketched), ', '.join(sketched))
    else:
        log("No new stub files to create (all already exist or are build/runtime files).")

    return 0


def run(goal: str, model: str = '', target_dir: str = '',
        max_iter: int = 10, force: bool = False, show_result: bool = False) -> int:
    if not model:
        model = os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        model = _select_model()
        if not model:
            return 1

    archive_dir = (os.environ.get('MU_AGENT_ARCHIVE_DIR', '') or
                   str(Path.home() / '.mu' / 'sessions'))
    complexity = detect_complexity(goal)
    planner_timeout = _COMPLEXITY_PLANNER[complexity]
    writer_timeout = _COMPLEXITY_WRITER[complexity]

    if target_dir:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        os.chdir(target_dir)

    err = _check_standalone(force)
    if err:
        print(err, file=sys.stderr)
        return 1

    os.makedirs(LOG_DIR, exist_ok=True)
    sess = AgentSession(goal, archive_dir, LOG_DIR, max_iter)
    current_plan: Optional[Plan] = None
    exit_code = 0

    def _on_signal(sig, frame):
        print("\nInterrupted.", file=sys.stderr)
        sess.finalize(130, current_plan)
        sys.exit(130)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        if Path('PLAN.md').exists():
            log("PLAN.md already exists — skipping task-planner.")
            err = _validate_existing_plan()
            if err:
                print(f"mu-agent: {err}", file=sys.stderr)
                exit_code = 1
                return exit_code
        else:
            if not _run_planning_phase(goal, model, planner_timeout, complexity):
                exit_code = 1
                return exit_code

        if strip_thinking_artifacts('PLAN.md'):
            log("WARNING: thinking artifact tokens stripped from PLAN.md")
        extracted = normalize_embedded_files('PLAN.md')
        if extracted:
            log("Extracted embedded files: %s", ', '.join(extracted))
        if normalize_test_command('PLAN.md'):
            log("Normalized test command for portability.")

        if os.environ.get('MU_LINT_PLAN') == '1':
            _lint_critique_pass('PLAN.md', goal, model, planner_timeout)

        p = parse('PLAN.md')
        current_plan = p

        dropped = drop_runtime_artifacts('PLAN.md', p)
        if dropped:
            log("Dropped runtime artifact tasks: %s", ', '.join(dropped))
            p = parse('PLAN.md')
            current_plan = p

        grounded = ground_plan('PLAN.md', p)
        if grounded:
            for change in grounded:
                log("Grounded plan against toolchain — %s", change)
            p = parse('PLAN.md')
            current_plan = p

        ok, missing = check_goal_alignment(p, goal)
        if not ok:
            log("WARNING: PLAN.md contains none of the goal keywords.")
        elif missing:
            log("NOTE: PLAN.md missing some goal terms: %s", ', '.join(missing))

        os.makedirs(sess.archive_path, exist_ok=True)
        try:
            shutil.copy2('PLAN.md', os.path.join(sess.archive_path, 'PLAN-initial.md'))
        except OSError:
            pass

        project_dir = os.getcwd()
        auto_system = _build_autonomous_system(project_dir)
        if _python_relevant(goal, p):
            for _skill_name in ('python-env', 'python-writer'):
                _skill = _load_skill(_skill_name)
                if _skill:
                    auto_system += '\n\n' + _skill
                    log("Loaded %s skill (Python task).", _skill_name)
        if _makefile_relevant(goal, p):
            _skill = _load_skill('makefile-writer')
            if _skill:
                auto_system += '\n\n' + _skill
                log("Loaded makefile-writer skill.")
        if any(t.file_path.endswith('.go') for t in p.tasks):
            _skill = _load_skill('go-writer')
            if _skill:
                auto_system += '\n\n' + _skill
                log("Loaded go-writer skill.")

        for i in range(1, max_iter + 1):
            task = next_task(p)
            if task is None:
                log("All tasks complete.")
                break

            log("Iteration %d / %d: %s", i, max_iter, task.file_path)
            companion = _companion_header(task.description)
            write_prompt = _build_write_prompt(goal, task, p, companion)

            if not _run_writer(model, task.file_path, write_prompt, auto_system, writer_timeout,
                               companion):
                if not Path(task.file_path).exists():
                    log("Writer did not produce %s — retrying.", task.file_path)
                    record_challenge(f"writer did not produce {task.file_path} on first attempt")
                    retry = (f"Write file NOW: `{task.file_path}`\n"
                             f"You ONLY have the Write tool. Use it immediately.\n"
                             f"GOAL: {goal}\n{p.plan_context}")
                    if companion:
                        retry += (f"\nAlso write `{companion}` first (declarations), "
                                  f"then `{task.file_path}` (implementation).")
                    ref = relevant_files_context(p, task.file_path)
                    if ref:
                        retry += f"\n\n## Reference files (do not rewrite)\n{ref}"
                        if is_test_file(task.file_path):
                            retry += "\nCRITICAL: Call EXACT method/function names from the reference files above.\n"
                    if not _run_writer(model, task.file_path, retry, auto_system, writer_timeout,
                                       companion):
                        log("Iteration %d: %s not written after retry.", i, task.file_path)
                        exit_code = 3
                        return exit_code

            # Empty-output check: only stub a file the model left with no code.
            try:
                ext = Path(task.file_path).suffix.lower()
                is_config = ext in ('.txt', '.toml', '.mod', '.sum', '.json',
                                    '.yaml', '.yml', '.lock')
                if (_is_effectively_empty(task.file_path) and
                        not is_build_file(task.file_path) and not is_config):
                    log("No code written to %s — inserting minimal stub.", task.file_path)
                    record_challenge(f"no code written for {task.file_path}")
                    stub_content = _default_stub(ext, task.file_path)
                    Path(task.file_path).write_text(stub_content)
            except OSError:
                pass

            if task.file_path.endswith('.py'):
                if fix_test_import_module(task.file_path):
                    log("Fixed %s: corrected import module name.", task.file_path)

            if task.file_path.endswith('.go') or task.file_path.endswith('go.mod'):
                if apply_go_reflexes():
                    log("Resolved Go module dependencies (go mod tidy).")

            if (is_build_file(task.file_path) and
                    Path(task.file_path).name.lower() == 'makefile'):
                apply_makefile_reflexes(task.file_path)
                log("Applied Makefile reflexes to %s.", task.file_path)

            lint_cmd = _lint_command(task.file_path, p)
            if lint_cmd:
                lint_log = os.path.join(LOG_DIR, f"lint-iter-{i:02d}.log")
                if not _run_cmd(lint_cmd, lint_log):
                    if py_autofix(task.file_path) and _run_cmd(lint_cmd, lint_log):
                        log("Lint auto-fixed (autoflake): %s", task.file_path)
                    else:
                        lint_head = _head_file(lint_log, 60)
                        det_fixed = (
                            (fix_multiline_single_quote(task.file_path, lint_head) or
                             fix_missing_close_paren(task.file_path, lint_head)) and
                            _run_cmd(lint_cmd, lint_log)
                        )
                        if det_fixed:
                            log("Lint auto-fixed (deterministic): %s", task.file_path)
                        else:
                            record_challenge(
                                f"lint repair needed for {task.file_path}", lint_head)
                            _run_repair_lint(model, lint_cmd, task.file_path, lint_log, lint_head,
                                            auto_system, writer_timeout, goal)
                            if not _run_cmd(lint_cmd, lint_log):
                                log("Lint still failing after repair for %s.", task.file_path)
                                record_failed_repair(f"lint repair for {task.file_path}",
                                                     _head_file(lint_log, 5))
                                exit_code = 3
                                return exit_code
                            log("Lint passed after repair: %s", task.file_path)
                else:
                    log("Lint passed: %s", task.file_path)

            test_cmd = p.test_command
            if test_cmd and is_test_file(task.file_path) and not has_pending_build_file(p):
                test_log = os.path.join(LOG_DIR, f"tests-iter-{i:02d}.log")
                if not _run_cmd(test_cmd, test_log):
                    log("Tests failing after %s — invoking repair.", task.file_path)
                    record_challenge(
                        f"tests failed after writing {task.file_path}",
                        _tail_file(test_log, 5))
                    ok, iters = _run_test_repair_loop(model, test_cmd, test_log, p,
                                                      auto_system, writer_timeout, goal)
                    sess.repair_iters += iters
                    if not ok:
                        log("Tests still failing after repair for %s.", task.file_path)
                        record_failed_repair(f"test repair after writing {task.file_path}",
                                             _tail_file(test_log, 5))
                        exit_code = 3
                        return exit_code

            mark_task_done('PLAN.md', task.file_path)
            log("Marked done: %s", task.file_path)
            print(f"\n  Iteration {i} done: {task.file_path}\n", flush=True)
            if show_result:
                _print_result(task.file_path)
                if companion and Path(companion).exists():
                    _print_result(companion)
            p = parse('PLAN.md')
            current_plan = p

        if not tasks_remaining(p):
            err, iters = _final_test_gate(model, p, auto_system, writer_timeout, goal)
            sess.repair_iters += iters
            if err:
                exit_code = 3
                return exit_code
            log("Goal complete.")
            print("\n  Goal complete!\n", flush=True)
            exit_code = 0
            return exit_code

        print(f"mu-agent: warning: reached max iterations ({max_iter}) with tasks remaining",
              file=sys.stderr)
        exit_code = 2
        return exit_code
    finally:
        sess.finalize(exit_code, current_plan)


# ── Planning ──────────────────────────────────────────────────────────────────

def _run_planning_phase(goal: str, model: str, planner_timeout: int, complexity: str) -> bool:
    log("Planning: %s (timeout=%ds complexity=%s)", goal, planner_timeout, complexity)
    for attempt in range(1, 4):
        if attempt > 1:
            log("Planner attempt %d / 3 (previous plan had wrong format)", attempt)
            if Path('PLAN.md').exists():
                Path('PLAN.md').unlink()
        _run_planner(goal, model, planner_timeout)
        if not Path('PLAN.md').exists():
            log("Attempt %d: no PLAN.md produced", attempt)
            continue
        data = Path('PLAN.md').read_bytes()
        if re.search(rb'(?m)^- \[[ x~]\]', data):
            break
        log("Attempt %d: PLAN.md has no task checklist (wrong format) — retrying", attempt)
    else:
        print("mu-agent: task-planner did not produce a valid PLAN.md after 3 attempts",
              file=sys.stderr)
        return False
    log("PLAN.md created.")
    print()
    print(Path('PLAN.md').read_text(), flush=True)
    return True


def _run_planner(goal: str, model: str, planner_timeout: int) -> None:
    import time
    project_dir = os.getcwd()
    skill = _load_skill('task-planner')
    goal_lower = goal.lower()
    example = (
        "## Summary\n"
        "Implement a command-line tool in C that prints a greeting. "
        "Build with make and verify with a direct invocation.\n\n"
        "## Files\n"
        "- [ ] main.c — C source defining `main` that prints the greeting\n"
        "- [ ] Makefile — build rules producing the `main` binary\n\n"
        "## Test Command\nmake && ./main\n\n"
        "## Dependencies\nclang>=14, make>=4"
    )
    challenges_block = _load_challenges_for_planner()
    rules = [
        "- Start with a `## Summary` section: 2-4 sentences describing the approach, "
        "key design decisions, and how correctness will be verified.",
        "- Then list ONLY filenames with `- [ ] ` prefix under `## Files`. "
        "Do NOT write file contents or code.",
        "- File paths must appear as bare tokens (e.g. `main.c`, `src/lib.rs`) "
        "with NO surrounding backticks, quotes, or angle brackets.",
        "- Every file entry MUST include a short description after `— ` that names the "
        "concrete entities (functions, classes, types) the file exposes or consumes. "
        "Backticks are fine around entity names in the description, just not around the path.",
        "- Entity names MUST be consistent across tasks: if file A's description says "
        "it defines `TodoManager`, file B must not refer to `TodoStore` for the same thing.",
        "- The `## Dependencies` section MUST list each tool/library with a concrete "
        "minimum version (e.g. `clang>=14`, `flask>=3`, `sqlite>=3.40`). "
        "Do NOT write bare names with no version.",
        "- No code blocks. Allowed headers: ## Summary / ## Files / ## Test Command / ## Dependencies.",
    ]
    challenges_text = (
        "Known recurring failure modes in this project — read these before "
        "drafting the plan and structure the plan so it does not trip them:\n\n"
        f"{challenges_block}\n\n"
    ) if challenges_block else ""

    # Inject language-specific writer skills at plan time when detectable from goal.
    # This ensures test-command guidance (e.g. "use go test not ./main") reaches
    # the planner before it locks in the Test Command field.
    extra_skills: list[str] = []
    if any(k in goal_lower for k in ('gin', ' go ', 'golang', '.go', 'go http')):
        gs = _load_skill('go-writer')
        if gs:
            extra_skills.append(gs)

    if os.environ.get('MU_PROMPT_CACHE') == '1':
        # Cache-friendly layout: all stable content (instructions, skill, rules,
        # challenges, example) goes in the system message as a byte-identical
        # prefix across problems, so LM Studio reuses its KV cache instead of
        # re-prefilling ~1k tokens each plan. Only the volatile DIR/GOAL trails.
        system = ("You are a planning agent.\n"
                  "Output ONLY the raw PLAN.md markdown. No preamble, no explanation, "
                  "no code blocks. Begin with ## Summary, then ## Files.")
        if skill:
            system += '\n\n' + skill
        for es in extra_skills:
            system += '\n\n' + es
        system += "\n\nRules:\n" + '\n'.join(rules)
        if challenges_text:
            system += "\n\n" + challenges_text.rstrip()
        system += f"\n\nExample output:\n{example}"
        user_msg = (f"DIR: {project_dir}\nGOAL: {goal}\n\n"
                    "Now output the PLAN.md for the goal above. Start with ## Summary.")
    else:
        system = (f"You are a planning agent in: {project_dir}\n"
                  "Output ONLY the raw PLAN.md markdown. No preamble, no explanation, "
                  "no code blocks. Begin with ## Summary, then ## Files.")
        if skill:
            system += '\n\n' + skill
        for es in extra_skills:
            system += '\n\n' + es
        user_msg = (
            f"Create a PLAN.md task list for this goal.\n\n"
            f"GOAL: {goal}\nDIR: {project_dir}\n\n"
            f"Rules:\n" + '\n'.join(rules) + "\n\n"
            + challenges_text
            + f"Example output:\n{example}\n\n"
            + "Now output the PLAN.md for the goal above. Start with ## Summary."
        )
    msgs = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user_msg},
    ]
    print("  Planning...", flush=True)
    t0 = time.time()
    try:
        msg, stats = chat(model, msgs, None, float(planner_timeout))
        elapsed = time.time() - t0
        log("chat: prompt=%d gen=%d time=%.1fs", stats.prompt_tokens, stats.generated_tokens, elapsed)
        log("Planner: %.1fs", elapsed)
    except Exception as e:
        log("Planner error: %s", e)
        return
    log("Planner raw: %r", (msg['content'] or '')[:400])
    content = extract_plan_content(msg['content'])
    if not content:
        log("Planner: empty response")
        return
    try:
        Path('PLAN.md').write_text(content)
    except OSError as e:
        log("Planner: could not write PLAN.md: %s", e)


# ── Writer ────────────────────────────────────────────────────────────────────

def _run_writer(model: str, target_file: str, prompt: str,
                autonomous_system: str, writer_timeout: int,
                companion: str = '') -> bool:
    Path(target_file).parent.mkdir(parents=True, exist_ok=True)
    if companion:
        Path(companion).parent.mkdir(parents=True, exist_ok=True)
        rules = (f"REMINDER: Write TWO files for this task.\n"
                 f"1. Call Write for `{companion}` first — declarations, types, and "
                 f"function prototypes only (no implementations).\n"
                 f"2. Call Write for `{target_file}` second — full implementation.\n"
                 f"Complete, runnable content. Stop immediately after the second Write.")
    else:
        rules = ("REMINDER: Call Write ONCE for the file you are given. "
                 "Complete, runnable content. Stop immediately after. Nothing else.")
    sess = Session(autonomous_system + '\n\n' + rules)
    sess.tool_set = tools.WRITER
    ok, err = sess.run(model, prompt, 'Writing', 15, target_file, float(writer_timeout))
    if err:
        log("Writer: %s", err)
    return ok


# ── Repair ────────────────────────────────────────────────────────────────────

_LANG_REPAIR_SKILL: dict[str, str] = {
    'Python': 'repair-python',
    'C': 'repair-c',
    'C++': 'repair-c',
    'Go': 'repair-go',
    'Rust': 'repair-rust',
}


def _load_repair_skills(p: Plan) -> str:
    """Return concatenated repair skills for all languages present in the plan."""
    langs = plan_languages(p)
    seen: set[str] = set()
    parts: list[str] = []
    for lang in langs:
        skill_name = _LANG_REPAIR_SKILL.get(lang, '')
        if skill_name and skill_name not in seen:
            seen.add(skill_name)
            content = _load_skill(skill_name)
            if content:
                parts.append(content)
    return '\n\n'.join(parts)


def _run_test_repair_loop(model: str, test_cmd: str, test_log: str, p: Plan,
                          autonomous_system: str, writer_timeout: int, goal: str,
                          ) -> tuple[bool, int]:
    """Run the repair loop against the test gate; return (passed, repair_iters)."""
    repair_skills = _load_repair_skills(p)
    system = autonomous_system + ('\n\n' + repair_skills if repair_skills else '')
    sess = Session(system + '\n\n' + _REPAIR_LOOP_RULES)
    sess.tool_set = tools.REPAIR

    def run_test() -> tuple[bool, str]:
        return _run_cmd(test_cmd, test_log), _tail_file(test_log, 60)

    def reapply() -> None:
        for t in p.tasks:
            if (Path(t.file_path).exists() and is_build_file(t.file_path) and
                    Path(t.file_path).name.lower() == 'makefile'):
                apply_makefile_reflexes(t.file_path)
        apply_go_reflexes()  # resolve Go module deps before each build attempt

    return sess.repair_loop(model, goal, _REPAIR_MAX_ITERS, float(writer_timeout),
                            run_test, reapply, _repair_context(p), _syntax_check)


def _syntax_check(path: str) -> tuple[bool, str]:
    """Cheap, dependency-free parse check of a single file for the repair loop's
    rollback. Returns (ok, error_text).

    Only languages with a pure-syntax parser are checked — Python (``ast.parse``)
    and Go (``gofmt -e``) — because those parse one file without resolving
    imports or cross-file symbols, so they never false-positive on a valid file
    that references a sibling. Every other extension returns ``(True, '')`` (no
    rollback); the lint and test gates remain the authority there. A parser is a
    language oracle, not a problem-specific rule.
    """
    ext = Path(path).suffix.lower()
    try:
        if ext == '.py':
            import ast
            ast.parse(Path(path).read_text())
            return True, ''
        if ext == '.go' and shutil.which('gofmt'):
            r = subprocess.run(['gofmt', '-e', path], capture_output=True,
                               text=True, timeout=15)
            return r.returncode == 0, (r.stderr or r.stdout)[:500]
    except SyntaxError as e:
        return False, f"{type(e).__name__}: {e}"
    except (OSError, ValueError, subprocess.SubprocessError):
        return True, ''
    return True, ''


def _repair_context(p: Plan) -> str:
    """Show the repair model the project's actual files, bounded in size.

    The repair loop otherwise sees only the test command's output. A small model
    cannot fix a root cause it can never see — e.g. a test that shares on-disk
    state, or a mismatch between a test's expectations and the source. Surfacing
    the real files lets it diagnose instead of editing blind. General by design:
    it dumps whatever files the plan names, with no problem-specific content.
    Source files are shown before test files so the model reads the code under
    test alongside the assertions that exercise it.
    """
    per_file, total_budget = 2500, 8000
    blocks, used = [], 0
    for t in sorted(p.tasks, key=lambda t: is_test_file(t.file_path)):
        fp = t.file_path
        if not Path(fp).exists():
            continue
        try:
            body = Path(fp).read_text()
        except OSError:
            continue
        if len(body) > per_file:
            body = body[:per_file] + '\n... [truncated]'
        block = f'### {fp}\n```\n{body}\n```\n'
        if used + len(block) > total_budget:
            break
        blocks.append(block)
        used += len(block)
    if not blocks:
        return ''
    return '## Current project files (read these before editing)\n' + '\n'.join(blocks) + '\n\n'


def _run_repair_lint(model: str, lint_cmd: str, file_path: str, lint_log: str, lint_head: str,
                     autonomous_system: str, writer_timeout: int, goal: str) -> None:
    file_content = ''
    try:
        data = Path(file_path).read_text()
        if len(data) < 3000:
            file_content = f'\n\nCurrent file `{file_path}`:\n```\n{data}\n```'
    except OSError:
        pass
    is_sq = ('missing closing quote in string literal' in lint_head or
              ('invalid-syntax' in lint_head and "execute('" in lint_head))
    is_mp = 'invalid-syntax' in lint_head and 'execute(' in lint_head and not is_sq
    # Detect missing import errors (generic Python import hint)
    is_missing_import = any(kw in lint_head for kw in ('ImportError:', 'NameError:'))
    hint = ''
    if is_sq:
        hint = "\n\nHINT: multi-line SQL string using single quotes — use triple-quoted strings."
    elif is_mp:
        hint = "\n\nHINT: missing closing ')' after triple-quoted string in execute() call."
    elif is_missing_import:
        # Extract missing name if possible
        m = re.search(r"(?:ImportError:.*?['\"](\w+)['\"]|NameError: name ['\"](\w+)['\"] is not defined)", lint_head)
        if m:
            missing_name = m.group(1) or m.group(2)
            hint = f"\n\nHINT: missing import – add `import {missing_name}` (or appropriate from‑module import) at the top of the file."
        else:
            hint = "\n\nHINT: missing import – add the required import at the top of the file."
    # Iterative repair: re-run the linter after each edit and feed the new output
    # back, with the file shown and syntax-breaking edits rolled back. Same loop
    # the test gate uses — a one-shot pass couldn't converge on multi-step fixes.
    context = (f"## Fix the lint/compile error in {file_path}. Only edit {file_path}; "
               f"do not create files.{hint}{file_content}{repair_history()}\n\n")
    sess = Session(autonomous_system + '\n\n' + _REPAIR_LOOP_RULES)
    sess.tool_set = tools.REPAIR

    def run_test() -> tuple[bool, str]:
        return _run_cmd(lint_cmd, lint_log), _head_file(lint_log, 60)

    sess.repair_loop(model, goal, _REPAIR_MAX_ITERS, float(writer_timeout),
                     run_test, None, context, _syntax_check)


def _run_mitigation_pass(model: str, p: Plan, challenges: str, goal: str) -> None:
    test_cmd = p.test_command
    if not test_cmd:
        log("Mitigation pass: no test command — skipping.")
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    mit_log = os.path.join(LOG_DIR, 'tests-mitigation.log')
    log("Challenges found from previous run — running mitigation pass.")
    if _run_cmd(test_cmd, mit_log):
        log("Mitigation pass: tests passing — challenges already resolved.")
        return
    log("Mitigation pass: tests failing — attempting repair.")
    complexity = detect_complexity(goal)
    writer_timeout = _COMPLEXITY_WRITER[complexity]
    project_dir = os.getcwd()
    challenge_context = (f"\n\n## Challenges from previous run\n{challenges}\n\n"
                         "Address these challenges as you repair.")
    auto_system = _build_autonomous_system(project_dir) + challenge_context
    ok, _ = _run_test_repair_loop(model, test_cmd, mit_log, p, auto_system, writer_timeout, goal)
    if ok:
        log("Mitigation pass: challenges resolved.")
    else:
        log("Mitigation pass: could not fully resolve challenges — proceeding anyway.")


def _final_test_gate(model: str, p: Optional[Plan], autonomous_system: str,
                     writer_timeout: int, goal: str) -> tuple[Optional[str], int]:
    """Run the final test gate with repair loop; return (error_msg_or_None, repair_iters)."""
    test_cmd = (p.test_command if p else '') or ''
    if not test_cmd:
        # Planner sometimes omits '## Test Command' (e.g. wraps output in code
        # fences and drops sections). Skipping the gate then declares success
        # without ever testing — a false positive. If the plan has test files,
        # run them; only skip when there is genuinely nothing to verify.
        test_files = [t.file_path for t in (p.tasks if p else []) if is_test_file(t.file_path)]
        if test_files:
            test_cmd = 'pytest ' + ' '.join(test_files)
            log("No '## Test Command' — defaulting to: %s", test_cmd)
        else:
            log("No '## Test Command' and no test files — skipping final test gate.")
            return None, 0
    test_log = os.path.join(LOG_DIR, 'tests-final.log')
    ok, iters = _run_test_repair_loop(model, test_cmd, test_log, p, autonomous_system,
                                      writer_timeout, goal)
    if ok:
        return None, iters
    record_failed_repair("final test gate: repair loop exhausted", _tail_file(test_log, 30))
    print("\n  Tests still failing after repair loop. Giving up.\n", flush=True)
    return "final tests failed", iters


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_standalone(force: bool) -> Optional[str]:
    if Path('PLAN.md').exists() or force:
        return None
    try:
        entries = [e for e in os.scandir('.') if not e.name.startswith('.')]
    except OSError:
        return None
    file_count = len(entries)
    git_commits = 0
    if Path('.git').exists():
        try:
            git_commits = int(subprocess.check_output(
                ['git', 'rev-list', '--count', 'HEAD'],
                text=True, stderr=subprocess.DEVNULL).strip())
        except Exception:
            pass
    if file_count > 5 or git_commits > 0:
        wd = os.getcwd()
        return (f"mu-agent: '{wd}' looks like an existing project "
                f"(files: {file_count}, git commits: {git_commits})\n"
                f"  Use --dir PATH for a fresh directory, or --force to proceed anyway.")
    return None


def _validate_existing_plan() -> Optional[str]:
    try:
        content = Path('PLAN.md').read_text()
    except OSError as e:
        return str(e)
    if re.search(r'(?m)^### Group ', content):
        return "PLAN.md uses old '### Group N' format — delete it to re-plan"
    if not re.search(r'(?m)^- \[([ x~])\]', content):
        return "existing PLAN.md has no task checklist — delete it to re-plan"
    return None


def _build_autonomous_system(project_dir: str) -> str:
    return f"""You are a code-writing agent running autonomously in: {project_dir}

ROLE: You receive one task — write a specific file — and execute it immediately.

PROTOCOL:
1. Call the Write tool exactly once with the requested path and complete file contents.
2. Derive all implementation details from the GOAL and PLAN.md. Make your own decisions — never ask for clarification.
3. Stop the moment Write completes. No summary, no explanation, no additional output.

OFF-LIMITS:
- Never ask questions or request confirmation.
- Never write files other than the one explicitly requested.
- No arbitrary network calls (curl, wget, fetch, http, etc.).
- Only install packages explicitly listed in PLAN.md.
- Never read from stdin unless the goal explicitly says "interactive"."""


def _makefile_relevant(goal: str, p: Plan) -> bool:
    """True when the plan includes a Makefile or the test command invokes make."""
    if any(Path(t.file_path).name == 'Makefile' for t in p.tasks):
        return True
    blob = f"{goal}\n{p.test_command}".lower()
    return 'make ' in blob or blob.strip().startswith('make')


def _python_relevant(goal: str, p: Plan) -> bool:
    """True when the task involves Python, so the python-env skill applies.

    Generic signal, not problem-specific: any .py file in the plan, or a test
    command / goal that names the Python toolchain (pytest, pip, python,
    requirements.txt). Non-Python tasks (C, Go, Rust, C#) never match.
    """
    if any(t.file_path.endswith('.py') for t in p.tasks):
        return True
    blob = f"{goal}\n{p.test_command}\n{p.plan_context}".lower()
    return any(k in blob for k in ('pytest', 'pip install', 'pip3 ',
                                   'python', 'requirements.txt'))


def _build_write_prompt(goal: str, task, p: Plan, companion: str = '') -> str:
    parts = [f"GOAL: {goal}\n\n## Plan\n{p.plan_context}"]
    existing = relevant_files_context(p, task.file_path)
    if existing:
        parts.append(f"\n\n## Reference files (do not rewrite)\n{existing}")
        if is_test_file(task.file_path):
            parts.append("\nCRITICAL: Call EXACT method/function names from the reference files above. Do not rename or alias them.\n")
    parts.append(f"\n\n## Task\nWrite file: `{task.file_path}`")
    if companion:
        parts.append(f"\nAlso write: `{companion}` — declare the interface (types and "
                     f"function prototypes) before writing the implementation.")
    if task.description:
        parts.append(f"\nPurpose: {task.description}")
    if is_test_file(task.file_path):
        parts.append("\n\nTEST ISOLATION: give each test its own fresh state. Construct the "
                     "code under test with an in-memory or per-test temporary store (e.g. a "
                     "`:memory:` database, or a tmp file/dir via a fixture), or reset state in "
                     "setup/teardown. Never assert exact row counts or contents against a store "
                     "that other tests in the file also write — they will accumulate and fail.")
    if Path(task.file_path).name.lower() == 'makefile':
        parts.append("\n\nMAKEFILE RULES: every name used as a prerequisite must have its own "
                     "`target:` rule or be a real file — if you write `all: run`, you must also "
                     "define a `run:` rule. Recipe lines are tab-indented.")
    if is_build_file(task.file_path):
        pending = pending_source_files(p, task.file_path)
        if pending:
            parts.append(f"\n\nCRITICAL — use these EXACT file paths from PLAN.md in "
                         f"`{task.file_path}`:\n{pending}")
    parts.append("""

## Steps
1. Determine the complete, correct content for the file from the goal and plan.
2. Call Write with the full, runnable content.
3. Stop immediately after Write — no other output.""")
    return ''.join(parts)


def _lint_command(file_path: str, p: Plan) -> str:
    if is_build_file(file_path):
        return ''
    ext = Path(file_path).suffix.lower()
    has_makefile = any(Path(t.file_path).name.lower() == 'makefile' for t in p.tasks)
    has_cargo = any(Path(t.file_path).name.lower() == 'cargo.toml' for t in p.tasks)
    has_tsconfig = any(Path(t.file_path).name.lower().startswith('tsconfig') for t in p.tasks)
    if ext == '.py':
        # pyflakes (pure-Python) covers F-codes and syntax errors; run it with
        # mu's own interpreter so the target venv needn't have it installed.
        if importlib.util.find_spec('pyflakes'):
            return f"{sys.executable} -m pyflakes {file_path}"
        return f"python3 -m py_compile {file_path}"
    if ext == '.go':
        if has_makefile:
            return ''
        d = str(Path(file_path).parent)
        return 'go vet .' if d == '.' else f"go vet ./{d}/..."
    if ext == '.rs':
        if has_cargo:
            return 'cargo check'
        stem = Path(file_path).stem
        return (f"rustc --edition=2021 -Dwarnings {file_path} "
                f"-o /tmp/mu_lint_{stem} && rm -f /tmp/mu_lint_{stem}")
    if ext in ('.ts', '.tsx'):
        if not shutil.which('tsc'):
            return ''
        return 'tsc --noEmit' if has_tsconfig else \
               f"tsc --noEmit --strict --target ES2020 --module commonjs {file_path}"
    if ext in ('.c', '.h'):
        return '' if has_makefile else f"gcc -fsyntax-only -Wall {file_path}"
    if ext in ('.cpp', '.cc', '.cxx', '.hpp'):
        return '' if has_makefile else f"g++ -fsyntax-only -Wall {file_path}"
    return ''


def _run_cmd(cmd: str, log_file: str, env: dict | None = None) -> bool:
    """Run a shell command, capturing stdout/stderr to ``log_file``.

    ``env`` optionally supplies environment variables (e.g., a modified ``PATH``
    to point at a temporary virtual‑env). If ``env`` is ``None`` the current
    process environment is used.
    """
    os.makedirs(os.path.dirname(log_file) or '.', exist_ok=True)
    try:
        with open(log_file, 'w') as f:
            return subprocess.run(['bash', '-c', cmd], stdout=f, stderr=f,
                                  timeout=120, env=env).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False

def _tail_file(path: str, n: int) -> str:
    try:
        lines = Path(path).read_text().splitlines()
        return '\n'.join(lines[-n:]) if len(lines) > n else '\n'.join(lines)
    except OSError:
        return ''


def _head_file(path: str, n: int) -> str:
    try:
        lines = Path(path).read_text().splitlines()
        return '\n'.join(lines[:n]) if len(lines) > n else '\n'.join(lines)
    except OSError:
        return ''


_IMPL_EXTS = frozenset({'.c', '.cpp', '.cc', '.cxx'})
_HEADER_EXTS = frozenset({'.h', '.hpp', '.hh', '.hxx'})


def _merge_header_pairs(plan_text: str) -> str:
    """Merge pending .h tasks into their paired pending .c/.cpp tasks.

    When both foo.h and foo.c are pending, the .h task is removed and a note
    is appended to the .c task so both files are written in one step.
    Only pairs where BOTH tasks are pending are merged; done tasks are left alone.
    """
    pending_re = re.compile(r'^- \[ \] (\S+)', re.MULTILINE)

    pending_h: dict[str, str] = {}  # stem -> file_path
    pending_c: dict[str, str] = {}

    for m in pending_re.finditer(plan_text):
        fp = m.group(1)
        ext = Path(fp).suffix.lower()
        stem = str(Path(fp).parent / Path(fp).stem)
        if ext in _HEADER_EXTS:
            pending_h[stem] = fp
        elif ext in _IMPL_EXTS:
            pending_c[stem] = fp

    pairs: dict[str, str] = {}  # h_fp -> c_fp
    for stem, h_fp in pending_h.items():
        if stem in pending_c:
            pairs[h_fp] = pending_c[stem]

    if not pairs:
        return plan_text

    c_to_h = {c: h for h, c in pairs.items()}
    result: list[str] = []
    for line in plan_text.splitlines(keepends=True):
        m = re.match(r'^(- \[ \] )(\S+)(.*?)(\n?)$', line)
        if not m:
            result.append(line)
            continue
        fp, rest, nl = m.group(2), m.group(3).rstrip(), m.group(4)
        if fp in pairs:
            continue  # remove the .h task line
        if fp in c_to_h:
            h_fp = c_to_h[fp]
            note = f'also write `{h_fp}`'
            rest = rest + f'; {note}' if rest.strip() else f' — {note}'
            result.append(f'{m.group(1)}{fp}{rest}{nl}')
        else:
            result.append(line)
    return ''.join(result)


def _companion_header(description: str) -> str:
    """Return the companion header path from a merged task description, or ''."""
    m = re.search(r'also write `([^`]+\.(?:h|hpp|hh|hxx))`', description or '')
    return m.group(1) if m else ''


def _print_result(file_path: str, max_lines: int = 60) -> None:
    try:
        lines = Path(file_path).read_text().splitlines()
    except OSError:
        return
    shown = lines[:max_lines]
    truncated = len(lines) > max_lines
    print(f"\n--- {file_path} ---", flush=True)
    print('\n'.join(shown), flush=True)
    if truncated:
        print(f"... [{len(lines) - max_lines} more lines]", flush=True)
    print("---\n", flush=True)


def _inject_lessons_section(plan_path: str, goal: str) -> None:
    """Append a `## Lessons From Prior Runs` section to plan_path.

    No-op if the enrich module declines (missing deps, sparse archive,
    no matching lesson). Honours the corroboration and concentration
    guards inside enrich.lessons_for.
    """
    try:
        from mu.enrich import lessons_for, render_lessons_section
    except ImportError:
        return
    try:
        lessons = lessons_for(goal)
    except Exception as e:
        log("enrich: lessons_for raised %s", e)
        return
    section = render_lessons_section(lessons)
    if not section:
        return
    try:
        text = Path(plan_path).read_text(encoding='utf-8')
    except OSError:
        return
    if '## Lessons From Prior Runs' in text:
        return
    new_text = text.rstrip('\n') + '\n\n' + section
    try:
        Path(plan_path).write_text(new_text, encoding='utf-8')
        log("enrich: injected %d lesson(s) into PLAN.md", len(lessons))
    except OSError:
        pass


def _lint_critique_pass(plan_path: str, goal: str, model: str,
                        planner_timeout: int) -> None:
    """Lint the plan and, on warnings, ask the planner to revise it once.

    The spaCy plan-lint arm: run the deterministic
    plan linter (`mu.lint`), feed any warnings back to the planner LLM as a
    critique, and replace PLAN.md with the revised output. A single pass —
    the revised plan is re-linted for diagnostics only, never re-prompted.

    No-op if the lint module is unavailable or the plan trips no checks.
    Gated by the caller via MU_LINT_PLAN, so the default planner path never
    imports `mu.lint` or calls an extra LLM turn.
    """
    try:
        from mu.lint import lint_plan, render_warnings
    except ImportError:
        return
    try:
        warnings = lint_plan(plan_path)
    except Exception as e:
        log("lint: lint_plan raised %s", e)
        return
    if not warnings:
        return
    log("lint: plan tripped %d check(s): %s", len(warnings), ' | '.join(warnings))

    try:
        original = Path(plan_path).read_text(encoding='utf-8')
    except OSError:
        return
    project_dir = os.getcwd()
    system = (f"You are a planning agent in: {project_dir}\n"
              "Output ONLY the raw PLAN.md markdown. No preamble, no explanation, "
              "no code blocks. Begin with ## Summary, then ## Files.")
    skill = _load_skill('task-planner')
    if skill:
        system += '\n\n' + skill
    user_msg = (f"GOAL: {goal}\n\nCurrent PLAN.md:\n\n{original}\n\n"
                f"{render_warnings(warnings)}")
    msgs = [{'role': 'system', 'content': system},
            {'role': 'user', 'content': user_msg}]
    try:
        msg, _ = chat(model, msgs, None, float(planner_timeout))
    except Exception as e:
        log("lint: critique chat failed: %s", e)
        return
    content = extract_plan_content(msg['content'])
    if not content or not re.search(r'(?m)^- \[[ x~]\]', content):
        log("lint: critique response had no valid checklist — keeping original plan")
        return
    try:
        Path(plan_path).write_text(content)
    except OSError as e:
        log("lint: could not write revised PLAN.md: %s", e)
        return
    log("lint: plan revised after critique")

    # The critique output bypasses the generation-phase normalizers, so re-run
    # them on the revision before it is parsed downstream.
    if strip_thinking_artifacts(plan_path):
        log("WARNING: thinking artifact tokens stripped from revised PLAN.md")
    if normalize_embedded_files(plan_path):
        log("Extracted embedded files from revised PLAN.md")
    if normalize_test_command(plan_path):
        log("Normalized test command in revised PLAN.md")

    try:
        remaining = lint_plan(plan_path)
        if remaining:
            log("lint: %d warning(s) remain after revision", len(remaining))
    except Exception:
        pass


def _load_challenges_for_planner() -> str:
    """Return the Open section of project CHALLENGES.md, or '' if unavailable."""
    try:
        text = Path('CHALLENGES.md').read_text(encoding='utf-8')
    except OSError:
        return ''
    if '## Open' not in text:
        return ''
    section = text.split('## Open', 1)[1]
    section = section.split('## Resolved', 1)[0]
    return section.strip()


def _load_skill(name: str) -> str:
    default_skills_dir = Path(__file__).parent.parent.parent / 'skills'
    skills_dir = Path(os.environ.get('MU_SKILLS_DIR', '') or default_skills_dir)
    skill_path = skills_dir / name / 'SKILL.md'
    if not skill_path.is_file():
        return ''
    content = skill_path.read_text(encoding='utf-8')
    if content.startswith('---'):
        end = content.find('\n---', 3)
        if end >= 0:
            content = content[end + 4:].strip()
    return content
