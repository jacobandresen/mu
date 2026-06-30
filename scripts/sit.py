#!/usr/bin/env python3
"""Autonomous mu improvement loop: run dojo problems and record results.

Run mode: load run model, run dojo board (n=3), record results.

Env:
  MU_SIT_RUN_MODEL       (default: mistralai/Mistral-7B-Instruct-v0.2)
  MU_SIT_RUN_CTX         (default: 4096)
  MU_SIT_ROUNDS          (default: infinite)
  MU_LMSTUDIO_HOST       (default: http://localhost:1234)
  MU_SIT_VERBOSE         enable verbose logging
  Note: On <=6GB VRAM GPUs, use 4-bit quant. For >24GB, use Mixtral-8x7B.
"""

import argparse, datetime, httpx, json, os, shutil, subprocess, sys, textwrap, time
from pathlib import Path

MU_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = MU_ROOT / ".mu" / "sit_history"
LOG_FILE = LOG_DIR / "attempts.jsonl"
RUN_LOG = LOG_DIR / "runs.jsonl"

RUN_MODEL = os.environ.get("MU_SIT_RUN_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
RUN_CTX = int(os.environ.get("MU_SIT_RUN_CTX", "4096"))
LMS_HOST = os.environ.get("MU_LMSTUDIO_HOST", "http://localhost:1234")
VERBOSE = os.environ.get("MU_SIT_VERBOSE", "").strip() not in ("", "0", "false")


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
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "cycle": cycle,
        "e_solved": round(e_solved, 4),
        "problems": {pid: round(_p_solve(data), 4) for pid, data in board.items()},
    }
    _append_jsonl(RUN_LOG, record)


def check_lms_running() -> None:
    try:
        r = httpx.get(f"{LMS_HOST}/v1/models", timeout=5.0)
        if r.status_code == 200:
            return
    except Exception:
        pass
    sys.exit(
        f"\nLM Studio server is not running at {LMS_HOST}.\n"
        "Please start it first:\n\n"
        "  lms server start\n"
        f"  lms load {RUN_MODEL}\n\n"
        "For >24GB VRAM GPUs, also load:\n"
        "  lms load mistralai/Mixtral-8x7B-Instruct-v0.1\n"
        "and set MU_SIT_ANALYSIS_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1\n\n"
        "Then re-run sit.py."
    )


def _load_model(model_id: str) -> bool:
    _log(f"Loading model: {model_id}")
    r = subprocess.run(
        [sys.executable, "-m", "mu", "model", "load", model_id],
        cwd=MU_ROOT,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        _log(f"  model load failed:\n{(r.stdout + r.stderr)[-400:]}")
        return False
    return True


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
        "MU_MODEL": RUN_MODEL,
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
                break
        else:
            proc.wait()
            if proc.returncode != 0:
                _log("  dojo board exited non-zero")
    except Exception as exc:
        _log(f"  dojo board error: {exc}")
        return {}, False

    if stop_early:
        _log("  board run stopped early — partial results available.")

    if BOARD_JSON.exists():
        try:
            board = _unwrap_board(json.loads(BOARD_JSON.read_text()))
            _log(f"  board loaded: {len(board)} problems")
            log_run(cycle=cycle, board=board, e_solved=_e_solved(board))
            for pid, data in board.items():
                _vlog(f"  {pid}: p_solve={_p_solve(data):.3f}  lang={data.get('lang', '?')}  first_error={str(data.get('first_error', ''))[:120]}")
            return board, stop_early
        except Exception as e:
            _log(f"  could not parse board JSON: {e}")
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
        _log("  Note: Analysis mode disabled. Run problems detected but analysis is not configured.")

        if args.rounds and cycle >= args.rounds:
            _log(f"Reached --rounds {args.rounds} — stopping.")
            break

        time.sleep(5)


if __name__ == "__main__":
    main()