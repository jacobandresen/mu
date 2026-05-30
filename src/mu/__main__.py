"""mu CLI — argparse entry point."""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from mu import __version__
from mu import agent
from mu import client
from mu import theme as _theme


def main() -> int:
    parser = argparse.ArgumentParser(
        prog='mu',
        description='mu — local AI coding toolkit',
        epilog=f'Requires: LM Studio running at {client.LMS_HOST} (override: MU_LMSTUDIO_HOST)',
    )
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('check', help='Verify all required dependencies are installed')

    setup_p = sub.add_parser('setup', help='Install system dependencies')
    setup_p.add_argument('-y', '--yes', action='store_true', help='Skip confirmation prompts')

    model_p = sub.add_parser('model', help='Browse and select LM Studio models')
    model_sub = model_p.add_subparsers(dest='model_subcmd')
    model_sub.add_parser('status', help='Show loaded models')
    model_sub.add_parser('list', help='List curated models')
    load_p = model_sub.add_parser('load', help='Load a model via the lmstudio SDK')
    load_p.add_argument('model_id', help='Model ID to load')
    warm_p = model_sub.add_parser(
        'warm', help='Load a model persistently and run a warm-up generation')
    warm_p.add_argument('model_id', nargs='?', default='',
                        help='Model ID to warm (default: recommended)')
    unload_p = model_sub.add_parser('unload', help='Unload a model via the lmstudio SDK')
    unload_p.add_argument('model_id', help='Model ID to unload')
    model_sub.add_parser('ensure-single',
                         help='Abort if more than one non-embedding model is loaded')

    research_p = sub.add_parser('research', help='Search the web and write a factual report')
    research_p.add_argument('topic', help='Topic to research')
    research_p.add_argument('output', nargs='?', default='', metavar='FILE',
                            help='Output file (default: <topic>_report.md)')
    research_p.add_argument('--model', default='',
                            help='LM Studio model ID (overrides MU_AGENT_MODEL)')

    deep_p = sub.add_parser('deep', help='Research each PLAN.md task and annotate with actionable context')
    deep_p.add_argument('goal', nargs='?', default='', metavar='GOAL',
                        help='Optional plain-English goal to anchor research queries')
    deep_p.add_argument('-d', '--dir', default='', metavar='PATH',
                        help='Directory containing PLAN.md (default: current)')
    deep_p.add_argument('--model', default='',
                        help='LM Studio model ID (overrides MU_AGENT_MODEL)')

    plan_p = sub.add_parser('plan', help='Generate PLAN.md and write file sketches')
    plan_p.add_argument('goal', help='Plain-English coding goal')
    plan_p.add_argument('-d', '--dir', default='', metavar='PATH',
                        help='Create/enter PATH before running')
    plan_p.add_argument('--force', action='store_true',
                        help='Skip the existing-project guard')
    plan_p.add_argument('--model', default='',
                        help='LM Studio model ID (overrides MU_AGENT_MODEL)')

    agent_p = sub.add_parser('agent', help='Autonomous goal-to-code orchestrator')
    agent_p.add_argument('goal', help='Plain-English coding goal')
    agent_p.add_argument('-d', '--dir', default='', metavar='PATH',
                         help='Create/enter PATH before running')
    agent_p.add_argument('-n', '--max-iter', type=int, default=10, dest='max_iter',
                         help='Maximum iterations (default: 10)')
    agent_p.add_argument('--force', action='store_true',
                         help='Skip the existing-project guard')
    agent_p.add_argument('--model', default='',
                         help='LM Studio model ID (overrides MU_AGENT_MODEL)')

    split_p = sub.add_parser('split', help='Split PLAN.md tasks into smaller, actionable files')
    split_p.add_argument('goal', nargs='?', default='', metavar='GOAL',
                         help='Optional goal hint to focus the split')
    split_p.add_argument('-d', '--dir', default='', metavar='PATH',
                         help='Directory containing PLAN.md (default: current)')
    split_p.add_argument('--model', default='',
                         help='LM Studio model ID (overrides MU_AGENT_MODEL)')

    flow_p = sub.add_parser('flow', help='Pair each PLAN.md task with a testable step')
    flow_p.add_argument('goal', nargs='?', default='', metavar='GOAL',
                        help='Optional goal hint to anchor pairing')
    flow_p.add_argument('-d', '--dir', default='', metavar='PATH',
                        help='Directory containing PLAN.md (default: current)')
    flow_p.add_argument('--model', default='',
                        help='LM Studio model ID (overrides MU_AGENT_MODEL)')

    assess_p = sub.add_parser('assess', help='Assess each PLAN.md task for missing information and backfill earlier steps')
    assess_p.add_argument('goal', nargs='?', default='', metavar='GOAL',
                          help='Optional goal hint to anchor the assessment')
    assess_p.add_argument('-d', '--dir', default='', metavar='PATH',
                          help='Directory containing PLAN.md (default: current)')
    assess_p.add_argument('--model', default='',
                          help='LM Studio model ID (overrides MU_AGENT_MODEL)')

    lint_p = sub.add_parser('lint', help='Report deterministic warnings for a PLAN.md (no LLM)')
    lint_p.add_argument('plan', nargs='?', default='PLAN.md', metavar='PLAN',
                        help='Path to the plan file (default: PLAN.md)')

    iterate_p = sub.add_parser('iterate', help='Continue executing an existing PLAN.md')
    iterate_p.add_argument('goal', nargs='?', default='', metavar='GOAL',
                           help='Optional goal hint (inferred from PLAN.md if omitted)')
    iterate_p.add_argument('-d', '--dir', default='', metavar='PATH',
                           help='Directory containing PLAN.md (default: current)')
    iterate_p.add_argument('-n', '--max-iter', type=int, default=10, dest='max_iter',
                           help='Maximum iterations (default: 10)')
    iterate_p.add_argument('--model', default='',
                           help='LM Studio model ID (overrides MU_AGENT_MODEL)')

    reflect_p = sub.add_parser('reflect',
                               help='Distill recent failed sessions into CHALLENGES.md entries')
    reflect_p.add_argument('-n', '--limit', type=int, default=10,
                           help='Maximum failed sessions to process when no IDs given (default: 10)')
    reflect_p.add_argument('--model', default='',
                           help='LM Studio model ID (overrides MU_AGENT_MODEL)')
    reflect_p.add_argument('--challenges', default='CHALLENGES.md',
                           help='Path to CHALLENGES.md (default: ./CHALLENGES.md)')
    reflect_p.add_argument('session_ids', nargs='*', metavar='SESSION_ID',
                           help='Specific session IDs to reflect on; '
                                'overrides --limit when given')

    sub.add_parser('version', help='Print version')

    clean_p = sub.add_parser('clean', help='Scan for large files and suggest cleanup')
    clean_p.add_argument('--threshold', type=int, default=50, metavar='MB',
                         help='Size threshold in MB (default: 50)')

    extract_p = sub.add_parser('extract', help='Extract code blocks from log files')
    extract_p.add_argument('log_file', help='Log file to extract from')
    extract_p.add_argument('--run', action='store_true', help='Execute shell blocks')

    theme_p = sub.add_parser('theme', help='Pick and apply a base16 colour scheme')
    theme_sub = theme_p.add_subparsers(dest='theme_subcmd')
    theme_list_p = theme_sub.add_parser('list', help=argparse.SUPPRESS)
    theme_list_p.add_argument('dir')
    theme_preview_p = theme_sub.add_parser('preview', help=argparse.SUPPRESS)
    theme_preview_p.add_argument('yaml_path')
    theme_set_p = theme_sub.add_parser('set', help=argparse.SUPPRESS)
    theme_set_p.add_argument('config_path')
    theme_set_p.add_argument('scheme_name')
    theme_setclaude_p = theme_sub.add_parser('set-claude', help=argparse.SUPPRESS)
    theme_setclaude_p.add_argument('settings_path')
    theme_setclaude_p.add_argument('yaml_path')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        'check': _cmd_check,
        'setup': _cmd_setup,
        'model': _cmd_model,
        'research': _cmd_research,
        'deep': _cmd_deep,
        'plan': _cmd_plan,
        'agent': _cmd_agent,
        'split': _cmd_split,
        'flow': _cmd_flow,
        'assess': _cmd_assess,
        'lint': _cmd_lint,
        'iterate': _cmd_iterate,
        'reflect': _cmd_reflect,
        'version': _cmd_version,
        'clean': _cmd_clean,
        'extract': _cmd_extract,
        'theme': _cmd_theme,
    }
    return dispatch[args.command](args) or 0


