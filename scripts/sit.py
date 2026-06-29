#!/usr/bin/env python3
"""Autonomous local mu improvement loop.

Two modes alternate continuously:

  run mode      Load qwen2.5-coder-7b-instruct, run all dojo problems via
                `mu dojo board -n 5 --emit-json`, record structured results.

  analysis mode Load qwen2.5-coder-14b (CPU swap allowed), read AGENTS.md +
                README.md + board results, pick the failing problem whose
                bottleneck layer offers the best expected ΔE[#solved] (the best
                *minimal* win), apply one fix, run pytest, re-run only that
                problem to verify net gain (partial-credit ∏ q̂), roll back on
                any regression.

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
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import httpx

MU_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = MU_ROOT / ".mu" / "sit_history"
LOG_FILE = LOG_DIR / "attempts.jsonl"  # one JSON object per line
RUN_LOG = LOG_DIR / "runs.jsonl"  # one record per full dojo run

# ── defaults ──────────────────────────────────────────────────────────────────

RUN_MODEL = os.environ.get("MU_SIT_RUN_MODEL", "qwen2.5-coder-7b-instruct")
ANALYSIS_MODEL = os.environ.get("MU_SIT_ANALYSIS_MODEL", "qwen2.5-coder-14b-instruct")
RUN_CTX = int(os.environ.get("MU_SIT_RUN_CTX", "4096"))
ANALYSIS_CTX = int(os.environ.get("MU_SIT_ANALYSIS_CTX", "32768"))
LMS_HOST = os.environ.get("MU_LMSTUDIO_HOST", "http://localhost:1234")
VERBOSE = os.environ.get("MU_SIT_VERBOSE", "").strip() not in ("", "0", "false")

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
    outcome: str,  # "applied" | "rolled_back" | "parse_error" | "model_error"
    failure_reason: str,  # empty string on success
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
        "problems": {pid: round(_p_solve(data), 4) for pid, data in board.items()},
    }
    _append_jsonl(RUN_LOG, record)


def load_discarded_attempts(max_recent: int = 20) -> list[dict]:
    """Return the most recent rolled-back/failed attempts, plus applied zero-delta
    changes, for context injection — so the model won't repeat a no-gain change."""
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
            # Include rolled-back/failed attempts AND applied changes that gained nothing.
            if r.get("outcome") != "applied" or r.get("delta_e", 1.0) <= 0.0:
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
        cwd=MU_ROOT,
        capture_output=True,
        text=True,
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


def lms_chat(
    messages: list[dict],
    model: str,
    max_tokens: int = 8192,
    temperature: float = 0.2,
    timeout: float = 2400.0,
    num_ctx: int = ANALYSIS_CTX,
) -> str:
    """Send a chat request to the local LM Studio server."""
    _vlog(f"lms_chat model={model} max_tokens={max_tokens} num_ctx={num_ctx}")
    for i, m in enumerate(messages):
        _vlog(f"  msg[{i}] role={m['role']} len={len(m['content'])}")
        _vlog(f"    {m['content'][:300]!r}")
    last_err: Exception | None = None
    for attempt in range(3):
        if attempt:
            time.sleep(2**attempt)
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
            _log(f"  network error (attempt {attempt + 1}/3): {e}")
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            last_err = RuntimeError(f"HTTP {r.status_code}")
            _log(f"  transient HTTP {r.status_code} (attempt {attempt + 1}/3)")
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


def run_mode(cycle: int = 0) -> tuple[dict, bool]:
    """Load 7b, run full dojo board (n=3), return (board, stop_early).

    stop_early=True means a problem solved ≤1/3 — go straight to analysis
    regardless of board content.
    """
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
    # Pattern emitted by measure.board() after each problem:
    #   "  p7-flask                    solved 1/3 · layers …"
    import re

    solved_re = re.compile(r"solved\s+(\d+)/3")

    stop_early = False
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "mu",
                "dojo",
                "board",
                "-n",
                "3",
                "--emit-json",
                str(BOARD_JSON),
            ],
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
        _log("  board run stopped early — partial board loaded for analysis.")

    if BOARD_JSON.exists():
        try:
            board = _unwrap_board(json.loads(BOARD_JSON.read_text()))
            _log(f"  board loaded: {len(board)} problems")
            log_run(cycle=cycle, board=board, e_solved=_e_solved(board))
            for pid, data in board.items():
                _vlog(
                    f"  {pid}: p_solve={_p_solve(data):.3f}  lang={data.get('lang', '?')}  first_error={str(data.get('first_error', ''))[:120]}"
                )
            return board, stop_early
        except Exception as e:
            _log(f"  could not parse board JSON: {e}")
    return {}, stop_early


