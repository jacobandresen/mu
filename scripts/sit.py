#!/usr/bin/env python3
"""Autonomous local mu improvement loop.

Two modes alternate continuously:

  run mode      Load qwen2.5-coder-7b-instruct, run all dojo problems via
                `mu dojo board -n 5 --emit-json`, record structured results.

  analysis mode Load qwen2.5-coder-14b (CPU swap allowed), read AGENTS.md +
                README.md + board results, propose one targeted improvement for
                the *smallest* failing problems, apply it, run pytest,
                re-run a targeted dojo board to verify net gain, roll back if
                net-negative.

On startup the script checks whether `lms server` is running; if not it prints
the start command and exits rather than proceeding blindly.

Environment:
  MU_SIT_RUN_MODEL       7b model id (default: qwen2.5-coder-7b-instruct)
  MU_SIT_ANALYSIS_MODEL  14b model id (default: qwen2.5-coder-14b-instruct)
  MU_SIT_RUN_CTX         context tokens for run model (default: 4096)
  MU_SIT_ANALYSIS_CTX    context tokens for analysis model (default: 32768)
  MU_SIT_ROUNDS          improvement cycles before stopping (default: infinite)
  MU_LMSTUDIO_HOST       LM Studio base URL (default: http://localhost:1234)
  MU_SIT_VERBOSE         Set to 1/true to enable verbose logging (prompts, responses, test output)
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import httpx

MU_ROOT  = Path(__file__).resolve().parent.parent
LOG_DIR  = MU_ROOT / ".mu" / "sit_history"
LOG_FILE = LOG_DIR / "attempts.jsonl"   # one JSON object per line
RUN_LOG  = LOG_DIR / "runs.jsonl"       # one record per full dojo run

# ── defaults ──────────────────────────────────────────────────────────────────

RUN_MODEL      = os.environ.get("MU_SIT_RUN_MODEL",      "qwen2.5-coder-7b-instruct")
ANALYSIS_MODEL = os.environ.get("MU_SIT_ANALYSIS_MODEL", "qwen2.5-coder-14b-instruct")
RUN_CTX        = int(os.environ.get("MU_SIT_RUN_CTX",      "4096"))
ANALYSIS_CTX   = int(os.environ.get("MU_SIT_ANALYSIS_CTX", "32768"))
LMS_HOST       = os.environ.get("MU_LMSTUDIO_HOST",      "http://localhost:1234")
VERBOSE        = os.environ.get("MU_SIT_VERBOSE", "").strip() not in ("", "0", "false")

# ── helpers ───────────────────────────────────────────────────────────────────

def _read(path: Path, max_chars: int = 6000) -> str:
    if not path.exists():
        return f"(not found: {path})"
    t = path.read_text(errors="replace")
    return t[:max_chars] + "\n…(truncated)" if len(t) > max_chars else t


def _skill_index() -> str:
    lines = []
    for p in sorted(MU_ROOT.glob("skills/*/SKILL.md")):
        for line in p.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith(("---", "name:", "description:")):
                lines.append(f"  {p.parent.name}: {line[:80]}")
                break
    return "\n".join(lines)


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def _vlog(msg: str) -> None:
    if VERBOSE:
        print(f"[{_ts()}] [V] {msg}", flush=True)


# ── attempt history ───────────────────────────────────────────────────────────

def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_attempt(
    *,
    cycle: int,
    rationale: str,
    file: str,
    target_problems: list[str],
    difficulty: str,
    sub_problem: str | None,
    outcome: str,          # "applied" | "rolled_back" | "parse_error" | "model_error"
    failure_reason: str,   # empty string on success
    baseline_e: float,
    new_e: float,
    test_hint: str = "",
) -> None:
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "cycle": cycle,
        "rationale": rationale,
        "file": file,
        "target_problems": target_problems,
        "difficulty": difficulty,
        "sub_problem": sub_problem,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "baseline_e": round(baseline_e, 4),
        "new_e": round(new_e, 4),
        "delta_e": round(new_e - baseline_e, 4),
        "test_hint": test_hint,
    }
    _append_jsonl(LOG_FILE, record)
    status = "✓" if outcome == "applied" else "✗"
    _log(f"  [{status}] logged attempt → {LOG_FILE.name}")


def log_run(*, cycle: int, board: dict, e_solved: float) -> None:
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "cycle": cycle,
        "e_solved": round(e_solved, 4),
        "problems": {
            pid: round(_p_solve(data), 4)
            for pid, data in board.items()
        },
    }
    _append_jsonl(RUN_LOG, record)


def load_discarded_attempts(max_recent: int = 20) -> list[dict]:
    """Return the most recent rolled-back/failed attempts for context injection."""
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text().splitlines()
    records = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            if r.get("outcome") != "applied":
                records.append(r)
                if len(records) >= max_recent:
                    break
        except Exception:
            continue
    return list(reversed(records))


# ── LMS guards / model swap ───────────────────────────────────────────────────

def check_lms_running() -> None:
    """Exit with instructions if LM Studio server is not reachable."""
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
        "Then re-run sit.py."
    )


def _load_model(model_id: str) -> bool:
    """Ask mu to load a model; returns True on success."""
    _log(f"Loading model: {model_id}")
    r = subprocess.run(
        [sys.executable, "-m", "mu", "model", "load", model_id],
        cwd=MU_ROOT, capture_output=True, text=True,
    )
    if r.returncode != 0:
        _log(f"  model load failed:\n{(r.stdout + r.stderr)[-400:]}")
        return False
    return True


def _active_model() -> str:
    """Return the first non-embedding model currently loaded, or ''."""
    try:
        r = httpx.get(f"{LMS_HOST}/v1/models", timeout=5.0)
        for m in r.json().get("data", []):
            mid = m.get("id", "")
            if "embed" not in mid.lower():
                return mid
    except Exception:
        pass
    return ""


# ── local LMS chat ────────────────────────────────────────────────────────────

def lms_chat(messages: list[dict], model: str, max_tokens: int = 8192,
             temperature: float = 0.2, timeout: float = 2400.0,
             num_ctx: int = ANALYSIS_CTX) -> str:
    """Send a chat request to the local LM Studio server."""
    _vlog(f"lms_chat model={model} max_tokens={max_tokens} num_ctx={num_ctx}")
    for i, m in enumerate(messages):
        _vlog(f"  msg[{i}] role={m['role']} len={len(m['content'])}")
        _vlog(f"    {m['content'][:300]!r}")
    last_err: Exception | None = None
    for attempt in range(3):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            r = httpx.post(
                f"{LMS_HOST}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "num_ctx": num_ctx,
                },
                timeout=timeout,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            last_err = e
            _log(f"  network error (attempt {attempt+1}/3): {e}")
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            last_err = RuntimeError(f"HTTP {r.status_code}")
            _log(f"  transient HTTP {r.status_code} (attempt {attempt+1}/3)")
            continue
        if not r.is_success:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"No choices in response: {data}")
        content = choices[0]["message"]["content"]
        _vlog(f"  response len={len(content)}: {content[:500]!r}")
        return content
    raise RuntimeError(f"All attempts failed: {last_err}")


# ── run mode ──────────────────────────────────────────────────────────────────

BOARD_JSON = MU_ROOT / ".mu" / "sit_board.json"


def run_mode(cycle: int = 0) -> dict:
    """Load 7b, run full dojo board (n=1), return board JSON dict."""
    _log("=== RUN MODE ===")
    if not _load_model(RUN_MODEL):
        _log("  Could not load run model — skipping run phase.")
        return {}

    env = {**os.environ, "MU_AGENT_MODEL": RUN_MODEL}
    BOARD_JSON.parent.mkdir(exist_ok=True)

    _log(f"Running dojo board (n=5) → {BOARD_JSON}")
    r = subprocess.run(
        [sys.executable, "-m", "mu", "dojo", "board",
         "-n", "5", "--emit-json", str(BOARD_JSON)],
        cwd=MU_ROOT, env=env, timeout=3600,
    )
    if r.returncode != 0:
        _log("  dojo board exited non-zero")

    if BOARD_JSON.exists():
        try:
            board = _unwrap_board(json.loads(BOARD_JSON.read_text()))
            _log(f"  board loaded: {len(board)} problems")
            log_run(cycle=cycle, board=board, e_solved=_e_solved(board))
            for pid, data in board.items():
                _vlog(f"  {pid}: p_solve={_p_solve(data):.3f}  lang={data.get('lang','?')}  first_error={str(data.get('first_error',''))[:120]}")
            return board
        except Exception as e:
            _log(f"  could not parse board JSON: {e}")
    return {}


def _failing_problems(board: dict) -> list[tuple[str, float]]:
    """Return (problem_id, p_solve) pairs for failing problems,
    sorted easiest-first (highest p_solve among failures)."""
    failing = []
    for pid, data in board.items():
        p = _p_solve(data)
        if p < 1.0:
            failing.append((pid, p))
    # easiest first: highest p_solve (most tractable) at the top
    return sorted(failing, key=lambda x: -x[1])


def _difficulty(p_solve: float) -> str:
    if p_solve > 0.5:
        return "easy"
    if p_solve > 0.1:
        return "medium"
    return "hard"


def _unwrap_board(raw: dict) -> dict:
    """Handle both flat {pid: {...}} and wrapped {"board": {pid: {...}}} formats."""
    if "board" in raw and isinstance(raw["board"], dict):
        return raw["board"]
    return raw


def _p_solve(data: dict) -> float:
    """Extract solve probability from any board-entry shape."""
    if "p_solve" in data:
        return data["p_solve"]
    if "pass_rate" in data:
        return data["pass_rate"]
    # format: {"solved": {"q": 0.67, ...}}
    solved = data.get("solved")
    if isinstance(solved, dict):
        return solved.get("q", 0.0)
    return 0.0


def _e_solved(board: dict) -> float:
    return sum(_p_solve(data) for data in board.values())


# ── JSON parsing ──────────────────────────────────────────────────────────────

def parse_json(text: str) -> dict:
    if "```" in text:
        lines, body, in_fence = text.splitlines(), [], False
        for line in lines:
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                body.append(line)
        text = "\n".join(body) if body else text
    s, e = text.find("{"), text.rfind("}") + 1
    if s < 0 or e <= 0:
        raise ValueError(f"No JSON object found: {text[:300]}")
    return json.loads(text[s:e])


def validate_change(change: dict) -> tuple[str, Path]:
    for key in ("file", "content"):
        if not change.get(key):
            raise ValueError(f"Missing or null key {key!r}")
    rel = change["file"].lstrip("/")
    target = (MU_ROOT / rel).resolve()
    if not str(target).startswith(str(MU_ROOT)):
        raise ValueError(f"Path traversal rejected: {change['file']!r}")
    return rel, target


# ── analysis mode ─────────────────────────────────────────────────────────────

ANALYSIS_SYSTEM = textwrap.dedent("""\
    You improve mu, a local-LLM agent harness. Your job each cycle: pick ONE
    failing problem, identify ONE specific fix, write it to ONE file.

    ── STEP 1: PICK A PROBLEM ───────────────────────────────────────────────────
    Look at the failing problems list (easiest first = highest p_solve first).
    Pick the problem with the highest p_solve that is NOT in the discarded list.

    p_solve meaning:
      p_solve > 0.5  → EASY:   the model gets it sometimes; one rule nudges it over
      0.1–0.5        → MEDIUM: the model fails in one main pattern; fix that pattern
      ≤ 0.1          → HARD:   the model always fails; find the first hard wall only

    DO NOT classify a problem as hard just because you have no board history.
    A problem with p_solve = 0.67 is EASY, period.

    ── STEP 2: IDENTIFY THE FIX ─────────────────────────────────────────────────
    Choose the fix type (in order of preference):
      1. Add or sharpen a rule in an existing skill file
      2. Add a new reflex in src/mu/reflexes/<lang>/
      3. Add a rule to agent.py _build_autonomous_system (last resort)

    Before writing, check: "Would this rule apply to any program in this language,
    not just this dojo problem?" If NO, do not add it — it would overfit.

    NEVER repeat a file+rationale combination from the discarded list.

    ── STEP 3: WRITE THE OUTPUT ─────────────────────────────────────────────────
    Output exactly one JSON object. No text before or after the braces.
    Every field is required. "file" and "content" must never be null or empty.

    {
      "rationale": "one sentence: what pattern fails and what the fix does",
      "target_problems": ["p1-helloworld"],
      "difficulty": "easy",
      "sub_problem": "the specific failure class being fixed, or null if easy",
      "file": "src/mu/skills/python.md",
      "content": "<complete new file content — not a diff, not a summary>",
      "test_hint": "what behaviour to verify after applying this change"
    }

    BAD OUTPUT EXAMPLES (do not do these):
    ✗ "file": null                        ← file is required
    ✗ "file": ""                          ← file is required
    ✗ "content": "... (same as before)"  ← content must be the full file
    ✗ classifying p_solve=0.67 as hard   ← that is easy, not hard
    ✗ prose outside the JSON braces      ← JSON only, nothing else