# ── check ─────────────────────────────────────────────────────────────────────

def _cmd_check(args) -> int:
    deps = [
        ("Core", [
            ("git", "git", "mu setup"),
            ("make", "make", "mu setup"),
        ]),
        ("Compiler toolchains", [
            ("python3", "python3", "mu setup"),
            ("clang (C/C++)", "clang", "mu setup"),
            ("go (Go)", "go", "mu setup  # brew install go / apt install golang"),
            ("cargo (Rust)", "cargo", "rustup toolchain install stable"),
            ("dotnet (C#)", "dotnet", "mu setup  # brew install dotnet / apt install dotnet-sdk"),
        ]),
        ("Libraries", [
            ("SDL2", "sdl2-config", "mu setup"),
        ]),
        ("Static analysis", [
            ("clang-tidy", "clang-tidy", "mu setup"),
            ("tsc (TypeScript)", "tsc", "mu setup"),
        ]),
    ]
    ok_count = fail_count = 0
    for section, items in deps:
        print(section)
        for label, cmd, hint in items:
            if shutil.which(cmd):
                print(f"  [OK]  {label}")
                ok_count += 1
            else:
                print(f"  [!!]  {label:<28} {hint}")
                fail_count += 1
        print()

    print("AI backend")
    if client.is_running():
        print(f"  [OK]  LM Studio ({client.LMS_HOST})")
        ok_count += 1
    else:
        print(f"  [!!]  {'LM Studio':<28} start LM Studio and load a model [{client.LMS_HOST}]")
        fail_count += 1
    print()

    print("Python packages")
    py_pkgs = [
        ("lmstudio", "lmstudio"),
        ("httpx", "httpx"),
        ("InquirerPy", "InquirerPy"),
        ("pyflakes", "pyflakes"),
        ("autoflake", "autoflake"),
    ]
    for label, module in py_pkgs:
        try:
            __import__(module)
            print(f"  [OK]  {label}")
            ok_count += 1
        except ImportError:
            print(f"  [!!]  {label:<28} pip3 install {label.lower()} --break-system-packages")
            fail_count += 1
    print()

    # Optional plan-lint extra (Option A). Informational only — never counted
    # toward pass/fail, since the feature is opt-in behind MU_LINT_PLAN=1.
    print("Plan lint (optional — MU_LINT_PLAN=1)")
    try:
        import spacy  # noqa: F401
        try:
            spacy.load('en_core_web_sm')
            print("  [OK]  spaCy + en_core_web_sm")
        except OSError:
            print("  [--]  spaCy present, model missing   python3 -m spacy download en_core_web_sm")
    except ImportError:
        print("  [--]  spaCy not installed             pip3 install 'mu[lint]'")
    print()

    if fail_count == 0:
        print(f"All {ok_count} dependencies present.")
        return 0
    print(f"{fail_count} missing, {ok_count} present.")
    print("Run: mu setup")
    return 1


