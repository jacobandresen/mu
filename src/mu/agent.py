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
import traceback
from pathlib import Path
from typing import Optional

from mu import tools
from mu.archive import AgentSession
from mu.client import (LMS_HOST, chat, list_downloaded_llm_paths, list_models,
                        load_catalog, load_model, max_prompt_tokens, normalize_model_bare,
                        preferred_model, recommended_model, set_chat_context)
from mu.plan import (Plan, _EXT_LANGUAGE, check_goal_alignment, clear_challenges,
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
                         fix_go_trailing_dot,
                         apply_plan_spec_reflexes, run_reflexes,
                         apply_csharp_write_reflexes, apply_csharp_repair_reflexes,
                         apply_js_write_reflexes, apply_js_repair_reflexes,
                         apply_rust_source_reflexes,
                         fix_csharp_missing_using,
                         fix_csharp_package_tfm_mismatch,
                         fix_csharp_xunit_packages,
                         fix_jest_config_js,
                         fix_jest_esm,
                         fix_jest_no_tests_found,
                         fix_json_unclosed_brackets,
                         fix_package_json_bare_jest,
                         fix_package_json_builtin_deps,
                         fix_flask_test_route_decorators,
                         fix_flask_init_db_import,
                         fix_missing_flask_client_fixture,
                         fix_sqlite_missing_row_factory,
                         fix_flask_post_missing_201,
                         fix_js_extra_closing_brace,
                         fix_vitest_globals,
                         fix_vitest_watch_mode,
                         fix_vue_missing_package,
                         fix_js_const_reassignment,
                         fix_literal_newlines,
                         fix_makefile_binary_name,
                         fix_missing_close_paren, fix_missing_pip_packages,
                         fix_multiline_single_quote,
                         fix_python_decorator_colon,
                         fix_python_method_indent,
                         fix_python_missing_def,
                         fix_python_missing_project_imports,
                         fix_python_missing_stdlib_imports,
                         fix_python_undefined_imports,
                         fix_requirements_path_entries,
                         fix_requirements_stdlib_entries,
                         fix_rust_cargo_toml,
                         fix_rust_cargo_bad_dependency,
                         fix_rust_duplicate_use,
                         fix_rust_println_missing_arg,
                         fix_rust_missing_trait_import,
                         fix_rust_unbalanced_braces,
                         fix_sqlite_class_missing_init_table,
                         fix_sqlite_conn_scope,
                         fix_sqlite_path_unlink,
                         fix_sqlite_test_isolation,
                         fix_sqlite_memory_multi_connect,
                         fix_test_import_module,
                         fix_tool_call_artifacts,
                         py_autofix)
from mu.session import REPAIR_ESCALATE, Session

LOG_DIR = ".mu"

_LIB_RE = re.compile(
    r'(?i)SDL2|OpenGL|ncurses|dotnet|C#|csharp|tensorflow|pytorch|'
    r'django|flask|opencv|wxwidgets|express|gin|cargo|'
    r'vue|react|svelte|angular|node\.js|nodejs')
_HARD_LIB_RE = re.compile(r'(?i)pytest|jest|vitest|xunit|nunit|rspec|cargo\s+test')
_COMPLEXITY_PLANNER = {'trivial': 120, 'simple': 200, 'complex': 360, 'hard': 480}
_COMPLEXITY_WRITER = {'trivial': 90, 'simple': 220, 'complex': 300, 'hard': 400}
_REPAIR_MAX_ITERS = 6
_STAGE_SEQUENCE = [
    ('model',    'PLAN-model.md'),
    ('backend',  'PLAN-backend.md'),
    ('frontend', 'PLAN-frontend.md'),
]


def _repair_loop_rules(plan_file: str = 'PLAN.md') -> str:
    return (
        "REPAIR RULES — follow exactly:\n"
        "1. You are fixing failing tests. Each turn, make ONE targeted change: "
        "call Edit, or Write to replace a whole file.\n"
        "2. Do NOT run any commands. The test is run for you after each edit "
        "and the new output is shown to you.\n"
        f"3. Only modify files that already exist. Do not create new files. "
        f"Do not touch {plan_file}.\n"
        "4. Never modify build configuration files: Cargo.toml, package.json, "
        "go.mod, go.sum, pyproject.toml, setup.py. Fix errors in source files, "
        "not build files — the build system is correct.\n"
        "5. Never modify files inside generated directories: .venv/, node_modules/, "
        "__pycache__/, target/, .cargo/, dist/, build/. "
        "These are managed by package managers, not by you.\n"
        "6. YOUR FIRST OUTPUT MUST BE a tool call (Edit or Write). "
        "Zero prose before the tool call. No thinking, no explanation — tool call first, nothing else."
    )


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
    # Tee into the session log dir so failures that never reach the test phase
    # (planner HTTP errors, writer stalls) still leave a distillable record in
    # the archive — 40 of 45 failures in one collection run archived empty
    # logs/ and observe could only say "(no test log)".
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, 'agent.log'), 'a') as fh:
            fh.write(msg + '\n')
    except OSError:
        pass


def _log_backend(model: str) -> None:
    """Print the active LM Studio host and model to stdout."""
    log("LM Studio: %s | Model: %s", LMS_HOST, model)


def _match_loaded(loaded: list[str], target: str) -> str:
    """Return the loaded model id matching the catalog id `target`, or ''.

    LM Studio sometimes serves a model under a shorter display identifier than
    the catalog uses (strips quantization suffix and .gguf extension), so fall
    back to a normalized bare-name match via normalize_model_bare.
    """
    if not target:
        return ''
    target_bare = normalize_model_bare(target)
    for m in loaded:
        if m == target or normalize_model_bare(m) == target_bare:
            return m
    return ''


def _select_model() -> str:
    """Pick the model for the agent.

    Resolution order: user-persisted preference → hardware-recommended →
    already-loaded catalog model. Loads the target model if needed.
    Returns '' on failure (caller should abort).
    """

    loaded = list_models()
    # Prefer explicitly saved selection over hardware recommendation.
    preferred = preferred_model()
    recommended = preferred or recommended_model()
    match = _match_loaded(loaded, recommended)
    if match:
        log("Using recommended model: %s", match)
        return match
    # If another catalog model is already loaded, prefer it over loading a
    # non-installed recommended model (avoids a confusing load error).
    catalog_norm = {
        normalize_model_bare(spec['id'])
        for spec in load_catalog()
        if spec.get('id')
    }
    for m in loaded:
        if normalize_model_bare(m) in catalog_norm:
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
    catalog_norm = {normalize_model_bare(cid) for cid in catalog_ids}
    for path in list_downloaded_llm_paths():
        if path in catalog_ids or normalize_model_bare(path) in catalog_norm:
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


_VAGUE_DESC_RE = re.compile(r'\b(module|logic|functionality|implement the|various|etc|handle)\b', re.I)


def _analyze_plan_quality(goal: str, p: Plan, max_iter: int) -> tuple[bool, float | None, list[str]]:
    """Initial analysis step: decide whether a plan is ambiguous enough to need
    improvement, returning (needs_improvement, predicted_success, reasons).

    Combines a scikit-learn P(success) estimate (when a model is trained) with
    cheap deterministic ambiguity heuristics. The heuristics encode the same
    failure modes the spec-tier rewrite fixes: missing test command, unnamed/
    extensionless files, vague descriptions, and a too-thin plan for a clearly
    multi-file goal. A plan only needs improving if it is actually under-specified.
    """
    reasons: list[str] = []
    pending = [t for t in p.tasks if not t.done]

    if not p.test_command.strip():
        reasons.append("no explicit test command")
    for t in pending:
        name = Path(t.file_path).name
        if '.' not in name and name.lower() != 'makefile':
            reasons.append(f"file '{t.file_path}' has no extension (ambiguous type)")
        if len(t.description.strip()) < 15 or _VAGUE_DESC_RE.search(t.description):
            reasons.append(f"task '{t.file_path}' has a vague/thin description")

    # A framework / multi-layer goal expressed as one or two tasks is under-decomposed.
    blob = goal.lower()
    multi_signals = ('api', 'database', 'server', 'frontend', 'backend', 'rest',
                     'flask', 'gin', 'asp.net', 'vue', 'blog', 'full-stack')
    if sum(s in blob for s in multi_signals) >= 2 and len(pending) <= 2:
        reasons.append(f"multi-component goal planned as only {len(pending)} task(s)")

    # scikit-learn estimate (optional — present only once a model is trained).
    proba: float | None = None
    try:
        from mu.predict import predict_success_proba
        proba = predict_success_proba(goal, len(p.tasks), max_iter)
    except Exception:
        proba = None
    thresh = float(os.environ.get('MU_IMPROVE_THRESHOLD', '0.6') or 0.6)
    low_proba = proba is not None and proba < thresh

    needs = bool(reasons) or low_proba
    return needs, proba, reasons


def improve_plan(goal: str = '', model: str = '', target_dir: str = '',
                 plan_file: str = 'PLAN.md', max_iter: int = 10,
                 force: bool = False) -> int:
    """Tighten an ambiguous PLAN.md so a weak model is tested on coding rather
    than on guessing under-specified structure.

    Deliberately DETERMINISTIC — the dojo's purpose is to turn weak-model failures
    into reflexes, so improvement is a plan reflex, not another LLM pass by the
    same weak model (which, measured, either produced invalid rewrites or hurt by
    decomposing). Two clearly-logged phases:
      1. ANALYZE — decide whether the plan is under-specified (heuristics +
         optional scikit-learn P(success)). If it is already specific, stop.
      2. IMPROVE — apply `apply_plan_spec_reflexes`: enrich pending task
         descriptions with the interface / test-harness contracts the writer
         otherwise guesses wrong. It NEVER adds, removes, or renames tasks
         (decomposition hurts small models) and calls no model.
    """
    if target_dir:
        os.chdir(target_dir)
    if not Path(plan_file).exists():
        print(f"mu-improve-plan: no {plan_file} found — run `mu plan` first", file=sys.stderr)
        return 1

    # Make the command's invocation unmistakable in the log.
    print(f"==> [mu-improve-plan] COMMAND INVOKED on {plan_file}", flush=True)
    original = Path(plan_file).read_text()
    p = parse(plan_file)
    if not goal:
        goal = p.plan_context[:200].strip()

    # ── Phase 0: deterministic plan lint (no LLM) ─────────────────────────────
    # Folded in from the former `mu lint` command: report spaCy-based warnings
    # (entity inconsistencies, vague verbs, underspecified tasks). Fail-soft —
    # lint_plan returns [] when spaCy isn't installed.
    try:
        from mu.lint import lint_plan
        warnings = lint_plan(plan_file)
    except Exception:
        warnings = []
    if warnings:
        log("improve-plan: %d lint warning(s):", len(warnings))
        for w in warnings:
            print(f"  - {w}")

    # ── Phase 1: analyze ──────────────────────────────────────────────────────
    log("improve-plan: analyzing plan adequacy …")
    needs, proba, reasons = _analyze_plan_quality(goal, p, max_iter)
    if proba is not None:
        log("improve-plan: predicted P(success) = %.0f%% (scikit-learn)", proba * 100)
    else:
        log("improve-plan: no trained predictor — using heuristics only "
            "(train via `python -m mu.predict`).")
    if reasons:
        log("improve-plan: %d ambiguity signal(s): %s", len(reasons), '; '.join(reasons))
    if not needs and not force:
        log("improve-plan: plan is adequately specified — no changes. "
            "(use --force to apply reflexes anyway.)")
        return 0

    # ── Phase 2: deterministic spec reflexes (no LLM, no new tasks) ────────────
    log("improve-plan: applying deterministic spec reflexes (no LLM, task count fixed).")
    notes = apply_plan_spec_reflexes(goal, plan_file)
    if not notes:
        log("improve-plan: no deterministic spec reflex applied — plan left unchanged.")
        return 0

    backup = os.path.join(LOG_DIR, f'{Path(plan_file).stem}-before-improve.md')
    os.makedirs(LOG_DIR, exist_ok=True)
    Path(backup).write_text(original)
    for note in notes:
        log("improve-plan reflex: %s", note)
    log("improve-plan: enriched %d task description(s); task count unchanged. Backup: %s.",
        len(notes), backup)
    print()
    print(Path(plan_file).read_text(), flush=True)
    return 0