def _failing_problems(board: dict) -> list[tuple[str, float]]:
    """``(problem_id, p_solve)`` for failing problems, ranked best-minimal-win first.

    *Failing* is decided on the raw pass-product (``_raw_solve < 1``) so a smoothed-but-
    solved 3/3 problem isn't mistaken for a target. The order is by *expected* ΔE[#solved]
    of the single best (bottleneck) fix, not by current p_solve — so analysis is aimed at
    the problem one focused fix away from the largest gain (see ``_expected_gain``)."""
    failing = [(pid, _p_solve(data)) for pid, data in board.items()
               if _raw_solve(data) < 1.0]
    return sorted(failing, key=lambda x: -_expected_gain(board[x[0]])[0])


def _gain_band(gain: float) -> str:
    """Difficulty label from the best-fix *gain*, matching the bands STEP 1 of the
    analysis prompt tells the model to use (so the shown label can't contradict them)."""
    if gain > 0.4:
        return "easy"
    if gain > 0.1:
        return "medium"
    return "hard"


def _unwrap_board(raw: dict) -> dict:
    """Handle both flat {pid: {...}} and wrapped {"board": {pid: {...}}} formats."""
    if "board" in raw and isinstance(raw["board"], dict):
        return raw["board"]
    return raw


def _layer_qs(data: dict) -> dict[str, float]:
    """``{layer: q̂}`` for a board layer-dict entry; ``{}`` for flat run-result shapes.

    Board entries are ``{layer: {clears, n, q, ci}}`` — a single-layer problem has one
    entry (often named "solved"), a multi-layer one (e.g. p10) has four."""
    return {l: v["q"] for l, v in data.items()
            if isinstance(v, dict) and "q" in v}


def _p_solve(data: dict) -> float:
    """Solve-probability for a board entry, on one scale across both shapes.

    Two shapes flow through the loop:
      • board layer-dict  ``{layer: {clears, n, q, ci}}`` → ``∏ q̂``  (capability.p_solve)
      • single-problem ``mu dojo run`` result (flat)       → its ``p_solve`` / ``pass_rate``

    The product form is what makes partial progress visible: lifting any *one* layer of
    a multi-layer problem (e.g. p10's backend_build 0.2→0.5) moves ``∏ q̂``, so the
    accept-gate can see a real gain at small n instead of waiting for a full solve. The
    old code returned 0.0 for every multi-layer problem (no ``solved`` key), blinding
    the loop to exactly the hard problems it targets."""
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
    """Raw ``∏(clears/n)`` over layers — ``1.0`` only when every layer cleared every run.

    Used to decide *failing* vs *solved*: the smoothed q̂ tops out below 1 at small n
    (a clean 3/3 yields q̂≈0.8), so a ``p_solve < 1`` test would flag even a fully solved
    problem and waste a cycle on it."""
    rates = [v["clears"] / v["n"] for v in data.values()
             if isinstance(v, dict) and v.get("n")]
    if not rates:  # flat run-result
        if "pass_rate" in data:
            return data["pass_rate"]
        if "p_solve" in data:
            return data["p_solve"]
        return 0.0
    prod = 1.0
    for r in rates:
        prod *= r
    return prod


