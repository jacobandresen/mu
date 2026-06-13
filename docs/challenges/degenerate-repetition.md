# Degenerate repetition

_‹ [All challenges](README.md)_

- **ID:** `degenerate-repetition`
- **Group:** Degenerate / malformed generation
- **CHALLENGES.md:** item 6
- **Status:** NOT reflex-recoverable — sampler + guard only

## What it is

The model falls into a token loop: `print(f"{task[print(f"{task[…`. The output is corrupt from the first token, so there is no valid code to repair.

## Problems affected

- [p8-node-todo](../problems/p8-node-todo.md) — long multi-file tasks raise the odds
- [p10-dotnet-vue-blog](../problems/p10-dotnet-vue-blog.md) — longest prompts, most exposure

## Relevant reflexes & mechanisms

- `MU_DEGEN_GUARD` — degeneration guard discards a repetition-loop block and resamples
- `MU_REPEAT_PENALTY` — sampler-level repeat penalty (granite-high failure mode)

## Residual / notes

Model ceiling — the single top residual failure. A reflex can't reconstruct intent from a repetition loop; the only levers are the sampler and discard-and-resample.