def iterate(goal: str = '', model: str = '', target_dir: str = '',
            max_iter: int = 10, plan_file: str = 'PLAN.md') -> int:
    """Continue executing an existing plan without re-planning."""
    if target_dir:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        os.chdir(target_dir)
    if not Path(plan_file).exists():
        print(f"mu-iterate: no {plan_file} found — run `mu plan` or `mu agent` first",
              file=sys.stderr)
        return 1
    plan_text = Path(plan_file).read_text()
    reset_text = re.sub(r'^(- \[)~(\] )', r'\1 \2', plan_text, flags=re.MULTILINE)
    reset_count = plan_text.count('- [~]')
    if reset_count:
        Path(plan_file).write_text(reset_text)
        log("Reset %d in-progress task(s) to pending.", reset_count)
    if not goal:
        p = parse(plan_file)
        goal = p.plan_context[:120].strip() or 'implement the plan'

    challenges = get_challenges(plan_file)
    if challenges:
        mit_model = model or os.environ.get('MU_AGENT_MODEL', '') or _select_model()
        if mit_model:
            _run_mitigation_pass(mit_model, parse(plan_file), challenges, goal)
        clear_challenges(plan_file)
        log("Cleared challenges section after mitigation pass.")

    return run(goal=goal, model=model, target_dir='', max_iter=max_iter, force=True,
               show_result=True, plan_file=plan_file)


def plan(goal: str, model: str = '', target_dir: str = '', force: bool = False,
         plan_file: str = 'PLAN.md') -> int:
    """Generate a plan file and write sketch stubs for each planned file."""
    if not model:
        model = os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        model = _select_model()
        if not model:
            return 1
    _log_backend(model)

    if target_dir:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        os.chdir(target_dir)

    err = _check_standalone(force, plan_file)
    if err:
        print(err, file=sys.stderr)
        return 1

    complexity = detect_complexity(goal)
    planner_timeout = _COMPLEXITY_PLANNER[complexity]

    if Path(plan_file).exists():
        log("%s already exists — skipping task-planner.", plan_file)
        err = _validate_existing_plan(plan_file)
        if err:
            print(f"mu-plan: {err}", file=sys.stderr)
            return 1
    else:
        if not _run_planning_phase(goal, model, planner_timeout, complexity, plan_file):
            return 1

    if strip_thinking_artifacts(plan_file):
        log("WARNING: thinking artifact tokens stripped from %s", plan_file)
    extracted = normalize_embedded_files(plan_file)
    if extracted:
        log("Extracted embedded files: %s", ', '.join(extracted))
    if normalize_test_command(plan_file):
        log("Normalized test command for portability.")

    if os.environ.get('MU_LINT_PLAN') == '1':
        _lint_critique_pass(plan_file, goal, model, planner_timeout)

    if os.environ.get('MU_ENRICH_LESSONS') == '1':
        _inject_lessons_section(plan_file, goal)

    p = parse(plan_file)

    dropped = drop_runtime_artifacts(plan_file, p)
    if dropped:
        log("Dropped runtime artifact tasks: %s", ', '.join(dropped))
        p = parse(plan_file)

    minority = drop_minority_languages(plan_file, p)
    if minority:
        langs = plan_languages(parse(plan_file))
        dominant = next(iter(langs)) if langs else '?'
        log("Dropped minority-language files (keeping %s): %s", dominant, ', '.join(minority))
        p = parse(plan_file)

    grounded = ground_plan(plan_file, p)
    if grounded:
        for change in grounded:
            log("Grounded plan against toolchain — %s", change)
        p = parse(plan_file)

    ok, missing = check_goal_alignment(p, goal)
    if not ok:
        log("WARNING: %s contains none of the goal keywords.", plan_file)
    elif missing:
        log("NOTE: %s missing some goal terms: %s", plan_file, ', '.join(missing))

    sketched = write_sketches(p, goal)
    if sketched:
        log("Sketched %d file(s): %s", len(sketched), ', '.join(sketched))
    else:
        log("No new stub files to create (all already exist or are build/runtime files).")

    return 0


