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
            ("neovim", "nvim", "mu setup"),
            ("git", "git", "mu setup"),
            ("make", "make", "mu setup"),
            ("gcc", "gcc", "mu setup"),
        ]),
        ("Language runtimes", [
            ("python3", "python3", "mu setup"),
            ("pytest", "pytest", "pip3 install pytest"),
        ]),
        ("Tools", [
            ("fzf", "fzf", "mu setup"),
            ("ripgrep (rg)", "rg", "mu setup"),
            ("fd", "fd", "mu setup"),
            ("jq", "jq", "mu setup"),
            ("fpc", "fpc", "mu setup"),
        ]),
        ("Libraries", [
            ("SDL2", "sdl2-config", "mu setup"),
        ]),
        ("Static analysis", [
            ("clang-tidy", "clang-tidy", "mu setup"),
            ("ruff", "ruff", "mu setup"),
            ("tsc (TypeScript)", "tsc", "mu setup"),
            ("cargo clippy (Rust)", "cargo", "rustup toolchain install stable"),
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

    print("Python SDK")
    try:
        import lmstudio  # noqa: F401
        print("  [OK]  lmstudio")
        ok_count += 1
    except ImportError:
        print("  [!!]  lmstudio                     pip3 install lmstudio --break-system-packages")
        fail_count += 1
    try:
        import httpx  # noqa: F401
        print("  [OK]  httpx")
        ok_count += 1
    except ImportError:
        print("  [!!]  httpx                        pip3 install httpx --break-system-packages")
        fail_count += 1
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
        pkgs = ['neovim', 'make', 'gcc', 'llvm', 'node', 'python', 'jq', 'git',
                'fpc', 'fzf', 'ripgrep', 'fd', 'SDL2', 'ruff']
        if not run_cmd('brew', 'install', *pkgs):
            return 1
        run_cmd('brew', 'install', '--cask', 'font-terminess-ttf-nerd-font')
    elif system == 'Linux':
        if Path('/etc/arch-release').exists():
            pkgs = ['--needed', 'neovim', 'ttf-terminus-nerd', 'base-devel', 'make',
                    'gcc', 'clang', 'nodejs', 'npm', 'python', 'jq', 'git', 'fpc',
                    'fzf', 'wl-clipboard', 'ripgrep', 'fd', 'unzip', 'ruff']
            if not run_cmd('sudo', 'pacman', '-S', *pkgs):
                return 1
        elif Path('/etc/debian_version').exists():
            for cmd in [['sudo', 'apt-get', 'update'],
                        ['sudo', 'apt-get', 'install', '-y', 'software-properties-common'],
                        ['sudo', 'add-apt-repository', '-y', 'ppa:neovim-ppa/stable'],
                        ['sudo', 'apt-get', 'update']]:
                if not run_cmd(*cmd):
                    return 1
            pkgs = ['-y', 'neovim', 'build-essential', 'make', 'gcc', 'clang',
                    'clang-tidy', 'nodejs', 'npm', 'python3', 'python3-pip', 'jq',
                    'git', 'fpc', 'fzf', 'ripgrep', 'fd-find', 'unzip']
            if not run_cmd('sudo', 'apt-get', 'install', *pkgs):
                return 1
            run_cmd('pip3', 'install', '--user', 'ruff')
            fdfind = shutil.which('fdfind')
            if fdfind and not Path('/usr/local/bin/fd').exists():
                run_cmd('sudo', 'ln', '-sf', fdfind, '/usr/local/bin/fd')
            print("Note: install Terminess Nerd Font from https://www.nerdfonts.com/font-downloads")
        else:
            print("Unsupported Linux distribution", file=sys.stderr)
            return 1
    else:
        print(f"Unsupported OS: {system}", file=sys.stderr)
        return 1

    print()
    print("Installing Python dependencies...")
    run_cmd('pip3', 'install', '--break-system-packages', 'lmstudio')

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
        return 0 if client.load_model(args.model_id) else 1
    if sub == 'unload':
        return _model_unload(args.model_id)
    if sub == 'ensure-single':
        return _model_ensure_single()
    if sub == 'list':
        return _model_list()
    return _model_picker()


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


def _model_list() -> int:
    catalog = _load_catalog()
    active = _active_model_ids()
    recommended = client.recommended_model()
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
            tags.append('recommended')
        tag_str = f"  [{', '.join(tags)}]" if tags else ''
        print(f"  {mid:<48} {ctx:>5}  {spec.get('description', '')}{tag_str}")
    return 0


def _model_picker() -> int:
    if not shutil.which('fzf'):
        print("fzf not found — install it first (mu setup)")
        return 1
    catalog = _load_catalog()
    active = _active_model_ids()
    recommended = client.recommended_model()
    if catalog:
        lines = []
        for spec in catalog:
            mid = spec.get('id', '')
            ctx = f"{spec.get('contextWindow', 0) // 1024}k"
            tags = []
            if _model_active(mid, active):
                tags.append('loaded')
            if mid == recommended:
                tags.append('recommended')
            suffix = f"  [{', '.join(tags)}]" if tags else ''
            lines.append(f"{mid:<48} {ctx:>5}  {spec.get('description', '')}{suffix}\t{mid}")
    else:
        lines = [f"{m}\t{m}" for m in loaded]
    try:
        result = subprocess.run(['fzf', '--delimiter=\t', '--with-nth=1'],
                                input='\n'.join(lines), capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            model = result.stdout.strip().split('\t')[-1].strip()
            if model:
                print(f"Selected: {model}")
                print(f"Load this model in LM Studio, then run: mu agent \"your goal\"")
    except Exception as e:
        print(f"Error: {e}")
        return 1
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
    if not shutil.which('fzf'):
        print("fzf not found — install it first (mu setup)")
        return 1

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

    mu_bin = shutil.which('mu') or sys.argv[0]
    lines = '\n'.join(f"{name}\t{path}" for name, path in items)

    try:
        result = subprocess.run(
            ['fzf', '--delimiter=\t', '--with-nth=1', '--prompt=theme> ',
             f'--preview={mu_bin} theme preview {{2}}', '--preview-window=right:45%'],
            input=lines, capture_output=False, text=True,
            stdout=subprocess.PIPE, stderr=None,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if result.returncode != 0 or not result.stdout.strip():
        return 0  # user cancelled

    line = result.stdout.strip()
    parts = line.split('\t', 1)
    scheme_name = parts[0]
    yaml_path = parts[1] if len(parts) == 2 else ''

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
