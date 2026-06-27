#!/usr/bin/env python3
"""One-shot daily mu improvement via OpenRouter (poolside/laguna-m.1:free).

Runs AT MOST ONCE PER DAY. A datestamp in .mu/improve_last_run prevents a
second execution on the same calendar date — pass --force to override.

Each invocation: reads AGENTS.md + challenge docs + ablations + skill/reflex
index, asks Laguna to identify ONE improvement (skill rule, reflex, or prompt
addition), writes the file, validates with pytest, rolls back on failure, then
runs `mu dojo board`. Uses 1 OpenRouter request (2 if a repair is needed).
OpenRouter free tier budget: ~100 requests total — one per day keeps it safe.

Usage:
    OPENROUTER_API_KEY=<key> python scripts/improve-once.py [--force]

Environment variables:
    OPENROUTER_API_KEY   Required.
    OPENROUTER_MODEL     Model (default: poolside/laguna-m.1:free).

Guards:
    Exits if already run today (unless --force).
    Exits if any mu agent/dojo or LM Studio model sessions are active.
    Exits cleanly on HTTP 402 or quota-exhausted response from OpenRouter.
"""
import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import httpx

import datetime

MU_ROOT = Path(__file__).resolve().parent.parent
OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "poolside/laguna-m.1:free"
STAMP_FILE = MU_ROOT / ".mu" / "improve_last_run"


# ── Daily-run guard ───────────────────────────────────────────────────────────

def guard_once_per_day(force: bool) -> None:
    today = datetime.date.today().isoformat()
    if STAMP_FILE.exists():
        last = STAMP_FILE.read_text().strip()
        if last == today and not force:
            sys.exit(f"Already ran today ({today}). Pass --force to override.")
    STAMP_FILE.parent.mkdir(exist_ok=True)
    STAMP_FILE.write_text(today)


# ── Quota error ───────────────────────────────────────────────────────────────

class QuotaExhausted(Exception):
    """Raised when OpenRouter signals that free-tier tokens are used up."""


# ── Guard: no concurrent sessions ────────────────────────────────────────────

def _running_lines() -> list[str]:
    try:
        return subprocess.check_output(["ps", "aux"], text=True,
                                       stderr=subprocess.DEVNULL).splitlines()
    except Exception:
        return []


def guard_no_concurrent_sessions() -> None:
    conflicts = []
    for line in _running_lines():
        low = line.lower()
        if "grep" in low or "improve-once" in low or "improve_once" in low \
                or "improve-loop" in low or "improve_loop" in low:
            continue
        if any(pat in low for pat in ("mu agent", "mu.dojo", "mu dojo", "mu.agent")):
            conflicts.append(("mu session", line.split(None, 10)[-1][:80]))
        # LM Studio model loaded: .lmstudio path + model-related arg
        if ".lmstudio" in low and any(k in low for k in ("model", ".gguf", "load")):
            conflicts.append(("lms session", line.split(None, 10)[-1][:80]))
    if conflicts:
        print("ERROR: active sessions detected — aborting to avoid conflicts:")
        for kind, desc in conflicts:
            print(f"  [{kind}] {desc}")
        sys.exit(1)


# ── OpenRouter client ─────────────────────────────────────────────────────────

def openrouter_chat(messages: list[dict], model: str, api_key: str,
                    timeout: float = 180.0) -> str:
    """Send messages to OpenRouter; return assistant text.

    Raises QuotaExhausted on HTTP 402 or a quota-signal in the response body.
    """
    r = httpx.post(
        OPENROUTER_BASE,
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/jacobandresen/mu",
            "X-Title": "mu-improve-loop",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.2,
            "max_tokens": 4096,
            "messages": messages,
        },
        timeout=timeout,
    )

    if r.status_code == 402:
        raise QuotaExhausted(f"HTTP 402 — free-token quota exhausted: {r.text[:200]}")

    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {r.text[:300]}") from e

    data = r.json()
    if err := data.get("error"):
        msg = str(err.get("message", err))
        if any(k in msg.lower() for k in ("quota", "credits", "free", "insufficient",
                                           "402", "no auth", "rate limit")):
            raise QuotaExhausted(f"OpenRouter quota error: {msg}")
        raise RuntimeError(f"OpenRouter error: {msg}")

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenRouter returned no choices: {data}")
    return choices[0]["message"]["content"]


# ── Context builders ──────────────────────────────────────────────────────────

