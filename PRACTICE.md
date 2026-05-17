# Practice

You are a master coding agent. Run the problems below with `mu agent`. Then inspect the session logs in `~/.mu`, identify weaknesses, and improve the agent code.

## Problems

**Trivial** — single file, no libraries:
```
mu agent --dir /tmp/mu/helloworld "write helloworld"
```

**Moderate** — external library + Makefile:
```
mu agent --dir /tmp/mu/line "render a line on screen via SDL2. Use sdl2-config in the Makefile to setup SDL2 libs"
```

**Moderate** — multi-file project structure:
```
mu agent --dir /tmp/mu/fibonacci "write the fibonacci sequence using c#. Use the dotnet command to compile c#"
```

**Simple** — standard library, single file:
```
mu agent --dir /tmp/mu/pythondata "write a python program that writes a todo entry to a sqlite3 database with table that contains a list of todos. create the todo table in the sqlite3 database via python. Show that the inserted entry can be read again"
```
