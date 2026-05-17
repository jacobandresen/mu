# Plan: Direct Ollama API Integration (Remove Pi)

## Context

`mu agent` currently spawns `pi` (an npm-installed Node.js coding agent) as a subprocess for every planning, writing, and repair step. Pi's only role is:
1. POST to Ollama's `/api/chat` with a system prompt + user prompt
2. Receive tool-call responses from the model
3. Dispatch `Write` / `Edit` / `Bash` / `Read` tool calls
4. Exit when the target file exists or the session ends

`mu run` is a thin syscall.Exec wrapper that just invokes pi directly for interactive use.

Both commands are eliminated. Mu owns the Ollama chat + tool-dispatch loop in Go, removing the npm dependency entirely.

---

## Dojo Findings (2026-05-17) — What They Tell Us

The latest dojo run (qwen3:8b, M2 8GB) went 6/7: P1–P6 all passed; P7 (Flask+pytest) failed. Three bugs were identified and **already fixed**:

| Bug | Root Cause | Fixed |
|-----|-----------|-------|
| `--thinking auto` rejected | pi flag validation error; repair silently did nothing | ✅ Disappears with pi removal |
| Combined-mode files bypass lint gate | Files written during planning skipped the write-loop lint check | ✅ lint gate added |
| Python pytest `ModuleNotFoundError` | `pytest` without `PYTHONPATH=.` can't find app module | ✅ `FixPythonMakefileTest` added |

Bug 1 (thinking mode) is a pi artifact that vanishes entirely — mu will control thinking via inline tokens (`/no_think`, `/think`) appended to the user message.

**Remaining dojo observations (not yet fixed):**
- `CheckGoalAlignment` fires false-positive NOTEs on nearly every problem (common verbs like "write", "using", "returns" treated as technical keywords). Low priority but adds noise.
- qwen3:8b shows significant variance on complex Go files (P5 needed 4 attempts; first 3 timed out at 300s). Timeout tuning may help but is a separate concern.

---

## What Needs to Be Built

### 1. `internal/ollama/client.go` — add `Chat()`

Add a `/api/chat` call that supports tool definitions and returns the assistant message (with `tool_calls` populated):

```go
type Message struct {
    Role      string     `json:"role"`
    Content   string     `json:"content"`
    ToolCalls []ToolCall `json:"tool_calls,omitempty"`
}
type ToolCall struct {
    Function struct {
        Name      string         `json:"name"`
        Arguments map[string]any `json:"arguments"`
    } `json:"function"`
}
func Chat(model string, messages []Message, tools []ToolDef, timeout time.Duration) (Message, error)
```

Uses `POST /api/chat` with `"stream": false`. Timeout passed per call (planner vs writer have different budgets).

---

### 2. New `internal/agent/tools.go` — four tool implementations

| Tool | What it does | Complexity |
|------|-------------|------------|
| `Write(path, content)` | `os.WriteFile` + `os.MkdirAll` | trivial |
| `Edit(path, old, new)` | read → strings.Replace (once) → write | simple |
| `Bash(command)` | `exec.Command("bash", "-c", cmd)`, capture stdout+stderr, return combined | moderate |
| `Read(path)` | `os.ReadFile` → string | trivial |

Tool schemas (JSON Schema format) are passed as `tools` in the `/api/chat` request so the model knows how to call them.

---

### 3. New `internal/agent/session.go` — message history and run loop

```go
type Session struct {
    Messages []ollama.Message // grows with each turn
}

// Run sends systemPrompt+userPrompt, dispatches tool calls, loops until:
//   - no more tool calls (agent stopped)
//   - watchFile exists (early exit)
//   - timeout exceeded
//   - maxTurns reached
func (s *Session) Run(model, systemPrompt, userPrompt string, tools []ToolDef, maxTurns int, watchFile string, timeout time.Duration) (bool, error)
```

The loop:
```
append(system, user) → Chat() → if tool_calls: dispatch → append tool result → loop
                               → if no tool_calls: done
                               → if watchFile exists: early exit
```

For repair, pass the same `*Session` (preserves prior message history). For fresh writes, create `new(Session)`.

**Thinking mode:** qwen3:8b uses `/no_think` and `/think` tokens appended to the user message:
- `thinking=off` → append `\n/no_think`
- `thinking=medium` → append `\n/think`
- (omitting the token lets the model decide)

---

### 4. New `./skills/` — skill files in the mu repo

Skills move from `~/Projects/dotfiles/pi/agent/skills/` (external dotfiles repo) into `./skills/` directly inside the mu repo:

```
skills/
  task-planner/
    SKILL.md
```

