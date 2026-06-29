# Language servers (LSP) — VSCode-style repair

mu can drive **language servers** as a repair oracle, the same engine VSCode uses. A server
gives structured diagnostics with exact ranges and — the part regex reflexes can't do —
**code actions** the server authors itself: add a missing `#include`, organize imports, import
a symbol, fix a signature. Implemented in [`src/mu/lsp.py`](../src/mu/lsp.py).

## Repair, not generation

LSP has no LLM, so it does **not** generate code from a goal. Its role is **repair** — a
deterministic, language-aware fixer that *complements* the model (and the regex reflexes),
not replaces it. In the agent it runs right after each file is written (`_apply_lsp_repair`,
behind `MU_LSP=1`), applying:

- `source.organizeImports` — goimports-style add-missing / remove-unused (the big win; works
  for every package, not the fixed set a regex reflex hard-codes);
- `quickfix` actions bound to error diagnostics (clangd "add include", trait imports, …);
- command-based assists (the server applies the edit via `workspace/applyEdit`).

It is **default ON** (fast servers only) and degrades to a no-op when no server is installed — never
blocks a run. Set `MU_LSP=0` to disable.

## Usage

```
mu lsp langs            # which servers are installed
mu lsp diagnose FILE    # show the server's diagnostics
mu lsp fix FILE         # apply quick-fixes / organizeImports
mu agent …              # repair loop, fast proven servers by default (clangd, gopls)
MU_LSP=0 mu agent …    # disable LSP repair
MU_LSP=all mu agent …  # also the slow/experimental servers (rust-analyzer, ts, roslyn)
```

The default (`MU_LSP` unset or `MU_LSP=1`) is deliberately limited to the fast, validated servers so it can't regress a run by
spawning a slow server that returns nothing (the p8 lesson). `MU_LSP=all` opts into the rest.

## Coverage & install (no sudo)

`mu setup` installs servers **per-user, without sudo**: `rustup component add rust-analyzer`,
`go install … gopls`, the Roslyn C# server (downloaded + extracted to `~/.local/share/roslyn-lsp`),
and npm servers under `--prefix ~/.local`. `toolchain.prepend_tool_paths` adds `~/go/bin`,
`~/.local/bin`, `~/.dotnet/tools` so they resolve at runtime.

| language | server | status |
|---|---|---|
| C / C++ | clangd | **works** — add-include verified (e.g. `#include <stdio.h>`), ~0.7s |
| Go | gopls | **works** — `organizeImports` auto-adds `fmt`/`net/http`, build passes |
| Python | pyright | installable (`pip install pyright`) |
| TS / JS | typescript-language-server | installable |
| Rust | rust-analyzer | starts + diagnoses; import assists need fuller capability negotiation to apply |
| C# | **Roslyn** (`Microsoft.CodeAnalysis.LanguageServer`, net10) | **works** — add-using verified (`using System.Collections.Generic;` fixes CS0246, diagnostics clear); ~7s/file (project load ⇒ `MU_LSP=all`). Replaces csharp-ls, which SIGABRTs on .NET 10. Needs the project-load handshake + **pull** diagnostics (`textDocument/diagnostic`), both in `lsp.py`. |

> **Safety:** a server returns several *mutually-exclusive* fixes for one diagnostic (add
> using X, OR generate a class, OR qualify), each with edits relative to the *original* file.
> `repair()` applies **one** action per round and re-diagnoses — applying several at once
> scrambles the file (the old csharp-ls corrupted a file into garbage before this was enforced).

## Empirical (dark dojo trials, qwen-7b, 2026-06-26)

- **p3-sdl2 (clangd):** 5/6 vs 85% baseline — no headroom, **no regression**; LSP fired 5/6.
- **p5-gin (gopls):** 6/8 (75%) vs 71% baseline, **repair-iters 0.8** — `organizeImports`
  fixes missing imports proactively, so the model needs far fewer repair rounds (efficiency
  win; pass-rate flat because the regex go-import reflex already covered common cases).
- **p8-node-todo (ts-server):** 2/8 vs 18/41 (44%) baseline, **LSP fired 0** — ts-server's
  project load exceeded the (then 3s) settle window, so it produced no fixes and only added
  per-file spawn overhead; the drop is variance + that overhead. Settle raised to 8s so it can
  fire, but **LSP is not a universal lift** — running a slow server that returns nothing is
  net-negative. (Plain-JS `require` is also not auto-importable the way Go/TS modules are.)

**Takeaway:** LSP is a sound repair lever **where a fast server meets an import/include-shaped
failure** (clangd, gopls) — strictly more general than per-pattern regex reflexes there. It is
*not* a blanket win: slow-to-start servers (rust-analyzer, ts-server) or non-import failures
add overhead for no benefit. Enable it selectively, not everywhere.

## Relation to scaffolding (parked)

Scaffolding (`MU_SCAFFOLD`) clears the .NET restore wall by construction but the p10/p13
ladder showed the binding constraint there is the **model**, not structure — it banks no
pass-rate lift, so it stays **opt-in / default-off** ([ablations.md](ablations.md)). LSP is
the preferred repair-side approach for languages with a server. For C# specifically, the Roslyn server
is the natural next step (replacing the .NET reflex stack with server diagnostics) once it is
installed and the capability gaps above are closed.
