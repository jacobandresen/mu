# Harness Engineering in mu

## Abstract

This document describes how **mu** — a local AI coding toolkit that drives an autonomous coding loop from a plain-English goal — instantiates the principles of *harness engineering*. It examines the structural role of the `sensors/` subsystem within the harness, characterises the planning pipeline as a verification-before-execution discipline, and situates these design choices within emerging academic frameworks for agent harness design.

---

## 1. Background: Harness Engineering

The term *harness engineering* denotes the discipline of deliberately designing the scaffolding that surrounds a foundation-model agent: the orchestration loop, tool registry, context management strategy, verification protocols, failure attribution mechanisms, and constraint boundaries that together convert a stateless language model into a goal-directed autonomous system [1][2].

The distinction between the *model* and the *harness* is operationally significant. Empirical evaluations have demonstrated that harness configuration accounts for more performance variance than model capability alone; the same base model running under different harness configurations has produced solve rates on SWE-bench ranging from approximately 5% to over 30% [3][4]. As Zhong and Zhu (2026) formalise it, an agent harness is "a runtime substrate surrounding a foundation-model software agent that manages context, tools, project memory, task state, observability, failure attribution, verification, permissions, and maintenance state" [1].

Zhong and Zhu propose eleven component responsibilities that a complete harness should fulfil:

| # | Component | Responsibility |
|---|-----------|----------------|
| 1 | Task interface | Ingests and normalises the user goal |
| 2 | Context manager | Selects and composes the model's input context |
| 3 | Tool registry | Exposes and validates callable tools |
| 4 | Project memory | Persists structured state across turns |
| 5 | Task state | Tracks completion status of sub-tasks |
| 6 | Observability layer | Records what the agent did and why |
| 7 | Failure attribution | Identifies the proximate cause of failures |
| 8 | Verification protocol | Applies requirement-level checks before acceptance |
| 9 | Permission boundary | Enforces which operations the agent may perform |
| 10 | Entropy auditor | Monitors for unbounded or divergent behaviour |
| 11 | Intervention logger | Records human and automated corrections |

The *H0–H3 harness ladder* they introduce provides a controlled-ablation vocabulary: H0 is a minimal baseline (goal + repository); H1 adds tool registries; H2 adds project memory; H3 adds the observability-verification layer [1]. mu operates at H3 across all components.

---

## 2. The mu Architecture as a Harness

mu's `mu agent "<goal>"` command instantiates a multi-phase orchestration loop described in `src/mu/agent.py`. The loop is not a single long-running model session; it is a *structured compound AI system* [5] in which discrete specialised agents (planner, writer, repair agent) are composed around a deterministic control plane. This separation reflects the architectural principle that "each decision — model selection, context management, safety, tool dispatch — should be independently configurable without affecting others" [5].

The following components collectively constitute mu's harness:

| Harness Component | mu Implementation |
|-------------------|-------------------|
| Task interface | CLI argument → `goal` in `run()` |
| Context manager | `_build_autonomous_system()`, skill files |
| Tool registry | `src/mu/tools.py` (Write, Edit, Bash, Read) |
| Project memory | `PLAN.md` (file-system-persistent task state) |
| Task state | `next_task()`, `mark_task_done()` |
| Observability | `~/.mu/sessions/<id>/` archive, `meta.json` |
| Failure attribution | `record_failed_repair()`, lint/test logs |
| Verification protocol | Lint gate, test gate, sensor fixers |
| Permission boundary | Repair sessions receive Write/Edit/Read only (no Bash) |
| Entropy auditor | `check_goal_alignment()`, stub detection |
| Intervention logger | `log()`, `sess.finalize()` |

---

## 3. The Planning Phase

Planning in mu produces `PLAN.md`: a file-system-persisted, machine-parseable task checklist that serves as the agent's shared external memory across the entire session.

### 3.1 LLM-Based Planning

