# Practice

## Setup

1. Create a working folder: `./dojo/<yourname>-<date>` (e.g. `./dojo/agentname-2026-05-17`)
2. Write all output and findings there

## Workflow

For each problem below:

1. Run it with `mu agent`
2. Inspect the session logs in `~/.mu`
3. Identify weaknesses in the agent
4. Improve the agent code (Go source in this directory) **and/or** the pi skills it relies on
5. Record findings in your dojo folder

### What you can improve

**Agent code** (`internal/` — Go source): orchestration logic, timeouts, plan validation,
prompt construction, complexity detection, test normalization.

**pi SKILLS** (`~/.pi/agent/skills/`): the skill files that shape how the underlying LLM
behaves during planning and writing. When you find the model consistently making the same
mistake, a skill-level fix is often more durable than a prompt patch in Go.

To improve a skill:
1. Edit it directly in `~/Projects/dotfiles/pi/agent/skills/<name>/SKILL.md`
2. Reload into `~/.pi/agent/skills/` with:
   ```sh
   make -C ~/Projects/dotfiles install-skills
   ```
3. Describe the change and its rationale in `findings.md`

Skills in `~/Projects/dotfiles/pi/agent/skills/` are the canonical source.
`~/.pi/agent/skills/` is the installed copy — always edit the dotfiles source and reinstall.

**Skills must work without mu agent.** A human should be able to run `pi` standalone
and invoke any skill without the mu agent wrapper. Keep skills self-contained.

## Standards

- Code must be readable by humans
- The best solution includes an automated test that proves the problem is solved
- A good agent generates code fast

## Problems

**Trivial** — single file, no libraries:
```
write helloworld
```

**Simple** — standard library, single file:
```
write a python program that writes a todo entry to a sqlite3 database with a table that contains a list of todos. Create the todo table in the sqlite3 database via python. Show that the inserted entry can be read again.
```

**Moderate** — external library + Makefile:
```
render a line on screen via SDL2. Use sdl2-config in the Makefile to set up SDL2 libs.
```

**Moderate** — multi-file project structure:
```
write the fibonacci sequence using C#. Use the dotnet command to compile C#.
```
