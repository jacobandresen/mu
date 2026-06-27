#!/usr/bin/env python3
"""One-shot daily mu improvement via OpenRouter (poolside/laguna-m.1:free).
Runs at most once per day. Pass --force to override.
Set OPENROUTER_API_KEY. Optionally OPENROUTER_MODEL to change model.
"""
import argparse, datetime, json, os, subprocess, sys, textwrap
from pathlib import Path
import httpx

MU_ROOT = Path(__file__).resolve().parent.parent
STAMP = MU_ROOT / ".mu" / "improve_last_run"
MODEL = "poolside/laguna-m.1:free"


class QuotaExhausted(Exception): pass


def guard_once_per_day(force):
    today = datetime.date.today().isoformat()
    if STAMP.exists() and STAMP.read_text().strip() == today and not force:
        sys.exit(f"Already ran today ({today}). Pass --force to override.")
    STAMP.parent.mkdir(exist_ok=True)
    STAMP.write_text(today)


def guard_no_sessions():
    lines = subprocess.check_output(["ps", "aux"], text=True, stderr=subprocess.DEVNULL).splitlines()
    bad = []
    for line in lines:
        low = line.lower()
        if "grep" in low or "cron.py" in low:
            continue
        if any(p in low for p in ("mu agent", "mu.dojo", "mu dojo", "mu.agent")):
            bad.append(line.split(None, 10)[-1][:80])
        if ".lmstudio" in low and any(k in low for k in ("model", ".gguf", "load")):
            bad.append(line.split(None, 10)[-1][:80])
    if bad:
        sys.exit("Active sessions detected:\n" + "\n".join(f"  {b}" for b in bad))


def chat(messages, model, api_key):
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://github.com/jacobandresen/mu"},
        json={"model": model, "temperature": 0.2, "max_tokens": 4096, "messages": messages},
        timeout=180,
    )
    if r.status_code == 402:
        raise QuotaExhausted(r.text[:200])
    r.raise_for_status()
    data = r.json()
    if err := data.get("error"):
        msg = str(err.get("message", err))
        if any(k in msg.lower() for k in ("quota", "credits", "free", "insufficient", "rate limit")):
            raise QuotaExhausted(msg)
        raise RuntimeError(msg)
    return data["choices"][0]["message"]["content"]


def _read(path, n):
    if not path.exists():
        return f"(not found: {path})"
    t = path.read_text(errors="replace")
    return t[:n] + f"\n…(truncated)" if len(t) > n else t


def _skill_index():
    out = []
    for p in sorted(MU_ROOT.glob("skills/*/SKILL.md")):
        for line in p.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith(("---", "name:", "description:")):
                out.append(f"  {p.parent.name}: {line[:80]}")
                break
    return "\n".join(out)


SYSTEM = textwrap.dedent("""\
    You are a senior engineer improving mu — a local-LLM agent harness using deterministic
    reflexes and skill prompts to repair weak-model mistakes.

    Identify ONE concrete, general improvement. Must pass the AGENTS.md honesty test:
    "Would I write this fix for any program in this language, independent of dojo problems?"

    Candidate types (best first):
    1. New rule in an existing skill file (skills/*/SKILL.md) — full file replacement.
    2. New reflex in src/mu/reflexes/<lang>/ for a recurring error class.
    3. A prompt rule in agent.py _build_autonomous_system.

    .NET/C# is in scope. Roslyn (MU_LSP=all) fixes CS0246 via add-using (~7s/file).
    Does NOT fix CS0103. TFM-grounding reflex clears NU1202 (MU_TFM_GROUNDING).

    Output a single JSON object, no prose outside braces:
    {"rationale": "...", "file": "path/from/mu/root", "content": "<full file>", "test_hint": "..."}
""")


def build_messages(repair_ctx=""):
    parts = [
        f"=== AGENTS.md ===\n{_read(MU_ROOT/'AGENTS.md', 5000)}",
        f"=== docs/challenges/README.md ===\n{_read(MU_ROOT/'docs/challenges/README.md', 3500)}",
        f"=== docs/lsp.md ===\n{_read(MU_ROOT/'docs/lsp.md', 2500)}",
        f"=== docs/ablations.md ===\n{_read(MU_ROOT/'docs/ablations.md', 2000)}",
        f"=== docs/problems/README.md ===\n{_read(MU_ROOT/'docs/problems/README.md', 2000)}",
        f"=== Skills ===\n{_skill_index()}",
        "Output JSON only.",
    ]
    if repair_ctx:
        parts.insert(-1, f"=== Previous attempt failed ===\n{repair_ctx}")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n\n".join(parts)}]


def parse_json(text):
    if "```" in text:
        text = text[text.find("```"):text.rfind("```")].lstrip("`json").strip()
    s, e = text.find("{"), text.rfind("}") + 1
    if s < 0:
        raise ValueError(f"No JSON in: {text[:200]}")
    return json.loads(text[s:e])


def apply(change):
    path = MU_ROOT / change["file"].lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(change["content"])
    print(f"  wrote {change['file']} ({path.stat().st_size:,}b)")
    return path


def run_tests():
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
                       capture_output=True, text=True, cwd=MU_ROOT, timeout=120)
    return r.returncode == 0, r.stdout + r.stderr


def improve(model, api_key):
    resp = chat(build_messages(), model, api_key)
    change = parse_json(resp)
    print(f"  rationale: {change.get('rationale','?')}\n  file: {change.get('file','?')}")
    target = MU_ROOT / change["file"].lstrip("/")
    original = target.read_text(errors="replace") if target.exists() else None
    apply(change)
    passed, out = run_tests()
    if passed:
        print("  tests passed ✓")
        return True
    print(f"  tests FAILED\n{out[-400:]}")
    repair_ctx = f"file: {change['file']}\nfailure:\n{out[-1500:]}"
    try:
        fix = parse_json(chat(build_messages(repair_ctx), model, api_key))
        apply(fix)
        passed, _ = run_tests()
        if passed:
            print("  tests passed after fix ✓")
            return True
    except QuotaExhausted:
        raise
    except Exception as e:
        print(f"  fix failed: {e}")
    if original is not None:
        target.write_text(original)
    elif target.exists():
        target.unlink()
    print(f"  rolled back {change['file']}")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        sys.exit("OPENROUTER_API_KEY not set")
    model = os.environ.get("OPENROUTER_MODEL", MODEL)
    guard_once_per_day(args.force)
    guard_no_sessions()
    print(f"mu cron · {model}")
    try:
        improve(model, api_key)
    except QuotaExhausted as e:
        sys.exit(f"Quota exhausted: {e}")
    print("\n=== mu dojo board ===")
    subprocess.run([sys.executable, "-m", "mu", "dojo", "board"], cwd=MU_ROOT, timeout=600)


if __name__ == "__main__":
    main()