The planner agent is always invoked with the `task-planner` skill injected into the system prompt. Skill files (packaged under `src/mu/skills/`, read at runtime via `_load_skill()`) are the mechanism by which the harness shapes model behaviour toward correct output formats — a form of *prompt-level guardrail* [5]. This design reflects the harness-engineering principle of *deferring model invocation to where it is irreplaceable* [2][3]: the harness manages orchestration deterministically, the model handles open-ended content generation.

### 3.2 Plan Normalisation (Pre-Execution Sensor Pass)

Before the write loop begins, mu applies a series of deterministic transformations to the plan. This normalisation pass is an early instantiation of the sensor subsystem: it identifies and corrects model-generated planning errors without a model call:

- **Embedded file extraction** — code blocks inside `PLAN.md` are materialised to disk (`normalize_embedded_files`)
- **Portability normalisation** — `python` → `python3` for shell portability (`normalize_test_command`)
- **Runtime artifact removal** — `.db`, `.sqlite`, `.o` entries are dropped from the task list (`drop_runtime_artifacts`)
- **Goal alignment check** — plan keywords are cross-referenced against the original goal (`check_goal_alignment`)
- **Thinking artifact removal** — `</think>` tags and similar reasoning traces are stripped from the plan (`strip_thinking_artifacts`)

The plan normalisation pass exemplifies *requirement-level verification before execution begins* — one of the five design principles Zhong and Zhu identify as central to H3-class harnesses [1].

---

## 4. The Sensors Subsystem

The `src/mu/sensors.py` module is mu's *verification protocol* layer. It contains language-specific, deterministic fixers that execute in response to observable model failure modes — without invoking the model. This design reflects a principle articulated in the harness engineering literature: "rigid, unchanging software tests — linters, type checkers — physically block an agent from completing a task until its output is verified" [4].

Sensors occupy a specific position in the harness's repair hierarchy:

```
Model writes file
       │
       ▼
Post-write sensors (deterministic, unconditional)
       │
       ▼
Lint gate (static analyser)
       │
   ┌───┴───────────────────────────────┐
   │ Lint fails                        │ Lint passes
   ▼                                   ▼
Tool-based auto-fix (e.g. ruff --fix) Mark task done
   │
   ▼
Deterministic sensors (error-conditional)
   │
   ▼
LLM repair agent (last resort, no Bash)
```

### 4.1 Sensor Classification

Sensors divide into two operational classes:

**Class A — Unconditional post-write sensors.** These run on every write of a specific file type, regardless of whether a lint error has been observed. They correct known-frequent model output patterns:

| File type | Sensor | Model failure pattern corrected |
|-----------|--------|---------------------------------|
| `Makefile` | `fix_makefile_space_indent` | Recipe lines indented with spaces instead of tabs |
| `Makefile` | `fix_orphan_top_level_commands` | Bare commands before any target declaration |
| `Makefile` | `fix_no_targets` | Plain script with no `target:` declaration |
| `Makefile` | `fix_inline_recipe` | `build: gcc main.c` (recipe must be tab-indented on next line) |
| `Makefile` | `fix_duplicate_var` | Same variable assigned twice |

**Class B — Error-conditional sensors.** These inspect the lint error message before acting. Their narrow precondition prevents false-positive rewrites:

| File type | Sensor | Trigger condition |
|-----------|--------|-------------------|
| `*.py` | `fix_multiline_single_quote` | `invalid-syntax` + single-quoted `.execute(` spanning lines |
| `*.py` | `fix_missing_close_paren` | `invalid-syntax` + unclosed `.execute("""` |
| `*.py` | `fix_test_import_module` | Test imports a module name not present on disk |
| `*.py` | `ruff_autofix` | Any lint failure (runs `ruff check --fix`) |

### 4.2 Design Properties

Each sensor function exhibits four invariants that distinguish it from heuristic or model-based repair:

1. **Narrow applicability check** — extension and/or error-message predicate evaluated before any file I/O
2. **Idempotency** — applying a sensor to already-correct output leaves the file unchanged
3. **Determinism** — given the same input file, the output is always identical
4. **Bounded scope** — each sensor targets one specific structural failure; it does not attempt general repair

