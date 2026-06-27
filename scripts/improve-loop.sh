#!/usr/bin/env bash
# improve-loop.sh — autonomous mu improvement loop via OpenRouter (laguna model).
#
# Reads AGENTS.md + docs/challenges/README.md, asks the model to identify and
# implement one concrete improvement (reflex or skill rule), validates with the
# test suite, then runs `mu dojo board` to capture the baseline.
#
# Usage:
#   OPENROUTER_API_KEY=<key> bash scripts/improve-loop.sh [--rounds N]
#
# Environment variables:
#   OPENROUTER_API_KEY   Required.
#   OPENROUTER_MODEL     Model to use (default: poolside/laguna-m.1:free — largest free Laguna).
#   MU_IMPROVE_ROUNDS    Improvement cycles (default: 3). Overridden by --rounds.
#
# Guards:
#   Exits if any mu agent/dojo or LM Studio sessions are active.
#   Exits if OpenRouter returns HTTP 402 or a quota-exhausted error.
set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────

MU_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${OPENROUTER_MODEL:-poolside/laguna-m.1:free}"
ROUNDS="${MU_IMPROVE_ROUNDS:-3}"
PY="${MU_ROOT}/.venv/bin/python"
OR_BASE="https://openrouter.ai/api/v1/chat/completions"

# Parse --rounds flag
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rounds) ROUNDS="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────

die() { echo "ERROR: $*" >&2; exit 1; }

# Call OpenRouter; echo the assistant text to stdout.
# Exits with code 2 and prints a message if quota is exhausted.
or_chat() {
  local payload="$1"
  local response
  local http_code

  # Write response body + HTTP code to a temp file to capture both.
  local tmp
  tmp="$(mktemp)"
  http_code=$(curl -s -o "$tmp" -w "%{http_code}" \
    -X POST "$OR_BASE" \
    -H "Authorization: Bearer ${OPENROUTER_API_KEY}" \
    -H "HTTP-Referer: https://github.com/jacobandresen/mu" \
    -H "X-Title: mu-improve-loop" \
    -H "Content-Type: application/json" \
    -d "$payload")
  response="$(cat "$tmp")"
  rm -f "$tmp"

  # HTTP 402 = quota exhausted
  if [[ "$http_code" == "402" ]]; then
    echo "QUOTA_EXHAUSTED: HTTP 402 — free token quota used up." >&2
    exit 2
  fi

  if [[ "$http_code" != "200" ]]; then
    die "OpenRouter returned HTTP $http_code: ${response:0:300}"
  fi

  # Check for quota error embedded in JSON body.
  local err_msg
  err_msg="$(echo "$response" | $PY -c "
import sys, json
d = json.load(sys.stdin)
e = d.get('error', {})
msg = str(e.get('message', e)) if e else ''
print(msg)
" 2>/dev/null || true)"

  if [[ -n "$err_msg" ]]; then
    lower="${err_msg,,}"
    if [[ "$lower" == *quota* || "$lower" == *credits* || "$lower" == *free* \
       || "$lower" == *insufficient* || "$lower" == *402* ]]; then
      echo "QUOTA_EXHAUSTED: $err_msg" >&2
      exit 2
    fi
    die "OpenRouter error: $err_msg"
  fi

  # Extract assistant content
  echo "$response" | $PY -c "
import sys, json
d = json.load(sys.stdin)
choices = d.get('choices') or []
if not choices:
    raise SystemExit('No choices in response: ' + str(d)[:200])
print(choices[0]['message']['content'])
"
}

# Build JSON payload for a single-user-turn request.
make_payload() {
  local system_text="$1"
  local user_text="$2"
  $PY - <<PYEOF
import json, sys
system = sys.stdin.readline()  # not used; read from args via env
system = """${system_text//\"/\\\"}"""
user   = """${user_text//\"/\\\"}"""
print(json.dumps({
    "model": "${MODEL}",
    "temperature": 0.2,
    "max_tokens": 4096,
    "messages": [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ],
}))
PYEOF
}

# Extract a key from the JSON change object the model returns.
json_get() {
  local key="$1" text="$2"
  echo "$text" | $PY -c "
import sys, json, re
text = sys.stdin.read()
start = text.find('{')
end   = text.rfind('}') + 1
if start < 0 or end <= 0:
    sys.exit('No JSON object found')
d = json.loads(text[start:end])
print(d['${key}'])
"
}

# ── Guard ─────────────────────────────────────────────────────────────────────