# ── setup ─────────────────────────────────────────────────────────────────────

def _cmd_setup(args) -> int:
    import platform
    yes = args.yes

    def confirm(prompt: str) -> bool:
        if yes:
            return True
        try:
            return input(f"{prompt} [y/N] ").strip().lower() == 'y'
        except (EOFError, KeyboardInterrupt):
            return False

    def run_cmd(*cmd) -> bool:
        print(f"  $ {' '.join(cmd)}")
        if not confirm("Proceed?"):
            return False
        return subprocess.run(cmd).returncode == 0

    system = platform.system()
    if system == 'Darwin':
        pkgs = ['make', 'llvm', 'node', 'git', 'fpc', 'SDL2', 'go', 'dotnet', 'rustup']
        if not run_cmd('brew', 'install', *pkgs):
            return 1
        if shutil.which('rustup'):
            run_cmd('rustup', 'toolchain', 'install', 'stable')
    elif system == 'Linux':
        if Path('/etc/arch-release').exists():
            pkgs = ['--needed', 'base-devel', 'make', 'gcc', 'clang', 'go', 'rust',
                    'nodejs', 'npm', 'python', 'git', 'fpc', 'dotnet-sdk',
                    'wl-clipboard', 'unzip']
            if not run_cmd('sudo', 'pacman', '-S', *pkgs):
                return 1
        elif Path('/etc/debian_version').exists():
            if not run_cmd('sudo', 'apt-get', 'update'):
                return 1
            pkgs = ['-y', 'build-essential', 'make', 'gcc', 'clang', 'clang-tidy',
                    'golang', 'cargo', 'nodejs', 'npm', 'python3', 'python3-pip',
                    'dotnet-sdk-8.0', 'git', 'fpc', 'unzip']
            if not run_cmd('sudo', 'apt-get', 'install', *pkgs):
                return 1
        else:
            print("Unsupported Linux distribution", file=sys.stderr)
            return 1
    else:
        print(f"Unsupported OS: {system}", file=sys.stderr)
        return 1

    # Optional plan-lint extra (Option A): only fetch the spaCy model if the
    # user has installed `mu[lint]`. Never force the heavy dependency here.
    try:
        import spacy  # noqa: F401
        try:
            spacy.load('en_core_web_sm')
        except OSError:
            print()
            print("Fetching spaCy model for plan lint (MU_LINT_PLAN)...")
            run_cmd(sys.executable, '-m', 'spacy', 'download', 'en_core_web_sm')
    except ImportError:
        pass

    print()
    print("AI backend: LM Studio")
    model = client.recommended_model()
    if not model:
        print("  Could not determine a recommended model for this hardware.")
        print("  Browse options with: mu model list")
    elif not client.is_running():
        print(f"  Recommended model for this system: {model}")
        print("  LM Studio isn't running — download it from https://lmstudio.ai, start it,")
        print("  then re-run `mu setup` to download the model automatically.")
    else:
        print(f"  Recommended model for this system: {model}")
        if confirm(f"Download {model} now?"):
            key = client.download_model(model, on_progress=_download_progress())
            print(f"  Downloaded: {key}" if key else "  Download failed — see message above.")
    print()
    print(f"  mu connects to {client.LMS_HOST} by default (override: MU_LMSTUDIO_HOST).")
    print("  Then run: mu agent \"your goal\"")
    return 0