These properties make sensors *safe to apply unconditionally* for Class A, and *safe to trust over model repair* for Class B — the model repair path is only reached when sensors have been exhausted. This ordering implements the harness principle of *attribution before recovery*: the harness identifies the precise failure mode and applies the minimal corrective action before escalating to the more expensive, less predictable model-based repair [1][5].

---

## 5. The Write Loop and Integrated Verification

The write loop (`run` → iteration block in `agent.py`) integrates planning state, writer sessions, sensors, and the lint/test gates into a single orchestrated cycle:

```
for each pending task in PLAN.md:
    1. Writer session (model produces file)
    2. Stub detection (< 100 bytes triggers retry with elevated thinking)
    3. Post-write sensors — Class A (unconditional, file-type-matched)
    4. Lint gate (static analyser run)
       → ruff --fix (if Python lint fails)
       → Class B sensors (error-conditional)
       → LLM repair agent (if sensors insufficient; Bash tool withheld)
       → Hard failure if lint still fails
    5. Test gate (if task is a test file and no pending build files)
       → LLM repair agent on test failure
    6. plan.MarkTaskDone()
```

The deliberate sequencing — sensors before model repair, model repair before failure — instantiates a *defense-in-depth* verification protocol [5]. The repair agent's restricted tool set (Write, Edit, Read; no Bash) enforces a *permission boundary* that prevents the agent from substituting test re-execution for code correction.

---

## 6. Empirical Validation: The Dojo

The `dojo/` directory is mu's *empirical harness evaluation environment*. It subjects the harness to a fixed seven-problem benchmark (P1–P7, spanning Hello World through Flask REST API) using a constrained guest model (`qwen3:8b`) on limited hardware (Apple M2, 8 GB). Each dojo session produces:

- Per-problem logs (`<problem>.log`)
- Per-problem generated plans (`<problem>/PLAN.md`)
- A `findings.md` analysis of failures, sensor gaps, and repair outcomes

This mirrors the *Missing-Harness Human Intervention Rate (M-HIR)* metric proposed by Zhong and Zhu [1]: failures that required external correction reveal harness gaps, each of which drives a targeted improvement to a sensor, skill file, or plan normalisation rule. The dojo thus functions as a *controlled ablation study* of the harness at the component level — the empirical methodology recommended for H3-class systems.

---

## 7. Overview Diagram

![mu harness architecture diagram](assets/harness_diagram.png)

---

## 8. Discussion

mu's architecture makes several non-obvious choices that are legible as harness engineering decisions:

**Sensors before model repair.** The cost hierarchy — deterministic fix → tool-based fix → LLM repair — reflects the harness engineering principle that *cheaper, more reliable interventions should be exhausted first* [2][3]. Model-based repair is non-deterministic; sensor-based repair is not.

**Bash withheld from repair agents.** The repair agent's tool restriction is a *permission boundary* [1] that prevents a class of failure mode: an agent that can execute `make` can silence a failing test by modifying the test rather than the source. Withholding Bash makes this substitution impossible at the schema level.

**`PLAN.md` as externalised project memory.** Storing task state in a file on disk rather than in the model's context window solves the *digital amnesia* problem [4]: the plan survives context resets, session interruptions, and model reloads. The harness reads it; the model writes to it; the sensors normalise it.

**Dojo as ongoing M-HIR measurement.** Each dojo run that produces a `findings.md` is an informal M-HIR calculation: the ratio of problems requiring external correction to total problems run. Over successive sessions, this drives sensor additions and plan normalisation rules — the empirical feedback loop that H3-class harnesses depend on [1].

---

## 9. Survey of the Literature

The following chapter surveys each cited work in the order in which it appears in this document. The aim is to situate each contribution within the broader intellectual landscape of harness engineering, identify the specific claims that bear on mu's design, and note where sources converge, diverge, or leave open questions.

---

### 9.1 Zhong & Zhu (2026) — A Formal Substrate Framework

**Full title:** *AI Harness Engineering: A Runtime Substrate for Foundation-Model Software Agents* (arXiv:2605.13357v1)

