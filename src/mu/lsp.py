"""Minimal Language Server Protocol client — VSCode-style diagnostics + quick-fixes.

mu already uses the compiler/linter as a diagnostic oracle (``diagnose``, the lint gate).
A language server is a *richer* oracle: structured diagnostics with exact ranges, and —
the part regex reflexes can't do — server-authored **code actions** (quick-fixes: add a
missing ``#include``, import a trait, fix a signature). This module speaks just enough LSP
to (1) get diagnostics for a file and (2) apply the server's ``quickfix`` code actions.

It does **not** generate code from a goal — LSP has no LLM; "generation" support is limited
to completion/code-actions. So the honest role here is **repair**: a deterministic,
language-aware fixer that complements the reflexes and feeds precise diagnostics to the model.

Servers are used only when actually installed (``shutil.which``); everything degrades to a
no-op otherwise, so this never blocks a run. Opt-in via ``MU_LSP=1`` for the agent path; the
``mu lsp`` CLI exercises it directly.
"""
from __future__ import annotations

import json
import os
import re
import select
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional


# Extension → server argv. Only servers that exist on PATH are used (see server_for).
_CLANGD = ["clangd", "--background-index=false", "--log=error"]
_SERVERS: dict[str, list[str]] = {
    ".c": _CLANGD, ".h": _CLANGD, ".cpp": _CLANGD, ".cc": _CLANGD, ".hpp": _CLANGD,
    ".rs": ["rust-analyzer"],
    ".go": ["gopls"],
    ".py": ["pyright-langserver", "--stdio"],
    ".ts": ["typescript-language-server", "--stdio"],
    ".tsx": ["typescript-language-server", "--stdio"],
    ".js": ["typescript-language-server", "--stdio"],
    ".jsx": ["typescript-language-server", "--stdio"],
    ".vue": ["vue-language-server", "--stdio"],
    ".cs": ["csharp-ls"],
}


# How long to wait for a server to publish diagnostics after didOpen. Fast single-file
# servers (clangd) settle in <1s; project-indexing servers (rust-analyzer runs `cargo
# check`, gopls/csharp-ls load the module) need much longer or they no-op (rust-analyzer
# returned nothing within 3s on p6).
_SETTLE: dict[str, float] = {"rust-analyzer": 15.0, "gopls": 8.0, "csharp-ls": 12.0,
                             "typescript-language-server": 8.0}


# Servers fast + reliable enough to enable by default (MU_LSP=1). Slow-to-start servers
# whose fixes are unproven here (rust-analyzer, ts/csharp) only run under MU_LSP=all, so the
# default can't regress a run by spawning a slow server that returns nothing (see p8 trial).
FAST_SERVERS = {"clangd", "gopls"}


def _settle_for(cmd: list[str]) -> float:
    return _SETTLE.get(cmd[0], 3.0)


def server_for(path: str) -> Optional[list[str]]:
    """The installed server argv for ``path``'s language, or None."""
    cmd = _SERVERS.get(Path(path).suffix.lower())
    if cmd and shutil.which(cmd[0]):
        return cmd
    return None


def available_languages() -> dict[str, str]:
    """Map of extension → server binary, for those installed (for `mu lsp`/diagnostics)."""
    out = {}
    for ext, cmd in _SERVERS.items():
        if shutil.which(cmd[0]):
            out[ext] = cmd[0]
    return out


def _uri(path: str) -> str:
    return Path(path).resolve().as_uri()


def _frame(obj: dict) -> bytes:
    body = json.dumps(obj).encode("utf-8")
    return b"Content-Length: %d\r\n\r\n%s" % (len(body), body)