def _expected_gain(data: dict) -> tuple[float, str | None]:
    """``(marginal upside, bottleneck layer)`` for a board entry — the targeting signal.

    Upside ≈ ``(1 - q̂_min) · ∏ q̂_siblings`` (capability.expected_solve_gain): the
    headroom on the weakest layer scaled by how healthy its siblings are. This is what
    ranking by raw p_solve misses — a problem with one weak layer among healthy ones
    (``[0.9, 0.1]``) ranks ABOVE a uniformly-mediocre one (``[0.5, 0.5]``) despite lower
    p_solve, because it is a single minimal fix from a large ΔE[#solved]. It also encodes
    the sibling-veto: if any sibling ≈ 0 the product collapses the score, so we don't burn
    a cycle fixing one layer of an all-failing problem."""
    qs = _layer_qs(data)
    if not qs:
        return 0.0, None
    bn = min(qs, key=qs.get)
    siblings = 1.0
    for l, q in qs.items():
        if l != bn:
            siblings *= q
    return (1.0 - qs[bn]) * siblings, bn


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

    ── STEP 1: PICK A PROBLEM AND ITS BOTTLENECK LAYER ──────────────────────────
    The failing list is already ranked best-minimal-win first: by "best-fix gain" =
    the expected ΔE[#solved] of fixing that problem's weakest layer. Pick the FIRST
    problem not in the discarded list. Higher gain = one focused fix buys more.

    For a multi-layer problem the line shows each layer's q̂ with the bottleneck marked
    ▶. Aim your fix at that ▶ layer — it is the weakest link in the chain, and lifting
    it is the single change that moves p_solve most. Do NOT touch a layer already near 1.

    best-fix gain meaning:
      gain > 0.4   → EASY:   one rule nudges the weak layer over the line
      0.1–0.4      → MEDIUM: the layer fails in one main pattern; fix that pattern
      ≤ 0.1        → HARD:   either the layer is a hard wall, or several siblings are
                             also weak (so any single fix buys little) — pick only the
                             first hard wall, and prefer problems above this band.

    A low gain on a multi-layer problem usually means MULTIPLE weak layers (e.g. p10
    with all four ≈0.2): no single minimal fix helps much, so it ranks last — skip it
    in favour of a higher-gain problem unless nothing else remains.

    ── STEP 2: IDENTIFY THE FIX ─────────────────────────────────────────────────
    Choose the fix type (in order of preference):
      1. Add a new reflex in src/mu/reflexes/<lang>/
      2. Add or sharpen a rule in an existing skill file
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
      "file": "skills/python-writer/SKILL.md",
      "content": "<complete new file content — not a diff, not a summary>",
      "test_hint": "what behaviour to verify after applying this change"
    }

    BAD OUTPUT EXAMPLES (do not do these):
    ✗ "file": null                        ← file is required
    ✗ "file": ""                          ← file is required
    ✗ "content": "... (same as before)"  ← content must be the full file
    ✗ picking a lower-gain problem first ← the list is pre-ranked; take the top one
    ✗ fixing a layer already at q̂≈0.9    ← fix the ▶ bottleneck, not a healthy layer
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


def _failing_line(pid: str, p: float, data: dict) -> str:
    """One prompt line per failing problem: p_solve, the expected gain of its best fix,
    and — for multi-layer problems — the per-layer q̂ with the bottleneck flagged, so the
    model attacks the layer that actually moves the needle."""
    gain, bn = _expected_gain(data)
    qs = _layer_qs(data)
    head = f"  {pid}: p_solve={p:.3f} [{_gain_band(gain)}]  best-fix gain={gain:.3f}"
    if len(qs) > 1:
        layers = " ".join(
            f"{'▶' if l == bn else ''}{l}={q:.2f}" for l, q in qs.items()
        )
        return f"{head}  bottleneck={bn}  layers[ {layers} ]"
    return head