def run(goal: str, model: str = '', target_dir: str = '',
        max_iter: int = 10, force: bool = False, show_result: bool = False,
        plan_file: str = 'PLAN.md') -> int:
    if not model:
        model = os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        model = _select_model()
        if not model:
            return 1
    _log_backend(model)

    archive_dir = (os.environ.get('MU_AGENT_ARCHIVE_DIR', '') or
                   str(Path.home() / '.mu' / 'sessions'))
    complexity = detect_complexity(goal)
    planner_timeout = _COMPLEXITY_PLANNER[complexity]
    writer_timeout = _COMPLEXITY_WRITER[complexity]

    if target_dir:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        os.chdir(target_dir)

    # Auto-trigger architect pass for hard multi-layer problems before planning.
    if not force and complexity == 'hard' and _is_multilayer(goal):
        if any(Path(pf).exists() for _, pf in _STAGE_SEQUENCE):
            # Stage plans already exist (e.g. prior interrupted run) — resume staged execution
            # rather than falling through to the standalone flow, which would fail because
            # PLAN.md doesn't exist when the directory has stage plans.
            log("Stage plans found — resuming staged execution.")
            return run_staged(goal, model, max_iter=max_iter)
        log("Hard multi-layer problem detected — running architect pass.")
        stages = _run_architect_pass(goal, model, planner_timeout)
        if len(stages) > 1:
            return run_staged(goal, model, max_iter=max_iter)
        log("Architect produced %d stage(s) — falling back to single-plan mode.",
            len(stages))

    err = _check_standalone(force, plan_file)
    if err:
        print(err, file=sys.stderr)
        return 1

    os.makedirs(LOG_DIR, exist_ok=True)
    sess = AgentSession(goal, archive_dir, LOG_DIR, max_iter, model=model)
    current_plan: Optional[Plan] = None
    exit_code = 0
    _architect_escalated = False  # cap: at most one architect escalation per session

    def _on_signal(sig, frame):
        print("\nInterrupted.", file=sys.stderr)
        sess.finalize(130, current_plan, plan_file)
        sys.exit(130)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        if Path(plan_file).exists():
            log("%s already exists — skipping task-planner.", plan_file)
            err = _validate_existing_plan(plan_file)
            if err:
                print(f"mu-agent: {err}", file=sys.stderr)
                sess.fail_reason = f'existing plan invalid: {err}'
                exit_code = 1
                return exit_code
        else:
            if not _run_planning_phase(goal, model, planner_timeout, complexity, plan_file):
                sess.fail_reason = 'planner produced no usable plan'
                exit_code = 1
                return exit_code

        if strip_thinking_artifacts(plan_file):
            log("WARNING: thinking artifact tokens stripped from %s", plan_file)
        extracted = normalize_embedded_files(plan_file)
        if extracted:
            log("Extracted embedded files: %s", ', '.join(extracted))
        if normalize_test_command(plan_file):
            log("Normalized test command for portability.")

        if os.environ.get('MU_LINT_PLAN') == '1':
            _lint_critique_pass(plan_file, goal, model, planner_timeout)

        # Opt-in spec-tightening pass: rewrite the freshly-planned PLAN.md to
        # remove ambiguity (filenames, test harness, data contracts) before the
        # writer loop. Runs before grounding so the test command is re-normalized.
        if os.environ.get('MU_IMPROVE_PLAN') == '1':
            improve_plan(goal, model, plan_file=plan_file)

        p = parse(plan_file)
        current_plan = p

        dropped = drop_runtime_artifacts(plan_file, p)
        if dropped:
            log("Dropped runtime artifact tasks: %s", ', '.join(dropped))
            p = parse(plan_file)
            current_plan = p

        grounded = ground_plan(plan_file, p)
        if grounded:
            for change in grounded:
                log("Grounded plan against toolchain — %s", change)
            p = parse(plan_file)
            current_plan = p

        ok, missing = check_goal_alignment(p, goal)
        if not ok:
            log("WARNING: %s contains none of the goal keywords.", plan_file)
        elif missing:
            log("NOTE: %s missing some goal terms: %s", plan_file, ', '.join(missing))

        os.makedirs(sess.archive_path, exist_ok=True)
        try:
            shutil.copy2(plan_file, os.path.join(sess.archive_path, 'PLAN-initial.md'))
        except OSError:
            pass

        # Opt-in doomed-run predictor (MU_PREDICT=1). Logs P(success) from the
        # goal + plan shape; with MU_PREDICT_ABORT and a low score it bails before
        # the expensive writer/repair loop. Non-destructive by default — purely
        # informational unless abort is explicitly enabled.
        if os.environ.get('MU_PREDICT') == '1':
            try:
                from mu.predict import predict_success_proba
                proba = predict_success_proba(goal, len(p.tasks), max_iter)
                if proba is not None:
                    log("Predicted P(success) = %.0f%%", proba * 100)
                    thresh = float(os.environ.get('MU_PREDICT_ABORT', '0') or 0)
                    if thresh > 0 and proba < thresh:
                        log("Aborting before writer loop: P(success) %.0f%% < "
                            "threshold %.0f%% (MU_PREDICT_ABORT).",
                            proba * 100, thresh * 100)
                        exit_code = 4  # finalized by the run() finally block
                        return exit_code
            except Exception as e:
                log("Predictor unavailable (%s) — continuing.", e)

        project_dir = os.getcwd()
        auto_system = _build_autonomous_system(project_dir, plan_file)
        loaded_skills: set[str] = set()
        if max_prompt_tokens() >= 2000:
            for _skill_name, _skill_content in _contextual_skills(goal, p):
                auto_system += '\n\n' + _skill_content
                loaded_skills.add(_skill_name)
                log("Loaded %s skill.", _skill_name)
        else:
            log("Skipping contextual skills (constrained token budget: %d tokens).", max_prompt_tokens())

        # Provided fixtures: a task whose file already exists (non-empty) in the
        # work dir was supplied (e.g. a correct Makefile copied in by fixture
        # mode — DOJO.md § Problem-space minimization, L2+). Not the model's job — mark it
        # done so the writer skips it. This is how a fixture removes a whole
        # failure class: the model never writes (and fails) the provided file.
        marked = False
        for t in p.tasks:
            if not t.done and Path(t.file_path).exists() and Path(t.file_path).stat().st_size > 0:
                mark_task_done(plan_file, t.file_path)
                log("Provided fixture: %s — skipping (not rewritten).", t.file_path)
                marked = True
        if marked:
            p = parse(plan_file)

        for i in range(1, max_iter + 1):
            task = next_task(p)
            if task is None:
                log("All tasks complete.")
                break

            log("Iteration %d / %d: %s", i, max_iter, task.file_path)
            companion = _companion_header(task.description)
            write_prompt = _build_write_prompt(goal, task, p, companion, plan_file,
                                               loaded_skills)

            if not _run_writer(model, task.file_path, write_prompt, auto_system, writer_timeout,
                               companion):
                if not Path(task.file_path).exists():
                    # Writer may have put the file in a subdirectory — check and move.
                    basename = Path(task.file_path).name
                    misplaced = next(
                        (p2 for p2 in Path('.').rglob(basename)
                         if p2 != Path(task.file_path) and p2.stat().st_size > 0),
                        None)
                    if misplaced:
                        Path(task.file_path).parent.mkdir(parents=True, exist_ok=True)
                        misplaced.rename(task.file_path)
                        log("Relocated %s → %s.", misplaced, task.file_path)
                if not Path(task.file_path).exists():
                    log("Writer did not produce %s — retrying.", task.file_path)
                    record_challenge(f"writer did not produce {task.file_path} on first attempt",
                                     plan_file=plan_file)
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
                    # Use a lean system on retry: drop skills that may have caused 400.
                    lean_system = _build_autonomous_system(project_dir, plan_file)
                    if not _run_writer(model, task.file_path, retry, lean_system, writer_timeout,
                                       companion):
                        # Retry may have written to wrong path — check again.
                        if not Path(task.file_path).exists():
                            misplaced2 = next(
                                (p2 for p2 in Path('.').rglob(basename)
                                 if p2 != Path(task.file_path) and p2.stat().st_size > 0),
                                None)
                            if misplaced2:
                                Path(task.file_path).parent.mkdir(parents=True, exist_ok=True)
                                misplaced2.rename(task.file_path)
                                log("Relocated (post-retry) %s → %s.", misplaced2, task.file_path)
                        if not Path(task.file_path).exists():
                            log("Iteration %d: %s not written after retry.", i, task.file_path)
                            sess.fail_reason = f'writer produced no file for {task.file_path} after retry'
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
                    record_challenge(f"no code written for {task.file_path}",
                                     plan_file=plan_file)
                    stub_content = _default_stub(ext, task.file_path)
                    Path(task.file_path).write_text(stub_content)
            except OSError:
                pass

            _apply_write_reflexes(task.file_path, p.test_command or '')

            lint_cmd = _lint_command(task.file_path, p)
            if lint_cmd:
                lint_log = os.path.join(LOG_DIR, f"lint-iter-{i:02d}.log")
                if not _run_cmd(lint_cmd, lint_log):
                    if py_autofix(task.file_path) and _run_cmd(lint_cmd, lint_log):
                        log("Lint auto-fixed (autoflake): %s", task.file_path)
                    else:
                        lint_head = _head_file(lint_log, 60)
                        lint_tail = _tail_file(lint_log, 60)
                        det_fixed = (
                            (fix_multiline_single_quote(task.file_path, lint_head) or
                             fix_missing_close_paren(task.file_path, lint_head) or
                             fix_literal_newlines(task.file_path, lint_head) or
                             fix_python_undefined_imports(task.file_path, lint_head) or
                             fix_rust_duplicate_use(task.file_path) or
                             fix_rust_println_missing_arg(task.file_path) or
                             fix_rust_missing_trait_import(task.file_path, lint_tail) or
                             fix_rust_unbalanced_braces(task.file_path, lint_tail)) and
                            _run_cmd(lint_cmd, lint_log)
                        )
                        if det_fixed:
                            log("Lint auto-fixed (deterministic): %s", task.file_path)
                        elif _lint_failures_all_cosmetic(lint_log):
                            # Only unused-variable warnings remain — correctness is
                            # fine and pytest will pass. Accept rather than spend the
                            # repair budget on a fix the small model can't make safely.
                            log("Lint: only cosmetic unused-variable warnings in %s — accepting.",
                                task.file_path)
                        else:
                            record_challenge(
                                f"lint repair needed for {task.file_path}", lint_head,
                                plan_file=plan_file)
                            _run_repair_lint(model, lint_cmd, task.file_path, lint_log, lint_head,
                                            writer_timeout, goal, plan_file)
                            if not _run_cmd(lint_cmd, lint_log) and not _lint_failures_all_cosmetic(lint_log):
                                log("Lint still failing after repair for %s.", task.file_path)
                                record_failed_repair(f"lint repair for {task.file_path}",
                                                     _head_file(lint_log, 5), plan_file)
                                sess.fail_reason = f'lint still failing after repair for {task.file_path}'
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
                        _tail_file(test_log, 5), plan_file=plan_file)
                    ok, iters = _run_test_repair_loop(model, test_cmd, test_log, p,
                                                      auto_system, writer_timeout, goal,
                                                      plan_file)
                    sess.repair_iters += max(iters, 0)
                    if not ok:
                        if iters == REPAIR_ESCALATE and not _architect_escalated:
                            _architect_escalated = True
                            log("Repair stuck — escalating to architect mode.")
                            print("==> [mu-agent] Repair loop stalled. Escalating to architect.",
                                  flush=True)
                            stages = _run_architect_pass(goal, model, planner_timeout)
                            if len(stages) > 1:
                                return run_staged(goal, model, max_iter=max_iter)
                            log("Architect produced %d stage(s) — cannot escalate further.",
                                len(stages))
                        log("Tests still failing after repair for %s.", task.file_path)
                        record_failed_repair(f"test repair after writing {task.file_path}",
                                             _tail_file(test_log, 5), plan_file)
                        sess.fail_reason = f'tests still failing after repair for {task.file_path}'
                        exit_code = 3
                        return exit_code

            mark_task_done(plan_file, task.file_path)
            log("Marked done: %s", task.file_path)
            print(f"\n  Iteration {i} done: {task.file_path}\n", flush=True)
            if show_result:
                _print_result(task.file_path)
                if companion and Path(companion).exists():
                    _print_result(companion)
            p = parse(plan_file)
            current_plan = p

        if not tasks_remaining(p):
            err, iters = _final_test_gate(model, p, auto_system, writer_timeout, goal,
                                          plan_file)
            sess.repair_iters += max(iters, 0)
            if err:
                if iters == REPAIR_ESCALATE and not _architect_escalated:
                    _architect_escalated = True
                    log("Final gate stuck — escalating to architect mode.")
                    print("==> [mu-agent] Final gate stalled. Escalating to architect.",
                          flush=True)
                    stages = _run_architect_pass(goal, model, planner_timeout)
                    if len(stages) > 1:
                        return run_staged(goal, model, max_iter=max_iter)
                    log("Architect produced %d stage(s) — cannot escalate further.",
                        len(stages))
                sess.fail_reason = f'final test gate failed: {err}'
                exit_code = 3
                return exit_code
            log("Goal complete.")
            print("\n  Goal complete!\n", flush=True)
            exit_code = 0
            return exit_code

        print(f"mu-agent: warning: reached max iterations ({max_iter}) with tasks remaining",
              file=sys.stderr)
        sess.fail_reason = f'reached max iterations ({max_iter}) with tasks remaining'
        exit_code = 2
        return exit_code
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception:
        # Without this, an uncaught exception reaches the finally with
        # exit_code still 0 and the crashed session is archived as 'success',
        # with the traceback lost to stderr.
        tb = traceback.format_exc()
        log("FATAL: uncaught exception — session failed.\n%s", tb)
        sess.fail_reason = sess.fail_reason or f'uncaught exception: {tb.strip().splitlines()[-1]}'
        exit_code = 1
        raise
    finally:
        sess.finalize(exit_code, current_plan, plan_file)


# ── Planning ──────────────────────────────────────────────────────────────────

_BLOCKING_CMD_RE = re.compile(r'(^|&&\s*|;\s*)\./')


def _plan_has_blocking_go_cmd(text: str) -> bool:
    """True when a Go plan's Test Command would start a blocking server.

    Checks for `./binary` in the Test Command of a plan that lists .go files.
    `go test ./...` is non-blocking; bare `./binary` hangs forever.
    """
    if not re.search(r'\b\w+\.go\b', text):
        return False
    m = re.search(r'(?m)^## Test Command\n(.+)', text)
    if not m:
        return False
    cmd = m.group(1).strip()
    return bool(_BLOCKING_CMD_RE.search(cmd)) and 'go test' not in cmd


def _run_planning_phase(goal: str, model: str, planner_timeout: int, complexity: str,
                        plan_file: str = 'PLAN.md') -> bool:
    log("Planning: %s (timeout=%ds complexity=%s)", goal, planner_timeout, complexity)
    for attempt in range(1, 4):
        if attempt > 1:
            log("Planner attempt %d / 3 (previous plan had wrong format)", attempt)
            if Path(plan_file).exists():
                Path(plan_file).unlink()
        _run_planner(goal, model, planner_timeout, plan_file)
        if not Path(plan_file).exists():
            log("Attempt %d: no %s produced", attempt, plan_file)
            continue
        text = Path(plan_file).read_text(errors='replace')
        # Use the real parser, not a raw regex, to decide "has a task checklist".
        # parse_content normalizes malformed bullets the model emits (e.g.
        # `- - [ ] main.py`, `  - [ ] main.py`); a raw `^- \[ \]` check rejects
        # those and retries to failure even though every downstream read recovers
        # the tasks fine — the same reject-only anti-pattern as the blocking-Go
        # guard below. Agreeing with the parser fixes the class.
        if not parse_content(text).tasks:
            log("Attempt %d: %s has no task checklist (wrong format) — retrying",
                attempt, plan_file)
            continue
        if _plan_has_blocking_go_cmd(text):
            # The model reliably re-emits the blocking `./binary` command on every
            # attempt (a Go HTTP server runs forever), so retrying just burns the
            # budget and fails the whole problem. Fix it deterministically instead:
            # normalize_test_command rewrites it to the non-blocking `go test ./...`.
            if normalize_test_command(plan_file):
                text = Path(plan_file).read_text()
            if _plan_has_blocking_go_cmd(text):
                log("Attempt %d: Go plan uses blocking ./binary test command — retrying", attempt)
                continue
            log("Rewrote blocking Go ./binary test command to a non-blocking check.")
        break
    else:
        print(f"mu-agent: task-planner did not produce a valid {plan_file} after 3 attempts",
              file=sys.stderr)
        return False
    log("%s created.", plan_file)
    print()
    print(Path(plan_file).read_text(), flush=True)
    return True


