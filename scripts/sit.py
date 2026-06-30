#!/usr/bin/env python3
"""Autonomous mu improvement loop: run dojo problems and record results.

Run mode: load run model, run dojo board (n=3), record results.

Env:
  MU_SIT_RUN_MODEL       (default: mistralai/Mistral-7B-Instruct-v0.2)
  MU_SIT_RUN_CTX         (default: 4096)
  MU_SIT_ROUNDS          (default: infinite)
  MU_LMSTUDIO_HOST       (default: http://localhost:1234)
  MU_SIT_VERBOSE         enable verbose logging
  Note: On <=6GB VRAM GPUs, use 4-bit quant. For >24GB, use Mixtral-8x7B-Instruct-v0.1.
"""

import argparse, datetime, httpx, json, os, shutil, subprocess, sys, time, traceback
from pathlib import Path

MU_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = MU_ROOT / ".mu" / "sit_history"
LOG_FILE = LOG_DIR / "attempts.jsonl"
RUN_LOG = LOG_DIR / "runs.jsonl"
ERROR_LOG = LOG_DIR / "errors.jsonl"

RUN_MODEL = os.environ.get("MU_SIT_RUN_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
RUN_CTX = int(os.environ.get("MU_SIT_RUN_CTX", "4096"))
LMS_HOST = os.environ.get("MU_LMSTUDIO_HOST", "http://localhost:1234")
VERBOSE = os.environ.get("MU_SIT_VERBOSE", "").strip() not in ("", "0", "false")


def _get_env_info() -> dict:
    """Gather environment info for debugging."""
    try:
        import mu
        mu_version = getattr(mu, "__version__", "unknown")
    except Exception:
        mu_version = "unknown"
    
    return {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "mu_version": mu_version,
        "run_model": RUN_MODEL,
        "run_ctx": RUN_CTX,
        "lms_host": LMS_HOST,
        "platform": sys.platform,
    }


def _log_error(context: str, exc: Exception | None = None, extra: dict = None) -> None:
    """Log error with stack trace to errors.jsonl for later analysis."""
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "context": context,
        "env": _get_env_info(),
    }
    if exc:
        record["error_type"] = type(exc).__name__
        record["error_msg"] = str(exc)
        record["stack_trace"] = traceback.format_exc()
    if extra:
        record.update(extra)
    _append_jsonl(ERROR_LOG, record)
    _log(f"  ERROR LOGGED to {ERROR_LOG.name}: {context}")


def _generate_error_summary(board: dict) -> dict:
    """Generate a concise, actionable error summary for improving unit tests.
    
    Returns a dict with structured error information that can be used to
    create targeted unit tests for mu modules.
    """
    summary = {
        "total_problems": len(board),
        "failing_problems": [],
        "modules_needing_tests": {},
        "error_patterns": {},
        "test_suggestions": [],
    }
    
    failing = _failing_problems(board)
    
    for pid, p_solve in failing:
        data = board.get(pid, {})
        first_error = data.get("first_error", "")
        lang = data.get("lang", "unknown")
        layers = _layer_qs(data)
        gain, bottleneck = _expected_gain(data)  # _expected_gain returns (gain, bottleneck)
        
        problem_summary = {
            "id": pid,
            "p_solve": round(p_solve, 4),
            "lang": lang,
            "first_error": first_error[:200],  # Truncate long errors
        }
        
        if bottleneck:
            module = _layer_to_module(bottleneck)
            problem_summary["bottleneck_layer"] = bottleneck
            problem_summary["suggested_module"] = module
            problem_summary["expected_gain"] = round(gain, 4)
            
            # Track modules needing tests
            if module not in summary["modules_needing_tests"]:
                summary["modules_needing_tests"][module] = {
                    "count": 0,
                    "problems": [],
                    "test_suggestion": _get_test_suggestion(module),
                }
            summary["modules_needing_tests"][module]["count"] += 1
            summary["modules_needing_tests"][module]["problems"].append(pid)
        
        # Track error patterns
        if first_error:
            error_key = first_error.split("\n")[0][:100]  # First line, truncated
            if error_key not in summary["error_patterns"]:
                summary["error_patterns"][error_key] = {
                    "count": 0,
                    "problems": [],
                    "example_error": first_error[:500],
                }
            summary["error_patterns"][error_key]["count"] += 1
            summary["error_patterns"][error_key]["problems"].append(pid)
        
        summary["failing_problems"].append(problem_summary)
    
    # Generate test suggestions
    for module, info in summary["modules_needing_tests"].items():
        summary["test_suggestions"].append({
            "module": module,
            "suggestion": info["test_suggestion"],
            "problem_count": info["count"],
            "example_problems": info["problems"][:3],
        })
    
    return summary