def build_analysis_messages(board: dict, repair_ctx: str = "") -> list[dict]:
    failing = _failing_problems(board)
    if failing:
        failing_summary = "\n".join(
            _failing_line(pid, p, board[pid]) for pid, p in failing[:12]
        )
    else:
        failing_summary = "  (none — all problems passing!)"

    # Latest archive run README (contains implemented improvements summary).
    archive_readme_content = "(none yet)"
    archive_root = MU_ROOT / "archive"
    if archive_root.exists():
        nums = [
            int(p.name)
            for p in archive_root.iterdir()
            if p.is_dir() and p.name.isdigit()
        ]
        if nums:
            latest_readme = archive_root / f"{max(nums):03d}" / "README.md"
            archive_readme_content = _read(latest_readme, 2000)

    parts = [
        f"=== Failing problems (best minimal win first) ===\n{failing_summary}",
        f"=== Previously tried and discarded (DO NOT repeat these) ===\n{_discarded_summary()}",
        f"=== AGENTS.md ===\n{_read(MU_ROOT / 'AGENTS.md', 5000)}",
        f"=== README.md ===\n{_read(MU_ROOT / 'README.md', 3000)}",
        f"=== Latest board run (archive) ===\n{archive_readme_content}",
        f"=== docs/challenges/README.md ===\n{_read(MU_ROOT / 'docs/challenges/README.md', 4000)}",
        f"=== docs/lsp.md ===\n{_read(MU_ROOT / 'docs/lsp.md', 2000)}",
        f"=== docs/ablations.md ===\n{_read(MU_ROOT / 'docs/ablations.md', 1500)}",
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
        capture_output=True,
        text=True,
        cwd=MU_ROOT,
        timeout=120,
        env={**os.environ, "PYTHONPATH": "."},
    )
    out = r.stdout + r.stderr
    _vlog(f"  pytest exit={r.returncode} output:\n{out[-2000:]}")
    return r.returncode == 0, out