Edit skills directly in the repo. No install step, no dotfiles roundtrip.

At build time the `skills/` tree is embedded into the binary via `//go:embed`:

```go
// internal/agent/skills.go
import "embed"

//go:embed ../../skills
var skillsFS embed.FS

func LoadSkill(name string) string {
    data, err := skillsFS.ReadFile("skills/" + name + "/SKILL.md")
    if err != nil {
        return ""
    }
    return string(data)
}
```

The binary carries skills without any runtime path dependency. `loadSkill()` in `agent.go` is replaced by `agent.LoadSkill()`.

---

### 5. `internal/subcommands/agent.go` — replace subprocess calls

Four call sites to replace:

| Function | Replaced by |
|----------|------------|
| `runPlanner` | `session.Run(model, systemPrompt+skillContent, plannerPrompt, tools, 1, "PLAN.md", plannerTimeout)` |
| `runCombinedPlanner` | same, watch for `PLAN.md` then first source file |
| `runWriterWithSession` | `session.Run(...)` watching `targetFile`, pass session for reuse on repair |
| `runRepair` / `runRepairLint` | reuse existing `*Session` (history preserved) |

Remove: `runBackground()`, `runBackgroundCombined()`, `killProcess()` — all process management helpers that become unnecessary.

Keep unchanged: `detectComplexity()`, `ensureAgentModel()`, `patchTemplate()`, `buildAutonomousSystem()`, `buildPlannerPrompt()`, `buildWritePrompt()`, all lint/test-gate logic. Replace `loadSkill()` call with `agent.LoadSkill()`.

---

### 6. `internal/subcommands/run.go` — delete

`mu run` was a pure pi passthrough (syscall.Exec). With pi gone it has no function. Delete the file and remove the `run` command registration from `cmd/mu/main.go`.

---

### 7. `internal/subcommands/check.go` — remove pi, remove node/npm

Drop pi from the deps list. Also drop node and npm — they were only needed to install pi. Keep ollama. Remove the pi install hint from the footer message.

---

### 8. Secondary: `CheckGoalAlignment` noise cleanup

In `internal/plan/parse.go`, tighten the word list used for goal alignment checks. Skip words under 5 chars and common task-description verbs (`write`, `using`, `create`, `show`, `include`, `returns`, `support`, `runs`, `provide`, `print`, `build`, `makes`). This reduces false-positive NOTEs on every dojo run.

---

## Files to Create / Modify

- **Create** `skills/task-planner/SKILL.md` — move from `~/Projects/dotfiles/pi/agent/skills/task-planner/SKILL.md`
- **Modify** `internal/ollama/client.go` — add `Chat()`, `Message`, `ToolCall`, `ToolDef` types
- **Create** `internal/agent/tools.go` — Write/Edit/Bash/Read implementations + JSON schemas
- **Create** `internal/agent/session.go` — `Session` struct and `Run()` loop
- **Create** `internal/agent/skills.go` — `//go:embed` FS + `LoadSkill()` function
- **Modify** `internal/subcommands/agent.go` — replace all subprocess calls with `session.Run()`; replace `loadSkill()` with `agent.LoadSkill()`
- **Delete** `internal/subcommands/run.go`
- **Modify** `internal/subcommands/check.go` — remove pi, node, npm from deps list
- **Modify** `cmd/mu/main.go` — remove `run` command registration
- **Modify** `internal/plan/parse.go` — tighten `CheckGoalAlignment` word list (secondary)

---

## What to Preserve / Reuse

- All of `internal/plan/` — unchanged
- `detectComplexity()` — drives timeouts (same values)
- `ensureAgentModel()` / `patchTemplate()` — still creates `:ralph` Ollama model variant
- `buildAutonomousSystem()` / `buildPlannerPrompt()` / `buildWritePrompt()` — become system/user message content directly
- `agent.LoadSkill()` — replaces `loadSkill()`; reads from embedded `skills/` FS compiled into the binary
- All lint/repair/test-gate logic in `agent.go` — unchanged, only the subprocess calls swap out

---

## Verification

1. `go build ./...` — no compile errors
2. `mu agent "write hello world in Python"` — produces `PLAN.md` + `main.py` without spawning any subprocess except tool calls
3. `mu agent "write a Flask REST API for todos with pytest"` — exercises repair loop and `FixPythonMakefileTest`
4. `mu check` — no pi or node entries; passes cleanly with only ollama required in AI backend
5. `mu run` — command no longer exists; `mu --help` does not list it
6. Dojo run: all 7 problems pass (P7 Flask works via PYTHONPATH fix already in place)