def _run_planner(goal: str, model: str, planner_timeout: int,
                 plan_file: str = 'PLAN.md') -> None:
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
    # Inject layout/env skills at plan time so the planner emits the right file
    # list and test command before locking them in.
    has_dotnet = any(k in goal_lower for k in ('asp.net', 'dotnet', 'c#', 'csharp', 'xunit', 'ef core'))
    has_vue = any(k in goal_lower for k in ('vue', 'vite', 'vitest'))
    if has_dotnet:
        ds = _load_skill('dotnet-mvc')
        if ds:
            extra_skills.append(ds)
    elif has_vue and not has_dotnet:
        # vue-ts-env: ensures planner includes package.json, vite.config.ts,
        # Makefile, and uses `npx vitest run` not bare `vitest`.
        vs = _load_skill('vue-ts-env')
        if vs:
            extra_skills.append(vs)

    # Estimate token budget (4 chars ≈ 1 token).  On a small context window the
    # full skill + challenges would exceed the limit and overflow the prompt.
    # Use a compact prompt that fits within the budget, leaving ~40 % for output.
    token_budget = max_prompt_tokens()
    _COMPACT_THRESHOLD = 2000  # tokens; below this, skip heavy skill/challenges
    use_compact = token_budget < _COMPACT_THRESHOLD

    if use_compact:
        # Stripped-down prompt: system header + goal only.  No skill, no
        # challenges, no example.  Keeps the total well under 1024 tokens.
        log("Planner: compact prompt (budget=%d tokens)", token_budget)
        system = (
            "You are a planning agent. "
            "Output ONLY raw PLAN.md markdown with exactly these sections: "
            "## Summary, ## Files, ## Test Command, ## Dependencies. "
            "No preamble, no explanation, no code fences."
        )
        user_msg = (
            f"DIR: {project_dir}\n"
            f"GOAL: {goal}\n\n"
            "CRITICAL: Each file in ## Files MUST use exactly this format:\n"
            "- [ ] filename.ext — short description\n\n"
            "No backticks around filenames. No colon. Use `- [ ]` checkbox and ` — ` separator.\n\n"
            "Example:\n"
            "## Summary\nImplement the goal using idiomatic patterns.\n\n"
            "## Files\n"
            "- [ ] main.py — entry point implementing the core logic\n"
            "- [ ] test_main.py — pytest tests for main.py\n\n"
            "## Test Command\npytest\n\n"
            "## Dependencies\npython>=3.11, pytest>=7\n\n"
            f"Now write the PLAN.md for the GOAL above. Start with ## Summary."
        )
    elif os.environ.get('MU_PROMPT_CACHE') == '1':
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
    set_chat_context('planner')
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
        Path(plan_file).write_text(content)
    except OSError as e:
        log("Planner: could not write %s: %s", plan_file, e)


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
    # On a very small context window, history accumulates across turns and any
    # nudge/follow-up turn would push the total past the limit and overflow. Use
    # a single turn so the session never sends a second request.
    max_turns = 1 if max_prompt_tokens() < 2000 else 15
    set_chat_context('writer', target_file)
    ok, err = sess.run(model, prompt, 'Writing', max_turns, target_file, float(writer_timeout))
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
    'C#': 'repair-csharp',
}


def _contextual_skills(goal: str, p: Plan) -> list[tuple[str, str]]:
    """Return (name, content) pairs for all context-sensitive skills that apply.

    These are skills driven by what the goal and plan describe — language
    domain, test patterns, server type — as opposed to per-language repair
    skills which are driven by the file extensions present in the plan.
    """
    is_dotnet = _dotnet_relevant(goal, p)
    is_python = _python_relevant(goal, p)
    candidates: list[tuple[str, bool]] = [
        ('makefile-writer',    _makefile_relevant(goal, p)),
        ('python-writer',      is_python),
        ('node-env',           _node_relevant(goal, p)),
        ('go-writer',          any(t.file_path.endswith('.go') for t in p.tasks)),
        ('sdl2-writer',        bool(re.search(r'(?i)\bSDL2?\b', goal))),
        ('vue-ts-env',         _vue_relevant(goal, p)),
        ('dotnet-mvc',         is_dotnet),
        ('test-isolation',     _test_isolation_relevant(goal, p) and not is_python and not is_dotnet),
        ('no-server-in-tests', _no_server_relevant(goal, p) and not is_python and not is_dotnet),
    ]
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for name, relevant in candidates:
        if relevant and name not in seen:
            seen.add(name)
            content = _load_skill(name)
            if content:
                result.append((name, content))
    return result


