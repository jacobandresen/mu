# Report: External NLP Tools for Plan Enrichment

**Date:** 2026-05-28
**Author:** Mu maintainers (drafted by Claude)
**Audience:** Mu contributors evaluating ways to raise dojo pass rate
**Status:** v2 — corrected archive path, sharpened Option A's target, added a null‑hypothesis arm, tightened the measurement protocol

## Problem framing

Mu's `plan` subcommand produces a `PLAN.md` consisting of:

- a `## Plan Context` block (goal, dependencies, constraints),
- a checklist of `- [ ] path — description` tasks,
- a `## Research Notes` section (optionally appended by `researcher.deep`),
- a single `test` command.

Empirically (see `CHALLENGES.md`), failure modes that survive the repair loop split into two buckets:

- **planning‑side**: vague task descriptions, contradictory entity names across tasks, missing dependency hints, and lessons from prior dojo runs that no one re‑introduced;
- **writing‑side**: forgotten imports, spurious symbols, Makefile indent drift.

NLP enrichment can only attack the planning‑side bucket. Writing‑side issues are sensor and prompt territory and are intentionally out of scope here. `researcher.deep` already does some planning‑side enrichment via an LLM web‑research pass, but it is slow, costs tokens, and is bounded by the planning model's own quality.

The question: **can a lightweight, deterministic Python NLP layer expand the plan further — and verifiably increase the success rate?**

## Design constraint

Whatever we add must remain consistent with Mu's prime directive of honesty: the enrichment must be *generic*, not problem‑specific patching. Tools that learn from `~/.mu/sessions/` (the prior‑run archive — currently 46 sessions) are acceptable; tools that hardcode "if plan mentions sqlite then add X" are not.

Note that retrieval can *backdoor* problem‑specific patching if the index keeps surfacing the same lesson for everything. The honesty boundary is "the retriever has no privileged knowledge the archive doesn't contain," not "retrieval is automatically safe." This needs explicit watching during evaluation.

## Three alternatives

### A. spaCy — rule‑based plan linter

