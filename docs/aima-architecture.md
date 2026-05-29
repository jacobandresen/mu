# Plan: Re-framing mu with *Artificial Intelligence: A Modern Approach*

**Status:** proposal only — a vocabulary and (optional) renaming plan. **Nothing
here has been applied, and no rename should be executed while the dojo is
running**, since `mu` is installed editable and renaming a module out from under
in-flight imports would break the suite. Adopt only when picked up deliberately.
**Source frame:** Russell & Norvig, *AIMA* — the Intelligent Agents chapter
(agent types, PEAS, the learning-agent schematic), the Problem-Solving by Search
chapter, the Automated Planning chapter, and the Learning chapters. Chapter and
figure numbers vary by edition; verify against your copy before citing — the
mapping below does not depend on the exact numbering.

## Thesis

mu is not "a wrapper around an LLM." Structurally it is a textbook **learning
agent** in the AIMA sense: a performance element that acts in a task
environment, a critic that scores those actions against a fixed performance
standard, a learning element that folds the critic's feedback back into the
agent's knowledge, and a problem generator that manufactures fresh experience.
Today these roles are spread across modules named for their *implementation*
(`sensors`, `session`, `reflect`, `dojo`) rather than their *function in the
agent*. Adopting AIMA's vocabulary makes the architecture legible and tells
contributors where new behaviour belongs.

This document (1) identifies mu's parts, (2) maps each to an AIMA concept and a
suggested name, and (3) gives a staged, low-risk plan for adopting the names.

---

## 1. The centerpiece: mu as an AIMA *learning agent*

AIMA's learning-agent schematic (Intelligent Agents chapter) decomposes a
learning agent into four components. mu has all four:

| AIMA component | What AIMA says it does | mu's realization | Suggested name |
|---|---|---|---|
| **Performance element** | Selects external actions from percepts — "the entire agent" of a non-learning design | `agent.plan/run` orchestration → `_run_planner` → `session.Session` writer loop → `tools.dispatch` | `performer` / `act/` |
| **Critic** | Judges actions against a *fixed performance standard*; tells the **learning element** how well the agent did | the **archived session outcome** (pass/fail tombstone in `~/.mu/sessions/`) — the signal `reflect`/`enrich` consume; performance standard = "the test command exits 0" | `critic` |
| **Learning element** | Uses the critic's feedback to improve the performance element | `reflect.py` (failed sessions → `CHALLENGES.md`) + `enrich.py` (retrieve past lessons at plan time) | `learner` |
| **Problem generator** | Suggests exploratory actions for new, informative experience | the **dojo**: `sit.sh` / `practice.sh` / `dojo/` problem set P1–P7 | `explorer` / `proband` |