Zhong and Zhu offer the most formally structured treatment of harness engineering in the current literature. Their central contribution is the decomposition of an agent harness into eleven distinct component responsibilities — task interface, context manager, tool registry, project memory, task state, observability layer, failure attribution, verification protocol, permission boundary, entropy auditor, and intervention logger — each defined independently so that a harness can be audited component-by-component rather than holistically.

The paper's most operationally useful construct is the **H0–H3 harness ladder**: a controlled-ablation taxonomy that classifies harness implementations by their cumulative capabilities. H0 designates a minimal baseline providing only goal specification and repository access. H1 adds a tool registry. H2 adds project memory. H3 adds the observability-verification layer, completing the feedback discipline. This ladder allows researchers and practitioners to reason about *which* harness investments are load-bearing for a given task difficulty, rather than treating harness engineering as an undifferentiated investment.

The paper introduces the **Missing-Harness Human Intervention Rate (M-HIR)** as an empirical metric: the proportion of agent episodes requiring human correction that is attributable to harness gaps rather than model error. This metric is significant because it shifts blame attribution away from the model and toward the infrastructure, providing a more accurate diagnosis of production failure. A high M-HIR signals underinvestment in harness components rather than model inadequacy.

A notable design principle the paper advances is *attribution before recovery*: the harness should identify the proximate structural cause of a failure before invoking any corrective mechanism. This principle is in tension with the more common engineering instinct to retry immediately; Zhong and Zhu argue that unattributed recovery risks masking systematic failure modes and degrades the feedback signal needed to improve the harness over time.

**Significance for mu:** The eleven-component framework maps with high fidelity onto mu's architecture (see Section 2). The M-HIR concept directly underlies the dojo's empirical methodology. The attribution-before-recovery principle explains mu's sensor hierarchy: sensors are applied in ascending cost order precisely because the failure type must be diagnosed before the repair mechanism is selected.

---

### 9.2 Böckeler via Fowler (2026) — Feedforward and Feedback Controls

**Full title:** *Harness engineering for coding agent users* (martinfowler.com)

Birgitta Böckeler's article, published under Martin Fowler's imprimatur, provides the most practitioner-oriented taxonomy of harness controls and remains one of the most widely cited treatments in the engineering community. Her central claim is that agent harnesses require two complementary control types that must co-exist: **guides** (feedforward controls that steer behaviour before action) and **sensors** (feedback controls that detect and correct deviations after action).

Böckeler warns explicitly that neither class alone is sufficient: "you get either an agent that keeps repeating the same mistakes (feedback-only) or an agent that encodes rules but never finds out whether they worked (feedforward-only)." This complementarity principle has significant architectural implications — a system that invests only in system prompt engineering without post-write verification, or only in linters without guidance, is structurally incomplete.

She introduces a second dimension orthogonal to the feedforward/feedback axis: **computational controls** (deterministic, CPU-based, millisecond-to-second latency) versus **inferential controls** (AI-based semantic analysis, GPU/NPU-based, non-deterministic, slower). The practical advice is to exhaust computational controls before invoking inferential ones, because computational controls are faster, cheaper, reproducible, and leave no ambiguity in their result. This preference ordering appears throughout her industry case studies:

- **OpenAI** maintains a layered architecture enforced by custom linters, structural tests, and periodic "garbage collection" agents that scan for drift — computational-first with inferential augmentation.
- **Stripe** uses pre-push hooks with heuristic linting and "blueprints" integrating feedback early — computational controls shifted as far left in the delivery lifecycle as possible.

Böckeler identifies **behaviour harnesses** — those enforcing functional correctness rather than structural quality — as the least mature category in current practice. She notes that AI-generated test suites "put a lot of faith into the AI-generated tests" and flags this circular dependency as an unresolved problem. She does not propose a solution, though she identifies the *approved fixtures* pattern (using externally curated, human-verified test cases) as promising.

The concept of **harnessability** — the degree to which a codebase is structurally amenable to harness controls — is introduced through Ned Letcher's notion of *ambient affordances*: the intrinsic properties of an environment that make it legible and governable. Strongly typed languages, clear module boundaries, and framework-constrained architectures all increase harnessability. This observation implies that harness engineering is not purely a runtime concern; it also shapes technology selection and architectural decisions at project inception.

