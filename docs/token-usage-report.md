# Token Usage in mu — Measurement and Minimization

## 1. Overview

Every call to `chat()` or `chat_or_retry()` in `client.py` already returns a `ChatStats` object containing `prompt_tokens` and `generated_tokens` pulled straight from the API's `usage` field. What is **missing** is any aggregation, phase tagging, or persistence of those numbers — they are logged once to stdout per call and then discarded.

---

## 2. Where Tokens Are Spent

mu makes LLM calls in seven distinct phases. The table below lists them from the code:

| Phase | Function(s) | Max calls per run | Multi-turn? |
|---|---|---|---|
| **Planner** | `_run_planner` | 1–3 (retry) | No |
| **Writer** | `Session.run` (via `_run_writer`) | 1 per task file | Yes, up to 15 turns |
| **Test repair** | `Session.repair_loop` (via `_run_test_repair_loop`) | 1 per failing test gate | Yes, up to 6 × 3 turns |
| **Lint repair** | `Session.repair_loop` (via `_run_repair_lint`) | 1 per failing lint gate | Yes, up to 6 × 3 turns |
| **Architect** | `_run_architect_pass` | 0 or 1 | No |
| **Stage planners** | `_run_stage_planner` | 0–3 | No |
| **Utility passes** | `split`, `flow`, `assess`, lint-critique | 0 or 1 each | No |

### What fills the prompt on each call

**Planner:** system = `_build_autonomous_system` (~250 tokens) + `task-planner` skill (~1,070 tokens) + optional language skills (e.g. `go-writer`, `dotnet-mvc+xunit`, `vue-ts-env`). User = project dir, goal, seven rules, challenges block from `CHALLENGES.md`, and a worked example. Skills alone contribute up to ~3,000 tokens for a dotnet goal.

**Writer (per task):** system = base protocol + all contextual skills active for this goal (e.g. `python-env` ~860 tokens + `python-writer` ~420 tokens). User = goal + full `plan_context`, reference files from `relevant_files_context` (already-written sibling files, up to ~2,000 tokens), and task description. In a 15-turn session, the entire history accumulates in `msgs` — each additional tool-result turn adds 200–600 tokens of conversation history. The third and later turns are dominated by prior output, not new instructions.

**Repair loop (per iteration):** system = lean base + per-language repair skill (~300–600 tokens). User turn 0 = goal + `_repair_context` (all project files, capped at 8,000 chars ≈ 2,000 tokens) + test output (60 lines). Subsequent turns append the previous turn's tool call, result, and new test output. After four iterations the conversation history is as large as the initial context.

A rough estimate for a three-file Python run on a 6,000-token budget:

| Phase | Prompt tokens |
|---|---|
| Planner | ~2,100 |
| Writer × 3 tasks | ~5,300 |
| Repair × 3 iters | ~2,900 |
| **Total prompt** | **~10,300** |

Skills alone account for roughly 40 % of all prompt tokens sent.

---

## 3. What to Measure and Why

To make optimization decisions with data rather than intuition, instrument each `chat()` / `chat_or_retry()` call to emit a structured record. The minimum useful fields are:

```json
{
  "phase":            "planner | writer | repair | ...",
  "task_file":        "src/app.py",
  "turn_index":       2,
  "prompt_tokens":    3812,
  "generated_tokens": 441,
  "system_bytes":     9200,
  "user_bytes":       2100,
  "history_turns":    3,
  "skills_loaded":    ["python-env", "python-writer"],
  "outcome":          "success | failure"
}
```

**Why each field:**

- `phase` + `task_file` reveal which phase dominates and whether a particular file type drives high repair costs.
- `system_bytes` vs `user_bytes` vs history length isolates the three components of the context window. If `system_bytes` is large and the system prompt is identical across turns, KV-cache reuse (`cache_prompt: True`) matters. If history is large, truncation or summarization would help.
- `skills_loaded` quantifies the marginal cost of each skill. A skill that fires on 90 % of runs but prevents 0 repair calls is cheap. One that fires rarely but is always included wastes tokens.
- `outcome` links token cost to result: a high-token repair run that still fails is the worst case; a zero-repair success on the first writer turn is the best. Plotting prompt tokens vs. outcome makes the cost of failure visible.