def _get_test_suggestion(module: str) -> str:
    """Get specific test suggestion for a mu module."""
    suggestions = {
        "planner (agent.py:PLAN.md parsing)": (
            "Add tests for PLAN.md parsing edge cases. Test with malformed plans, "
            "missing sections, and various task formats. Verify that the planner "
            "correctly identifies dependencies and ordering."
        ),
        "planner (agent.py)": (
            "Add tests for planner decision making. Test with different problem types "
            "and verify that the planner produces valid, executable plans."
        ),
        "writer (session.py:Session.run)": (
            "Add tests for code generation. Test that generated code compiles/runs, "
            "matches the expected structure, and handles edge cases. Use the "
            "language-specific skills to guide generation."
        ),
        "writer (session.py)": (
            "Add tests for the writer loop. Test file creation, editing, and "
            "verification steps. Ensure partial writes are handled correctly."
        ),
        "reflexes (reflexes/)": (
            "Add unit tests for each reflex in the reflexes/ package. Each reflex "
            "should have at least one test that demonstrates it fixes the specific "
            "error pattern it targets. Test both matching and non-matching cases."
        ),
        "lint (lint.py)": (
            "Add tests for lint detection. Test that linters catch the errors "
            "they're designed to find. Create test files with known issues."
        ),
        "test gate (session.py:test execution)": (
            "Add tests for test command execution. Verify that tests run correctly, "
            "results are parsed properly, and failures are diagnosed accurately."
        ),
        "repair loop (session.py:Session.repair_loop)": (
            "Add tests for the repair loop. Test that it correctly identifies "
            "and applies fixes for common error patterns. Verify it doesn't loop infinitely."
        ),
        "language toolchain (tools.py)": (
            "Add tests for language-specific toolchain operations. Test compilation, "
            "build, and execution for each supported language. Verify error handling."
        ),
    }
    return suggestions.get(module, f"Add unit tests for {module}")


def write_error_summary(board: dict, archive_dir: Path | None = None) -> Path:
    """Write a concise error summary file for the current board state.
    
    Returns the path to the written summary file.
    """
    summary = _generate_error_summary(board)
    
    # Create summary content
    lines = [
        "# Error Summary",
        "",
        f"**Total problems:** {summary['total_problems']}",
        f"**Failing problems:** {len(summary['failing_problems'])}",
        "",
    ]
    
    # Modules needing tests
    if summary["modules_needing_tests"]:
        lines.append("## Modules Needing Unit Tests")
        lines.append("")
        for module, info in sorted(summary["modules_needing_tests"].items(), 
                                   key=lambda x: -x[1]["count"]):
            lines.append(f"### {module}")
            lines.append(f"- **Problems affected:** {info['count']}")
            lines.append(f"- **Example problems:** {', '.join(info['problems'][:5])}")
            lines.append(f"- **Test suggestion:** {info['test_suggestion']}")
            lines.append("")
    
    # Error patterns
    if summary["error_patterns"]:
        lines.append("## Common Error Patterns")
        lines.append("")
        for error, info in sorted(summary["error_patterns"].items(),
                                  key=lambda x: -x[1]["count"]):
            lines.append(f"- **`{error}`** ({info['count']} occurrences)")
            lines.append(f"  - Problems: {', '.join(info['problems'][:5])}")
            lines.append("")
    
    # Per-problem details
    if summary["failing_problems"]:
        lines.append("## Failing Problems (by priority)")
        lines.append("")
        for prob in summary["failing_problems"][:10]:  # Top 10
            lines.append(f"- **{prob['id']}** (p_solve={prob['p_solve']}, lang={prob['lang']})")
            if prob.get("bottleneck_layer"):
                lines.append(f"  - Bottleneck: {prob['bottleneck_layer']} → {prob.get('suggested_module', 'unknown')}")
            if prob.get("first_error"):
                lines.append(f"  - First error: {prob['first_error'][:100]}")
            lines.append("")
    
    content = "\n".join(lines)
    
    # Determine output path
    if archive_dir:
        output_path = archive_dir / "ERROR_SUMMARY.md"
    else:
        output_path = LOG_DIR / "latest_error_summary.md"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    
    # Also write JSON version for programmatic access
    json_path = output_path.with_suffix('.json')
    json_path.write_text(json.dumps(summary, indent=2))
    
    # Only show relative path if it's under MU_ROOT
    try:
        rel_path = output_path.relative_to(MU_ROOT)
        _log(f"  Error summary written to {rel_path}")
        _log(f"  JSON summary written to {rel_path.with_suffix('.json')}")
    except ValueError:
        _log(f"  Error summary written to {output_path}")
        _log(f"  JSON summary written to {json_path}")
    
    return output_path