Finally, Böckeler invokes **Ashby's Law of Requisite Variety** to justify standardisation of service topologies: a regulator must possess at least as much variety as the system it governs. By constraining the output space (committing to three or four standard service patterns rather than infinite architectural variation), organisations make comprehensive harness coverage achievable. This is a rare application of cybernetic theory to software architecture and deserves wider attention.

**Significance for mu:** Böckeler's guide/sensor taxonomy directly maps onto mu's skill files (guides) and `sensors/` package (feedback). Her computational-before-inferential ordering is the explicit design rationale for mu's sensor hierarchy. The observation that behaviour harnesses remain immature partly explains why mu's dojo focuses on compilation and lint correctness rather than semantic functional testing.

---

### 9.3 Masood (2026) — The Enterprise Control Plane

**Full title:** *Agent Harness Engineering — The Rise of the AI Control Plane* (Medium)

Masood approaches harness engineering from an enterprise production perspective, opening with the claim that 88% of enterprise AI agent projects fail due to inadequate runtime infrastructure rather than model deficiency, with 65% of failures specifically attributable to *context drift*, *schema misalignment*, and *state degradation* — collectively termed "harness defects."

His most provocative economic claim is that strategic harness optimisation can reduce token costs by an order of magnitude (from $3.00/MTok to $0.30/MTok) while simultaneously reducing latency by a factor of four, primarily by maintaining **prefix stability** (keeping the leading portion of context window content unchanged between turns to preserve KV-cache locality). This frames harness engineering not merely as a reliability concern but as a significant cost engineering discipline.

Masood introduces the **Reasoning Sandwich** — a Plan-Execute-Verify loop in which high-capability models handle planning and verification while cheaper models execute intermediate steps. His error cascade argument provides quantitative motivation: even a per-step accuracy of 85% compounds to approximately 20% task completion probability over ten steps ((0.85)^10 ≈ 0.20). Intermediate verification gates interrupt the error cascade before it propagates. This argument implicitly justifies the write-loop structure common to systems like mu.

The concept of **Context Rot** — the progressive degradation of model attention quality as context windows accumulate noise — is named and attributed structural significance. Masood's recommended mitigation is externalising memory to virtual filesystems (markdown or JSON files on disk), analogous to virtual memory in operating systems. He cites `AGENTS.md` and `todo.md` as durable, machine-readable externalisation formats. The further concept of the **Ralph Loop** describes a harness mechanism that intercepts premature task exits, reinjects the original intent into a fresh context, and resumes — a form of context reset that preserves long-horizon continuity.

Masood distinguishes between **bounded workflows** (single scoped agents with supervisor patterns and phase-gating) and *chaotic swarms* (multi-agent meshes), advocating strongly for the former on grounds of debuggability and cost predictability. He cites standardisation protocols — **Model Context Protocol (MCP)** for agent-to-tool interaction and the **Agent-to-Agent (A2A) Protocol** for lateral delegation — as emerging infrastructure standards that reduce vendor lock-in analogously to USB-C in hardware.

**Significance for mu:** Masood's error cascade argument provides quantitative justification for mu's per-file lint gate rather than deferred end-of-session testing. His Context Rot / virtual memory framing is the theoretical basis for `PLAN.md` as externalised task state. The KV-cache prefix stability observation, while not explicitly implemented in mu's current architecture, is relevant to future prompt caching work.

---

### 9.4 MindStudio Engineering (2026) — Performance Variance as Empirical Motivation

**Full title:** *What Is Harness Engineering? Why Your Agent Wrapper Drives More Performance Than the Model*

This practitioner-oriented survey article serves primarily to quantify the performance differential attributable to harness design. Drawing on research from Stanford and Tsinghua University, the authors report that identical base models can exhibit solve-rate gaps of up to 6× based solely on harness configuration choices. The specific finding from SWE-bench evaluations — solve rates ranging from approximately 5% to 30%+ across harness variants of the same model — constitutes the most-cited empirical datum in the harness engineering literature and provides the foundational motivation for treating harness design as a primary rather than secondary concern.