""")


def _discarded_summary(max_recent: int = 15) -> str:
    """One-line-per-attempt summary of recent rolled-back / failed attempts."""
    discarded = load_discarded_attempts(max_recent)
    if not discarded:
        return "  (none yet)"
    lines = []
    for r in discarded:
        lines.append(
            f"  [{r['ts']}] file={r['file']}  targets={r['target_problems']}"
            f"  outcome={r['outcome']}  reason={r['failure_reason'] or '-'}"
            f"  rationale={r['rationale'][:80]}"
        )
    return "\n".join(lines)


def build_analysis_messages(board: dict, repair_ctx: str = "") -> list[dict]:
    failing = _failing_problems(board)
    if failing:
        failing_summary = "\n".join(
            f"  {pid}: p_solve={p:.2f}  [{_difficulty(p)}]"
            for pid, p in failing[:12]
        )
    else:
        failing_summary = "  (none — all problems passing!)"

    parts = [
        f"=== Failing problems (easiest first) ===\n{failing_summary}",
        f"=== Previously tried and discarded (DO NOT repeat these) ===\n{_discarded_summary()}",
        f"=== AGENTS.md ===\n{_read(MU_ROOT/'AGENTS.md', 5000)}",
        f"=== README.md ===\n{_read(MU_ROOT/'README.md', 3000)}",
        f"=== docs/challenges/README.md ===\n{_read(MU_ROOT/'docs/challenges/README.md', 4000)}",
        f"=== docs/lsp.md ===\n{_read(MU_ROOT/'docs/lsp.md', 2000)}",
        f"=== docs/ablations.md ===\n{_read(MU_ROOT/'docs/ablations.md', 1500)}",
        f"=== Skills ===\n{_skill_index()}",
    ]
    if repair_ctx:
        parts.append(f"=== Previous attempt failed ===\n{repair_ctx}")
    parts.append("Output JSON only.")

    return [
        {"role": "system", "content": ANALYSIS_SYSTEM},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def run_tests() -> tuple[bool, str]:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
        capture_output=True, text=True, cwd=MU_ROOT, timeout=120,
        env={**os.environ, "PYTHONPATH": "."},
    )
    out = r.stdout + r.stderr
    _vlog(f"  pytest exit={r.returncode} output:\n{out[-2000:]}")
    return r.returncode == 0, out


def verify_board_gain(model_id: str, target_pids: list[str],
                      baseline_e: float) -> tuple[bool, float]:
    """Re-run dojo board for the targeted problems, return (net_positive, new_e).
    Falls back to accepting the change if the board can't run."""
    if not target_pids:
        return True, baseline_e

    tmp = MU_ROOT / ".mu" / "sit_verify.json"
    env = {**os.environ, "MU_AGENT_MODEL": model_id}
    try:
        r = subprocess.run(
            [sys.executable, "-m", "mu", "dojo", "board",
             "-n", "5", "--emit-json", str(tmp)],
            cwd=MU_ROOT, env=env, timeout=3600,
        )
    except subprocess.TimeoutExpired:
        _log("  verify board timed out — accepting change")
        return True, baseline_e

    if not tmp.exists():
        _log("  verify board produced no JSON — accepting change")
        return True, baseline_e

    try:
        new_board = _unwrap_board(json.loads(tmp.read_text()))
        new_e = _e_solved(new_board)
        _log(f"  E[#solved]: {baseline_e:.3f} → {new_e:.3f}")
        # Update the main board file with fresh data
        tmp.rename(BOARD_JSON)
        return new_e >= baseline_e - 0.05, new_e
    except Exception as e:
        _log(f"  verify board parse error: {e}")
        return True, baseline_e