def _load_repair_skills(p: Plan, goal: str = '') -> str:
    """Return language-specific repair skills for all languages in the plan.

    Contextual skills (vue-ts-env, node-env, python-env, etc.) are already
    present in ``autonomous_system`` from the write phase, so they are NOT
    re-added here. Re-adding them doubles the system prompt size and can push
    the total context past the model's limit, causing 400 errors in the repair
    loop. Only per-language repair guides (repair-python, repair-go, etc.) are
    appended — they are small and repair-specific.
    """
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
                          plan_file: str = 'PLAN.md') -> tuple[bool, int]:
    """Run the repair loop against the test gate; return (passed, repair_iters)."""
    # Use a LEAN repair system: only the base protocol + language repair skills.
    # The full autonomous_system (with all contextual skills like vue-ts-env,
    # node-env, dotnet-mvc) is too large to combine with the project
    # files and test output without overflowing the model's context window.
    # The repair loop reads current files directly — it doesn't need write-time
    # guidance on how to structure a new Vue project.
    repair_skills = _load_repair_skills(p, goal)
    lean_system = _build_autonomous_system(os.getcwd())
    system = lean_system + ('\n\n' + repair_skills if repair_skills else '')
    sess = Session(system + '\n\n' + _repair_loop_rules(plan_file))
    sess.tool_set = tools.REPAIR
    set_chat_context('repair')

    def run_test() -> tuple[bool, str]:
        return _run_cmd(test_cmd, test_log), _extract_test_failures(test_log)

    def reapply() -> None:
        # First, run the full write-reflex pass on whatever the previous
        # repair turn modified — repair edits get the same deterministic
        # fixes as initial writes (missing imports, artifacts, …).
        _reflex_modified_files()
        # Remove stale .cs files that are NOT in this stage's plan.
        # The root .csproj picks up ALL .cs files recursively, so orphaned copies
        # from previous stages or the repair model cause CS0101/CS0260/CS0234.
        stage_paths = {Path(t.file_path) for t in p.tasks if t.file_path.endswith('.cs')}
        stage_dirs = {Path(t.file_path).parent for t in p.tasks if t.file_path.endswith('.cs')}
        _skip_dirs = {'obj', 'bin', '.git', 'node_modules', '.venv'}
        for cs_file in list(Path('.').rglob('*.cs')):
            # Never touch build/dependency output directories
            if any(part in _skip_dirs for part in cs_file.parts):
                continue
            if cs_file in stage_paths:
                continue
            # Keep files whose parent directory is an expected stage directory
            if cs_file.parent in stage_dirs or cs_file.parent == Path('.'):
                # Only delete if same basename as a stage file (likely duplicate)
                if any(cs_file.name == sp.name for sp in stage_paths):
                    try:
                        cs_file.unlink()
                        log("Deleted orphaned .cs duplicate: %s", cs_file)
                    except OSError:
                        pass
            elif any(cs_file.name == sp.name for sp in stage_paths):
                # Unexpected subdir but same basename as a stage file → repair duplicate
                try:
                    cs_file.unlink()
                    log("Deleted stale .cs from unexpected subdir: %s", cs_file)
                except OSError:
                    pass
        # Project-level Cargo.toml guard: run the cargo reflex chain before every
        # test attempt whenever a manifest exists — independent of whether the
        # plan has a cargo.toml task. The repair model routinely rewrites
        # Cargo.toml with a hallucinated dependency (e.g. `binary = "fib"`) that
        # is valid TOML but an invalid version requirement, so fix_rust_cargo_toml
        # (structure-only) leaves it; fix_rust_cargo_bad_dependency strips it. The
        # chain is a no-op on a clean manifest, so it never fights a legitimate
        # edit. Most Rust plans only have a src/main.rs task, so a per-task guard
        # never fired here — this is the gate that was missing.
        if Path('Cargo.toml').exists():
            run_reflexes([fix_rust_cargo_toml, fix_rust_cargo_bad_dependency],
                         'Cargo.toml')

        for t in p.tasks:
            if not Path(t.file_path).exists():
                continue
            # Always un-escape literal \n in any source file before testing
            fix_literal_newlines(t.file_path)
            if is_build_file(t.file_path) and Path(t.file_path).name.lower() == 'makefile':
                apply_makefile_reflexes(t.file_path)
                fix_makefile_binary_name(t.file_path, p.test_command or '')
            elif t.file_path.lower() == 'cargo.toml':
                # Covered by the project-level Cargo.toml guard above.
                pass
            elif t.file_path.endswith('.rs'):
                if Path(test_log).exists():
                    if fix_rust_missing_trait_import(t.file_path, _tail_file(test_log, 60)):
                        log("Repair reapply: added missing trait import to %s.", t.file_path)
            elif t.file_path.endswith('.cs'):
                test_out = _tail_file(test_log, 60) if Path(test_log).exists() else ''
                # skip files not mentioned in the error output — avoids redundant work
                fname = Path(t.file_path).name
                if not test_out or fname in test_out or t.file_path in test_out:
                    if apply_csharp_repair_reflexes(t.file_path, test_out):
                        log("Repair reapply: applied C# repair reflexes to %s.", t.file_path)
            elif Path(t.file_path).suffix.lower() in ('.js', '.jsx', '.mjs', '.ts', '.tsx'):
                js_test_out = _tail_file(test_log, 60) if Path(test_log).exists() else ''
                apply_js_repair_reflexes(t.file_path, js_test_out)
            if t.file_path.endswith('.py'):
                fix_flask_test_route_decorators(t.file_path)
                fix_flask_init_db_import(t.file_path)
                fix_sqlite_missing_row_factory(t.file_path)
                fix_sqlite_memory_multi_connect(t.file_path)
                fix_sqlite_conn_scope(t.file_path)
                fix_sqlite_class_missing_init_table(t.file_path)
                fix_flask_post_missing_201(t.file_path)
                # A test that uses app/db/a model from the implementation module
                # without importing it passes the syntax-only lint gate and only
                # fails at pytest runtime with NameError. The lint-phase resolver
                # never sees it, so resolve it here from the test output.
                if Path(test_log).exists():
                    if fix_python_undefined_imports(t.file_path, _tail_file(test_log, 60)):
                        log("Repair reapply: added missing import(s) to %s.", t.file_path)
        for t in p.tasks:  # trailing-dot in any .go file before go mod tidy
            if t.file_path.endswith('.go') and Path(t.file_path).exists():
                fix_go_trailing_dot(t.file_path)
        apply_go_reflexes()  # resolve Go module deps before each build attempt
        if fix_csharp_xunit_packages(os.getcwd()):
            log("Repair reapply: added xunit packages to .csproj.")
        if fix_csharp_package_tfm_mismatch(os.getcwd()):
            log("Repair reapply: aligned Microsoft.* package majors with the TFM.")
        # If any package.json exists but its node_modules is absent, run npm install.
        # The repair loop may rewrite package.json but never re-runs install.
        for t in p.tasks:
            if t.file_path.endswith('package.json') and Path(t.file_path).exists():
                pkg_dir = Path(t.file_path).parent
                # Strip Node builtins (e.g. an invented `"fs": "^14"`) first — npm
                # install fails with ETARGET on any of them.
                fix_package_json_builtin_deps(str(pkg_dir))
                if not (pkg_dir / 'node_modules').exists():
                    subprocess.run(['npm', 'install'], cwd=str(pkg_dir),
                                   capture_output=True, timeout=120)
        # If a requirements.txt exists, ensure .venv is set up and packages are installed.
        # Symmetric with npm install above. If the venv doesn't exist yet (e.g. the
        # Makefile is broken and never ran 'python3 -m venv .venv'), create it now
        # so the test command's '.venv/bin/pytest' invocation can succeed.
        req = Path('requirements.txt')
        if req.exists():
            # Strip stdlib module names before installing — they are not on PyPI and
            # would cause the entire pip invocation to fail (blocking pytest install).
            fix_requirements_stdlib_entries(str(req))
            venv_pip = Path('.venv/bin/pip')
            if not venv_pip.exists():
                subprocess.run(['python3', '-m', 'venv', '.venv'],
                               capture_output=True, timeout=60)
            if venv_pip.exists():
                # Install requirements first, then pytest separately so a bad entry
                # in requirements.txt cannot block the test runner from installing.
                subprocess.run([str(venv_pip), 'install', '-r', str(req), '-q'],
                               capture_output=True, timeout=120)
                subprocess.run([str(venv_pip), 'install', 'pytest', 'spacy', '-q'],
                               capture_output=True, timeout=120)
        # Re-apply package.json bare-jest fix — repair model may rewrite scripts.test
        if fix_jest_config_js(os.getcwd()):
            log("Re-applied: fixed jest.config.js syntax.")
        if fix_package_json_bare_jest(os.getcwd()):
            log("Re-applied: replaced bare jest with npx jest in package.json.")
        # Re-apply Jest/Vitest reflexes — the repair model may have rewritten
        # package.json or vite.config.ts, removing a testRegex or globals:true
        # that was added during the pre-flight pass. Read the latest test log
        # to check whether those fixes are still needed.
        if Path(test_log).exists():
            latest_out = _tail_file(test_log, 60)
            if fix_jest_no_tests_found(latest_out, os.getcwd()):
                log("Re-applied Jest testRegex (repair: No tests found).")
            if fix_jest_esm(latest_out, os.getcwd()):
                log("Re-applied NODE_OPTIONS=--experimental-vm-modules (repair: Jest ESM).")
            if fix_vitest_watch_mode(os.getcwd()):
                log("Re-applied vitest run mode in package.json.")
            if fix_vue_missing_package(os.getcwd()):
                log("Re-applied: added missing vue package to package.json.")
            if fix_vitest_globals(os.getcwd(), latest_out):
                log("Re-applied Vitest globals:true (repair: ReferenceError).")
            for t in p.tasks:
                if Path(t.file_path).exists() and Path(t.file_path).suffix.lower() in (
                    '.js', '.jsx', '.mjs', '.ts', '.tsx'
                ):
                    if fix_js_const_reassignment(t.file_path, latest_out):
                        log("Fixed %s: changed const to let (Assignment to constant variable).",
                            t.file_path)
            for t in p.tasks:
                if Path(t.file_path).exists() and t.file_path.endswith('.py'):
                    if fix_missing_flask_client_fixture(t.file_path, latest_out):
                        log("Re-applied: added Flask client fixture to %s.", t.file_path)

    # Run the test once before pre-flight reflexes so the log exists and is current.
    # _final_test_gate creates a fresh log path; without this first run the log
    # would be empty or stale, causing all error-pattern reflexes to be skipped.
    # First, ensure npm dependencies are installed so the test command can reach
    # jest/vitest — otherwise the pre-flight fails with "command not found" instead
    # of a meaningful test failure, and the error-pattern reflexes never fire.
    for t in p.tasks:
        if t.file_path.endswith('package.json') and Path(t.file_path).exists():
            pkg_dir = Path(t.file_path).parent
            fix_package_json_builtin_deps(str(pkg_dir))  # strip builtins before install
            if not (pkg_dir / 'node_modules').exists():
                subprocess.run(['npm', 'install'], cwd=str(pkg_dir),
                               capture_output=True, timeout=120)
    if fix_jest_config_js(os.getcwd()):
        log("Fixed jest.config.js: converted JSON to CommonJS or removed conflict.")
    if fix_package_json_bare_jest(os.getcwd()):
        log("Fixed package.json: replaced bare jest with npx jest (pre-flight).")
    # Strip any @app.route decorators and init_db imports from test files before first run
    for t in p.tasks:
        if Path(t.file_path).exists() and t.file_path.endswith('.py'):
            if fix_flask_test_route_decorators(t.file_path):
                log("Pre-flight: stripped @app.route decorators from %s.", t.file_path)
            if fix_flask_init_db_import(t.file_path):
                log("Pre-flight: removed init_db import from %s.", t.file_path)
    _run_cmd(test_cmd, test_log)
    initial_out = _tail_file(test_log, 60)
    if fix_missing_pip_packages(initial_out, os.getcwd()):
        log("Added missing pip packages to requirements before repair.")
    # Add missing Flask client fixture if tests use `client` but fixture not defined
    for t in p.tasks:
        if Path(t.file_path).exists() and t.file_path.endswith('.py'):
            if fix_missing_flask_client_fixture(t.file_path, initial_out):
                log("Added Flask client fixture to %s.", t.file_path)
    if fix_jest_no_tests_found(initial_out, os.getcwd()):
        log("Broadened Jest testRegex in package.json (No tests found).")
    if fix_jest_esm(initial_out, os.getcwd()):
        log("Added NODE_OPTIONS=--experimental-vm-modules for Jest ESM (pre-flight).")
    if fix_vitest_watch_mode(os.getcwd()):
        log("Changed vitest to vitest run in package.json.")
    if fix_vue_missing_package(os.getcwd()):
        log("Added missing vue package to package.json.")
    if fix_vitest_globals(os.getcwd(), initial_out):
        log("Enabled Vitest globals in vite.config.ts.")
    for t in p.tasks:
        if Path(t.file_path).exists():
            if fix_js_extra_closing_brace(t.file_path, initial_out):
                log("Fixed %s: fixed unbalanced brace/paren.", t.file_path)
            if Path(t.file_path).suffix.lower() in ('.js', '.jsx', '.mjs', '.ts', '.tsx'):
                if fix_js_const_reassignment(t.file_path, initial_out):
                    log("Fixed %s: changed const to let (Assignment to constant variable).",
                        t.file_path)
            if t.file_path.endswith('.cs') and 'CS0246' in initial_out:
                if fix_csharp_missing_using(t.file_path, initial_out):
                    log("Fixed %s: added missing using directive(s).", t.file_path)

    return sess.repair_loop(model, goal, _REPAIR_MAX_ITERS, float(writer_timeout),
                            run_test, reapply, syntax_check=_syntax_check,
                            make_context=lambda test_out: _repair_context(p, test_out))


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
        if ext in ('.js', '.mjs') and shutil.which('node'):
            r = subprocess.run(['node', '--check', path], capture_output=True,
                               text=True, timeout=15)
            return r.returncode == 0, (r.stderr or r.stdout)[:500]
    except SyntaxError as e:
        return False, f"{type(e).__name__}: {e}"
    except (OSError, ValueError, subprocess.SubprocessError):
        return True, ''
    return True, ''


_FUNC_START: dict[str, re.Pattern] = {
    '.py':  re.compile(r'^(?:def |class |async def )'),
    '.js':  re.compile(r'^(?:function |const |class |async function )'),
    '.jsx': re.compile(r'^(?:function |const |class |async function )'),
    '.ts':  re.compile(r'^(?:function |const |class |async function |export )'),
    '.tsx': re.compile(r'^(?:function |const |class |async function |export )'),
    '.rs':  re.compile(r'^(?:fn |pub fn |async fn |impl |pub struct )'),
    '.go':  re.compile(r'^func '),
}


def _error_lines_for_file(file_path: str, test_output: str) -> list[int]:
    """Return sorted list of line numbers referenced in test_output for file_path."""
    fname = re.escape(Path(file_path).name)
    matches = re.finditer(r'(?:^|[\s"\'(/])' + fname + r':(\d+)', test_output,
                          re.MULTILINE)
    nums = [int(m.group(1)) for m in matches if 1 <= int(m.group(1)) <= 100_000]
    return sorted(set(nums))


def _file_block(fp: str, test_output: str, per_file: int) -> str:
    """Return a code block for fp, windowed to the enclosing function around the
    first error line if one is found in test_output. Falls back to head-truncation
    for files with no referenced line, and returns '' on read error.
    """
    try:
        body = Path(fp).read_text()
    except OSError:
        return ''

    error_lines = _error_lines_for_file(fp, test_output)
    if not error_lines:
        if len(body) > per_file:
            body = body[:per_file] + '\n... [truncated]'
        return f'### {fp}\n```\n{body}\n```\n'

    # Locate the first mentioned error, walk back to enclosing function start.
    err = error_lines[0]
    lines = body.splitlines()
    n = len(lines)
    ext = Path(fp).suffix.lower()
    func_pat = _FUNC_START.get(ext)

    start = max(0, err - 30)
    if func_pat:
        for i in range(err - 2, max(-1, err - 100), -1):
            if i < n and func_pat.match(lines[i]):
                start = i
                break
    end = min(n, err + 10)

    chunk = '\n'.join(lines[start:end])
    if len(chunk) > per_file:
        chunk = chunk[:per_file] + '\n... [truncated]'
    note = f' (lines {start + 1}–{end}, error at {err})'
    return f'### {fp}{note}\n```\n{chunk}\n```\n'


def _repair_context(p: Plan, test_output: str = '') -> str:
    """Show the repair model the project's actual files, bounded in size.

    When test_output contains ``file:line`` references, each file's block is
    windowed to the enclosing function around the first error line instead of
    being head-truncated. Source files are shown before test files so the model
    reads the implementation alongside the assertions that exercise it.
    """
    per_file, total_budget = 2500, 8000
    blocks, used = [], 0
    for t in sorted(p.tasks, key=lambda t: is_test_file(t.file_path)):
        fp = t.file_path
        if not Path(fp).exists():
            continue
        block = _file_block(fp, test_output, per_file)
        if not block:
            continue
        if used + len(block) > total_budget:
            break
        blocks.append(block)
        used += len(block)
    if not blocks:
        return ''
    return '## Current project files (read these before editing)\n' + '\n'.join(blocks) + '\n\n'