[spaCy](https://spacy.io) provides fast dependency parsing, POS tagging, and named‑entity recognition in pure Python (`pip install spacy && python -m spacy download en_core_web_sm`).

**What it would do in Mu.** Before handing `PLAN.md` to the writer, run each task description plus the `## Plan Context` through spaCy and surface deterministic warnings, then feed them back to the planner LLM for a second pass (a critique loop, not user‑facing output):

- Vague verbs (`handle`, `support`, `manage`, `process`) without a direct object → flag for refinement.
- Pronouns without antecedents (`it`, `this`) crossing task boundaries → ambiguous reference.
- Task description shorter than N tokens → likely under‑specified.
- **Cross‑task entity inconsistency** — task 1 says "TodoManager", task 2 says "TodoStore". This is the strongest signal: it correlates with the writer producing one file that imports a name another file never defined.

**Pros.** Deterministic, fast (~10 ms per task), no API cost, easy to unit‑test on a fixture corpus. The cross‑task entity check directly targets a real failure mode we have seen (writer hallucinates the wrong class name because the plan was inconsistent).
**Cons.** Surface‑level; cannot judge whether the *content* is correct, only whether the *form* is well‑specified. Will not catch missing‑import errors in test files — those are writer‑side and out of scope here.

### B. sentence‑transformers — semantic retrieval from `archive/`

[sentence-transformers](https://www.sbert.net) (`pip install sentence-transformers`) gives embeddings via small local models (e.g. `all-MiniLM-L6-v2`, ~80 MB, runs CPU‑only).

**What it would do in Mu.** `~/.mu/sessions/` already stores every prior dojo run's `PLAN-final.md`, `meta.json`, and logs (46 sessions as of this writing — well past cold‑start). Embed (a) each prior plan's context, and (b) each recorded `CHALLENGES.md` entry. At plan time, embed the new goal and retrieve the top‑k most similar prior runs. Inject a `## Lessons From Prior Runs` block citing the failure modes that hit similar plans before ("a previous sqlite‑related task failed because tests were not isolated — see commit 4dc186c").

The corpus is currently mixed across machines/users; before relying on it, decide whether the index should be per‑user (local cache) or repo‑shared (committed embeddings). Repo‑shared is simpler but couples training data to git history.

**Pros.** Genuinely learns from project history. Strongest signal for the recurrence pattern noted in `CHALLENGES.md`. No LLM call needed at retrieval time.
**Cons.** Requires `sentence-transformers` (~150 MB) and an index step. Bigger risk: if only a few archived runs hit a given semantic neighbourhood, the same lesson gets surfaced for *every* loosely‑related plan — see the honesty caveat above. Mitigation: require ≥3 distinct prior runs to corroborate a lesson before injecting it.

### C. KeyBERT — keyword expansion for research queries

[KeyBERT](https://github.com/MaartenGr/KeyBERT) (`pip install keybert`) wraps sentence‑transformers to extract the most semantically central n‑gram keywords from a passage.

**What it would do in Mu.** `researcher._compose_topic` currently concatenates `lang + description + goal` into a search topic. KeyBERT could extract the salient terms from `plan_context` + `task.description` and produce a richer query (e.g. "tkinter event loop threading" instead of "Python GUI"). This sharpens the research pass so its bullets land closer to the actual implementation hurdle.

**Pros.** Drop‑in upgrade for an existing path; small surface area; reuses any sentence‑transformer already downloaded for option B.
**Cons.** Only helps when `researcher.deep` is run (it isn't always). The benefit is bounded by the downstream LLM's ability to use the better query.

### D. Null hypothesis — improve the planner prompt instead

Before adding any dependency, the honest baseline is: rewrite the planner's system prompt to ask for the things spaCy would lint (consistent names, concrete verbs, dependency hints) and to consult `CHALLENGES.md` directly (it is already small enough to inline). If this closes most of the gap, the NLP layer is unjustified weight.

This arm costs nothing to run and should be measured alongside A/B/C as the floor every other arm has to beat.

## Comparison

| | D. Prompt only | A. spaCy | B. sentence‑transformers | C. KeyBERT |
|---|---|---|---|---|
| Failure mode targeted | all of the below, weakly | underspecified / inconsistent tasks | repeating known failures | weak research queries |
| Determinism | low (LLM) | high | high (modulo embed model) | medium |
| Cold‑start cost | none | none | archive already at 46 runs | needs model download |
| Runtime per plan | +1 LLM turn | <50 ms | ~200 ms | ~300 ms |
| Dependency footprint | none | ~50 MB | ~150 MB | ~150 MB (shared with B) |
| Honesty risk | low | low (purely formal) | medium — see caveat | low |
| Composability | baseline | feeds planner | feeds planner | feeds researcher |

## How to measure effectiveness

The dojo (`dojo/p1‑p4`, plus future problems) is already an A/B harness. Proposed protocol:

1. **Fix the test set.** Freeze the current dojo problems plus three new held‑out ones (never used while tuning the enrichment). Total problems P = 7.
2. **Run all four arms.** D (prompt only), A (spaCy), B (retrieval), and the current `main` baseline. Optional fifth arm: B+A stacked. Same model, same temperature for all arms.
3. **Pick N from a power calculation, not by feel.** LLM stochasticity is the dominant noise source. To detect a 10 pp absolute lift on a baseline near 50% pass rate at α=0.05, β=0.2 with a paired design, expect N ≈ 15 runs per (problem × arm) — i.e. ~100 runs per arm. For a faster screening read, N=5 detects only ≥25 pp shifts reliably; use N=5 as a *kill criterion* (drop arms that show no signal at all) and N=15 to *decide*.
4. **Record per run** (already in `~/.mu/sessions/<id>/meta.json` or trivially added):
   - `pass`: 1 if the final test command exits 0;
   - `first_try_pass`: 1 if no repair‑loop iteration was needed;
   - `repair_iters`, `sensor_invocations`, `wall_seconds`, `tokens_in/out`.
5. **Primary metric:** pass rate. Paired bootstrap over (problem × seed) pairs; report point estimate plus 95% CI vs. baseline.
6. **Secondary metrics:** `first_try_pass` (cleaner signal than `pass` because it isn't laundered through repair), `repair_iters`, `wall_seconds`, total tokens. An arm that lifts `pass` but doubles tokens is a different proposition than one that does both.
7. **Acceptance criterion (decided in advance):** ship an arm if it beats the baseline by ≥10 pp on `pass` with a CI that doesn't cross zero, *and* it doesn't increase wall time by more than 50%. Otherwise it goes back on the shelf — no "interesting trend, let's keep it" exceptions.
8. **Diagnostic, not a metric:** spot‑check 5 plans per arm by hand to confirm the enrichment is doing what the design claims (spaCy flagging real ambiguities, not noise; retrieval surfacing actually‑related lessons).

For B specifically, also report **retrieval precision@3**: of the three nearest archived runs, how many a human judges relevant. And track **lesson concentration** — if one lesson is being injected into >40% of plans, the retriever has collapsed and B is failing the honesty boundary regardless of pass rate.

## Recommendation

**Run D first as a one‑afternoon experiment. Then, only if D fails to clear the bar, build B.**

Reasoning:

- D costs nothing and tests the load‑bearing assumption behind every other arm: that the planner needs *external* help and not just better instructions. If a prompt rewrite that inlines `CHALLENGES.md` and demands consistent entity names lifts pass rate enough, the NLP layer is a solution looking for a problem.
- If D underperforms, the failure pattern in `CHALLENGES.md` is *recurrence* — the same shape of mistake re‑appearing across problems — and retrieval (B) directly attacks recurrence in a way prompt engineering structurally cannot. Linting (A) and query expansion (C) target softer signals.
- B composes with what already exists: `~/.mu/sessions/` is populated (46 runs), `researcher.deep` already knows how to append a section to `PLAN.md`, and `_set_research_notes` is a near drop‑in target for a `_set_lessons` sibling.
- C piggybacks on B's dependency; once B is in, C is cheap to add as a third experiment.
- A is the last to add, only if pass rate is still capped by underspecified tasks after B+D.

**Concrete first step (D).** Edit the planner system prompt to: (1) inline the current `CHALLENGES.md`, (2) require a `## Dependencies` section with concrete versions, (3) require entity names to be consistent across tasks. Run the measurement protocol at N=5 (kill criterion) over the 7‑problem set. If `first_try_pass` improves by ≥10 pp, escalate to N=15 and decide.

**Concrete second step (B, only if D doesn't clear the bar).** Add `src/mu/enrich.py` exposing `lessons_for(goal: str, k: int = 3) -> list[str]`, an index‑build entry point invoked at the end of `Archive.finalize`, and a flag in `agent.plan` that appends retrieved lessons to `PLAN.md` under `## Lessons From Prior Runs`. Enforce the ≥3‑corroboration rule and the <40% lesson‑concentration cap. Repeat the protocol.