This data can be written to `.mu/token-log.jsonl` (one JSON object per line) using `AgentSession.finalize` for aggregation across dojo runs.

---

## 4. How to Minimize Token Usage

The following reductions are ordered by expected impact, with no changes to the prime directive or correctness guarantees.

### 4.1 Enable prompt-cache layout by default (~30 % saving on writer calls)

`MU_PROMPT_CACHE=1` is already implemented in `_run_planner`. It moves all stable content (skills, rules, challenges, example) into the **system** message and puts only the volatile DIR/GOAL in the user message. LM Studio's KV cache (`cache_prompt: True`) can then reuse the system-prompt prefix across every writer call within one run, cutting the prefill cost proportionally to the system-to-user ratio. Currently, the default path puts rules, challenges, and examples in the **user** message, which changes hash on every new goal and defeats the cache.

**Apply the same layout to the writer's `auto_system`:** the REMINDER suffix (`"Call Write ONCE…"`) appended in `_run_writer` makes the system prompt unique per task, breaking cache reuse. Moving the per-task note into the user message would make the system prompt reusable across all writer calls in the same run.

### 4.2 Narrow the repair context to the relevant file(s)

`_repair_context` dumps every file in the plan (up to 8,000 chars total, 2,500 chars per file). For a three-iteration repair loop that sends three user messages each containing this block, those files are sent three times. The right approach: on turn 0 send the full context; on turns 1+ include only the file(s) modified by the previous edit, not the entire project. The `seen_states` dict in `repair_loop` already tracks which paths were touched — use it to narrow the context.

### 4.3 Prune the repair loop history

The `repair_loop` never trims `msgs`. After six iterations a "still failing" run has sent the full conversation history — planner context, every file state, every test output — six times. A sliding window that keeps only the last N turns (e.g. 3) plus the initial user turn would cap history growth without losing the model's short-term memory of what it already tried.

### 4.4 Do not load contextual skills if they also fire at plan time

Several skills (`go-writer`, `dotnet-mvc`, `dotnet-xunit`, `vue-ts-env`) are injected both in `_run_planner` and in the writer's `auto_system` via `_contextual_skills`. If the planner already used the skill to produce the correct test command and file list, re-sending it to the writer costs tokens with diminishing benefit. An opt-in environment variable (`MU_PLANNER_SKILLS_IN_WRITER=0`) to suppress them from the writer once the plan is validated would reduce writer system prompt size by 1,000–5,000 tokens on framework-heavy goals.

### 4.5 Replace the full challenges block with retrieved lessons

`_load_challenges_for_planner` sends the entire Open section of `CHALLENGES.md` to every planner call. The `enrich.py` retrieval already exists and is gated by `MU_ENRICH_LESSONS=1`. Making selective retrieval the default (and full-block injection the opt-in) eliminates irrelevant challenges from the system prompt. The retriever's corroboration guard already prevents spurious lessons from appearing.

### 4.6 Reference files: send only the file under test, not all siblings

`relevant_files_context` can include multiple already-written source files. For a test file task, the only file that needs to appear is the source file it tests — not every other file in the plan. Narrowing the selection to one or two files would reduce the writer's user message by several hundred tokens on projects with multiple source files.

---

## 5. Summary

| Recommendation | Estimated saving | Complexity |
|---|---|---|
| Prompt-cache layout by default | ~20–35 % of writer prompt tokens | Low |
| Incremental repair context | ~30 % of repair tokens on iterations 2–6 | Low |
| Sliding-window repair history | ~25 % of long repair runs | Low |
| Suppress planner skills in writer (opt-in) | ~15–40 % of writer system tokens on framework goals | Low |
| Selective challenges retrieval by default | ~5–15 % of planner prompt | Medium |
| Narrower reference file selection | ~5–10 % of writer user prompt | Low |

None of these changes require touching the model, the dojo problems, or the reflexes. They are all strictly prompt-management changes that reduce redundant context. Measurement (§3) should precede any of them so the actual distribution of token cost across phases is known rather than estimated.