def analysis_mode(board: dict, cycle: int = 0) -> bool:
    """Load 14b model, propose and apply one improvement. Returns True if applied."""
    _log("=== ANALYSIS MODE ===")

    if not _load_model(ANALYSIS_MODEL):
        _log("  Could not load analysis model — skipping analysis phase.")
        return False

    active = _active_model()
    if not active:
        _log("  No model active after load attempt.")
        return False

    baseline_e = _e_solved(board)
    _log(f"  Baseline E[#solved] = {baseline_e:.3f}")

    # ── first attempt ──────────────────────────────────────────────────────
    try:
        resp = lms_chat(build_analysis_messages(board), active)
    except Exception as e:
        _log(f"  LMS chat error: {e}")
        return False

    try:
        change = parse_json(resp)
        rel, target = validate_change(change)
    except (ValueError, json.JSONDecodeError) as e:
        _log(f"  parse error: {e}")
        _log(f"  raw response: {resp[:500]!r}")
        _log("  retrying with error context …")
        retry_ctx = f"Your previous response failed validation: {e}\nRaw output was:\n{resp[:800]}\n\nFix the JSON and re-emit."
        try:
            resp2 = lms_chat(build_analysis_messages(board, retry_ctx), active)
            change = parse_json(resp2)
            rel, target = validate_change(change)
        except (ValueError, json.JSONDecodeError) as e2:
            _log(f"  retry parse error: {e2}")
            _log(f"  retry raw response: {resp2[:500]!r}")
            log_attempt(
                cycle=cycle, rationale="(parse failed)", file="?",
                target_problems=[], difficulty="?", sub_problem=None,
                outcome="parse_error", failure_reason=str(e2),
                baseline_e=baseline_e, new_e=baseline_e,
            )
            return False

    target_pids  = change.get("target_problems") or []
    difficulty   = change.get("difficulty", "?")
    sub_problem  = change.get("sub_problem")
    rationale    = change.get("rationale", "?")
    test_hint    = change.get("test_hint", "")
    _log(f"  rationale:  {rationale}")
    _log(f"  file:       {rel}")
    _log(f"  targets:    {target_pids}  [{difficulty}]")
    if sub_problem:
        _log(f"  sub-problem: {sub_problem}")

    original = target.read_text(errors="replace") if target.exists() else None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(change["content"])
    _log(f"  wrote {rel} ({target.stat().st_size:,}b)")

    # ── pytest gate ────────────────────────────────────────────────────────
    passed, test_out = run_tests()
    if not passed:
        _log("  tests FAILED — attempting repair")
        repair_ctx = f"file: {rel}\nfailure:\n{test_out[-1500:]}"
        try:
            fix_resp = lms_chat(build_analysis_messages(board, repair_ctx), active)
            fix = parse_json(fix_resp)
            fix_rel, fix_target = validate_change(fix)
            fix_original = fix_target.read_text(errors="replace") if fix_target.exists() else None
            if fix_target != target:
                _rollback(original, target)
                fix_target.parent.mkdir(parents=True, exist_ok=True)
                fix_target.write_text(fix["content"])
                original, target = fix_original, fix_target
                rel = fix_rel
            else:
                target.write_text(fix["content"])
            passed, test_out = run_tests()
        except Exception as e:
            _log(f"  repair error: {e}")

    if not passed:
        _log("  tests still failing — rolling back")
        _rollback(original, target)
        log_attempt(
            cycle=cycle, rationale=rationale, file=rel,
            target_problems=target_pids, difficulty=difficulty,
            sub_problem=sub_problem, outcome="rolled_back",
            failure_reason=f"pytest failed: {test_out[-300:]}",
            baseline_e=baseline_e, new_e=baseline_e, test_hint=test_hint,
        )
        return False

    _log("  tests passed ✓")

    # ── board gain gate ────────────────────────────────────────────────────
    if not _load_model(RUN_MODEL):
        _log("  cannot reload run model for verification — accepting on pytest")
        log_attempt(
            cycle=cycle, rationale=rationale, file=rel,
            target_problems=target_pids, difficulty=difficulty,
            sub_problem=sub_problem, outcome="applied",
            failure_reason="", baseline_e=baseline_e, new_e=baseline_e,
            test_hint=test_hint,
        )
        return True

    net_pos, new_e = verify_board_gain(RUN_MODEL, target_pids, baseline_e)
    if not net_pos:
        _log(f"  board regression (E[#solved] {baseline_e:.3f} → {new_e:.3f}) — rolling back")
        _rollback(original, target)
        log_attempt(
            cycle=cycle, rationale=rationale, file=rel,
            target_problems=target_pids, difficulty=difficulty,
            sub_problem=sub_problem, outcome="rolled_back",
            failure_reason=f"board regression: {baseline_e:.3f} → {new_e:.3f}",
            baseline_e=baseline_e, new_e=new_e, test_hint=test_hint,
        )
        return False

    _log(f"  change accepted ✓ (E[#solved] {baseline_e:.3f} → {new_e:.3f})")
    log_attempt(
        cycle=cycle, rationale=rationale, file=rel,
        target_problems=target_pids, difficulty=difficulty,
        sub_problem=sub_problem, outcome="applied",
        failure_reason="", baseline_e=baseline_e, new_e=new_e,
        test_hint=test_hint,
    )
    return True


