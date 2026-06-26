"""mu CLI — argparse entry point."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from mu import __version__
from mu import agent
from mu import client


def _extend_path() -> None:
    """Prepend common tool install locations that shells may not include."""
    from mu.toolchain import prepend_tool_paths
    prepend_tool_paths()


def main() -> int:
    """Parse CLI arguments and dispatch to the requested mu sub-command."""
    _extend_path()
    # `mu dojo …` is the test rig — hidden from the product CLI and handed off
    # verbatim to its own argparse (so `mu dojo --help` etc. work cleanly).
    if len(sys.argv) > 1 and sys.argv[1] == 'dojo':
        from mu.dojo.cli import main as dojo_main
        return dojo_main(sys.argv[2:])
    parser = argparse.ArgumentParser(
        prog='mu',
        description='mu — local AI coding toolkit',
        epilog=f'Requires: LM Studio running at {client.LMS_HOST} (override: MU_LMSTUDIO_HOST)',
    )
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('check', help='Verify all required dependencies are installed')

    setup_p = sub.add_parser('setup', help='Install system dependencies')
    setup_p.add_argument('-y', '--yes', action='store_true', help='Skip confirmation prompts')

    lsp_p = sub.add_parser('lsp', help='Language-server diagnostics + quick-fix repair (VSCode-style)')
    lsp_p.add_argument('lsp_args', nargs='*', metavar='ARG',
                       help='<diagnose|fix|langs> [file]')

    model_p = sub.add_parser('model', help='Browse and select models')
    model_sub = model_p.add_subparsers(dest='model_subcmd')
    model_sub.add_parser('status', help='Show loaded models')
    model_sub.add_parser('list', help='List curated models')
    load_p = model_sub.add_parser('load', help='Load a model in LM Studio')
    load_p.add_argument('model_id', help='Model ID (e.g. qwen2.5-coder-7b-instruct)')

    warm_p = model_sub.add_parser(
        'warm', help='Load a model persistently and run a warm-up generation')
    warm_p.add_argument('model_id', nargs='?', default='',
                        help='Model ID to warm (default: recommended)')
    unload_p = model_sub.add_parser('unload', help='Unload a model via the lmstudio SDK')
    unload_p.add_argument('model_id', help='Model ID to unload')
    model_sub.add_parser('ensure-single',
                         help='Abort if more than one non-embedding model is loaded')

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

    improve_p = sub.add_parser('improve',
                               help='Analyze a PLAN.md and tighten ambiguous specs (filenames, '
                                    'test harness, data contracts, decomposition) so a weak model '
                                    'is tested on coding, not guessing')
    improve_p.add_argument('goal', nargs='?', default='', metavar='GOAL',
                           help='Optional goal hint (inferred from PLAN.md if omitted)')
    improve_p.add_argument('-d', '--dir', default='', metavar='PATH',
                           help='Directory containing PLAN.md (default: current)')
    improve_p.add_argument('--plan', default='PLAN.md', metavar='PLAN',
                           help='Plan file to improve (default: PLAN.md)')
    improve_p.add_argument('--force', action='store_true',
                           help='Rewrite even if the analysis finds the plan adequate')
    improve_p.add_argument('--model', default='',
                           help='LM Studio model ID (overrides MU_AGENT_MODEL)')

    architect_p = sub.add_parser('architect',
                                  help='Generate ARCHITECTURE.md and staged plan files for a hard problem')
    architect_p.add_argument('goal', help='Plain-English coding goal')
    architect_p.add_argument('-d', '--dir', default='', metavar='PATH',
                             help='Create/enter PATH before running')
    architect_p.add_argument('--model', default='',
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
                               help='Distill recent failed sessions into docs/challenges/README.md entries')
    reflect_p.add_argument('-n', '--limit', type=int, default=10,
                           help='Maximum failed sessions to process when no IDs given (default: 10)')
    reflect_p.add_argument('--model', default='',
                           help='LM Studio model ID (overrides MU_AGENT_MODEL)')
    reflect_p.add_argument('--challenges', default='docs/challenges/README.md',
                           help='Path to the challenge KB (default: docs/challenges/README.md)')
    reflect_p.add_argument('session_ids', nargs='*', metavar='SESSION_ID',
                           help='Specific session IDs to reflect on; '
                                'overrides --limit when given')

    kb_p = sub.add_parser('kb',
                          help='Build/show the reflex knowledge base (catalog + model profiles)')
    kb_p.add_argument('--sessions', default='',
                      help='Session archive dir (default: ~/.mu/sessions)')

    sub.add_parser('version', help='Print version')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        'check': _cmd_check,
        'setup': _cmd_setup,
        'model': _cmd_model,
        'plan': _cmd_plan,
        'agent': _cmd_agent,
        'improve': _cmd_improve,
        'architect': _cmd_architect,
        'iterate': _cmd_iterate,
        'reflect': _cmd_reflect,
        'kb': _cmd_kb,
        'lsp': _cmd_lsp,
        'version': _cmd_version,
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

    print("LM Studio")
    if client.is_running():
        print(f"  [OK]  LM Studio server ({client.LMS_HOST})")
        ok_count += 1
    else:
        print(f"  [!!]  {'LM Studio':<28} start it: lms server start && lms load <model> [{client.LMS_HOST}]")
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

    # Optional static-analysis tools. Present = repair loop can use them.
    # Not counted toward pass/fail — all are optional enrichments.
    print("Optional analysis (repair loop enrichment — no-op when absent)")
    opt_tools = [
        ("ruff",    "ruff",    "pip3 install ruff",                          "Python fast linter"),
        ("pyright", "pyright", "pip3 install pyright  OR  npm i -g pyright", "Python type checker"),
        ("eslint",  "eslint",  "npm install -g eslint",                      "JavaScript/TypeScript linter"),
        ("biome",   "biome",   "npm install -g @biomejs/biome",              "JS/TS formatter+linter"),
    ]
    for label, cmd, hint, desc in opt_tools:
        if shutil.which(cmd):
            print(f"  [--]  {label}")
        else:
            print(f"  [--]  {label:<10} not found   {hint}")
    # cargo clippy: separate component from cargo itself
    import subprocess as _sp
    try:
        _cp = _sp.run(['cargo', 'clippy', '--version'], capture_output=True, timeout=5)
        if _cp.returncode == 0:
            print("  [--]  cargo clippy")
        else:
            print("  [--]  cargo clippy not found   rustup component add clippy")
    except Exception:
        print("  [--]  cargo clippy not found   rustup component add clippy")
    print()

    # Optional plan-lint extra. Informational only — never counted toward
    # pass/fail; it enriches the lint phase of `mu improve` when present.
    print("Plan lint (optional — used by `mu improve`)")
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
    dotnet_installed = bool(shutil.which('dotnet'))
    if system == 'Darwin':
        pkgs = ['make', 'llvm', 'node', 'git', 'fpc', 'SDL2', 'go', 'rustup']
        if not dotnet_installed:
            pkgs.append('dotnet')
        if not run_cmd('brew', 'install', *pkgs):
            return 1
        if shutil.which('rustup'):
            run_cmd('rustup', 'toolchain', 'install', 'stable')
    elif system == 'Linux':
        if Path('/etc/arch-release').exists():
            pkgs = ['--needed', 'base-devel', 'make', 'gcc', 'clang', 'go', 'rust',
                    'nodejs', 'npm', 'python', 'git', 'fpc', 'wl-clipboard', 'unzip']
            if not dotnet_installed:
                pkgs.append('dotnet-sdk')
            if not run_cmd('sudo', 'pacman', '-S', *pkgs):
                return 1
        elif Path('/etc/debian_version').exists():
            if not run_cmd('sudo', 'apt-get', 'update'):
                return 1
            pkgs = ['-y', 'build-essential', 'make', 'gcc', 'clang', 'clang-tidy',
                    'clangd', 'golang', 'cargo', 'nodejs', 'npm', 'python3',
                    'python3-pip', 'git', 'fpc', 'unzip']
            if not dotnet_installed:
                pkgs.append('dotnet-sdk-8.0')
            if not run_cmd('sudo', 'apt-get', 'install', *pkgs):
                return 1
        else:
            print("Unsupported Linux distribution", file=sys.stderr)
            return 1
    else:
        print(f"Unsupported OS: {system}", file=sys.stderr)
        return 1

    # Optional analysis tools — repair loop enrichment.
    # Each is skipped (no-op) when absent, so none are required.
    print()
    print("Optional analysis tools (repair loop enrichment)")
    import importlib.util as _ilu
    missing_opt: list[tuple[str, list[str]]] = []
    if not _ilu.find_spec('ruff'):
        missing_opt.append(('ruff', [sys.executable, '-m', 'pip', 'install', 'ruff']))
    if not _ilu.find_spec('pyright'):
        missing_opt.append(('pyright', [sys.executable, '-m', 'pip', 'install', 'pyright']))
    if shutil.which('npm'):
        if not shutil.which('eslint'):
            missing_opt.append(('eslint', ['npm', 'install', '-g', 'eslint']))
        if not shutil.which('biome'):
            missing_opt.append(('biome', ['npm', 'install', '-g', '@biomejs/biome']))
    if shutil.which('rustup'):
        try:
            cp = subprocess.run(['cargo', 'clippy', '--version'],
                                capture_output=True, timeout=5)
            if cp.returncode != 0:
                missing_opt.append(('cargo clippy', ['rustup', 'component', 'add', 'clippy']))
        except Exception:
            missing_opt.append(('cargo clippy', ['rustup', 'component', 'add', 'clippy']))
    if not missing_opt:
        print("  All optional analysis tools already present.")
    else:
        for label, cmd in missing_opt:
            print(f"  {label} not found.")
            run_cmd(*cmd)

    # Language servers (LSP repair — `mu lsp`, MU_LSP=1). VSCode-style diagnostics +
    # quick-fix code actions. Each gated on its toolchain and skipped if already present;
    # all degrade to a no-op at runtime when absent, so none are required.
    print()
    print("Language servers (LSP repair)")
    ls_missing: list[tuple[str, list[str]]] = []
    if shutil.which('rustup') and not shutil.which('rust-analyzer'):
        ls_missing.append(('rust-analyzer', ['rustup', 'component', 'add', 'rust-analyzer']))
    if shutil.which('go') and not shutil.which('gopls'):
        ls_missing.append(('gopls', ['go', 'install', 'golang.org/x/tools/gopls@latest']))
    # npm globals without sudo: install under a user prefix (~/.local ⇒ bins in
    # ~/.local/bin, which prepend_tool_paths adds to PATH). No system writes.
    _npm_prefix = str(Path.home() / '.local')
    if shutil.which('npm'):
        if not shutil.which('typescript-language-server'):
            ls_missing.append(('typescript-language-server',
                               ['npm', 'install', '-g', '--prefix', _npm_prefix,
                                'typescript-language-server', 'typescript']))
        if not shutil.which('vue-language-server'):
            ls_missing.append(('vue-language-server',
                               ['npm', 'install', '-g', '--prefix', _npm_prefix, '@vue/language-server']))
    if dotnet_installed and not shutil.which('csharp-ls'):
        # dotnet global tools already install per-user (~/.dotnet/tools), no sudo.
        ls_missing.append(('csharp-ls', ['dotnet', 'tool', 'install', '-g', 'csharp-ls']))
    # pyright-langserver (Python) comes from the pyright install in the optional-tools section.
    if not shutil.which('clangd'):
        print("  clangd (C/C++) not found — install via your llvm/clang package "
              "(arch: clang · debian: clangd · mac: llvm).")
    if not ls_missing:
        print("  All installable language servers already present.")
    else:
        for label, cmd in ls_missing:
            print(f"  {label} not found.")
            run_cmd(*cmd)

    # Optional plan-lint (used by `mu improve`): spaCy + en_core_web_sm model.
    print()
    print("Optional plan lint (used by `mu improve`)")
    try:
        import spacy  # noqa: F401
        try:
            spacy.load('en_core_web_sm')
            print("  spaCy + en_core_web_sm already present.")
        except OSError:
            print("  spaCy present, model missing.")
            run_cmd(sys.executable, '-m', 'spacy', 'download', 'en_core_web_sm')
    except ImportError:
        print("  spaCy not installed.")
        if run_cmd(sys.executable, '-m', 'pip', 'install', "mu[lint]"):
            run_cmd(sys.executable, '-m', 'spacy', 'download', 'en_core_web_sm')

    print()
    print("AI backend: LM Studio")
    catalog = client.load_catalog()
    model = next((m['id'] for m in catalog if m.get('setup_default')), None) or client.recommended_model()
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
    """Check if catalog model ID matches an active model (handles org/ prefix differences,
    case differences, and GGUF quantization suffixes in the filename)."""
    if mid in active:
        return True
    bare = client.normalize_model_bare(mid)
    return any(client.normalize_model_bare(a) == bare for a in active)


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
    recommended = client.recommended_model()
    preferred = _load_preferred_model()
    if not catalog:
        for m in _active_model_ids():
            print(m)
        return 0
    active = _active_model_ids()
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
    """Return the curated model catalog."""
    return client.load_catalog()



# ── plan ──────────────────────────────────────────────────────────────────────

def _cmd_plan(args) -> int:
    return agent.plan(goal=args.goal, model=args.model,
                      target_dir=args.dir, force=args.force)


# ── agent ─────────────────────────────────────────────────────────────────────

def _cmd_agent(args) -> int:
    return agent.run(goal=args.goal, model=args.model, target_dir=args.dir,
                     max_iter=args.max_iter, force=args.force)


# ── improve ───────────────────────────────────────────────────────────────────

def _cmd_improve(args) -> int:
    return agent.improve(goal=args.goal, model=args.model, target_dir=args.dir,
                              plan_file=args.plan, force=args.force)


# ── architect ─────────────────────────────────────────────────────────────────

def _cmd_architect(args) -> int:
    model = args.model or os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        model = agent._select_model()
        if not model:
            return 1
    if args.dir:
        Path(args.dir).mkdir(parents=True, exist_ok=True)
        os.chdir(args.dir)
    from mu.agent import _COMPLEXITY_PLANNER, detect_complexity
    timeout = _COMPLEXITY_PLANNER[detect_complexity(args.goal)]
    stages = agent._run_architect_pass(args.goal, model, timeout)
    if not stages:
        print("mu-architect: no stages produced.", file=sys.stderr)
        return 1
    print(f"mu-architect: produced stages: {', '.join(stages)}")
    return 0


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


# ── kb ─────────────────────────────────────────────────────────────────────────

def _cmd_kb(args) -> int:
    """Rebuild the reflex knowledge base from the session archive and print it."""
    from mu import reflexdb
    sessions = args.sessions or os.environ.get('MU_AGENT_ARCHIVE_DIR', '') or None
    counts = reflexdb.build(sessions_dir=sessions)
    print(f"Reflex KB rebuilt: {counts['reflex']} reflexes, {counts['session']} "
          f"sessions, {counts['firing']} firings, {counts['model_profile']} model profiles.\n")
    print(reflexdb.report())
    return 0


# ── version ───────────────────────────────────────────────────────────────────

def _cmd_lsp(args) -> int:
    """Language-server diagnostics + quick-fix repair (VSCode-style)."""
    from mu import lsp
    return lsp.cli(args.lsp_args)


def _cmd_version(args) -> int:
    print(f"mu version {__version__}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