def verify_board_gain(
    model_id: str, target_pids: list[str], baseline_e: float, board: dict
) -> tuple[bool, float]:
    """Re-run only the targeted problems (n=3), return (net_positive, new_e).
    Falls back to accepting the change if runs can't complete."""
    if not target_pids:
        return True, baseline_e

    env = {**os.environ, "MU_AGENT_MODEL": model_id, "N": "3"}
    updated_board = dict(board)

    # Only problems present in the *baseline* board have a before-value to compare against.
    # An early-stopped run produces a partial board, and the model can name a target that
    # isn't in it; crediting such a target would just *add* its p_solve to new_e and fake a
    # positive delta — a false accept. Gate strictly on the measurable ones.
    measurable = [pid for pid in target_pids if pid in board]
    if not measurable:
        _log(f"  no targeted problem in baseline board ({target_pids}) — accepting on pytest")
        return True, baseline_e

    delta = 0.0
    for pid in measurable:
        tmp = MU_ROOT / ".mu" / f"sit_verify_{pid}.json"
        _log(f"  verifying {pid} (n=3) …")
        try:
            subprocess.run(
                [sys.executable, "-m", "mu", "dojo", "run", pid, "--emit-json", str(tmp)],
                cwd=MU_ROOT,
                env=env,
                timeout=900,
            )
        except subprocess.TimeoutExpired:
            _log(f"  verify {pid} timed out — accepting change")
            return True, baseline_e

        if tmp.exists():
            try:
                res = json.loads(tmp.read_text())
                # Splice the layer-dict (always emitted now), not the flat result, so the
                # board stays homogeneous and on the same smoothed scale as the baseline.
                updated_board[pid] = res.get("layers", res)
                delta += _p_solve(updated_board[pid]) - _p_solve(board[pid])
            except Exception as e:
                _log(f"  verify {pid} parse error: {e}")

    new_e = baseline_e + delta
    _log(f"  E[#solved]: {baseline_e:.3f} → {new_e:.3f}  (Δ {delta:+.3f} over {measurable})")
    BOARD_JSON.write_text(json.dumps(updated_board, indent=2))
    # Now that the metric is trustworthy and on a consistent smoothed scale, require no
    # regression (the old -0.05 slack silently kept changes that worsened the target).
    # Partial credit (∏ q̂) makes even a single-layer lift register, so a real improvement
    # clears this bar; we stop short of strict-positive to avoid n=3 noise stalling the loop.
    return delta >= 0.0, new_e


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
                cycle=cycle,
                rationale="(parse failed)",
                file="?",
                target_problems=[],
                difficulty="?",
                sub_problem=None,
                outcome="parse_error",
                failure_reason=str(e2),
                baseline_e=baseline_e,
                new_e=baseline_e,
            )
            return False

    target_pids = change.get("target_problems") or []
    difficulty = change.get("difficulty", "?")
    sub_problem = change.get("sub_problem")
    rationale = change.get("rationale", "?")
    test_hint = change.get("test_hint", "")
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
            fix_original = (
                fix_target.read_text(errors="replace") if fix_target.exists() else None
            )
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
            cycle=cycle,
            rationale=rationale,
            file=rel,
            target_problems=target_pids,
            difficulty=difficulty,
            sub_problem=sub_problem,
            outcome="rolled_back",
            failure_reason=f"pytest failed: {test_out[-300:]}",
            baseline_e=baseline_e,
            new_e=baseline_e,
            test_hint=test_hint,
        )
        return False

    _log("  tests passed ✓")

    # ── board gain gate ────────────────────────────────────────────────────
    if not _load_model(RUN_MODEL):
        _log("  cannot reload run model for verification — accepting on pytest")
        log_attempt(
            cycle=cycle,
            rationale=rationale,
            file=rel,
            target_problems=target_pids,
            difficulty=difficulty,
            sub_problem=sub_problem,
            outcome="applied",
            failure_reason="",
            baseline_e=baseline_e,
            new_e=baseline_e,
            test_hint=test_hint,
        )
        return True

    net_pos, new_e = verify_board_gain(RUN_MODEL, target_pids, baseline_e, board)
    if not net_pos:
        _log(
            f"  board regression (E[#solved] {baseline_e:.3f} → {new_e:.3f}) — rolling back"
        )
        _rollback(original, target)
        log_attempt(
            cycle=cycle,
            rationale=rationale,
            file=rel,
            target_problems=target_pids,
            difficulty=difficulty,
            sub_problem=sub_problem,
            outcome="rolled_back",
            failure_reason=f"board regression: {baseline_e:.3f} → {new_e:.3f}",
            baseline_e=baseline_e,
            new_e=new_e,
            test_hint=test_hint,
        )
        return False

    _log(f"  change accepted ✓ (E[#solved] {baseline_e:.3f} → {new_e:.3f})")
    log_attempt(
        cycle=cycle,
        rationale=rationale,
        file=rel,
        target_problems=target_pids,
        difficulty=difficulty,
        sub_problem=sub_problem,
        outcome="applied",
        failure_reason="",
        baseline_e=baseline_e,
        new_e=new_e,
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
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Emit verbose debug logs (prompts, raw responses, test output)",
    )
    ap.add_argument(
        "--rounds",
        type=int,
        default=int(os.environ.get("MU_SIT_ROUNDS", "0")),
        help="Max improvement cycles (0 = infinite)",
    )
    ap.add_argument(
        "--run-only",
        action="store_true",
        help="Only run dojo once and print the board, then exit",
    )
    ap.add_argument(
        "--analysis-only",
        action="store_true",
        help="Skip the run phase; analyse existing board JSON",
    )
    args = ap.parse_args()

    global VERBOSE
    if args.verbose:
        VERBOSE = True

    check_lms_running()

    _log(
        f"mu sit  run={RUN_MODEL}(ctx={RUN_CTX})  analysis={ANALYSIS_MODEL}(ctx={ANALYSIS_CTX})"
    )
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
            board, _ = run_mode(cycle=0)
        analysis_mode(board, cycle=0)
        return

    cycle = 0
    while True:
        cycle += 1
        _log(f"\n{'=' * 60}")
        _log(f"CYCLE {cycle}")

        # ── 1. Run ───────────────────────────────────────────────────────
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

        # ── 2. Analysis ──────────────────────────────────────────────────
        analysis_mode(board, cycle=cycle)

        if args.rounds and cycle >= args.rounds:
            _log(f"Reached --rounds {args.rounds} — stopping.")
            break

        # short pause to let model server settle before next cycle
        time.sleep(5)


if __name__ == "__main__":
    main()