def _read(path: Path, max_chars: int = 6000) -> str:
    if not path.exists():
        return f"(not found: {path})"
    t = path.read_text(errors="replace")
    return t[:max_chars] + "\n…(truncated)" if len(t) > max_chars else t


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def _vlog(msg: str) -> None:
    if VERBOSE:
        print(f"[{_ts()}] [V] {msg}", flush=True)


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_run(*, cycle: int, board: dict, e_solved: float) -> None:
    """Log run results with detailed problem analysis."""
    env_info = _get_env_info()
    
    problems_detail = {}
    failing_modules = {}  # Track which mu modules have failures
    
    for pid, data in board.items():
        p_solve = _p_solve(data)
        raw_solve = _raw_solve(data)
        problems_detail[pid] = {
            "p_solve": round(p_solve, 4),
            "raw_solve": round(raw_solve, 4),
            "lang": data.get("lang", "unknown"),
            "first_error": data.get("first_error", ""),
        }
        
        # Extract layer information with module hints
        layers = _layer_qs(data)
        if layers:
            problems_detail[pid]["layers"] = layers
            # Identify bottleneck layer and map to mu module
            gain, bottleneck = _expected_gain(data)
            if bottleneck:
                problems_detail[pid]["bottleneck_layer"] = bottleneck
                problems_detail[pid]["expected_gain"] = round(gain, 4)
                # Map layer names to mu modules
                module_hint = _layer_to_module(bottleneck)
                if module_hint:
                    failing_modules[module_hint] = failing_modules.get(module_hint, 0) + 1
                    problems_detail[pid]["suggested_module"] = module_hint
    
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "cycle": cycle,
        "e_solved": round(e_solved, 4),
        "env": env_info,
        "problems": problems_detail,
        "failing_modules": failing_modules,
    }
    _append_jsonl(RUN_LOG, record)


def check_lms_running() -> None:
    """Exit with instructions if LM Studio server is not reachable."""
    try:
        r = httpx.get(f"{LMS_HOST}/v1/models", timeout=5.0)
        if r.status_code == 200:
            return
        _log_error("LM Studio HTTP error", extra={"status_code": r.status_code, "url": f"{LMS_HOST}/v1/models"})
    except httpx.NetworkError as e:
        _log_error("LM Studio network error", e, extra={"host": LMS_HOST})
    except Exception as e:
        _log_error("LM Studio check failed", e, extra={"host": LMS_HOST})
    
    sys.exit(
        f"\nLM Studio server is not running at {LMS_HOST}.\n"
        "Please start it first:\n\n"
        "  lms server start\n"
        f"  lms load {RUN_MODEL}\n\n"
        "For >24GB VRAM GPUs, also load:\n"
        "  lms load mistralai/Mixtral-8x7B-Instruct-v0.1\n\n"
        "Then re-run sit.py."
    )