def _apply_write_reflexes(file_path: str, test_command: str = '') -> None:
    """Run the per-language deterministic fix pass over one just-written file.

    Applied after every file modification the model makes — the initial
    writer AND each repair-loop edit. Repair edits used to skip this pass,
    so a repair that introduced e.g. `Flask(__name__)` without the import
    shipped broken even though the import reflex existed (2 stalled p7
    sessions, 2026-06-12 run 3).
    """
    if fix_tool_call_artifacts(file_path):
        log("Fixed %s: stripped tool-call artifact lines.", file_path)
    if fix_json_unclosed_brackets(file_path):
        log("Fixed %s: closed unclosed JSON brackets.", file_path)
    if fix_literal_newlines(file_path):
        log("Fixed %s: replaced literal \\n with real newlines.", file_path)

    if file_path.endswith('.cs'):
        apply_csharp_write_reflexes(file_path)
        log("Applied C# write reflexes to %s.", file_path)

    if file_path.endswith('.csproj'):
        if fix_csharp_package_tfm_mismatch(str(Path(file_path).parent) or '.'):
            log("Aligned Microsoft.* package majors with the TFM in %s.", file_path)

    if file_path.endswith('.py'):
        if fix_flask_test_route_decorators(file_path):
            log("Fixed %s: stripped @app.route decorators from test file.", file_path)
        if fix_flask_init_db_import(file_path):
            log("Fixed %s: removed init_db import (not defined in app.py).", file_path)
        if fix_sqlite_missing_row_factory(file_path):
            log("Fixed %s: added row_factory = sqlite3.Row after connect.", file_path)
        if fix_flask_post_missing_201(file_path):
            log("Fixed %s: added 201 to POST route return.", file_path)
        if fix_python_method_indent(file_path):
            log("Fixed %s: re-indented def after class decorator.", file_path)
        if fix_python_missing_def(file_path):
            log("Fixed %s: inserted missing def after orphaned decorator.", file_path)
        if fix_python_decorator_colon(file_path):
            log("Fixed %s: removed spurious colon from decorator.", file_path)
        if fix_python_missing_project_imports(file_path):
            log("Fixed %s: added missing project imports.", file_path)
        if fix_python_missing_stdlib_imports(file_path):
            log("Fixed %s: added missing stdlib imports.", file_path)
        if fix_test_import_module(file_path):
            log("Fixed %s: corrected import module name.", file_path)
        if fix_sqlite_path_unlink(file_path):
            log("Fixed %s: wrapped db_path.unlink() with Path().", file_path)
        if fix_sqlite_test_isolation(file_path):
            log("Fixed %s: replaced SQLite file path with :memory:.", file_path)
        if fix_sqlite_memory_multi_connect(file_path):
            log("Fixed %s: consolidated :memory: SQLite connections.", file_path)
        fp = Path(file_path)
        if fp.stem.startswith('test_'):
            for sib in fp.parent.glob('*.py'):
                if not sib.stem.startswith('test_') and sib.name != fp.name:
                    if fix_sqlite_test_isolation(str(sib)):
                        log("Fixed sibling %s: replaced SQLite file path with :memory:.", str(sib))
                    if fix_sqlite_memory_multi_connect(str(sib)):
                        log("Fixed sibling %s: consolidated :memory: SQLite connections.", str(sib))

    ext_lower = Path(file_path).suffix.lower()
    if ext_lower in ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.vue') \
            or file_path.lower().endswith('.vue'):
        apply_js_write_reflexes(file_path)
        log("Applied JS/Vue write reflexes to %s.", file_path)

    if file_path.endswith('.go') or file_path.endswith('go.mod'):
        if fix_go_trailing_dot(file_path):
            log("Reflex: removed dangling trailing '.' in %s.", file_path)
        if apply_go_reflexes():
            log("Resolved Go module dependencies (go mod tidy).")

    if file_path.lower() == 'cargo.toml':
        # Chain the Cargo.toml reflexes to a fixpoint: regenerate corrupted
        # structure, then strip hallucinated bad-version dependencies.
        run_reflexes([fix_rust_cargo_toml, fix_rust_cargo_bad_dependency],
                     file_path)

    if file_path.endswith('.rs'):
        apply_rust_source_reflexes(file_path)
        log("Applied Rust source reflexes to %s.", file_path)

    if file_path.endswith('requirements.txt'):
        if fix_requirements_path_entries(file_path):
            log("Fixed %s: removed path entries from requirements.", file_path)
        if fix_requirements_stdlib_entries(file_path):
            log("Fixed %s: removed stdlib entries from requirements.", file_path)

    if (is_build_file(file_path) and
            Path(file_path).name.lower() == 'makefile'):
        apply_makefile_reflexes(file_path)
        fix_makefile_binary_name(file_path, test_command)
        log("Applied Makefile reflexes to %s.", file_path)

    if Path(file_path).name.lower() == 'package.json':
        pkg_dir = str(Path(file_path).parent)
        if fix_package_json_builtin_deps(pkg_dir):
            log("Fixed %s: removed Node builtin(s) from dependencies.", file_path)
        if fix_package_json_bare_jest(pkg_dir):
            log("Fixed %s: replaced bare jest with npx jest.", file_path)


def _reflex_modified_files() -> None:
    """Apply the write-reflex pass to whatever the model just modified.

    Wired into repair loops as (part of) the per-iteration ``reapply`` hook;
    pulls the paths from tools.flush_modified() so it sees exactly the files
    the last repair turn touched, relative to the project dir.
    """
    for f in tools.flush_modified():
        rel = os.path.relpath(f) if os.path.isabs(f) else f
        if Path(rel).exists():
            _apply_write_reflexes(rel)


def _run_repair_lint(model: str, lint_cmd: str, file_path: str, lint_log: str, lint_head: str,
                     writer_timeout: int, goal: str,
                     plan_file: str = 'PLAN.md') -> None:
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
               f"do not create files.{hint}{file_content}{repair_history(plan_file)}\n\n")
    # Lean system: base protocol + only the one per-language repair guide for this
    # file. The full write-time system (python-env, python-writer, makefile-writer,
    # etc.) is ~1.9k tokens of guidance on how to *structure new projects* — useless
    # for fixing a lint error, and on a small model it bloats the prompt enough to
    # trigger degenerate 2-token replies or 400 context-overflow in the repair loop.
    lang = _EXT_LANGUAGE.get(Path(file_path).suffix.lower(), '')
    repair_skill = _load_skill(_LANG_REPAIR_SKILL.get(lang, '')) if lang else ''
    lean_system = _build_autonomous_system(os.getcwd())
    if repair_skill:
        lean_system += '\n\n' + repair_skill
    sess = Session(lean_system + '\n\n' + _repair_loop_rules(plan_file))
    sess.tool_set = tools.REPAIR
    set_chat_context('lint-repair', file_path)

    def run_test() -> tuple[bool, str]:
        return _run_cmd(lint_cmd, lint_log), _head_file(lint_log, 60)

    def lint_reapply() -> None:
        # Run the write-reflex pass on files the previous repair turn modified
        # — repair edits get the same deterministic fixes as initial writes.
        _reflex_modified_files()
        # Always regenerate Cargo.toml to the minimal grounded version before
        # each lint attempt. The repair model tends to add external crate deps
        # (e.g., `fibonacci = "0.1.1"`) that fail to compile. The fix_rust_cargo_toml
        # reflex only triggers on corrupted TOML; here we force-regenerate regardless.
        cargo = Path('Cargo.toml')
        if cargo.exists() and '.rs' in (file_path or ''):
            proj = Path(os.getcwd()).name or 'app'
            main_rs = next(
                (str(f) for f in Path('.').rglob('main.rs')
                 if 'target' not in str(f) and '.cargo' not in str(f)),
                None)
            bin_section = (
                f'\n[[bin]]\nname = "{proj}"\npath = "{main_rs}"\n'
                if main_rs and not main_rs.startswith('src/') else ''
            )
            clean = (
                '[package]\n'
                f'name = "{proj}"\n'
                'version = "0.1.0"\n'
                'edition = "2021"\n'
                + bin_section
            )
            current = cargo.read_text()
            if current.strip() != clean.strip():
                cargo.write_text(clean)
                log("Repair reapply (lint): reset Cargo.toml to minimal.")

    sess.repair_loop(model, goal, _REPAIR_MAX_ITERS, float(writer_timeout),
                     run_test, lint_reapply, context, _syntax_check)


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
                     writer_timeout: int, goal: str,
                     plan_file: str = 'PLAN.md') -> tuple[Optional[str], int]:
    """Run the final test gate with repair loop; return (error_msg_or_None, repair_iters)."""
    test_cmd = (p.test_command if p else '') or ''
    if not test_cmd:
        # Planner sometimes omits '## Test Command' (e.g. wraps output in code
        # fences and drops sections). Skipping the gate then declares success
        # without ever testing — a false positive. If the plan has test files,
        # run them; only skip when there is genuinely nothing to verify.
        test_files = [t.file_path for t in (p.tasks if p else []) if is_test_file(t.file_path)]
        if test_files:
            exts = {Path(f).suffix.lower() for f in test_files}
            if exts <= {'.rs'}:
                test_cmd = 'cargo test'
            elif exts <= {'.go'}:
                test_cmd = 'go test ./...'
            elif exts <= {'.cs'}:
                test_cmd = 'dotnet test'
            elif exts & {'.js', '.ts', '.jsx', '.tsx', '.mjs'}:
                # JS/TS project — if a Makefile exists, use make test, otherwise npx jest
                test_cmd = 'make test' if Path('Makefile').exists() else 'npx jest'
            else:
                py_files = [f for f in test_files if Path(f).suffix == '.py']
                test_cmd = ('pytest ' + ' '.join(py_files)) if py_files else 'pytest'
            log("No '## Test Command' — defaulting to: %s", test_cmd)
        else:
            log("No '## Test Command' and no test files — skipping final test gate.")
            return None, 0
    test_log = os.path.join(LOG_DIR, 'tests-final.log')
    ok, iters = _run_test_repair_loop(model, test_cmd, test_log, p, autonomous_system,
                                      writer_timeout, goal, plan_file)
    if ok:
        return None, iters
    record_failed_repair("final test gate: repair loop exhausted", _tail_file(test_log, 30),
                         plan_file)
    if iters == REPAIR_ESCALATE:
        print("\n  Tests stuck (same error repeating). Escalating.\n", flush=True)
    else:
        print("\n  Tests still failing after repair loop. Giving up.\n", flush=True)
    return "final tests failed", iters


# ── Architect ─────────────────────────────────────────────────────────────────

def _is_multilayer(goal: str) -> bool:
    """True when the goal describes a problem with at least two distinct layers.

    Detects: API/server + frontend, or model + API, or backend + frontend.
    Generic signal — no hardcoded problem names or filenames.
    """
    g = goal.lower()
    has_backend = any(k in g for k in (
        'api', 'backend', 'server', 'rest', 'endpoint', 'route', 'handler',
        'flask', 'django', 'express', 'gin', 'fastapi', 'asp.net', 'dotnet',
        'http', 'crud',
    ))
    has_frontend = any(k in g for k in (
        'frontend', 'vue', 'react', 'svelte', 'angular', 'ui', 'web app',
        'webapp', 'browser', 'component', 'page', 'vite', 'vitest',
    ))
    return has_backend and has_frontend