def _read(path: Path, max_chars: int) -> str:
    if not path.exists():
        return f"(not found: {path})"
    text = path.read_text(errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n… (truncated at {max_chars} chars)"
    return text


def _skill_index() -> str:
    lines = []
    for skill_md in sorted(MU_ROOT.glob("skills/*/SKILL.md")):
        name = skill_md.parent.name
        for line in skill_md.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("---") and not line.startswith("name:") \
                    and not line.startswith("description:"):
                lines.append(f"  {name}: {line[:80]}")
                break
        else:
            lines.append(f"  {name}")
    return "\n".join(lines)


def _reflex_registry_summary() -> str:
    """One-line per registered reflex: id → function name."""
    reg = MU_ROOT / "src/mu/reflexes/registry.py"
    if not reg.exists():
        return "(registry not found)"
    lines = []
    for line in reg.read_text(errors="replace").splitlines():
        # Pick up _rule(...) or direct dict entries that name a reflex
        if "artifact" in line and "evidence" in line:
            lines.append(f"  {line.strip()[:100]}")
    return "\n".join(lines[:40]) or "(no entries parsed)"


SYSTEM_PROMPT = textwrap.dedent("""\
    You are a senior engineer improving the mu codebase — a local-LLM agent harness
    that uses deterministic reflexes and skill prompts to repair weak-model mistakes.

    == Your task ==
    Identify ONE concrete, general improvement and output it as JSON. Every suggestion
    must pass the AGENTS.md honesty test:
      "Would I write this fix for any program in this language, independent of the
       dojo problems? If 'no' — don't add it."

    == Candidate types (in value order) ==
    1. A new rule added to an existing skill file (skills/*/SKILL.md) — safest, most
       impactful. The full file is replaced; preserve all existing rules.
    2. A new reflex in src/mu/reflexes/<lang>/ for a class of recurring model error.
    3. A prompt rule in agent.py's _build_autonomous_system.

    == .NET / C# is explicitly in scope ==
    The .NET problems (p4, p10, p13, p14) have a model-ceiling component (CS0103
    undefined-name) but also tractable layers above it. The Roslyn language server
    (`MU_LSP=all`) is the primary lever for the next layer:

    Roslyn (Microsoft.CodeAnalysis.LanguageServer, net10):
    - Activated by MU_LSP=all in the agent hook _apply_lsp_repair (lsp.py).
    - Fixes CS0246 "type or namespace not found" by emitting `using X.Y;` via the
      codeAction `source.addImport` / quickfix. Verified: using directives land,
      diagnostics clear. Latency ~7 s/file (project load) — gated behind MU_LSP=all.
    - Does NOT fix CS0103 (undefined-name) — that is model semantic quality, not an
      import issue. Do not conflate the two.
    - Replaces the retired csharp-ls (which SIGABRTs on .NET 10).
    - skills/repair-csharp/skill.md already maps CS-codes to targeted advice; you
      may extend it (e.g. add CS0103 mitigation patterns) or extend skills/dotnet-mvc.

    Useful C# context for skill rules:
    - TFM grounding: the TFM-grounding reflex raises TargetFramework when EF Core
      version exceeds the installed SDK, clearing NU1202 restore failures. Already
      shipped (MU_TFM_GROUNDING, default-off, pending A/B verdict).
    - Entry-point: CS5001 (no Main) is fixable with a rule; partial class Program is
      the clean pattern for ASP.NET minimal-API entry points with WebApplicationFactory.

    == Output format ==
    A single JSON object — no prose outside the braces:
    {
      "rationale": "<one sentence: why this is general and valuable>",
      "file": "<path relative to mu root, e.g. skills/repair-csharp/skill.md>",
      "content": "<complete new file content — full replacement, never a diff>",
      "test_hint": "<what to grep/check to confirm the change landed>"
    }
""")


def build_messages(repair_context: str = "") -> list[dict]:
    agents    = _read(MU_ROOT / "AGENTS.md",                        max_chars=5000)
    challeng  = _read(MU_ROOT / "docs/challenges/README.md",        max_chars=3500)
    lsp_doc   = _read(MU_ROOT / "docs/lsp.md",                     max_chars=2500)
    ablations = _read(MU_ROOT / "docs/ablations.md",                max_chars=2000)
    problems  = _read(MU_ROOT / "docs/problems/README.md",          max_chars=2000)
    skills    = _skill_index()
    reflexes  = _reflex_registry_summary()

    user_parts = [
        f"=== AGENTS.md (abridged) ===\n{agents}",
        f"=== docs/challenges/README.md ===\n{challeng}",
        f"=== docs/lsp.md (Roslyn / LSP repair) ===\n{lsp_doc}",
        f"=== docs/ablations.md (lever verdicts + backlog) ===\n{ablations}",
        f"=== docs/problems/README.md (per-problem status) ===\n{problems}",
        f"=== Existing skill files ===\n{skills}",
        f"=== Registered reflexes (registry.py) ===\n{reflexes}",
        "Identify and implement the single best improvement. Output JSON only.",
    ]
    if repair_context:
        user_parts.insert(-1, f"=== Previous attempt failed ===\n{repair_context}")

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": "\n\n".join(user_parts)},
    ]