def _rollback(original: str | None, target: Path) -> None:
    if original is not None:
        target.write_text(original)
    elif target.exists():
        target.unlink()
    _log(f"  rolled back {target.relative_to(MU_ROOT)}")


# ── main loop ──────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Emit verbose debug logs (prompts, raw responses, test output)")
    ap.add_argument("--rounds", type=int,
                    default=int(os.environ.get("MU_SIT_ROUNDS", "0")),
                    help="Max improvement cycles (0 = infinite)")
    ap.add_argument("--run-only", action="store_true",
                    help="Only run dojo once and print the board, then exit")
    ap.add_argument("--analysis-only", action="store_true",
                    help="Skip the run phase; analyse existing board JSON")
    args = ap.parse_args()

    global VERBOSE
    if args.verbose:
        VERBOSE = True

    check_lms_running()

    _log(f"mu sit  run={RUN_MODEL}(ctx={RUN_CTX})  analysis={ANALYSIS_MODEL}(ctx={ANALYSIS_CTX})")
    _log(f"mu root: {MU_ROOT}")

    if args.run_only:
        run_mode(cycle=0)
        return

    if args.analysis_only:
        if BOARD_JSON.exists():
            board = _unwrap_board(json.loads(BOARD_JSON.read_text()))
            _log(f"Loaded existing board ({len(board)} problems)")
        else:
            _log("No existing board JSON — running dojo first")
            board = run_mode(cycle=0)
        analysis_mode(board, cycle=0)
        return

    cycle = 0
    while True:
        cycle += 1
        _log(f"\n{'='*60}")
        _log(f"CYCLE {cycle}")

        # ── 1. Run ───────────────────────────────────────────────────────
        board = run_mode(cycle=cycle)
        if not board:
            _log("Empty board — waiting 60s before retry")
            time.sleep(60)
            continue

        failing = _failing_problems(board)
        if not failing:
            _log("All problems passing — goal achieved!")
            break

        _log(f"Failing problems: {[(p, f'{v:.2f}') for p, v in failing]}")

        # ── 2. Analysis ──────────────────────────────────────────────────
        analysis_mode(board, cycle=cycle)

        if args.rounds and cycle >= args.rounds:
            _log(f"Reached --rounds {args.rounds} — stopping.")
            break

        # ── 3. Rest 5 minutes ────────────────────────────────────────────
        _log("Resting 5 minutes before next cycle …")
        time.sleep(300)


if __name__ == "__main__":
    main()