guard_no_concurrent_sessions() {
  local found=0
  while IFS= read -r line; do
    lower="${line,,}"
    # Skip self and grep
    [[ "$lower" == *improve-loop* || "$lower" == *grep* ]] && continue

    if [[ "$lower" == *"mu agent"* || "$lower" == *"mu.dojo"* \
       || "$lower" == *"mu dojo"* || "$lower" == *"mu.agent"* ]]; then
      echo "  active mu session: ${line:0:80}" >&2
      found=1
    fi
    # LM Studio model session: lms process with model-related args
    if [[ "$lower" == *lms* ]] && \
       [[ "$lower" == *model* || "$lower" == *.gguf* || "$lower" == *load* ]]; then
      echo "  active lms session: ${line:0:80}" >&2
      found=1
    fi
  done < <(ps aux 2>/dev/null)

  if [[ "$found" -eq 1 ]]; then
    die "active mu/lms sessions detected — aborting to avoid conflicts (see above)"
  fi
}

# ── Context ───────────────────────────────────────────────────────────────────

read_file_truncated() {
  local path="$1" limit="${2:-6000}"
  if [[ ! -f "$path" ]]; then echo "(file not found: $path)"; return; fi
  local content
  content="$(head -c "$limit" "$path")"
  local full_len
  full_len="$(wc -c < "$path")"
  if [[ "$full_len" -gt "$limit" ]]; then
    echo "$content"
    echo "... (truncated at $limit bytes)"
  else
    echo "$content"
  fi
}

build_system_prompt() {
  cat <<'SYSTEM'
You are a senior engineer improving the mu codebase — a local-LLM agent harness
that uses deterministic reflexes to repair weak-model mistakes.

Your task: identify ONE concrete, general improvement to implement right now.
An improvement must pass the AGENTS.md honesty test:
  "Would I write this fix for any program in this language, independent of the
   dojo problems? If 'no, only because problem X needs it' — don't add it."

Preferred candidates (highest value first):
1. A new rule in an existing skill file under skills/ (most impactful, lowest risk).
2. A new reflex in src/mu/reflexes/<lang>/ for a recurring error class.
3. A prompt rule addition to an existing agent.py system-prompt builder.

Do NOT suggest .NET/C# reflexes (model-ceiling per AGENTS.md §0a), features
already listed as "covered" in challenges/README.md, or dojo-specific hacks.

Output a JSON object — nothing else, no prose outside the braces:
{
  "rationale": "<one sentence: why this has general value>",
  "file": "<path relative to mu root, e.g. skills/python-writer/SKILL.md>",
  "content": "<complete new content for that file — full replacement, not a diff>",
  "test_hint": "<what to grep or check to verify the change landed>"
}
SYSTEM
}

build_user_prompt() {
  local agents skills challenges
  agents="$(read_file_truncated "${MU_ROOT}/AGENTS.md" 5000)"
  challenges="$(read_file_truncated "${MU_ROOT}/docs/challenges/README.md" 4000)"
  skills="$(find "${MU_ROOT}/skills" -name "SKILL.md" | sort | while read -r f; do
    echo "  ${f#${MU_ROOT}/}: $(head -3 "$f" | tail -1)"
  done)"

  cat <<USERPROMPT
=== AGENTS.md (abridged) ===
${agents}

=== docs/challenges/README.md ===
${challenges}

=== Existing skill files ===
${skills}

Identify and implement the single best improvement. Output JSON only.
USERPROMPT
}

# ── One improvement cycle ─────────────────────────────────────────────────────