# ── Parse and apply ───────────────────────────────────────────────────────────

def parse_change(text: str) -> dict:
    """Extract the first JSON object from model output."""
    # Strip markdown fences if present
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        text = text[start:end].lstrip("`").lstrip("json").strip()

    j_start = text.find("{")
    j_end   = text.rfind("}") + 1
    if j_start < 0 or j_end <= 0:
        raise ValueError(f"No JSON object in model output:\n{text[:400]}")
    return json.loads(text[j_start:j_end])


def apply_change(change: dict) -> Path:
    rel  = change["file"].lstrip("/")
    path = MU_ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(change["content"])
    print(f"  wrote {rel} ({path.stat().st_size:,} bytes)")
    return path


def run_tests() -> tuple[bool, str]:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
        capture_output=True, text=True, cwd=MU_ROOT, timeout=120,
    )
    return r.returncode == 0, r.stdout + r.stderr


def run_dojo_board() -> None:
    print("\n=== mu dojo board ===")
    subprocess.run([sys.executable, "-m", "mu", "dojo", "board"],
                   cwd=MU_ROOT, timeout=600)


# ── One improvement round ─────────────────────────────────────────────────────

def improve_once(round_n: int, model: str, api_key: str) -> bool:
    """Try one improvement. Returns True if a change was applied and tests pass."""
    print(f"\n── Round {round_n} {'─' * 50}")
    print("Querying model...")

    # Ask the model
    for attempt in range(1, 4):
        try:
            response = openrouter_chat(build_messages(), model, api_key)
            break
        except QuotaExhausted:
            raise
        except Exception as e:
            print(f"  API error (attempt {attempt}/3): {e}")
            if attempt == 3:
                return False
    else:
        return False

    # Parse
    try:
        change = parse_change(response)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"  Could not parse JSON: {e}\n  Model output: {response[:300]}")
        return False

    print(f"  rationale : {change.get('rationale', '?')}")
    print(f"  target    : {change.get('file', '?')}")

    # Save original for rollback
    target = MU_ROOT / change["file"].lstrip("/")
    original_text = target.read_text(errors="replace") if target.exists() else None

    apply_change(change)

    # Validate
    print("  running tests...")
    passed, test_out = run_tests()
    if passed:
        print("  tests passed ✓")
        return True

    # One repair attempt
    print(f"  tests FAILED — requesting fix from model...")
    print(test_out[-600:])

    repair_ctx = (
        f"You proposed:\n  file: {change['file']}\n"
        f"  rationale: {change.get('rationale', '')}\n\n"
        f"After applying it, tests failed:\n```\n{test_out[-2000:]}\n```\n"
        "Output a corrected JSON object (same schema) that makes the tests pass."
    )
    try:
        fix_response = openrouter_chat(build_messages(repair_ctx), model, api_key)
        fix_change   = parse_change(fix_response)
        apply_change(fix_change)
        passed, test_out2 = run_tests()
        if passed:
            print("  tests passed after fix ✓")
            return True
        print("  still failing after fix — rolling back")
    except QuotaExhausted:
        raise
    except Exception as e:
        print(f"  fix attempt failed: {e}")

    # Rollback
    if original_text is not None:
        target.write_text(original_text)
        print(f"  rolled back {target.relative_to(MU_ROOT)}")
    elif target.exists():
        target.unlink()
        print(f"  removed {target.relative_to(MU_ROOT)} (was new)")
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--force", action="store_true",
                    help="Run even if already executed today")
    args = ap.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        sys.exit("ERROR: OPENROUTER_API_KEY not set.")

    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)

    print(f"mu improve-once · model: {model}")
    print(f"mu root: {MU_ROOT}")

    guard_once_per_day(args.force)
    guard_no_concurrent_sessions()
    print("Guards passed — running today's improvement.\n")

    applied = 0
    try:
        if improve_once(1, model, api_key):
            applied = 1
    except QuotaExhausted as e:
        print(f"\nStopping: {e}")
    except KeyboardInterrupt:
        print("\nInterrupted.")

    print(f"\n── {'improvement applied' if applied else 'no improvement applied'} ──")
    run_dojo_board()


if __name__ == "__main__":
    main()
