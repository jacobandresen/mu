# Practice

## Dojo run 

0. Clean the ./dojo folder
1. Run ./sit.sh  
2. Inspect the logs ./dojo
3. Inspect the session logs in `~/.mu`
4. Identify weaknesses in the agent
5. Implement changes to improve the agent code and the skills it relies on
6. Bump the mu version.
8. Commit your changes with reference to the mu version
7. Record where to push next in DOJO.md 

### What you can improve

**Agent code** (`src/mu/` — Python source): orchestration logic, timeouts, plan validation,
prompt construction, complexity detection, test normalization.

**Skills** (`src/mu/skills/` — Markdown, packaged as data): the skill files that shape how
the underlying LLM behaves during planning and writing. When you find the model consistently
making the same mistake, a skill-level fix is often more durable than a code change.

To improve a skill:
1. Edit it directly in `src/mu/skills/<name>/SKILL.md` in this repo
2. No rebuild needed with an editable install — skills are read at runtime via `importlib.resources`
3. Describe the change and its rationale in `findings.md`

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

**Moderate** — Go HTTP server with external framework:
```
write a Go HTTP server with a GET /ping endpoint that returns JSON {"status":"ok"}. Use the Gin framework. Include a Makefile.
```

**Moderate** — Rust CLI with cargo:
```
write a Rust command-line program that prints the first 10 Fibonacci numbers. Use cargo to build and run.
```

**Hard** — multi-dependency REST API with tests:
```
write a Python REST API using Flask with a SQLite backend. Support POST /todos (body: JSON with a "task" field) and GET /todos (returns list of todos). Include a pytest test file that tests both endpoints. Provide a Makefile that installs dependencies with pip and runs pytest.
```