def _download_progress():
    """Return an on_progress callback that prints download percent every ~5%."""
    state = {'last': -5}

    def cb(update) -> None:
        total = getattr(update, 'total_bytes', 0) or 0
        done = getattr(update, 'downloaded_bytes', 0) or 0
        if total <= 0:
            return
        pct = int(done * 100 / total)
        if pct >= state['last'] + 5 or pct >= 100:
            state['last'] = pct
            print(f"  downloading... {pct}% ({done // (1024*1024)} / {total // (1024*1024)} MB)")

    return cb


# ── model ─────────────────────────────────────────────────────────────────────

def _cmd_model(args) -> int:
    sub = getattr(args, 'model_subcmd', None)
    if sub == 'status':
        return _model_status()
    if sub == 'load':
        if client.load_model(args.model_id):
            _save_preferred_model(args.model_id)
            return 0
        return 1
    if sub == 'warm':
        return _model_warm(args.model_id)
    if sub == 'unload':
        return _model_unload(args.model_id)
    if sub == 'ensure-single':
        return _model_ensure_single()
    if sub == 'list':
        return _model_list()
    return _model_picker()


def _model_warm(model_id: str = '') -> int:
    """Ensure the target model is loaded and run a warm-up generation.

    Resolution order: explicit arg → MU_AGENT_MODEL env var → recommended.
    If the wrong model is running, it is unloaded and the correct one is
    loaded.  If the model is not yet downloaded, it is fetched from the hub.
    `client.load_model` uses ttl=None so the model stays resident across later
    runs until LM Studio restarts.
    """
    import time
    if not client.is_running():
        print(f"LM Studio not running at {client.LMS_HOST}", file=sys.stderr)
        return 1
    model = (model_id or os.environ.get('MU_AGENT_MODEL', '')
             or _load_preferred_model() or client.recommended_model())
    if not model:
        print("No model given and no recommended model found.", file=sys.stderr)
        return 1
    if not client.load_model(model):
        return 1
    # Resolve to the identifier LM Studio actually serves it under.
    active = _active_model_ids()
    target = next((a for a in active if _model_active(model, {a})), model)
    print(f"Warming up {target} …", flush=True)
    t0 = time.time()
    try:
        msg, stats = client.chat(
            target, [{'role': 'user', 'content': 'Reply with one word: ready'}],
            None, 120.0)
    except Exception as e:
        print(f"Warm-up generation failed: {e}", file=sys.stderr)
        return 1
    dt = time.time() - t0
    reply = (msg.get('content') or '').strip().replace('\n', ' ')[:40]
    print(f"Warm in {dt:.1f}s ({stats.generated_tokens} tok): {reply!r}")
    print("Resident (ttl=None) — stays loaded for later runs until LM Studio restarts.")
    # Single-slot check: one KV-cache slot means no eviction/contention, so the
    # prompt-prefix cache survives between calls. load_model already unloaded
    # others; warn if anything snuck back in.
    others = sorted(_active_model_ids() - {target})
    if others:
        print(f"Note: other models resident ({', '.join(others)}); run "
              "`mu model ensure-single` for a single KV-cache slot.")
    else:
        print("Single non-embedding model resident — one KV-cache slot.")
    return 0