improve_once() {
  local round="$1"
  echo ""
  echo "── Round ${round} ──────────────────────────────────────────"
  echo "Asking model for improvement..."

  local system_prompt user_prompt payload response
  system_prompt="$(build_system_prompt)"
  user_prompt="$(build_user_prompt)"

  # Build payload using Python (handles JSON escaping reliably)
  payload="$($PY -c "
import json, sys
msgs = [
    {'role': 'system', 'content': open('/dev/stdin').read()},
]
" <<< "$system_prompt" 2>/dev/null || true)"

  # Simpler: use Python to assemble the full payload from files/strings.
  payload="$($PY - <<PYEOF
import json
system = open('${MU_ROOT}/AGENTS.md', errors='replace').read()[:5000]
challenges = open('${MU_ROOT}/docs/challenges/README.md', errors='replace').read()[:4000]
import subprocess, sys
skills_raw = subprocess.check_output(
    ['find', '${MU_ROOT}/skills', '-name', 'SKILL.md'],
    text=True).strip().split('\n')
skills = '\n'.join(
    f"  {p.replace('${MU_ROOT}/', '')}: " +
    open(p, errors='replace').readlines()[2].strip()
    for p in sorted(skills_raw) if p)

SYSTEM = """$(build_system_prompt)"""

USER = f"""=== AGENTS.md (abridged) ===
{system}

=== docs/challenges/README.md ===
{challenges}

=== Existing skill files ===
{skills}

Identify and implement the single best improvement. Output JSON only."""

print(json.dumps({
    'model': '${MODEL}',
    'temperature': 0.2,
    'max_tokens': 4096,
    'messages': [
        {'role': 'system', 'content': SYSTEM},
        {'role': 'user',   'content': USER},
    ],
}))
PYEOF
)"

  response="$(or_chat "$payload")"

  local rationale file content
  rationale="$(json_get rationale "$response")"
  file="$(json_get file "$response")"
  content="$(json_get content "$response")"

  echo "  Rationale : $rationale"
  echo "  Target    : $file"

  local target_path="${MU_ROOT}/${file}"
  local backup=""
  if [[ -f "$target_path" ]]; then
    backup="$(cat "$target_path")"
  fi

  # Apply the change
  mkdir -p "$(dirname "$target_path")"
  printf '%s' "$content" > "$target_path"
  echo "  Written   : $target_path ($(wc -c < "$target_path") bytes)"

  # Validate
  echo "  Running tests..."
  local test_out test_exit=0
  test_out="$(cd "$MU_ROOT" && "$PY" -m pytest tests/ -q --tb=short 2>&1)" || test_exit=$?

  if [[ $test_exit -eq 0 ]]; then
    echo "  Tests passed ✓"
    return 0
  fi

  echo "  Tests FAILED — asking model to fix..."
  echo "${test_out: -800}"

  # One repair attempt via OpenRouter
  local fix_payload fix_response fix_file fix_content
  fix_payload="$($PY - <<PYEOF
import json
orig_response = open('/dev/stdin').read()
test_output   = """${test_out: -2000}"""
print(json.dumps({
    'model': '${MODEL}',
    'temperature': 0.2,
    'max_tokens': 4096,
    'messages': [
        {'role': 'assistant', 'content': orig_response},
        {'role': 'user', 'content':
            'Tests failed after your change. Output a corrected JSON object '
            '(same schema) that fixes the issue.\n\nTest output:\n\`\`\`\n'
            + test_output + '\n\`\`\`'},
    ],
}))
PYEOF
  <<< "$response")"

  fix_response="$(or_chat "$fix_payload" 2>&1)" || {
    echo "  Fix request failed — rolling back."
    _rollback "$target_path" "$backup"
    return 1
  }

  fix_file="$(json_get file "$fix_response")"
  fix_content="$(json_get content "$fix_response")"
  local fix_target="${MU_ROOT}/${fix_file}"
  mkdir -p "$(dirname "$fix_target")"
  printf '%s' "$fix_content" > "$fix_target"

  test_out="$(cd "$MU_ROOT" && "$PY" -m pytest tests/ -q --tb=short 2>&1)" || test_exit=$?
  if [[ $test_exit -eq 0 ]]; then
    echo "  Tests passed after fix ✓"
    return 0
  fi

  echo "  Still failing — rolling back."
  _rollback "$target_path" "$backup"
  return 1
}

_rollback() {
  local path="$1" backup="$2"
  if [[ -n "$backup" ]]; then
    printf '%s' "$backup" > "$path"
    echo "  Rolled back $path"
  else
    rm -f "$path"
    echo "  Removed $path (was new)"
  fi
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
  [[ -z "${OPENROUTER_API_KEY:-}" ]] && die "OPENROUTER_API_KEY not set"

  echo "mu improve-loop · model: ${MODEL} · rounds: ${ROUNDS}"
  echo "mu root: ${MU_ROOT}"

  guard_no_concurrent_sessions
  echo "Guard passed — no concurrent mu/lms sessions."

  cd "$MU_ROOT"

  local applied=0
  for ((i=1; i<=ROUNDS; i++)); do
    improve_once "$i" && applied=$((applied + 1)) || true
  done

  echo ""
  echo "── Summary: ${applied}/${ROUNDS} improvements applied ──"
  echo ""
  echo "=== Running mu dojo board ==="
  "$PY" -m mu dojo board
}

main "$@"
