# Repair-context budget

_‹ [All challenges](README.md)_

- **ID:** `repair-context-budget`
- **Group:** Full-stack orchestration / multi-file
- **Open list:** [item 11](README.md#open)
- **Status:** mitigated by budget + reserve + shrink

## What it is

The loaded window bounds prompt AND generation together; large skill stacks and accumulated repair history overflow it, and LM Studio hard-rejects with HTTP 400 mid-loop.

## Problems affected

- [p8-node-todo](../problems/p8-node-todo.md) — long repair histories with whole files in tool-call args
- [p9-vue-todo](../problems/p9-vue-todo.md) — heavy writer prompts (304k phase tokens, run 7)
- [p10-dotnet-vue-blog](../problems/p10-dotnet-vue-blog.md) — largest prompts in the set (33k median, run 7)

## Relevant reflexes & mechanisms

- `_fit_prompt_budget` — drops oldest repair history units, trims the current message middle
- `_GEN_RESERVE` — reserves 1536 tokens of the window for generation
- `_shrink_oversized` — chat()-level middle-cut of any oversized prompt
- `_strip_ansi` — strips Vitest ANSI codes that inflated test output ~10×

## Residual / notes

Run-4 logged 31 overflows, run-5 36; the two-layer fix (budget + reserve, then chat-level shrink) drove run-7 to zero. Never load above MU_NUM_CTX on an 8GB host.