The article proposes six critical harness components: context window management (strategic retrieval rather than passive accumulation), tool interface design (specific rather than generic naming to reduce model ambiguity), planning and decomposition (structured plan-then-execute rather than unstructured generation), error recovery logic (retry mechanisms with escalation paths), output parsing and validation (bridging model text to actionable results), and memory architecture (intentional design across short-term, working, and long-term layers).

The article identifies six common failure patterns in deployed harnesses: static system prompts that cannot adapt to task state, excessive tool availability that increases model decision overhead, missing fallback strategies, passive context accumulation, skipped output validation, and absent observability. Each failure pattern corresponds to a missing or degraded harness component, providing a diagnostic checklist for practitioners.

**Significance for mu:** The 6× performance gap statistic grounds the design philosophy that harness investment dominates model selection as a determinant of task success. The tool interface design point is consistent with mu's choice to expose exactly four precisely-named tools (Write, Edit, Bash, Read) rather than a broad tool surface.

---

### 9.5 Nayak (2026) — The Operating System Analogy

**Full title:** *Harness Engineering: Building the Operating System for Autonomous Agents* (Medium / The AI Forum)

Nayak's contribution is primarily conceptual: he advances the **operating system analogy** for agent harnesses, arguing that the harness occupies the same architectural position relative to an LLM that an OS kernel occupies relative to application processes — mediating access to resources, enforcing isolation, managing state, and providing a stable interface between a reasoning engine and an unpredictable environment. This analogy is productive because it clarifies why the harness must be engineered separately from the model: just as application correctness cannot be delegated to the OS, harness correctness cannot be delegated to the model.

The article's central philosophical reframing is notable: "The model is a reasoning engine. The harness is an engineering system. They are different responsibilities, and conflating them is the source of most production AI failures." This cleanly separates the model evaluation question (is the reasoning correct?) from the harness engineering question (is the system correct?), allowing each to be addressed by different disciplines.

Nayak's empirical demonstration — comparing a raw LLM against a harnessed system on an auto-insurance claim processing benchmark — is the sharpest quantitative argument in the surveyed literature. The raw model achieved 50% accuracy (8/16 test cases) while producing rule violations. The harnessed system achieved 100% accuracy with architectural enforcement making constraint violations impossible regardless of model output. This 2× accuracy gain, achieved entirely through harness design with no model change, directly instantiates the performance variance claim from the MindStudio study.

The **fly-by-wire analogy** is introduced to address the autonomy question: pilots still operate fly-by-wire aircraft, but architectural protections prevent them from commanding manoeuvres that would destroy the airframe. The analogy captures the key property of a well-engineered harness — it does not eliminate human or model agency but *bounds* it to the feasible region. The corrollary is the **Principle of Least Authority**: sub-agents should receive only the tools necessary for their specific role, as broader tool access expands the failure surface without benefit.

Nayak's **middleware stack** concept — four interceptor layers (observability, call budget enforcement, loop detection, claims verification) wrapping every model invocation — provides a concrete architectural pattern for implementing the observability and entropy auditing components of the Zhong-Zhu framework.

**Significance for mu:** The operating system analogy is a useful framing for mu's architecture: the harness (`src/mu/agent.py`, `src/mu/sensors.py`, `src/mu/plan.py`) is the OS; the LM Studio-hosted model is the application. The Principle of Least Authority directly explains mu's repair agent tool restriction. The 50% → 100% accuracy improvement from adding deterministic rails mirrors mu's sensor philosophy.

---

### 9.6 OpenDev / Terminal Coding Agents (arXiv:2603.05344v1) — Compound AI Systems

**Full title:** *Building AI Coding Agents for the Terminal: Scaffolding, Harness, Context Engineering, and Lessons Learned*

This arxiv paper describes the engineering of a production terminal-native coding agent and is the most architecturally detailed of the surveyed works. Its primary contribution is the distinction between **scaffolding** (the pre-execution phase that assembles system prompts, tool schemas, and subagent registries before the first turn) and the **harness** (the runtime orchestration layer that coordinates tool execution, context management, safety enforcement, and session persistence during execution). This two-phase decomposition is conceptually cleaner than treating harness engineering as a monolithic concern.

