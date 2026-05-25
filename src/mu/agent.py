"""Autonomous coding agent orchestration."""

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
from mu.client import chat, list_models, load_model, recommended_model
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
from mu.sensors import (apply_go_sensors, apply_makefile_sensors,
                        fix_missing_close_paren, fix_multiline_single_quote,
                        fix_test_import_module, ruff_autofix, _run_ast_fixers)
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
    if recommended:
        log("Recommended model %s not loaded — loading via LM Studio...", recommended)
        if load_model(recommended):
            loaded = list_models()
            model = _match_loaded(loaded, recommended) or recommended
            log("Using recommended model: %s", model)
            return model
        log("Could not load recommended model — falling back.")
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
            skill = _load_skill('python-env')
            if skill:
                auto_system += '\n\n' + skill
                log("Loaded python-env skill (Python task).")

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

            # Near-empty check
            try:
                size = Path(task.file_path).stat().st_size
                ext = Path(task.file_path).suffix.lower()
                is_config = ext in ('.txt', '.toml', '.mod', '.sum', '.json',
                                    '.yaml', '.yml', '.lock')
                if size < 100 and not is_build_file(task.file_path) and not is_config:
                    log("Near-empty %s (%d bytes) — inserting minimal stub.", task.file_path, size)
                    record_challenge(f"near-empty file written for {task.file_path} ({size} bytes)")
                    # Delete the empty/near‑empty file
                    Path(task.file_path).unlink(missing_ok=True)
                    # Write a generic language‑specific stub so the file is no longer near‑empty
                    stub_content = _default_stub(ext, task.file_path)
                    Path(task.file_path).write_text(stub_content)
                    # Optionally, give the model a chance to improve the file later via normal repair loop.
            except OSError:
                pass

            if task.file_path.endswith('.py'):
                if fix_test_import_module(task.file_path):
                    log("Fixed %s: corrected import module name.", task.file_path)

            if task.file_path.endswith('.go') or task.file_path.endswith('go.mod'):
                if apply_go_sensors():
                    log("Resolved Go module dependencies (go mod tidy).")

            if (is_build_file(task.file_path) and
                    Path(task.file_path).name.lower() == 'makefile'):
                apply_makefile_sensors(task.file_path)
                log("Applied Makefile sensors to %s.", task.file_path)

            # Run generic AST‑based fixers for any file type
            if _run_ast_fixers(task.file_path):
                log("AST fixers applied to %s", task.file_path)

            lint_cmd = _lint_command(task.file_path, p)
            if lint_cmd:
                lint_log = os.path.join(LOG_DIR, f"lint-iter-{i:02d}.log")
                if not _run_cmd(lint_cmd, lint_log):
                    if ruff_autofix(task.file_path) and _run_cmd(lint_cmd, lint_log):
                        log("Lint auto-fixed (ruff --fix): %s", task.file_path)
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
                            _run_repair_lint(model, lint_cmd, task.file_path, lint_head,
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
                    if not _run_test_repair_loop(model, test_cmd, test_log, p,
                                                 auto_system, writer_timeout, goal):
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
            err = _final_test_gate(model, p, auto_system, writer_timeout, goal)
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
    system = (f"You are a planning agent in: {project_dir}\n"
              "Output ONLY the raw PLAN.md markdown. No preamble, no explanation, no code blocks. "
              "Begin with ## Summary, then ## Files.")
    skill = _load_skill('task-planner')
    if skill:
        system += '\n\n' + skill
    example = (
        "## Summary\n"
        "Implement a command-line tool in C that prints a greeting. "
        "Build with make and verify with a direct invocation.\n\n"
        "## Files\n"
        "- [ ] main.c — C source\n"
        "- [ ] Makefile — build rules\n\n"
        "## Test Command\nmake && ./main\n\n"
        "## Dependencies\nclang, make"
    )
    msgs = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': (
            f"Create a PLAN.md task list for this goal.\n\n"
            f"GOAL: {goal}\nDIR: {project_dir}\n\n"
            f"Rules:\n"
            f"- Start with a `## Summary` section: 2-4 sentences describing the approach, "
            f"key design decisions, and how correctness will be verified.\n"
            f"- Then list ONLY filenames with `- [ ] ` prefix under `## Files`. "
            f"Do NOT write file contents or code.\n"
            f"- No code blocks. Allowed headers: ## Summary / ## Files / ## Test Command / ## Dependencies.\n\n"
            f"Example output:\n{example}\n\n"
            f"Now output the PLAN.md for the goal above. Start with ## Summary.")},
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

def _run_test_repair_loop(model: str, test_cmd: str, test_log: str, p: Plan,
                          autonomous_system: str, writer_timeout: int, goal: str) -> bool:
    sess = Session(autonomous_system + '\n\n' + _REPAIR_LOOP_RULES)
    sess.tool_set = tools.REPAIR

    def run_test() -> tuple[bool, str]:
        return _run_cmd(test_cmd, test_log), _tail_file(test_log, 60)

    def reapply() -> None:
        for t in p.tasks:
            if (Path(t.file_path).exists() and is_build_file(t.file_path) and
                    Path(t.file_path).name.lower() == 'makefile'):
                apply_makefile_sensors(t.file_path)
        apply_go_sensors()  # resolve Go module deps before each build attempt

    return sess.repair_loop(model, goal, _REPAIR_MAX_ITERS, float(writer_timeout),
                            run_test, reapply)


def _run_repair_lint(model: str, lint_cmd: str, file_path: str, lint_head: str,
                     autonomous_system: str, writer_timeout: int, goal: str) -> None:
    file_content = ''
    try:
        data = Path(file_path).read_text()
        if len(data) < 3000:
            file_content = f'\n\nCurrent file:\n```\n{data}\n```'
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
    fix_rules = (f"REPAIR PROTOCOL:\n"
                 f"- Call Edit to make the smallest targeted change to fix {file_path}.\n"
                 f"- Only modify {file_path}. Do not create new files or modify other files.\n"
                 f"- Do not modify PLAN.md.")
    prompt = (f"GOAL: {goal}\n\nLint failed for {file_path}. Fix it now.\n\n"
              f"Lint errors:\n{lint_head}{hint}{file_content}{repair_history()}")
    sess = Session(autonomous_system + '\n\n' + fix_rules)
    sess.tool_set = tools.REPAIR
    _, err = sess.run(model, prompt, 'Repairing', 4, '', float(writer_timeout))
    if err:
        log("Lint repair: %s", err)


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
    if _run_test_repair_loop(model, test_cmd, mit_log, p, auto_system, writer_timeout, goal):
        log("Mitigation pass: challenges resolved.")
    else:
        log("Mitigation pass: could not fully resolve challenges — proceeding anyway.")


def _final_test_gate(model: str, p: Optional[Plan], autonomous_system: str,
                     writer_timeout: int, goal: str) -> Optional[str]:
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
            return None
    test_log = os.path.join(LOG_DIR, 'tests-final.log')
    if _run_test_repair_loop(model, test_cmd, test_log, p, autonomous_system,
                             writer_timeout, goal):
        return None
    record_failed_repair("final test gate: repair loop exhausted", _tail_file(test_log, 30))
    print("\n  Tests still failing after repair loop. Giving up.\n", flush=True)
    return "final tests failed"


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
        return (f"ruff check --select=E9,F {file_path}" if shutil.which('ruff')
                else f"python3 -m py_compile {file_path}")
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