The fit is exact enough to be a design check: **the dojo is the problem
generator.** Its only job is to drive the agent into varied situations (C,
SQLite, SDL2, C#, Go, Rust, Flask) so the critic produces signal the learner
can use. Shuffling problem order (`sit.sh` line 60) is precisely AIMA's "explore
to avoid priming on one failure mode."

Two corrections must not be conflated:

- **In-episode correction** is `session.repair_loop` — a *model-based reflex*
  (§3) that reacts to the latest test output *within a single run*. It does not
  change the agent; it just gets this one task to pass.
- **Across-episode learning** is the critic→learner path. The critic's signal
  for *learning* is the persisted pass/fail outcome, not the live repair loop.

The **feedback path** is the load-bearing insight: critic → learner → knowledge
base → next run's performance element. Concretely:
`AgentSession.finalize` writes the outcome tombstone →
`reflect`/`enrich` read the archive → `CHALLENGES.md` + retrieved lessons →
`_run_planner` consumes them on the next goal.

(The **performance element** here is itself composite — the planner selects the
action sequence and the writer loop executes it. §5 lists them as separate rows;
both are subcomponents of the one performance element.)

---

## 2. PEAS — mu's task environment

AIMA specifies any agent by **P**erformance / **E**nvironment / **A**ctuators /
**S**ensors. Writing mu's PEAS down clarifies what the agent is optimizing and
what it can touch:

- **Performance measure:** `pass` (final test exits 0), `first_try_pass` (no
  repair needed), `repair_iters`, `wall_seconds`, `tokens`. (Already recorded
  per run in the session `meta.json`.)
- **Environment:** the project working directory + the host toolchains
  (compilers, `pytest`, `cargo`, `dotnet`, …) + LM Studio. Classification:
  *partially observable* (the agent sees only what it reads/runs),
  *stochastic* (the LLM), *sequential* (edits accumulate), *dynamic-ish*,
  *discrete*, effectively *single-agent*.
- **Actuators:** `tools._write`, `_edit`, `_bash` — the only ways mu changes the
  world.
- **Sensors:** `tools._read` + the captured stdout/stderr of the test and lint
  commands. These are mu's *percepts*.

---

## 3. The agent-type spectrum

mu is not one agent type; it is a stack, lowest to highest:

| AIMA agent type | Defining trait | Where mu does it |
|---|---|---|
| **Simple reflex** | condition → action rules, no memory | `sensors.py` — every `fix_*` is literally *if lint shows X, rewrite Y*. These are condition-action reflexes, **not** sensors. |
| **Model-based reflex** | keeps internal state, acts on history | `session.repair_loop` — carries the running edit/test history between turns |
| **Goal-based** | searches/plans toward an explicit goal | `_run_planner` → `PLAN.md`; `plan.py` is the goal & problem representation |
| **Utility-based** | prefers better outcomes, not just "a" goal | partial today — `detect_complexity` tunes effort; the perf-measure could become an explicit utility |
| **Learning** | improves with experience | `reflect` + `enrich` + the archive |

**Naming consequence:** `sensors.py` is the most mis-named module under the AIMA
lens — its contents are reflex *effectors*, while the real sensors live in
`tools._read` and the gate outputs. See §5.

---

## 4. Knowledge, planning, and search vocabulary

- **Knowledge base (TELL/ASK):** `CHALLENGES.md` (learned, mutable) + `skills/`
  (given, static background knowledge) + the session archive (episodic memory).
  `reflect` and `enrich.index_session` **TELL** the KB; `_run_planner`
  (`_load_challenges_for_planner`) and `enrich.lessons_for` **ASK** it.
- **Problem formulation (the Search chapter):** `PLAN.md` is the agent's *plan* — a goal
  (`## Summary`), an action sequence (`## Files` checklist), and a goal test
  (`## Test Command`). `plan.parse` is the problem reader.
- **Plan refinement (the Planning chapter, HTN-flavoured):** `split` / `flow` / `assess` /
  `iterate` are hierarchical-task-network style refinements of an existing plan;
  `lint.py` is a **pre-execution plan critic** (validates plan *form* before any
  action), distinct from the **post-execution critic** (tests).
- **Reasoning substrate / oracle:** `client.py` is the interface to the
  inference engine (the LLM). In AIMA terms it is the agent's reasoning
  mechanism, not a component of the agent's design per se.
- **Active perception / information gathering:** `researcher.py` is an
  *information-gathering sub-agent* that actively perceives the web and writes
  findings into the plan. (This is the opposite of AIMA's *sensorless* search,
  which acts with no percepts — here the whole point is to acquire percepts.)

---

## 5. Full part → AIMA concept → suggested name

| mu part (today) | AIMA concept | Suggested name | Note |
|---|---|---|---|
| `agent.py` (`plan`,`run`,`iterate`) | agent program / control architecture | `architecture.py` or keep `agent.py` | the "agent = architecture + program" top level |
| `_run_planner` + `plan.py` | goal-based planner + problem rep | `planner` (role) / `Plan` stays | PLAN.md = the plan |
| `session.py` (writer loop) | **performance element** | `performer.py` | the part that acts |
| `session.repair_loop` + gates | **critic** (perf standard = tests pass) | `critic` | a-posteriori critic |
| `lint.py` | pre-execution plan critic | `plan_critic.py` | a-priori critic |
| `sensors.py` | **simple-reflex condition-action rules** (effectors) | `reflexes.py` | **mis-named** today; not sensors |
| `tools.py` Write/Edit/Bash | **actuators** | `actuators` (within `tools`) | how mu changes the world |
| `tools.py` Read + gate stdout | **sensors / percepts** | `percepts` | the real sensors |
| `reflect.py` | **learning element** (offline) | `learner.py` | TELLs the KB |
| `enrich.py` | learning element (retrieval) / episodic recall | `recall.py` | ASKs the archive |
| `archive.py` | **episodic memory** (experience store) | `memory.py` | the example database |
| `CHALLENGES.md` | learned **knowledge base** | (keep) | mutable rules |
| `skills/` | **background knowledge** (given axioms) | (keep) | static KB |
| `dojo/`,`sit.sh`,`practice.sh` | **problem generator** + perf-measure harness | `explorer/` + `bench` | drives experience |
| `models-catalog.json` | actuator/effector capability registry | (keep) | which "bodies" are available |
| `client.py` | reasoning-engine interface (oracle) | (keep) | not an agent component |
| `researcher.py` | information-gathering sub-agent | `scout.py` | active perception |
| `theme.py` | — (UI, outside the agent) | (keep) | not in scope |

---

## 6. Adoption plan (staged, low-risk)

There is **no test suite**, so a big-bang module rename is an uninsured change.
Adopt the vocabulary in order of value-to-risk:

**Stage 0 — documentation only (zero code risk).**
- Land this file. Add an "Agent anatomy (AIMA)" section to `AGENTS.md` with the
  four-component diagram and the PEAS block. Update module docstrings to name the
  role: e.g. `sensors.py` → *"Simple-reflex condition-action rules (effectors)
  applied after model writes — the agent's reflex layer."* No symbol changes.

**Stage 1 — rename the one actively-misleading module.**
- `sensors.py` → `reflexes.py` (and `apply_*`/`fix_*` stay). This is the single
  rename that removes a real comprehension trap (effectors masquerading as
  sensors). One module, ~6 import sites (`agent.py`); mechanical. Provide
  `sensors = reflexes` shim for one release if anything external imports it.

**Stage 2 — introduce role names without moving code.**
- Add thin role aliases at import time so contributors can speak AIMA:
  `from mu import reflect as learner`, `enrich as recall`, `archive as memory`.
  Aliases first, physical file renames only once they've proven stable.

**Stage 3 — split `tools.py` along the sensor/actuator seam.**
- Group `_write/_edit/_bash` under an `actuators` banner and `_read` (+ a future
  `observe_tests`) under `percepts`, even if they stay one file. Makes the PEAS
  boundary visible in code.

**Stage 4 — make utility explicit (genuine capability, not just naming).**
- Promote the performance measure from scattered log fields to a single
  `Utility` record the critic emits and the learner consumes — the missing
  "utility-based agent" rung in §3. This is where the AIMA frame stops being
  cosmetic and starts guiding design.

**Sequencing rule:** Stages 0–1 are safe now. Stages 2–4 should each ship with
at least a smoke test of the affected path first, given the no-test constraint.

---

## 7. A test suite the AIMA structure suggests

mu has **no tests today**, which is why every change this far has been verified
by hand and the dojo. The AIMA decomposition is also a *testability map*: each
component has a different determinism profile, so each wants a different kind of
test. The organizing move is to separate the **stochastic core** (the oracle)
from the **deterministic shell** (everything else) and test them differently.

### 7.1 The seams: where test doubles plug in

Testing mu is mostly a problem of **substituting two non-deterministic boundaries**
— the LLM and the host toolchain — and **isolating three pieces of ambient state**
— the working directory, the session archive, and `MU_*` env vars. Find the
seams first; the tests are easy once they exist.

| Seam | Real implementation | Why it must be doubled | How to double it |
|---|---|---|---|
| **LLM** | `client.chat` / `client.chat_or_retry` | stochastic; needs LM Studio + GPU | fake oracle (§7.2) |
| **Toolchain** | `agent._run_cmd` (`bash -c` for lint/test gates) | needs gcc/cargo/dotnet/pytest; slow, env-dependent | fake runner returning pass/fail + canned log (§7.3) |
| **Working dir** | `os.chdir(target_dir)`, `Path('PLAN.md')`, `Path('.').rglob`, `LOG_DIR='.mu'` | functions assume they run *inside* the project; tests would read/scribble the repo | `monkeypatch.chdir(tmp_path)` (§7.4) |
| **Archive** | `~/.mu/sessions/` via `MU_AGENT_ARCHIVE_DIR` | tests must not pollute (or read) the real 129-session archive | set `MU_AGENT_ARCHIVE_DIR=tmp` (§7.4) |
| **Env knobs** | `MU_AGENT_MODEL`, `MU_LINT_PLAN`, `MU_ENRICH_LESSONS`, `MU_LMSTUDIO_HOST` | a value in the dev's shell would change outcomes | autouse fixture scrubs them (§7.4) |

Seams *not* worth doubling: `sensors.py`'s direct `subprocess` calls to `go`/`gofmt`
and `client.py`'s `free`/`sysctl` RAM probes. Test the Go reflexes only on a
runner that has Go (mark `needs_go`), and treat `_vram_gb`/`_ram_gb` as
integration-only. Don't mock what you can't assert anything meaningful about.

### 7.2 The fake oracle (corrected for mu's two entry points)

There are **two** LLM call sites, and where you patch matters because each module
binds its own name with `from mu.client import …`:

- `agent.py` (planner, plan-lint critique, split/flow/assess) calls **`chat`**
  directly → patch **`mu.agent.chat`**.
- `session.py` (repair loop), `researcher.py`, `reflect.py` call
  **`chat_or_retry`**, which internally calls the `client`-module-global `chat`
  → patching **`mu.client.chat`** covers all three.

So a complete double patches both names. (Signatures:
`chat(model, msgs, tools, timeout) -> (dict, ChatStats)`;
`chat_or_retry(model, msgs, tools, deadline) -> (dict, ChatStats)`.)

```python
# tests/conftest.py
import types, pytest
from mu.client import ChatStats

@pytest.fixture
def oracle(monkeypatch):
    """Scriptable LLM. script[substring_of_prompt] = assistant_reply."""
    script, calls = {}, []
    def _reply(messages):
        calls.append(messages)
        prompt = messages[-1]['content']
        body = next((r for k, r in script.items() if k in prompt), '')
        return {'role': 'assistant', 'content': body, 'tool_calls': []}, \
               ChatStats(prompt_tokens=0, generated_tokens=0)   # match real fields
    monkeypatch.setattr('mu.agent.chat', lambda m, msg, t, to: _reply(msg))
    monkeypatch.setattr('mu.client.chat', lambda m, msg, t, to: _reply(msg))
    return types.SimpleNamespace(script=script, calls=calls)
```

**Testability refactor worth doing (turns two patch points into one):** have
`agent.py` call the planner through `chat_or_retry` (or reference `client.chat`
module-qualified) like every other consumer. Then a single `mu.client.chat`
patch covers the whole agent, and the planner gets the same retry behaviour the
repair loop already has. Pure win; do it as part of test scaffolding.

### 7.3 The toolchain seam: test the critic without compilers

The lint/test **gates** (the critic) run through one function —
`agent._run_cmd(cmd, log_file, env=None)` — which executes `bash -c cmd` and
returns a bool. Faking it lets you exercise the **repair loop's control flow**
(the part mu actually owns) without gcc/pytest installed:

```python
@pytest.fixture
def runner(monkeypatch):
    """Script gate outcomes by iteration. results = [False, True] -> fail then pass."""
    results = []
    def fake_run_cmd(cmd, log_file, env=None):
        ok = results.pop(0) if results else True
        Path(log_file).write_text('FAILED' if not ok else 'ok')  # canned percept
        return ok
    monkeypatch.setattr('mu.agent._run_cmd', fake_run_cmd)
    return results
```

This is what makes the **repair-loop termination** test (the one true
infinite-loop risk) possible offline: script `[False]*99`, assert the loop stops
at `_REPAIR_MAX_ITERS`.

### 7.4 Test isolation: one autouse sandbox

Every test runs in a clean world. This fixture prevents the three ambient-state
leaks and is the difference between a suite that's reproducible and one that
passes only on your machine:

```python
@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                                   # cwd seam
    monkeypatch.setenv('MU_AGENT_ARCHIVE_DIR', str(tmp_path/'arch'))  # archive seam
    for v in ('MU_AGENT_MODEL','MU_LINT_PLAN','MU_ENRICH_LESSONS','MU_LMSTUDIO_HOST'):
        monkeypatch.delenv(v, raising=False)                     # env seam
    return tmp_path
```

### 7.5 Test pyramid, keyed to the AIMA components

| Layer | Components | Determinism | Doubles needed | Speed |
|---|---|---|---|---|
| **Unit** | reflexes (`sensors`), plan critic (`lint`), problem rep (`plan`), percepts/actuators (`tools`), learner guards (`reflect`/`enrich`) | fully deterministic | none (or `tmp_path`) | ms |
| **Component** | planner, critic/repair loop, plan-lint critique | deterministic *given* the oracle | `FakeOracle`, `tmp_path` | ms–s |
| **Integration** | `agent.run` end-to-end on a trivial goal | deterministic given oracle + real toolchain | `FakeOracle` + real `gcc`/`pytest` | s |
| **Characterization (the dojo)** | problem generator over real LLM | stochastic | nothing — it *is* the live system | minutes |

The dojo stays exactly as it is — it is the *characterization / acceptance*
layer (the performance-measure harness), not a unit test. The point of the lower
layers is to stop using a 30-minute stochastic run to catch a one-line
regression a 5 ms unit test would have caught.

### 7.6 Per-component test cases (concrete)

**Reflexes — `sensors.py` (biggest, easiest win).** Every `fix_*` is a pure
`file → bool` + side effect. Table-drive them:
- `fix_makefile_space_indent`: space-indented recipe → tab-indented; already-tabbed → no-op, returns False.
- `fix_missing_close_paren`, `fix_multiline_single_quote`: malformed fixture → repaired; well-formed → untouched.
- `py_autofix`: unused import removed; used import kept; syntax-error file → returns False, file unchanged.
- `fix_go_unused_imports`, `fix_no_targets`, `fix_inline_recipe`, `fix_duplicate_var`: one trip case + one no-op case each.
- **Idempotence property:** applying any reflex twice equals applying it once.

**Plan critic — `lint.py`.** (Some of these were run ad-hoc this session; make
them permanent.)
- `_check_entity_consistency`: `TodoManager`/`TodoStore` across tasks → flag; same-task reuse → no flag; `UserAuth`/`UserProfile` (non-role tails) → no flag.
- `_check_leading_pronouns`, `_check_short_descriptions`: trip + clean cases.
- **The spaCy divergence test** (justifies the 50 MB dep): "handle gracefully" → spaCy flags, regex fallback does not; vague verb *with* a direct object → neither flags. Mark `@pytest.mark.skipif(no spaCy model)`.
- `render_warnings([])` → `''`.

**Problem representation — `plan.py`.**
- `parse` round-trips: `parse_content(text)` then re-render preserves tasks, statuses, test command, context.
- `next_task` skips done/in-progress; `mark_task_done` flips exactly one box.
- Normalizers (`strip_thinking_artifacts`, `normalize_embedded_files`, `normalize_test_command`, `drop_runtime_artifacts`, `drop_minority_languages`): fixture-in → expected-out, plus no-op on already-clean input.

**Percepts / actuators — `tools.py`.**
- `dispatch` routes each tool name to the right handler; unknown name → error string, no raise.
- `_edit` on non-unique `old_str` → reports failure, leaves file unchanged (a real correctness trap).
- `extract_code_block` / `_extract_fence`: fenced, unfenced, and mislabeled-language inputs.

**Critic / repair loop — `session.py`** (uses `FakeOracle`).
- Script the oracle to "fix" a failing file on turn 2 → loop reports pass, stops, ≤ N iterations.
- Script it to never fix → loop exhausts `_REPAIR_MAX_ITERS` and gives up cleanly (no infinite loop — the property that matters most).

**Learner guards — `reflect.py` / `enrich.py`** (deterministic, no embeddings if
you stub `_embed`).
- `reflect`: `_is_duplicate` blocks a near-identical title; `_is_problem_specific` rejects a hardcoded-to-one-problem lesson (the honesty boundary).
- `enrich`: the **≥3-corroboration** rule and the **<40 % concentration cap** (the retriever's honesty guards) — feed a synthetic archive and assert a lesson backed by 2 runs is withheld, and a lesson that would land in >40 % of plans is dropped.

**Performance element / orchestration — `agent.plan`** (uses `FakeOracle`).
- Flag-off invariant: with `MU_LINT_PLAN` unset, `mu.lint` is never imported and the oracle is called exactly once (the planner). *(Already verified manually this session — make it a regression test.)*
- Flag-on: script a vague plan then a clean revision → assert `PLAN.md` ends clean and the oracle was called twice.

### 7.7 Worked examples (runnable)

The point of the seams above is that real tests become short. Four that would
have caught regressions from *this* session:

```python
# Unit — a reflex is a pure transform (no doubles, uses the autouse sandbox)
def test_makefile_space_indent_fixes_then_is_idempotent():
    from mu.sensors import fix_makefile_space_indent
    Path('Makefile').write_text("all:\n    echo hi\n")     # 4 spaces
    assert fix_makefile_space_indent('Makefile') is True
    assert "\techo hi" in Path('Makefile').read_text()      # now a tab
    assert fix_makefile_space_indent('Makefile') is False   # idempotent no-op

# Unit — the plan critic, deterministic checks
def test_lint_flags_entity_mismatch():
    from mu.lint import lint_plan
    Path('PLAN.md').write_text(
        "## Files\n- [ ] a.py — defines `TodoManager`\n"
        "- [ ] b.py — exposes `TodoStore` over HTTP and queues items\n")
    warns = lint_plan('PLAN.md')
    assert any('entity-mismatch' in w for w in warns)

# Component — repair loop TERMINATES when the gate never passes (runner + oracle)
def test_repair_loop_gives_up(oracle, runner):
    runner[:] = [False] * 99                 # gate always fails
    oracle.script['REPAIR'] = '<edit that does not help>'
    ... drive session.repair_loop ...
    assert iters <= _REPAIR_MAX_ITERS        # no infinite loop

# Component — the planner survives GARBAGE model output (the harness's real job)
def test_planner_retries_on_unparseable_then_succeeds(oracle):
    oracle.script['Create a PLAN.md'] = 'I think the answer is 42.'   # no checklist
    # second attempt (different prompt path) returns a valid plan
    ... assert agent._run_planning_phase(...) eventually writes a valid PLAN.md
```

### 7.8 The highest-value target: reaction to bad model output

mu's *value* is not the model — it is the harness that makes a flaky model
usable. So the tests that matter most assert how mu **reacts to bad percepts and
bad generations**, all deterministic given the fake oracle:

- Planner returns prose with no `- [ ]` checklist → `_run_planning_phase` retries
  up to 3× then fails cleanly (no crash, non-zero exit).
- `extract_plan_content` on fenced / thinking-tag / empty output → returns the
  plan body or `''`, never a traceback.
- Writer emits a code fence with the wrong language tag → `extract_code_block`
  still recovers the body.
- Oracle raises / times out → `chat_or_retry` retries then surfaces a clean
  error; the repair loop and `agent.run` exit with a code, not a stack trace.
- Model writes a near-empty file → `_is_effectively_empty` triggers the stub.

These are exactly the behaviours the dojo exercises stochastically and
expensively; pinning them as fast unit tests is the biggest single payoff.

### 7.9 Tooling, fixtures & CI

- `pytest` is already in the `dev` extra; add `pytest-cov`. No new *core* deps.
- Fixtures in `tests/fixtures/`: malformed Makefiles, a `PLAN.md` per lint check,
  a stubbed session archive (a couple of `meta.json` + log dirs) for the learner.
- Markers in `pyproject.toml` so the suite is green with no model/toolchain:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  markers = [
    "needs_lmstudio: requires a running LM Studio",
    "needs_spacy: requires spaCy + en_core_web_sm",
    "needs_go: requires the Go toolchain",
  ]
  ```
  Gate with `@pytest.mark.skipif(importlib.util.find_spec('spacy') is None, …)` etc.
- **CI** (GitHub Actions sketch): `pip install -e '.[dev,lint]'`; optionally
  `python -m spacy download en_core_web_sm`; run
  `pytest -m "not needs_lmstudio" --cov=mu`. The unit + component layers must
  finish in **< 10 s** with no network and no GPU. Anything needing LM Studio is
  the dojo's job, not CI's.
- **Coverage targets that mean something:** aim high on the deterministic shell
  (`sensors`, `lint`, `plan`, `tools`) where a number reflects real safety; do
  *not* chase coverage through the oracle-driven paths, where a passing test
  proves the fake was scripted right, not that mu is correct.

### 7.10 Suggested first PR (value / effort order)

1. `FakeOracle` fixture + `tests/` scaffold (§7.1).
2. Reflex unit tests (§7.3, first block) — largest surface, zero doubles, immediate regression safety for `sensors.py`.
3. Plan-critic + plan-parser unit tests — locks in `lint.py` and `plan.py`.
4. Repair-loop termination test — guards the one true infinite-loop risk.
5. The two `agent.plan` flag invariants — protects the `MU_LINT_PLAN` wiring added this session.

Stages 2–4 of the renaming plan (§6) should not ship until at least items 1–3
here exist; that is what turns "uninsured rename" into a safe one.

## 8. One-paragraph summary for `AGENTS.md`

> mu is a learning agent. A **planner** turns a goal into a `PLAN.md` (the
> agent's plan); a **performer** (the writer loop) executes it through
> **actuators** (Write/Edit/Bash) while reading the world through **percepts**
> (Read + test output); a **critic** scores the result against a fixed standard
> (the test command exits 0) and drives a repair loop; a **reflex layer**
> (today `sensors.py`) applies condition-action fixes; a **learner** (`reflect`
> + `enrich`) distills outcomes from the **episodic memory** (`~/.mu/sessions/`)
> into the **knowledge base** (`CHALLENGES.md`, `skills/`); and the **dojo** is
> the **problem generator** that manufactures the experience the learner needs.