The paper advocates for **separation of concerns** as the primary architectural principle: planning, tool dispatch, context management, and safety enforcement should each be independently configurable. It implements this through a **dual-mode architecture** in which Plan Mode grants a specialised Planner subagent read-only tool access, while Normal Mode grants full execution capabilities. Constraints are enforced at the schema level (the planner's tool list simply does not include Write) rather than through runtime checks, eliminating a class of state-machine bugs.

**Context engineering** is elevated to a first-class discipline with three mechanisms: *adaptive context compaction* (progressively reducing older observations to prevent context saturation), *event-driven system reminders* (injected messages counteracting instruction fade-out over long sessions), and a *dual-memory architecture* separating episodic from working memory. The paper identifies context pressure as "the central constraint driving prompt structuring" — consistent with Masood's Context Rot framing and the widespread recommendation to externalise state to disk.

The paper describes a **three-tier skill hierarchy** (builtin, project, user) providing domain-specific prompt templates, and a **lazy tool discovery** pattern using MCP to defer loading external tool schemas until needed, reducing per-turn token overhead.

The discussion section names three "ReAct loop" foundational references — Yao et al., Zaharia et al. on compound AI systems, and context engineering research on entropy reduction — indicating that harness engineering as a discipline is consolidating around a recognisable set of theoretical ancestors.

**Significance for mu:** The scaffolding/harness distinction clarifies mu's own architecture: plan normalisation and skill loading are scaffolding; the write loop with sensor invocations is the harness. The schema-level enforcement of the repair agent's tool restriction echoes the paper's recommendation to enforce constraints structurally. Mu's skill files implement the project tier of the three-tier skill hierarchy.

---

### 9.7 Anthropic Engineering (2026) — GAN-Inspired Multi-Agent Harnesses

**Full title:** *Harness design for long-running application development*

This article from Anthropic Engineering documents the design and empirical evaluation of a three-agent harness architecture inspired by Generative Adversarial Networks (GANs): a **Planner** that expands minimal prompts into full product specifications, a **Generator** that implements features iteratively within negotiated completion criteria, and an **Evaluator** that tests through live interaction and grades against explicit standards. The core motivation is eliminating **self-evaluation bias** — the systematic tendency of models to overestimate the quality of their own outputs when asked to self-critique.

The paper's most significant empirical result is a direct cost-quality comparison: a solo agent approach (approximately $9, 20 minutes) produced non-functional output, while the three-agent harness ($200, 6 hours) produced a fully playable retro game application. The 22× cost increase yielded a categorical quality improvement (non-functional to functional), suggesting that harness investment is not merely incremental but can cross qualitative thresholds inaccessible to solo agents.

The **Sprint Construct** is introduced as a scope management mechanism: Generator and Evaluator negotiate a detailed set of completion criteria before implementation begins, bridging the gap between high-level specification and testable deliverables. This pre-execution negotiation functions as a form of schema-level constraint: the generator's work is bounded by explicit, agreed criteria rather than unconstrained interpretation of the original goal.

The paper's recommendation on context management is notable for contradicting the common preference for in-context compaction: **context resets** — completely clearing the context window and providing a structured handoff document — outperformed compaction for maintaining model coherence on long-horizon tasks, particularly with earlier model versions. This suggests that the optimal context strategy is task-length-dependent, and that very long sessions may require architectural support for clean context boundaries rather than continuous context management.

A methodological recommendation with broad applicability is **dynamic complexity scaling**: as model capabilities improve, systematically remove one harness component at a time to identify which scaffolding elements are still load-bearing. This empirical harness ablation methodology is closely related to the Zhong-Zhu H0–H3 ladder and to mu's dojo practice of running the same problem set across successive versions.

**Significance for mu:** The GAN-inspired Planner/Generator/Evaluator pattern is structurally analogous to mu's planner agent → writer agent → repair agent pipeline, though mu's evaluator role is played by deterministic lint and test gates rather than a model-based evaluator. The Sprint Construct is conceptually related to mu's PLAN.md task checklist, which pre-commits the writer to a specific set of files. The dynamic complexity scaling recommendation is directly applicable to mu's dojo methodology.

---

### 9.8 Cross-Cutting Themes

Across the eight surveyed works, four recurring themes emerge that collectively define the current consensus in harness engineering research:

**1. The Agent = Model + Harness identity.** Every source subscribes to this formula as the foundational framing. The implication is that evaluation, investment, and debugging should be decomposed accordingly: model evaluation (reasoning quality) and harness evaluation (infrastructure correctness) are separate disciplines requiring different methods.

**2. Deterministic controls before inferential controls.** Böckeler, Nayak, and the Firecrawl survey all explicitly recommend exhausting computational (deterministic) controls before invoking LLM-based repair. Masood and Zhong-Zhu imply this through their cost and attribution frameworks. The sole exception is Anthropic Engineering's evaluator agent, which performs inferential evaluation — but in that context the model-based evaluator is cheaper than a human evaluator, not cheaper than a deterministic test.

**3. Externalised memory as the solution to context limitations.** All sources address the finite context window as a primary constraint. The universal solution is externalising state to file-system-persistent structured documents (`PLAN.md`, `AGENTS.md`, `todo.md`, `meta.json`). This convergence reflects a pragmatic consensus: no context management strategy within the window is as reliable as moving state outside it.

**4. Empirical harness evaluation through ablation.** The Zhong-Zhu H0–H3 ladder, the Anthropic dynamic complexity scaling recommendation, and mu's dojo methodology all operationalise the same insight: harness components should be added and removed systematically, with outcome metrics collected at each level, to identify which investments are genuinely load-bearing. Ad hoc harness design without ablation cannot distinguish essential scaffolding from cargo-cult complexity.

A significant **open problem** shared across sources is the *behaviour harness*: enforcing functional correctness rather than structural quality. Böckeler identifies it as the least mature harness category; Nayak's auto-insurance demonstration addresses it only within a narrow, rule-bounded domain; the Anthropic three-agent system requires an AI-based evaluator to approximate it. For general-purpose coding agents, functional correctness harnesses remain an unsolved problem — a limitation that mu acknowledges implicitly by relying on deterministic lint gates rather than semantic test oracles.

---

## References

[1] Zhong, H. & Zhu, S. (2026). *AI Harness Engineering: A Runtime Substrate for Foundation-Model Software Agents*. arXiv:2605.13357v1. https://arxiv.org/html/2605.13357v1

[2] Masood, A. (2026, April). *Agent Harness Engineering — The Rise of the AI Control Plane*. Medium / Towards AI. https://medium.com/@adnanmasood/agent-harness-engineering-the-rise-of-the-ai-control-plane-938ead884b1d

[3] Fowler, M. (2026). *Harness engineering for coding agent users*. martinfowler.com. https://martinfowler.com/articles/harness-engineering.html

[4] Firecrawl Engineering. (2026). *What Is an Agent Harness? The Infrastructure That Makes AI Agents Actually Work*. https://www.firecrawl.dev/blog/what-is-an-agent-harness

[5] (2026). *Building AI Coding Agents for the Terminal: Scaffolding, Harness, Context Engineering, and Lessons Learned*. arXiv:2603.05344v1. https://arxiv.org/html/2603.05344v1

[6] MindStudio Engineering. (2026). *What Is Harness Engineering? Why Your Agent Wrapper Drives More Performance Than the Model*. https://www.mindstudio.ai/blog/what-is-harness-engineering

[7] Nayak, P. (2026, March). *Harness Engineering: Building the Operating System for Autonomous Agents*. Medium / The AI Forum. https://medium.com/the-ai-forum/harness-engineering-building-the-operating-system-for-autonomous-agents-1e20c105f689

[8] Anthropic Engineering. (2026). *Harness design for long-running application development*. https://www.anthropic.com/engineering/harness-design-long-running-apps