def _detect_stages(arch_text: str) -> list[str]:
    """Parse the '## Stages' section of ARCHITECTURE.md and return stage names."""
    m = re.search(r'(?m)^## Stages\s*\n(.*?)(?=\n## |\Z)', arch_text, re.DOTALL)
    if not m:
        return []
    return re.findall(r'^(model|backend|frontend):', m.group(1), re.MULTILINE)


def _run_stage_planner(stage: str, goal: str, model: str, arch_text: str,
                       timeout: int) -> bool:
    """Generate PLAN-{stage}.md using the architecture as context.

    Returns True if a valid plan file was produced.
    """
    import time
    plan_file = f'PLAN-{stage}.md'
    skill = _load_skill('task-planner')
    architect_skill = _load_skill('architect')

    stage_constraints = {
        'model': (
            "Plan ONLY the data layer described in ARCHITECTURE.md §Stages/model. "
            "The physical storage is ALWAYS SQLite — use it directly (no ORM unless "
            "the goal explicitly names one). "
            "Include a backend test file that exercises the schema — this is how "
            "the data model will be validated. "
            "All features named in the GOAL must be reflected in the schema."
        ),
        'backend': (
            "Plan ONLY the backend layer described in ARCHITECTURE.md §Stages/backend. "
            "Assume all data model files from PLAN-model.md are already implemented "
            "and correct. "
            "Include test files that cover both the model and backend routes. "
            "All features named in the GOAL must have corresponding API endpoints."
        ),
        'frontend': (
            "Plan ONLY the frontend layer described in ARCHITECTURE.md §Stages/frontend. "
            "Assume the backend API from PLAN-backend.md is already working and stable. "
            "All features named in the GOAL must be exposed in the UI. "
            "Do NOT plan backend files — only UI components, pages, and their tests."
        ),
    }
    constraint = stage_constraints.get(stage, '')

    system = (
        f"You are a planning agent producing {plan_file} for the {stage} stage only.\n"
        "Output ONLY the raw plan markdown — no preamble, no explanation, no code fences.\n"
        "Begin with ## Summary, then ## Files, then ## Test Command, then ## Dependencies.\n\n"
        "HARD CONSTRAINTS:\n"
        "- No Docker, no containers, no Dockerfiles, no docker-compose files.\n"
        "- SQLite is the only allowed database.\n"
        "- Every feature from the GOAL must appear in this stage's files.\n"
    )
    if skill:
        system += '\n\n' + skill
    if architect_skill:
        system += '\n\n' + architect_skill

    user_msg = (
        f"GOAL: {goal}\n\n"
        f"ARCHITECTURE:\n{arch_text}\n\n"
        f"STAGE INSTRUCTION: {constraint}\n\n"
        f"Create {plan_file} for the {stage} stage only. "
        "The ## Test Command must test ONLY this stage's files. "
        "Start with ## Summary."
    )

    msgs = [{'role': 'system', 'content': system},
            {'role': 'user', 'content': user_msg}]
    log("Stage planner: %s (timeout=%ds)", stage, timeout)
    print(f"  Planning {stage} stage...", flush=True)
    t0 = time.time()
    set_chat_context('stage-planner', stage)
    try:
        msg, stats = chat(model, msgs, None, float(timeout))
        elapsed = time.time() - t0
        log("chat: prompt=%d gen=%d time=%.1fs",
            stats.prompt_tokens, stats.generated_tokens, elapsed)
    except Exception as e:
        log("Stage planner error (%s): %s", stage, e)
        return False

    content = extract_plan_content(msg.get('content') or '')
    if not content or not re.search(r'(?m)^- \[[ x]\] ', content):
        log("Stage planner (%s): no valid task checklist produced.", stage)
        return False

    try:
        Path(plan_file).write_text(content)
        log("Stage plan written: %s", plan_file)
        print(f"\n{plan_file}:\n{content}\n", flush=True)
        return True
    except OSError as e:
        log("Stage planner: could not write %s: %s", plan_file, e)
        return False


def _run_architect_pass(goal: str, model: str, timeout: int) -> list[str]:
    """Generate ARCHITECTURE.md and per-stage plan files.

    Returns the list of stage names that have a generated plan file.
    """
    import time
    skill = _load_skill('architect')
    system = (
        "You are a software architect. Output ONLY the ARCHITECTURE.md markdown.\n"
        "No preamble, no explanation, no code fences around the whole document.\n"
        "HARD CONSTRAINTS:\n"
        "- No Docker, no containers, no Dockerfiles, no compose files.\n"
        "- SQLite is the only allowed data store.\n"
        "- All features from the GOAL must appear in the architecture.\n"
    )
    if skill:
        system += '\n\n' + skill

    user_msg = (
        f"GOAL: {goal}\n\n"
        "Produce ARCHITECTURE.md with ## System Context, ## Containers, "
        "## Implementation Order, and ## Stages sections. "
        "The ## Stages section must list each stage on its own line as: "
        "'model: ...', 'backend: ...', 'frontend: ...' (omit stages that don't apply)."
    )

    msgs = [{'role': 'system', 'content': system},
            {'role': 'user', 'content': user_msg}]
    log("Architect pass (timeout=%ds)", timeout)
    print("  Architecting...", flush=True)
    t0 = time.time()
    set_chat_context('architect')
    try:
        msg, stats = chat(model, msgs, None, float(timeout))
        elapsed = time.time() - t0
        log("chat: prompt=%d gen=%d time=%.1fs",
            stats.prompt_tokens, stats.generated_tokens, elapsed)
    except Exception as e:
        log("Architect error: %s", e)
        return []

    arch_text = (msg.get('content') or '').strip()
    if not arch_text:
        log("Architect: empty response.")
        return []

    try:
        Path('ARCHITECTURE.md').write_text(arch_text)
        log("ARCHITECTURE.md written.")
    except OSError as e:
        log("Architect: could not write ARCHITECTURE.md: %s", e)
        return []

    if strip_thinking_artifacts('ARCHITECTURE.md'):
        log("WARNING: thinking artifacts stripped from ARCHITECTURE.md")
        arch_text = Path('ARCHITECTURE.md').read_text()

    if '## Stages' not in arch_text:
        log("Architect: response missing ## Stages section.")
        return []

    print(f"\nARCHITECTURE.md:\n{arch_text}\n", flush=True)

    stages = _detect_stages(arch_text)
    if not stages:
        log("Architect: no stages detected in ## Stages section.")
        return []

    log("Detected stages: %s", ', '.join(stages))
    produced = []
    for stage in stages:
        if _run_stage_planner(stage, goal, model, arch_text, timeout):
            produced.append(stage)

    return produced


def run_staged(goal: str, model: str = '', target_dir: str = '',
               max_iter: int = 10) -> int:
    """Execute staged plan files sequentially with a hard backend→frontend gate."""
    if not model:
        model = os.environ.get('MU_AGENT_MODEL', '') or _select_model()
        if not model:
            return 1

    if target_dir:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        os.chdir(target_dir)

    active = [(name, pf) for name, pf in _STAGE_SEQUENCE if Path(pf).exists()]
    if not active:
        log("run_staged: no stage plan files found.")
        return 1

    for i, (stage_name, plan_file) in enumerate(active):
        log("=== Stage %d/%d: %s (%s) ===", i + 1, len(active), stage_name, plan_file)
        print(f"\n{'='*60}\n  Stage {i+1}/{len(active)}: {stage_name}\n{'='*60}\n",
              flush=True)

        rc = run(goal, model, plan_file=plan_file, force=True, max_iter=max_iter)
        if rc != 0:
            log("Stage '%s' failed (rc=%d) — halting staged execution.", stage_name, rc)
            return rc

        # Explicit backend→frontend gate: backend tests must pass before frontend begins.
        next_stages = active[i + 1:]
        if stage_name == 'backend' and any(n == 'frontend' for n, _ in next_stages):
            gate_rc = _inter_stage_gate(plan_file, goal, model)
            if gate_rc != 0:
                log("Backend→Frontend gate FAILED — frontend stage will NOT run.")
                return gate_rc
            log("Backend gate PASSED — proceeding to frontend.")

    return 0


def _inter_stage_gate(plan_file: str, goal: str, model: str) -> int:
    """Hard gate between backend and frontend stages.

    Closes the _final_test_gate escape hatch: if the backend plan has no test
    command and no test files, that is a hard failure rather than a silent skip.
    """
    p = parse(plan_file)
    test_cmd = p.test_command.strip() if p.test_command else ''

    if not test_cmd:
        test_files = [t.file_path for t in p.tasks if is_test_file(t.file_path)]
        if test_files:
            test_cmd = 'pytest ' + ' '.join(test_files)
            log("Inter-stage gate: no test command — inferred: %s", test_cmd)
        else:
            log("Inter-stage gate: %s has no test command and no test files.", plan_file)
            log("Cannot verify backend before frontend. Halting.")
            return 3

    gate_log = os.path.join(LOG_DIR, 'tests-backend-gate.log')
    if _run_cmd(test_cmd, gate_log):
        return 0

    log("Inter-stage gate: backend tests failing — attempting repair before frontend.")
    auto_system = _build_autonomous_system(os.getcwd(), plan_file)
    ok, _ = _run_test_repair_loop(model, test_cmd, gate_log, p, auto_system,
                                  _COMPLEXITY_WRITER['hard'], goal, plan_file)
    return 0 if ok else 3


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_standalone(force: bool, plan_file: str = 'PLAN.md') -> Optional[str]:
    if Path(plan_file).exists() or force:
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


def _validate_existing_plan(plan_file: str = 'PLAN.md') -> Optional[str]:
    try:
        content = Path(plan_file).read_text()
    except OSError as e:
        return str(e)
    if re.search(r'(?m)^### Group ', content):
        return f"{plan_file} uses old '### Group N' format — delete it to re-plan"
    if not re.search(r'(?m)^- \[([ x~])\]', content):
        return f"existing {plan_file} has no task checklist — delete it to re-plan"
    return None


def _build_autonomous_system(project_dir: str, plan_file: str = 'PLAN.md') -> str:
    return f"""You are a code-writing agent running autonomously in: {project_dir}

ROLE: You receive one task — write a specific file — and execute it immediately.

PROTOCOL:
1. Call the Write tool exactly once with the requested path and complete file contents.
2. Derive all implementation details from the GOAL and {plan_file}. Make your own decisions — never ask for clarification.
3. Stop the moment Write completes. No summary, no explanation, no additional output.

OFF-LIMITS:
- Never ask questions or request confirmation.
- Never write files other than the one explicitly requested.
- No arbitrary network calls (curl, wget, fetch, http, etc.).
- Only install packages explicitly listed in {plan_file}.
- Programs you write must NOT read from stdin (Console.ReadLine, input(), sys.stdin, scanf, etc.)
  unless the goal explicitly says "interactive". Use hard-coded sample values or CLI arguments instead."""


