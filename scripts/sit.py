#!/usr/bin/env python3
"""Run dojo problems and record results.

Env: MU_SIT_RUN_MODEL, MU_SIT_RUN_CTX, MU_LMSTUDIO_HOST, MU_SIT_VERBOSE
"""

import argparse, datetime, httpx, json, os, shutil, subprocess, sys, time
from pathlib import Path

MU_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = MU_ROOT / ".mu" / "sit_history"
RUN_LOG = LOG_DIR / "runs.jsonl"
ERROR_LOG = LOG_DIR / "errors.jsonl"

RUN_MODEL = os.environ.get("MU_SIT_RUN_MODEL", "mistral-7b-instruct-v0.2")
RUN_CTX = int(os.environ.get("MU_SIT_RUN_CTX", "4096"))
LMS_HOST = os.environ.get("MU_LMSTUDIO_HOST", "http://localhost:1234")
VERBOSE = os.environ.get("MU_SIT_VERBOSE", "").strip() not in ("", "0", "false")

def _get_env_info():
    try:
        import mu
        mu_version = getattr(mu, "__version__", "unknown")
    except Exception:
        mu_version = "unknown"
    return {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "mu_version": mu_version,
        "run_model": RUN_MODEL,
        "run_ctx": RUN_CTX,
        "lms_host": LMS_HOST,
        "platform": sys.platform,
    }

def _log_error(context: str, exc=None, extra=None):
    """Log error to errors.jsonl."""
    record = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
              "context": context, "env": _get_env_info()}
    if exc:
        record.update({"error_type": type(exc).__name__, "error_msg": str(exc)})
    if extra:
        record.update(extra)
    _append_jsonl(ERROR_LOG, record)
    _log(f"  ERROR LOGGED: {context}")

def write_error_summary(board, archive_dir=None):
    """Write a simple error summary."""
    failing = _failing_problems(board)
    lines = [f"# Error Summary\n", f"Total: {len(board)}, Failing: {len(failing)}\n"]
    for pid, p_solve in failing[:10]:
        data = board.get(pid, {})
        lines.append(f"- {pid} p={p_solve:.2f} lang={data.get('lang','?')}")
        if err := data.get('first_error', '')[:100]:
            lines.append(f"  {err}")
    content = '\n'.join(lines)
    output_path = (archive_dir or LOG_DIR) / "ERROR_SUMMARY.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    _log(f"  Summary written to {output_path.relative_to(MU_ROOT)}")

def _ts():
    return datetime.datetime.now().strftime("%H:%M:%S")

def _log(msg):
    print(f"[{_ts()}] {msg}", flush=True)

def _append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

def log_run(*, cycle, board, e_solved):
    """Log run results."""
    problems_detail = {}
    for pid, data in board.items():
        problems_detail[pid] = {
            "p_solve": round(_p_solve(data), 4),
            "raw_solve": round(_raw_solve(data), 4),
            "lang": data.get("lang", "unknown"),
            "first_error": data.get("first_error", "")[:200],
        }
    record = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
              "cycle": cycle, "e_solved": round(e_solved, 4),
              "env": _get_env_info(), "problems": problems_detail}
    _append_jsonl(RUN_LOG, record)

def check_lms_running():
    """Exit if LM Studio server is not reachable."""
    try:
        r = httpx.get(f"{LMS_HOST}/v1/models", timeout=5.0)
        if r.status_code == 200:
            return
        _log_error("LM Studio HTTP error", extra={"status": r.status_code})
    except Exception as e:
        _log_error("LM Studio check failed", e)
    sys.exit(f"\nStart LM Studio:\n  lms server start\n  lms load {RUN_MODEL}\n")