def _active_model_ids() -> set[str]:
    """IDs of models currently loaded in LM Studio memory (via SDK)."""
    try:
        import lmstudio
        return {getattr(m, 'identifier', '') for m in lmstudio.list_loaded_models()
                if 'embed' not in getattr(m, 'identifier', '').lower()}
    except Exception:
        return set()


def _model_active(mid: str, active: set[str]) -> bool:
    """Check if catalog model ID matches an active model (handles org/ prefix differences)."""
    if mid in active:
        return True
    bare = mid.split('/')[-1]
    return any(bare == a or a.endswith('/' + bare) for a in active)


def _model_status() -> int:
    recommended = client.recommended_model()
    active = _active_model_ids()
    available = client.list_models()

    print("Active (loaded in memory):")
    if active:
        for mid in active:
            tag = '  [recommended]' if mid == recommended else ''
            print(f"  {mid}{tag}")
    else:
        print("  (none)")

    print("\nAvailable in LM Studio:")
    if available:
        for mid in available:
            tag = '  [recommended]' if mid == recommended else ''
            loaded_tag = '  [active]' if mid in active else ''
            print(f"  {mid}{loaded_tag}{tag}")
    else:
        print("  (none — load a model in LM Studio first)")
    return 0


def _model_unload(model_id: str) -> int:
    try:
        import lmstudio
        loaded = lmstudio.list_loaded_models()
        for m in loaded:
            if getattr(m, 'identifier', '') == model_id:
                m.unload()
                print(f"Unloaded: {model_id}")
                return 0
        print(f"Not loaded: {model_id}", file=sys.stderr)
        return 1
    except ImportError:
        print("lmstudio SDK not installed — run: pip3 install lmstudio --break-system-packages",
              file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error unloading {model_id}: {e}", file=sys.stderr)
        return 1


def _model_ensure_single() -> int:
    """Abort if more than one non-embedding model is loaded in memory. Dojo precondition."""
    try:
        import lmstudio
        loaded = lmstudio.list_loaded_models()
    except ImportError:
        print("lmstudio SDK not installed — run: pip3 install lmstudio --break-system-packages",
              file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: could not query LM Studio: {e}", file=sys.stderr)
        return 1

    non_embed = [m for m in loaded if 'embed' not in getattr(m, 'identifier', '').lower()]
    if not non_embed:
        print("ERROR: no model loaded in LM Studio — load a model first.", file=sys.stderr)
        return 1
    if len(non_embed) == 1:
        print(f"OK: {non_embed[0].identifier}")
        return 0
    ids = [m.identifier for m in non_embed]
    print("ERROR: multiple models loaded in LM Studio:", file=sys.stderr)
    for mid in ids:
        print(f"  {mid}", file=sys.stderr)
    print("Unload extras before running the dojo:", file=sys.stderr)
    for mid in ids[1:]:
        print(f"  mu model unload {mid}", file=sys.stderr)
    return 1


def _save_preferred_model(model_id: str) -> None:
    client.save_preferred_model(model_id)


def _load_preferred_model() -> str:
    return client.preferred_model()


def _model_list() -> int:
    catalog = _load_catalog()
    active = _active_model_ids()
    recommended = client.recommended_model()
    preferred = _load_preferred_model()
    if not catalog:
        for m in active:
            print(m)
        return 0
    print("Curated models (load in LM Studio before running mu agent)")
    for spec in catalog:
        mid = spec.get('id', '')
        ctx = f"{spec.get('contextWindow', 0) // 1024}k"
        tags = []
        if _model_active(mid, active):
            tags.append('loaded')
        if mid == recommended:
            tags.append('★ recommended for this hardware')
        if mid == preferred:
            tags.append('selected')
        tag_str = f"  [{', '.join(tags)}]" if tags else ''
        print(f"  {mid:<48} {ctx:>5}  {spec.get('description', '')}{tag_str}")
    return 0


def _fuzzy_pick(rows: list[tuple[str, object]], prompt: str):
    """Fuzzy-select one row (pure-Python fzf replacement).

    ``rows`` is a list of ``(display, value)`` pairs. Returns the chosen value,
    or None if the user cancelled or InquirerPy is unavailable.
    """
    try:
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
    except ImportError:
        print("InquirerPy not installed — run: pip3 install inquirerpy", file=sys.stderr)
        return None
    if not rows:
        return None
    choices = [Choice(value=value, name=display) for display, value in rows]
    try:
        return inquirer.fuzzy(
            message=prompt, choices=choices, max_height="70%", mandatory=False,
        ).execute()
    except KeyboardInterrupt:
        return None


def _model_picker() -> int:
    catalog = _load_catalog()
    active = _active_model_ids()
    recommended = client.recommended_model()
    preferred = _load_preferred_model()
    if catalog:
        rows = []
        for spec in catalog:
            mid = spec.get('id', '')
            ctx = f"{spec.get('contextWindow', 0) // 1024}k"
            tags = []
            if _model_active(mid, active):
                tags.append('loaded')
            if mid == recommended:
                tags.append('★ recommended')
            if mid == preferred:
                tags.append('selected')
            suffix = f"  [{', '.join(tags)}]" if tags else ''
            rows.append((f"{mid:<48} {ctx:>5}  {spec.get('description', '')}{suffix}", mid))
        # Sort: recommended first, then preferred, then rest
        rows.sort(key=lambda r: (r[1] != recommended, r[1] != preferred, r[0]))
    else:
        rows = [(m, m) for m in sorted(active)]
    model = _fuzzy_pick(rows, "model> ")
    if model:
        print(f"Selected: {model}")
        _save_preferred_model(model)
        client.load_model(model)
    return 0


def _load_catalog() -> list[dict]:
    return client.load_catalog()


# ── research ──────────────────────────────────────────────────────────────────

def _cmd_research(args) -> int:
    from mu import researcher
    model = args.model or os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        model = agent._select_model()
        if not model:
            return 1
    output = args.output or researcher.report_filename(args.topic)
    return researcher.research(args.topic, output, model)


# ── deep ──────────────────────────────────────────────────────────────────────

def _cmd_deep(args) -> int:
    from mu import researcher
    model = args.model or os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        model = agent._select_model()
        if not model:
            return 1
    target_dir = args.dir
    if target_dir:
        os.chdir(target_dir)
    plan_path = 'PLAN.md'
    if not Path(plan_path).exists():
        print(f"mu-deep: {plan_path} not found — run `mu plan` first", file=sys.stderr)
        return 1
    return researcher.deep(plan_path, model, args.goal)


# ── plan ──────────────────────────────────────────────────────────────────────

def _cmd_plan(args) -> int:
    return agent.plan(goal=args.goal, model=args.model,
                      target_dir=args.dir, force=args.force)


# ── agent ─────────────────────────────────────────────────────────────────────

def _cmd_agent(args) -> int:
    return agent.run(goal=args.goal, model=args.model, target_dir=args.dir,
                     max_iter=args.max_iter, force=args.force)


# ── split ─────────────────────────────────────────────────────────────────────

def _cmd_split(args) -> int:
    return agent.split(goal=args.goal, model=args.model, target_dir=args.dir)


# ── flow ──────────────────────────────────────────────────────────────────────

def _cmd_flow(args) -> int:
    return agent.flow(goal=args.goal, model=args.model, target_dir=args.dir)


# ── assess ────────────────────────────────────────────────────────────────────

def _cmd_assess(args) -> int:
    return agent.assess(goal=args.goal, model=args.model, target_dir=args.dir)


# ── lint ──────────────────────────────────────────────────────────────────────

def _cmd_lint(args) -> int:
    from mu.lint import lint_plan
    if not Path(args.plan).exists():
        print(f"mu-lint: {args.plan} not found — run `mu plan` first", file=sys.stderr)
        return 1
    warnings = lint_plan(args.plan)
    if not warnings:
        print(f"{args.plan}: no warnings.")
        return 0
    for w in warnings:
        print(f"- {w}")
    print(f"\n{len(warnings)} warning(s).")
    return 1


# ── iterate ───────────────────────────────────────────────────────────────────

def _cmd_iterate(args) -> int:
    return agent.iterate(goal=args.goal, model=args.model,
                         target_dir=args.dir, max_iter=args.max_iter)


# ── reflect ───────────────────────────────────────────────────────────────────

def _cmd_reflect(args) -> int:
    from mu import reflect
    return reflect.reflect(model=args.model, limit=args.limit,
                           challenges_path=args.challenges,
                           session_ids=args.session_ids or None)


# ── version ───────────────────────────────────────────────────────────────────

def _cmd_version(args) -> int:
    print(f"mu version {__version__}")
    return 0


# ── clean ─────────────────────────────────────────────────────────────────────

def _cmd_clean(args) -> int:
    threshold = args.threshold * 1024 * 1024
    found = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__')]
        for f in files:
            path = os.path.join(root, f)
            try:
                size = os.path.getsize(path)
                if size >= threshold:
                    found.append((size, path))
            except OSError:
                pass
    if not found:
        print(f"No files larger than {args.threshold}MB found.")
        return 0
    found.sort(reverse=True)
    print(f"Large files (>{args.threshold}MB):")
    for size, path in found:
        print(f"  {size / (1024 * 1024):6.1f}MB  {path}")
    print("\nTo remove:")
    for _, path in found:
        print(f"  rm {path!r}")
    return 0


# ── extract ───────────────────────────────────────────────────────────────────

def _cmd_extract(args) -> int:
    try:
        data = Path(args.log_file).read_text()
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    fence_re = re.compile(r'^```(\w+)?\s*$')
    close_re = re.compile(r'^```\s*$')
    path_re = re.compile(r'^(?://|#)\s*(\S+\.\S+)\s*$')
    lines, i, extracted = data.splitlines(), 0, []
    while i < len(lines):
        m = fence_re.match(lines[i])
        if m:
            lang = m.group(1) or ''
            i += 1
            block = []
            while i < len(lines) and not close_re.match(lines[i]):
                block.append(lines[i])
                i += 1
            i += 1
            if not block:
                continue
            pm = path_re.match(block[0])
            if pm:
                fp = pm.group(1)
                print(f"Extracting: {fp} ({lang})")
                try:
                    Path(fp).parent.mkdir(parents=True, exist_ok=True)
                    Path(fp).write_text('\n'.join(block[1:]))
                    extracted.append(fp)
                except OSError as e:
                    print(f"  Error: {e}")
            elif lang in ('sh', 'bash', 'shell') and args.run:
                subprocess.run(['bash', '-c', '\n'.join(block)])
        else:
            i += 1
    print(f"\nExtracted {len(extracted)} file(s)." if extracted else "No files extracted.")
    return 0


# ── theme ─────────────────────────────────────────────────────────────────────

def _cmd_theme(args) -> int:
    sub = getattr(args, 'theme_subcmd', None)

    if sub == 'list':
        for name, path in _theme.list_schemes(args.dir):
            print(f"{name}\t{path}")
        return 0

    if sub == 'preview':
        s = _theme.parse_scheme(args.yaml_path)
        if not s:
            print(f"Error: could not parse {args.yaml_path}", file=sys.stderr)
            return 1
        _theme.preview(s)
        return 0

    if sub == 'set':
        try:
            _theme.set_wezterm(args.config_path, args.scheme_name)
            print(f"updated {args.config_path} -> {args.scheme_name} (base16)")
        except (OSError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    if sub == 'set-claude':
        try:
            name = _theme.set_claude(args.settings_path, args.yaml_path)
            print(name)
        except (OSError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    # Interactive picker
    return _theme_picker()


def _theme_picker() -> int:
    home = Path.home()
    xdg_data = os.environ.get('XDG_DATA_HOME', str(home / '.local' / 'share'))
    schemes_dir = Path(os.environ.get('SCHEMES_DIR',
                                      Path(xdg_data) / 'tinted-theming' / 'schemes'))
    try:
        base16_dir = _theme.ensure_schemes(schemes_dir)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    items = _theme.list_schemes(base16_dir)
    if not items:
        print("No base16 schemes found.")
        return 1

    # Pick → preview the swatch → confirm, looping until the user accepts or quits.
    rows = [(name, (name, path)) for name, path in items]
    scheme_name = yaml_path = ''
    while True:
        chosen = _fuzzy_pick(rows, "theme> ")
        if not chosen:
            return 0  # user cancelled
        scheme_name, yaml_path = chosen
        s = _theme.parse_scheme(yaml_path)
        if s:
            _theme.preview(s)
        try:
            answer = input(f"Apply {scheme_name}? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 0
        if answer in ('', 'y', 'yes'):
            break

    wezterm_cfg = home / '.wezterm.lua'
    if not wezterm_cfg.exists():
        print(f"Error: {wezterm_cfg} not found", file=sys.stderr)
        return 1

    try:
        _theme.set_wezterm(wezterm_cfg, scheme_name)
        print(f"updated {wezterm_cfg} -> {scheme_name} (base16)")
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    claude_cfg = home / '.claude' / 'settings.json'
    if claude_cfg.exists() and yaml_path:
        try:
            claude_theme = _theme.set_claude(claude_cfg, yaml_path)
            print(f"updated {claude_cfg} -> {claude_theme}")
        except (OSError, ValueError) as e:
            print(f"Warning: {e}", file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main())