def _node_relevant(goal: str, p: Plan) -> bool:
    """True when the task is a Node.js project that installs packages or runs tests."""
    if any(t.file_path in ('package.json', 'package-lock.json') for t in p.tasks):
        return True
    blob = _goal_blob(goal, p) if p.test_command else goal.lower()
    return any(k in blob for k in ('node.js', 'nodejs', 'npm', 'jest', 'node '))


def _goal_blob(goal: str, p: Plan) -> str:
    """Lowercase concatenation of goal and test command — used by all _relevant checks."""
    return f"{goal}\n{p.test_command}".lower()


def _test_isolation_relevant(goal: str, p: Plan) -> bool:
    blob = _goal_blob(goal, p)
    has_db = any(k in blob for k in ('sqlite', 'database', ' db ', 'json file', 'storage'))
    has_tests = bool(re.search(r'\b(?:test|pytest|jest|vitest|xunit)\b', blob))
    return has_db and has_tests


def _no_server_relevant(goal: str, p: Plan) -> bool:
    blob = _goal_blob(goal, p)
    has_server = any(k in blob for k in ('http', 'server', 'api', 'flask',
                                          'gin', 'express', 'fastapi', 'asp.net', 'dotnet'))
    has_tests = bool(re.search(r'\b(?:test|pytest|jest|vitest|xunit)\b', blob))
    return has_server and has_tests


def _vue_relevant(goal: str, p: Plan) -> bool:
    if any(t.file_path.endswith('.vue') for t in p.tasks):
        return True
    return 'vue' in _goal_blob(goal, p)


def _dotnet_relevant(goal: str, p: Plan) -> bool:
    """True when the task involves an ASP.NET Core web API (not just a CLI dotnet app)."""
    blob = _goal_blob(goal, p)
    has_dotnet = any(t.file_path.endswith('.csproj') for t in p.tasks) or 'dotnet' in blob
    has_api = any(k in blob for k in ('api', 'endpoint', 'http', 'ef core', 'entityframework',
                                       'sqlite', 'database', 'web'))
    return has_dotnet and has_api


def _makefile_relevant(goal: str, p: Plan) -> bool:
    if any(Path(t.file_path).name == 'Makefile' for t in p.tasks):
        return True
    blob = _goal_blob(goal, p)
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


# A loaded skill whose content already states these contracts makes the matching
# inline block below redundant. The writer system prompt (with skills) is re-sent
# on every writer turn, so dropping the duplicate saves those tokens each turn
# without changing the guidance the model receives. All three test-isolation
# skills carry the per-test-fresh-state rule; makefile-writer carries the
# target/tab rules.
_TEST_ISOLATION_SKILLS = frozenset({'python-writer', 'test-isolation', 'dotnet-mvc'})
_MAKEFILE_SKILLS = frozenset({'makefile-writer'})


def _build_write_prompt(goal: str, task, p: Plan, companion: str = '',
                        plan_file: str = 'PLAN.md',
                        loaded_skills: set[str] | None = None) -> str:
    # On a very small context window keep the prompt minimal so the model has
    # enough budget left to write the file.
    compact = max_prompt_tokens() < 2000
    loaded_skills = loaded_skills or set()
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
    if not compact:
        # Emit each inline contract only when no loaded skill already states it —
        # the skill (in the re-sent system prompt) covers the model otherwise.
        if is_test_file(task.file_path) and not (loaded_skills & _TEST_ISOLATION_SKILLS):
            parts.append("\n\nTEST ISOLATION: give each test its own fresh state. Construct the "
                         "code under test with an in-memory or per-test temporary store (e.g. a "
                         "`:memory:` database, or a tmp file/dir via a fixture), or reset state in "
                         "setup/teardown. Never assert exact row counts or contents against a store "
                         "that other tests in the file also write — they will accumulate and fail.")
        if Path(task.file_path).name.lower() == 'makefile' and not (loaded_skills & _MAKEFILE_SKILLS):
            parts.append("\n\nMAKEFILE RULES: every name used as a prerequisite must have its own "
                         "`target:` rule or be a real file — if you write `all: run`, you must also "
                         "define a `run:` rule. Recipe lines are tab-indented.")
        if is_build_file(task.file_path):
            pending = pending_source_files(p, task.file_path)
            if pending:
                parts.append(f"\n\nCRITICAL — use these EXACT file paths from {plan_file} in "
                              f"`{task.file_path}`:\n{pending}")
    parts.append("""

## Steps
1. Determine the complete, correct content for the file from the goal and plan.
2. Call Write with the full, runnable content.
3. Stop immediately after Write — no other output.""")
    return ''.join(parts)


def _lint_failures_all_cosmetic(lint_log: str) -> bool:
    """True if every reported lint line is a purely cosmetic unused-variable
    warning ("assigned to but never used").

    Such warnings (pyflakes F841) never affect correctness — the code runs and
    pytest passes regardless — yet they fail the lint gate and send a small model
    into a doomed repair loop over a variable it usually can't safely remove (the
    RHS commonly has a side effect, e.g. `parser_list = subparsers.add_parser(...)`).
    Unused *imports* are deliberately NOT treated as cosmetic here — autoflake
    strips those, and leaving them masks real missing-symbol problems. Returns
    False on an empty log so a genuinely-clean rerun isn't misread as cosmetic.
    """
    try:
        lines = [ln for ln in Path(lint_log).read_text().splitlines() if ln.strip()]
    except OSError:
        return False
    if not lines:
        return False
    return all('assigned to but never used' in ln for ln in lines)


_CARGO_CLIPPY_AVAILABLE: 'Optional[bool]' = None


def _cargo_clippy_available() -> bool:
    """Return True if `cargo clippy` is installed (checked once and cached)."""
    global _CARGO_CLIPPY_AVAILABLE
    if _CARGO_CLIPPY_AVAILABLE is None:
        try:
            r = subprocess.run(['cargo', 'clippy', '--version'],
                               capture_output=True, timeout=10)
            _CARGO_CLIPPY_AVAILABLE = r.returncode == 0
        except Exception:
            _CARGO_CLIPPY_AVAILABLE = False
    return bool(_CARGO_CLIPPY_AVAILABLE)


def _lint_command(file_path: str, p: Plan) -> str:
    if is_build_file(file_path):
        return ''
    ext = Path(file_path).suffix.lower()
    has_makefile = any(Path(t.file_path).name.lower() == 'makefile' for t in p.tasks)
    has_cargo = (any(Path(t.file_path).name.lower() == 'cargo.toml' for t in p.tasks)
                 or Path('Cargo.toml').exists())
    has_tsconfig = any(Path(t.file_path).name.lower().startswith('tsconfig') for t in p.tasks)
    if ext == '.py':
        # pyflakes (pure-Python) covers F-codes and syntax errors; run it with
        # mu's own interpreter so the target venv needn't have it installed.
        # Cosmetic-only failures (unused variables) are filtered out of the gate
        # decision downstream (see _lint_failures_all_cosmetic) rather than by
        # switching linters — the deterministic repair reflexes parse pyflakes'
        # exact message format, so its output format must be preserved.
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
            # Don't lint with cargo check until all .rs files from the plan are written —
            # a missing sibling module file causes E0583 that the repair loop can't fix
            # (it can't create new files) and the real file will arrive in a later iteration.
            rs_tasks = [t for t in p.tasks if t.file_path.endswith('.rs')]
            if any(not Path(t.file_path).exists() for t in rs_tasks):
                return ''
            return 'cargo clippy' if _cargo_clippy_available() else 'cargo check'
        stem = Path(file_path).stem
        return (f"rustc --edition=2021 -Dwarnings {file_path} "
                f"-o /tmp/mu_lint_{stem} && rm -f /tmp/mu_lint_{stem}")
    if ext in ('.ts', '.tsx'):
        if not shutil.which('tsc'):
            return ''
        # tsc resolves npm type declarations from node_modules. Running it
        # before `npm install` always fails with "Cannot find module" errors
        # that look like code bugs but are actually missing node_modules.
        # Skip the lint gate and let the test gate (which runs make/npm) be
        # the authority once deps are installed.
        test_cmd_lower = (p.test_command or '').lower()
        has_pkg_json = any(t.file_path.endswith('package.json') for t in p.tasks)
        # Vitest handles its own type-checking during test runs; tsc standalone
        # is not useful and would fail before npm install runs.
        uses_vitest = 'vitest' in test_cmd_lower
        # Check if node_modules is absent in the file's directory or any parent.
        file_dir = Path(file_path).parent
        node_modules_missing = not any(
            (d / 'node_modules').exists()
            for d in [file_dir] + list(file_dir.parents)[:3]
        )
        if (has_pkg_json or uses_vitest) and node_modules_missing:
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

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mGKHF]|\x1b\].*?\x1b\\|\x1b[A-Za-z]')


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text (terminal color, cursor sequences)."""
    return _ANSI_RE.sub('', text)


def _read_file_lines(path: str, n: int, *, tail: bool = False) -> str:
    try:
        raw = Path(path).read_text()
        text = _strip_ansi(raw)
        lines = text.splitlines()
        subset = lines[-n:] if tail else lines[:n]
        return '\n'.join(subset)
    except OSError:
        return ''


def _tail_file(path: str, n: int) -> str:
    return _read_file_lines(path, n, tail=True)


def _extract_test_failures(log_path: str, max_chars: int = 3000) -> str:
    """Extract failure-focused content from a test log.

    Locates the FAILURES/ERRORS section (pytest), bullet failure blocks (jest/vitest),
    or the failures summary (cargo test), and returns that — not the noisy header.
    Falls back to the last 60 lines for unrecognised formats or passing runs.
    """
    try:
        raw = Path(log_path).read_text(errors='replace')
        content = _strip_ansi(raw)
    except OSError:
        return ''
    if not content.strip():
        return ''

    # Pytest: "=== FAILURES ===" or "=== ERRORS ===" section
    m = re.search(r'^={5,}\s+(FAILURES|ERRORS)\s+={5,}', content, re.MULTILINE)
    if m:
        chunk = content[m.start():]
        if len(chunk) > max_chars:
            chunk = chunk[:max_chars] + '\n... [truncated]'
        return chunk

    # Jest / Vitest: failure blocks start with a "● " bullet
    m = re.search(r'^\s*●\s+', content, re.MULTILINE)
    if m:
        chunk = content[m.start():]
        if len(chunk) > max_chars:
            chunk = chunk[:max_chars] + '\n... [truncated]'
        return chunk

    # Cargo test: "failures:" summary block
    m = re.search(r'^failures:\s*$', content, re.MULTILINE)
    if m:
        chunk = content[m.start():]
        if len(chunk) > max_chars:
            chunk = chunk[:max_chars] + '\n... [truncated]'
        return chunk

    # Unknown format or passing run: fall back to tail
    lines = content.splitlines()
    return '\n'.join(lines[-60:])


def _head_file(path: str, n: int) -> str:
    return _read_file_lines(path, n, tail=False)


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
    set_chat_context('lint-critique')
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