def _load_model(model_id):
    _log(f"Loading model: {model_id}")
    try:
        r = subprocess.run([sys.executable, "-m", "mu", "model", "load", model_id],
                          cwd=MU_ROOT, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            _log(f"  model load failed: {r.stderr[-200:]}")
            return False
        return True
    except Exception as e:
        _log(f"  model load error: {e}")
        return False

BOARD_JSON = MU_ROOT / ".mu" / "sit_board.json"

def _unwrap_board(raw):
    return raw.get("board") if isinstance(raw.get("board"), dict) else raw

def _layer_qs(data):
    return {l: v["q"] for l, v in data.items() if isinstance(v, dict) and "q" in v}

def _p_solve(data):
    if "p_solve" in data:
        return data["p_solve"]
    if "pass_rate" in data:
        return data["pass_rate"]
    qs = _layer_qs(data)
    prod = 1.0
    for q in qs.values():
        prod *= q
    return prod if qs else 0.0

def _raw_solve(data):
    rates = [v["clears"] / v["n"] for v in data.values()
             if isinstance(v, dict) and v.get("n")]
    if not rates:
        return data.get("pass_rate", data.get("p_solve", 0.0))
    prod = 1.0
    for r in rates:
        prod *= r
    return prod

def _e_solved(board):
    return sum(_p_solve(data) for data in board.values())

def _expected_gain(data):
    qs = _layer_qs(data)
    if not qs:
        return 0.0, None
    bn = min(qs, key=qs.get)
    siblings = 1.0
    for l, q in qs.items():
        if l != bn:
            siblings *= q
    return (1.0 - qs[bn]) * siblings, bn

def _failing_problems(board):
    failing = [(pid, _p_solve(data)) for pid, data in board.items()
               if _raw_solve(data) < 1.0]
    return sorted(failing, key=lambda x: -_expected_gain(board[x[0]])[0])

def run_mode(cycle=0):
    """Run dojo board with current model."""
    _log("=== RUN MODE ===")
    if not _load_model(RUN_MODEL):
        return {}, False

    dojo_runs_dir = MU_ROOT / "dojo"
    if dojo_runs_dir.exists():
        shutil.rmtree(dojo_runs_dir, ignore_errors=True)
    dojo_runs_dir.mkdir(parents=True, exist_ok=True)
    
    env = {**os.environ, "MU_AGENT_MODEL": RUN_MODEL,
           "ROUND_TIMEOUT": "600", "MU_DOJO_SAVE_RUNS": str(dojo_runs_dir)}
    BOARD_JSON.parent.mkdir(exist_ok=True)

    _log(f"Running dojo board (n=3) → {BOARD_JSON}")
    import re
    solved_re = re.compile(r"solved\s+(\d+)/3")

    stop_early = False
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "mu", "dojo", "board", "-n", "3", "--emit-json", str(BOARD_JSON)],
            cwd=MU_ROOT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True)
        deadline = time.monotonic() + 3600
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            m = solved_re.search(line)
            if m and int(m.group(1)) <= 1:
                _log(f"  early stop: {line.strip()}")
                stop_early = True
                proc.kill()
                break
            if time.monotonic() > deadline:
                _log("  timeout after 3600s")
                proc.kill()
                break
        else:
            proc.wait()
    except Exception as exc:
        _log(f"  error: {exc}")
        return {}, False

    if BOARD_JSON.exists():
        try:
            board = _unwrap_board(json.loads(BOARD_JSON.read_text()))
            _log(f"  board: {len(board)} problems")
            log_run(cycle=cycle, board=board, e_solved=_e_solved(board))
            archive_root = MU_ROOT / "archive"
            latest = None
            if archive_root.exists():
                existing = [int(p.name) for p in archive_root.iterdir()
                           if p.is_dir() and p.name.isdigit()]
                if existing:
                    latest = archive_root / f"{max(existing):03d}"
            write_error_summary(board, latest)
            return board, stop_early
        except Exception as e:
            _log(f"  parse error: {e}")
    return {}, stop_early

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    global VERBOSE
    if args.verbose:
        VERBOSE = True

    check_lms_running()
    _log(f"mu sit run={RUN_MODEL}(ctx={RUN_CTX}) root={MU_ROOT}")
    _log("Running dojo board...")
    board, stop_early = run_mode(cycle=1)
    
    if not board and not stop_early:
        _log("Empty board — no results.")
    elif failing := _failing_problems(board):
        _log(f"Failing: {[(p, f'{v:.2f}') for p, v in failing]}")
    else:
        _log("All passing!")

if __name__ == "__main__":
    main()