class LspClient:
    """A tiny synchronous LSP client over a server's stdio. One server per instance."""

    def __init__(self, cmd: list[str], root: str):
        self.cmd = cmd
        self.root = str(Path(root).resolve())
        self.proc: Optional[subprocess.Popen] = None
        self._id = 0
        self.diagnostics: dict[str, list] = {}
        self._edited = False   # set when the server applies an edit via workspace/applyEdit

    # ── framing ────────────────────────────────────────────────────────────────
    def _read_exact(self, n: int, deadline: float) -> Optional[bytes]:
        """Read exactly ``n`` bytes from the server, honoring ``deadline`` via select."""
        out = self.proc.stdout
        buf = b""
        while len(buf) < n:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            r, _, _ = select.select([out], [], [], remaining)
            if not r:
                return None
            chunk = out.read(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _read_message(self, deadline: float) -> Optional[dict]:
        assert self.proc and self.proc.stdout
        # headers terminate at \r\n\r\n; read byte-wise (headers are tiny) under the deadline
        header = b""
        while b"\r\n\r\n" not in header:
            b = self._read_exact(1, deadline)
            if b is None:
                return None
            header += b
            if len(header) > 8192:
                return None
        m = re.search(rb"Content-Length:\s*(\d+)", header, re.IGNORECASE)
        if not m:
            return None
        body = self._read_exact(int(m.group(1)), deadline)
        if body is None:
            return None
        try:
            return json.loads(body)
        except Exception:
            return None

    def _send(self, obj: dict) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(_frame(obj))
        self.proc.stdin.flush()

    # ── rpc ───────────────────────────────────────────────────────────────────
    def _notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: dict, timeout: float = 15.0):
        self._id += 1
        rid = self._id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self._read_message(deadline)
            if msg is None:
                break
            self._dispatch(msg)
            if msg.get("id") == rid and ("result" in msg or "error" in msg):
                return msg.get("result")
        return None

    def _dispatch(self, msg: dict) -> None:
        if msg.get("method") == "textDocument/publishDiagnostics":
            p = msg.get("params", {})
            self.diagnostics[p.get("uri", "")] = p.get("diagnostics", [])
        # Many assists (rust-analyzer imports, some gopls/ts fixes) deliver their edit via a
        # server→client workspace/applyEdit request after executeCommand — apply it here.
        elif msg.get("method") == "workspace/applyEdit":
            ok = _apply_workspace_edit(msg.get("params", {}).get("edit", {}))
            self._edited = self._edited or ok
            self._send({"jsonrpc": "2.0", "id": msg.get("id"), "result": {"applied": ok}})
        # server→client requests we must answer to stay live
        elif msg.get("method") == "workspace/configuration":
            self._send({"jsonrpc": "2.0", "id": msg.get("id"),
                        "result": [{} for _ in msg.get("params", {}).get("items", [])]})
        elif msg.get("method") in ("client/registerCapability", "window/workDoneProgress/create"):
            self._send({"jsonrpc": "2.0", "id": msg.get("id"), "result": None})

    # ── lifecycle ───────────────────────────────────────────────────────────────
    def start(self) -> bool:
        try:
            self.proc = subprocess.Popen(
                self.cmd, cwd=self.root, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        except Exception:
            return False
        init = self._request("initialize", {
            "processId": os.getpid(),
            "rootUri": Path(self.root).as_uri(),
            "capabilities": {
                "textDocument": {
                    "publishDiagnostics": {"relatedInformation": True},
                    "codeAction": {"codeActionLiteralSupport": {
                        "codeActionKind": {"valueSet": ["quickfix", "source"]}}},
                },
                "workspace": {"applyEdit": True, "workspaceEdit": {"documentChanges": True}},
            },
        }, timeout=20.0)
        if init is None:
            self.stop()
            return False
        self._notify("initialized", {})
        return True

    def stop(self) -> None:
        if not self.proc:
            return
        try:
            self._request("shutdown", {}, timeout=3.0)
            self._notify("exit", {})
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None

    # ── document ops ─────────────────────────────────────────────────────────────
    def _lang_id(self, path: str) -> str:
        return {".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
                ".rs": "rust", ".go": "go", ".py": "python",
                ".ts": "typescript", ".tsx": "typescriptreact",
                ".js": "javascript", ".jsx": "javascriptreact",
                ".vue": "vue", ".cs": "csharp"}.get(Path(path).suffix.lower(), "plaintext")

    def open(self, path: str, settle: float = 3.0) -> list:
        """didOpen ``path`` and collect the diagnostics the server pushes back."""
        uri = _uri(path)
        text = Path(path).read_text(errors="replace")
        self._notify("textDocument/didOpen", {"textDocument": {
            "uri": uri, "languageId": self._lang_id(path), "version": 1, "text": text}})
        # diagnostics arrive asynchronously after analysis — pump until they land or settle.
        deadline = time.time() + settle
        while time.time() < deadline:
            msg = self._read_message(deadline)
            if msg is None:
                break
            self._dispatch(msg)
            # Only stop once we have *non-empty* diagnostics: project-indexing servers
            # (rust-analyzer) publish an empty batch on open and the real ones after
            # `cargo check`, so breaking on the first (empty) batch returns nothing.
            if self.diagnostics.get(uri):
                extra = time.time() + 0.4
                while time.time() < extra:
                    m2 = self._read_message(extra)
                    if m2 is None:
                        break
                    self._dispatch(m2)
                break
        return self.diagnostics.get(uri, [])

    def code_actions(self, path: str, diagnostics: list) -> list:
        uri = _uri(path)
        if not diagnostics:
            return []
        rng = diagnostics[0].get("range")
        res = self._request("textDocument/codeAction", {
            "textDocument": {"uri": uri},
            "range": rng,
            "context": {"diagnostics": diagnostics, "only": ["quickfix"]},
        }) or []
        return res

    def source_actions(self, path: str, kind: str) -> list:
        """Whole-file `source` code actions (e.g. ``source.organizeImports`` —
        goimports-style add-missing/remove-unused for Go/TS, the highest-value LSP
        repair). Not tied to a diagnostic, so requested over the whole document."""
        uri = _uri(path)
        nlines = Path(path).read_text(errors="replace").count("\n") + 1
        res = self._request("textDocument/codeAction", {
            "textDocument": {"uri": uri},
            "range": {"start": {"line": 0, "character": 0},
                      "end": {"line": nlines, "character": 0}},
            "context": {"diagnostics": [], "only": [kind]},
        }) or []
        return res

    def resolve(self, action: dict) -> dict:
        """Resolve a code action that defers its edit (codeAction/resolve)."""
        if action.get("edit") or "data" not in action:
            return action
        return self._request("codeAction/resolve", action) or action

    def execute_command(self, command: dict) -> bool:
        """Run a code action's command; the server applies its edit via workspace/applyEdit
        (handled in _dispatch). Returns True if any edit landed."""
        if not command or "command" not in command:
            return False
        self._edited = False
        self._request("workspace/executeCommand", {
            "command": command["command"], "arguments": command.get("arguments", [])})
        return self._edited


def _apply_workspace_edit(edit: dict) -> bool:
    """Apply a WorkspaceEdit (changes or documentChanges) to disk. Returns True if any."""
    changed = False
    changes = edit.get("changes") or {}
    docs = edit.get("documentChanges") or []
    items = list(changes.items())
    for dc in docs:
        if "textDocument" in dc and "edits" in dc:
            items.append((dc["textDocument"]["uri"], dc["edits"]))
    for uri, edits in items:
        path = Path(uri.replace("file://", ""))
        try:
            text = path.read_text()
        except OSError:
            continue
        new = _apply_text_edits(text, edits)
        if new != text:
            path.write_text(new)
            changed = True
    return changed


def _apply_text_edits(text: str, edits: list) -> str:
    """Apply LSP TextEdits (line/char ranges) to ``text``. Edits applied bottom-up."""
    lines = text.splitlines(keepends=True)

    def off(pos):
        ln, ch = pos["line"], pos["character"]
        return sum(len(l) for l in lines[:ln]) + ch

    spans = sorted(((off(e["range"]["start"]), off(e["range"]["end"]), e["newText"])
                    for e in edits), key=lambda x: x[0], reverse=True)
    for s, e, nt in spans:
        text = text[:s] + nt + text[e:]
    return text


def _summarize(diags: list) -> str:
    sev = {1: "error", 2: "warn", 3: "info", 4: "hint"}
    out = []
    for d in diags:
        r = d.get("range", {}).get("start", {})
        out.append(f"  {sev.get(d.get('severity'),'?'):5} {r.get('line',0)+1}:{r.get('character',0)+1} "
                   f"[{d.get('code','')}] {d.get('message','').splitlines()[0][:90]}")
    return "\n".join(out)


def diagnose(path: str) -> list:
    """Return the server's diagnostics for ``path`` (empty if no server / unavailable)."""
    cmd = server_for(path)
    if not cmd:
        return []
    client = LspClient(cmd, str(Path(path).parent))
    if not client.start():
        return []
    try:
        return client.open(path, settle=_settle_for(cmd))
    finally:
        client.stop()


def _apply_actions(client: "LspClient", actions: list) -> bool:
    applied = False
    for a in actions:
        if not isinstance(a, dict):
            continue
        a = client.resolve(a)
        edit = a.get("edit")
        if edit and _apply_workspace_edit(edit):
            applied = True
        # Command-based assist (no inline edit): execute it; the server applies via
        # workspace/applyEdit. ``command`` may be a Command object or a bare string.
        cmd = a.get("command")
        if cmd and not edit:
            cmd_obj = cmd if isinstance(cmd, dict) else {"command": cmd, "arguments": a.get("arguments", [])}
            if client.execute_command(cmd_obj):
                applied = True
    return applied


def repair(path: str, max_rounds: int = 3) -> bool:
    """Apply the server's code actions to ``path`` until clean or no progress.

    Two complementary fixers: (1) ``source.organizeImports`` — the goimports-style
    add-missing/remove-unused pass (the big win for Go/TS/Rust), run every round; and
    (2) ``quickfix`` actions bound to error diagnostics (clangd "add include",
    rust-analyzer trait imports, signature fixes). Returns True if any edit was applied.
    """
    cmd = server_for(path)
    if not cmd:
        return False
    client = LspClient(cmd, str(Path(path).parent))
    if not client.start():
        return False
    settle = _settle_for(cmd)
    any_fix = False
    try:
        for _ in range(max_rounds):
            diags = client.open(path, settle=settle)
            applied = _apply_actions(client, client.source_actions(path, "source.organizeImports"))
            errs = [d for d in diags if d.get("severity") == 1]
            if errs:
                applied = _apply_actions(client, client.code_actions(path, errs)) or applied
            any_fix = any_fix or applied
            client.diagnostics.clear()
            if not applied:
                break
    finally:
        client.stop()
    return any_fix


def cli(args) -> int:
    """`mu lsp <diagnose|fix> <file>` — exercise the client directly."""
    if not args or args[0] not in ("diagnose", "fix", "langs") or (
            args[0] in ("diagnose", "fix") and len(args) < 2):
        print("usage: mu lsp <diagnose|fix|langs> [file]")
        return 2
    if args[0] == "langs":
        langs = available_languages()
        print("installed language servers:" if langs else "no language servers installed")
        for ext, srv in sorted(langs.items()):
            print(f"  {ext} -> {srv}")
        return 0
    path = args[1]
    if server_for(path) is None:
        print(f"no installed language server for {path}")
        return 1
    if args[0] == "diagnose":
        diags = diagnose(path)
        print(f"{len(diags)} diagnostic(s) for {path}:")
        print(_summarize(diags))
        return 0
    before = len(diagnose(path))
    changed = repair(path)
    after = len(diagnose(path))
    print(f"lsp fix {path}: applied={changed}  diagnostics {before} -> {after}")
    return 0