def _load_model(model_id: str) -> bool:
    _log(f"Loading model: {model_id}")
    try:
        r = subprocess.run(
            [sys.executable, "-m", "mu", "model", "load", model_id],
            cwd=MU_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.returncode != 0:
            error_output = (r.stdout + r.stderr)[-400:]
            _log(f"  model load failed:\n{error_output}")
            _log_error("model load failed", extra={"model": model_id, "returncode": r.returncode, "output": error_output})
            return False
        return True
    except subprocess.TimeoutExpired:
        _log(f"  model load timed out after 120s")
        _log_error("model load timeout", extra={"model": model_id, "timeout": 120})
        return False
    except Exception as e:
        _log(f"  model load error: {e}")
        _log_error("model load exception", e, extra={"model": model_id})
        return False


def _active_model() -> str:
    try:
        r = httpx.get(f"{LMS_HOST}/v1/models", timeout=5.0)
        for m in r.json().get("data", []):
            mid = m.get("id", "")
            if "embed" not in mid.lower():
                return mid
    except Exception:
        pass
    return ""


BOARD_JSON = MU_ROOT / ".mu" / "sit_board.json"


def _unwrap_board(raw: dict) -> dict:
    if "board" in raw and isinstance(raw["board"], dict):
        return raw["board"]
    return raw


def _layer_qs(data: dict) -> dict[str, float]:
    return {l: v["q"] for l, v in data.items()
            if isinstance(v, dict) and "q" in v}


def _p_solve(data: dict) -> float:
    if "p_solve" in data:
        return data["p_solve"]
    if "pass_rate" in data:
        return data["pass_rate"]
    qs = _layer_qs(data)
    if qs:
        prod = 1.0
        for q in qs.values():
            prod *= q
        return prod
    return 0.0


def _raw_solve(data: dict) -> float:
    rates = [v["clears"] / v["n"] for v in data.values()
             if isinstance(v, dict) and v.get("n")]
    if not rates:
        if "pass_rate" in data:
            return data["pass_rate"]
        if "p_solve" in data:
            return data["p_solve"]
        return 0.0
    prod = 1.0
    for r in rates:
        prod *= r
    return prod


def _e_solved(board: dict) -> float:
    return sum(_p_solve(data) for data in board.values())


def _expected_gain(data: dict):
    qs = _layer_qs(data)
    if not qs:
        return 0.0, None
    bn = min(qs, key=qs.get)
    siblings = 1.0
    for l, q in qs.items():
        if l != bn:
            siblings *= q
    return (1.0 - qs[bn]) * siblings, bn


def _layer_to_module(layer_name: str) -> str:
    """Map layer/step names to mu modules for targeted improvements."""
    layer_lower = layer_name.lower()
    
    # Map common layer names to mu modules
    layer_mappings = {
        "plan": "planner (agent.py:PLAN.md parsing)",
        "planning": "planner (agent.py)",
        "write": "writer (session.py:Session.run)",
        "writing": "writer (session.py)",
        "reflex": "reflexes (reflexes/ package)",
        "reflexes": "reflexes (reflexes/ package)",
        "lint": "lint (lint.py)",
        "test": "test gate (session.py:test execution)",
        "testing": "test gate (session.py)",
        "repair": "repair loop (session.py:Session.repair_loop)",
        "solve": "planner (agent.py)",
        "compile": "language toolchain (tools.py)",
        "build": "language toolchain (tools.py)",
        "backend": "language toolchain (tools.py)",
        "frontend": "language toolchain (tools.py)",
        "integration": "test gate (session.py)",
        "unit": "test gate (session.py)",
    }
    
    for pattern, module in layer_mappings.items():
        if pattern in layer_lower:
            return module
    
    # Default mappings based on common prefixes
    if layer_lower.startswith(("plan", "plann")):
        return "planner (agent.py)"
    if layer_lower.startswith(("write", "writ")):
        return "writer (session.py)"
    if layer_lower.startswith(("reflex", "fix")):
        return "reflexes (reflexes/)"
    if layer_lower.startswith(("lint", "check")):
        return "lint (lint.py)"
    if layer_lower.startswith(("test", "spec")):
        return "test gate (session.py)"
    if layer_lower.startswith(("repair", "fix")):
        return "repair loop (session.py)"
    
    return "unknown"


def _failing_problems(board: dict):
    failing = [(pid, _p_solve(data)) for pid, data in board.items()
               if _raw_solve(data) < 1.0]
    return sorted(failing, key=lambda x: -_expected_gain(board[x[0]])[0])


def run_mode(cycle: int = 0) -> tuple[dict, bool]:
    """Run dojo board with current model."""
    _log("=== RUN MODE ===")
    if not _load_model(RUN_MODEL):
        _log("  Could not load run model — skipping run phase.")
        return {}, False

    dojo_runs_dir = MU_ROOT / "dojo"
    if dojo_runs_dir.exists():
        shutil.rmtree(dojo_runs_dir, ignore_errors=True)
    dojo_runs_dir.mkdir(parents=True, exist_ok=True)
    
    env = {
        **os.environ,
        "MU_AGENT_MODEL": RUN_MODEL,
        "ROUND_TIMEOUT": "600",
        "MU_DOJO_SAVE_RUNS": str(dojo_runs_dir),
    }
    BOARD_JSON.parent.mkdir(exist_ok=True)

    _log(f"Running dojo board (n=3) → {BOARD_JSON}")
    import re
    solved_re = re.compile(r"solved\s+(\d+)/3")

    stop_early = False
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "mu", "dojo", "board", "-n", "3", "--emit-json", str(BOARD_JSON)],
            cwd=MU_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + 3600
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            m = solved_re.search(line)
            if m and int(m.group(1)) <= 1:
                _log(f"  early stop: {line.strip()}")
                stop_early = True
                proc.kill()
                proc.wait()
                break
            if time.monotonic() > deadline:
                _log("  dojo board timed out after 3600s — stopping.")
                proc.kill()
                proc.wait()
                _log_error("dojo board timeout", extra={"timeout_seconds": 3600})
                break
        else:
            proc.wait()
            if proc.returncode != 0:
                _log(f"  dojo board exited non-zero (code={proc.returncode})")
                _log_error("dojo board non-zero exit", extra={"returncode": proc.returncode})
    except Exception as exc:
        _log(f"  dojo board error: {exc}")
        _log_error("dojo board exception", exc)
        return {}, False

    if stop_early:
        _log("  board run stopped early — partial results available.")

    if BOARD_JSON.exists():
        try:
            board = _unwrap_board(json.loads(BOARD_JSON.read_text()))
            _log(f"  board loaded: {len(board)} problems")
            log_run(cycle=cycle, board=board, e_solved=_e_solved(board))
            
            # Write error summary for unit test improvements
            # Try to write to latest archive directory if it exists
            archive_root = MU_ROOT / "archive"
            if archive_root.exists():
                existing = [int(p.name) for p in archive_root.iterdir() 
                           if p.is_dir() and p.name.isdigit()]
                if existing:
                    latest_archive = archive_root / f"{max(existing):03d}"
                    write_error_summary(board, latest_archive)
                else:
                    write_error_summary(board)
            else:
                write_error_summary(board)
            
            for pid, data in board.items():
                _vlog(f"  {pid}: p_solve={_p_solve(data):.3f}  lang={data.get('lang', '?')}  first_error={str(data.get('first_error', ''))[:120]}")
            
            # Log module improvement suggestions
            failing = _failing_problems(board)
            if failing:
                _log(f"  Problems needing attention: {len(failing)}")
                for pid, _ in failing[:5]:  # Top 5
                    data = board.get(pid, {})
                    gain, bottleneck = _expected_gain(data)
                    if bottleneck:
                        module = _layer_to_module(bottleneck)
                        _log(f"    {pid}: bottleneck='{bottleneck}' → improve {module} (gain={gain:.3f})")
            
            return board, stop_early
        except Exception as e:
            _log(f"  could not parse board JSON: {e}")
            _log_error("board JSON parsing failed", e, extra={"file": str(BOARD_JSON)})
    return {}, stop_early


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Emit verbose debug logs")
    ap.add_argument("--rounds", type=int, default=int(os.environ.get("MU_SIT_ROUNDS", "0")),
                    help="Max run cycles (0 = infinite)")
    ap.add_argument("--run-only", action="store_true",
                    help="Only run dojo once and print the board, then exit")
    args = ap.parse_args()

    global VERBOSE
    if args.verbose:
        VERBOSE = True

    check_lms_running()

    _log(f"mu sit  run={RUN_MODEL}(ctx={RUN_CTX})")
    _log(f"mu root: {MU_ROOT}")

    if args.run_only:
        run_mode(cycle=0)
        return

    cycle = 0
    while True:
        cycle += 1
        _log(f"\n{'=' * 60}")
        _log(f"CYCLE {cycle}")

        board, stop_early = run_mode(cycle=cycle)
        if not board and not stop_early:
            _log("Empty board — waiting 60s before retry")
            time.sleep(60)
            continue

        failing = _failing_problems(board)
        if not failing:
            _log("All problems passing — goal achieved!")
            break

        _log(f"Failing problems: {[(p, f'{v:.2f}') for p, v in failing]}")

        if args.rounds and cycle >= args.rounds:
            _log(f"Reached --rounds {args.rounds} — stopping.")
            break

        time.sleep(5)


if __name__ == "__main__":
    main()