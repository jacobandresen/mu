"""HTTP client for the LM Studio OpenAI-compatible API."""

import itertools
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Optional


def _default_host() -> str:
    """Resolve the API host: env var > config file > default."""
    if h := os.environ.get("MU_LMSTUDIO_HOST"):
        return h
    try:
        from pathlib import Path
        p = Path.home() / ".mu" / "config.json"
        if p.exists():
            cfg = json.loads(p.read_text(encoding="utf-8"))
            if h := cfg.get("host"):
                return h
    except Exception:
        pass
    return "http://localhost:1234"


LMS_HOST = _default_host()
# Context window sent per-request so the API setting overrides whatever LM Studio
# UI value is loaded. Default 6000: fits Q4_K_M + system overhead on M2 8 GB
# without triggering swap (8192 causes 6x slowdown — see docs/MODELS.md Tuning).
_NUM_CTX = int(os.environ.get("MU_NUM_CTX", "6000"))

# Anti-degeneration: small models at near-greedy temperature with no repetition
# penalty fall into token loops — e.g. a writer emitting
# `print(f"{task[print(f"{task[…` and corrupting the whole file. llama.cpp's
# windowed repeat penalty (repeat_last_n=64) is the surgical fix: it dampens
# tight loops without punishing the legitimate distant repetition that real code
# is full of (indentation, `self.`, dict keys), the way a global frequency
# penalty would. 1.1 is llama.cpp's well-tested default; set MU_REPEAT_PENALTY=1.0
# to disable.
_REPEAT_PENALTY = float(os.environ.get("MU_REPEAT_PENALTY", "1.1"))

# Reproducibility for measurement runs. By default unset → the server samples
# freely (different output each run), which is what you want to surface diverse
# failures. Set MU_SEED to a fixed integer to pin llama.cpp's RNG so the same
# input yields the same output — used with temperature 0 for clean A/B testing
# of a deterministic change. A seed only makes runs reproducible when the input
# is identical; a prompt change still alters the token stream.
_SEED = os.environ.get("MU_SEED")


def normalize_model_bare(name: str) -> str:
    """Normalize a model ID to a bare name for loose equality checks.

    Strips the org/path prefix, the ``.gguf`` extension, and any GGUF
    quantization suffix (e.g. ``-Q3_K_L``, ``-Q4_K_M``, ``-F16``).
    The result is lowercased so comparisons are case-insensitive.

    LM Studio assigns a short "display" identifier when it loads a GGUF
    (e.g. ``devstral-small-2-24b-instruct-2512``) that omits the
    quantization suffix present in the filename, so a direct string
    comparison between the requested path and the loaded identifier fails.
    This function normalises both sides to the same base name.
    """
    name = name.split('/')[-1].split('@')[0].lower()
    if name.endswith('.gguf'):
        name = name[:-5]
    # Strip GGUF quantization suffixes: -q4_k_m, -q3_k_l, -f16, -bf16, -iq2_xxs …
    name = re.sub(r'[-_](q[0-9]|f16|bf16|iq[0-9]).*$', '', name)
    return name


@dataclass
class ChatStats:
    prompt_tokens: int = 0
    generated_tokens: int = 0


# ---------------------------------------------------------------------------
# Per-session token log
# ---------------------------------------------------------------------------
# Records one entry per chat() call. Cleared by flush_token_log() which is
# called from AgentSession.finalize so each session gets its own snapshot.

_token_log: list[dict] = []
_chat_phase: str = ''
_chat_task: str = ''


def set_chat_context(phase: str, task_file: str = '') -> None:
    """Tag subsequent chat() calls with a phase label and optional task file.

    Call this before each logical phase boundary (planner, writer, repair …)
    so the token log can break down usage by phase.
    """
    global _chat_phase, _chat_task
    _chat_phase = phase
    _chat_task = task_file


def flush_token_log() -> list[dict]:
    """Return and clear the accumulated token log for this session."""
    global _token_log
    out, _token_log = _token_log, []
    return out


# ---------------------------------------------------------------------------
# Per-session chat transcript
# ---------------------------------------------------------------------------
# One entry per chat() call: what the model was asked and what it replied,
# truncated. The token log answers "how much"; this answers "what" — without
# it a failed session's archive can show a bad file on disk but not the
# response that produced it. Flushed by AgentSession.finalize.

_transcript: list[dict] = []
_TRANSCRIPT_TRUNC = 4000  # chars per captured field


def _trunc(s: Optional[str], limit: int = _TRANSCRIPT_TRUNC) -> str:
    s = s or ''
    if len(s) <= limit:
        return s
    return s[:limit] + f'…[truncated, {len(s)} chars total]'


def _record_transcript(messages: list[dict], msg: Optional[dict],
                       error: str = '') -> None:
    entry: dict = {
        'phase': _chat_phase,
        'task_file': _chat_task,
        'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        # The last message is the live instruction (the rest is mostly stable
        # system/header content already visible in earlier entries).
        'last_message': _trunc(str((messages or [{}])[-1].get('content', ''))),
        'n_messages': len(messages or []),
    }
    if error:
        entry['error'] = _trunc(error, 600)
    if msg is not None:
        entry['response'] = _trunc(str(msg.get('content') or ''))
        calls = []
        for tc in msg.get('tool_calls') or []:
            fn = tc.get('function', {})
            calls.append({'name': fn.get('name', ''),
                          'arguments': _trunc(str(fn.get('arguments', '')))})
        if calls:
            entry['tool_calls'] = calls
    _transcript.append(entry)


def flush_transcript() -> list[dict]:
    """Return and clear the accumulated chat transcript for this session."""
    global _transcript
    out, _transcript = _transcript, []
    return out


def is_running() -> bool:
    try:
        import httpx
        return httpx.get(f"{LMS_HOST}/v1/models", timeout=5.0).status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        import httpx
        r = httpx.get(f"{LMS_HOST}/v1/models", timeout=5.0)
        r.raise_for_status()
        return [m['id'] for m in r.json().get('data', [])]
    except Exception:
        return []


def _lms_client():
    """Return an lmstudio.Client pointed at the auto-discovered local API host."""
    import lmstudio
    c = lmstudio.Client()
    host = c.find_default_local_api_host()
    return lmstudio.Client(host)


def list_downloaded_llm_paths() -> list[str]:
    """Paths of LLM models downloaded to LM Studio (not necessarily loaded).

    Returns paths in the same format as catalog IDs (e.g. ``google/gemma-4-e4b``).
    Returns [] on error or if the SDK is unavailable.
    """
    try:
        c = _lms_client()
        return [
            m.path
            for m in c.list_downloaded_models()
            if getattr(m, 'type', '') != 'embedding' and getattr(m, 'path', '')
        ]
    except Exception:
        return []


def _catalog_path():
    import os
    from pathlib import Path
    default = Path(__file__).parent.parent.parent / 'models-catalog.json'
    return Path(os.environ.get('MU_MODELS_CATALOG', '') or default)


def load_catalog() -> list[dict]:
    """Curated model specs shipped alongside the package."""
    try:
        return json.loads(_catalog_path().read_text(encoding='utf-8')).get('models', [])
    except Exception:
        return []


def load_catalog_tiers() -> dict:
    """Tier definitions (minRamGb thresholds) from models-catalog.json.

    Returns a dict like {"8gb": {"minRamGb": 0}, "16gb": {"minRamGb": 14}, ...}.
    Falls back to sane defaults if the catalog is missing or malformed.
    """
    try:
        return json.loads(_catalog_path().read_text(encoding='utf-8')).get('tiers', {})
    except Exception:
        return {"8gb": {"minRamGb": 0}, "16gb": {"minRamGb": 14}, "32gb": {"minRamGb": 30}}


def _vram_gb() -> float:
    """Best-effort GPU VRAM in GiB; 0.0 if it can't be determined."""
    import platform
    import subprocess
    if platform.system() == 'Darwin':
        # Apple Silicon uses unified memory — the GPU draws on system RAM.
        return _ram_gb()
    try:
        out = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
            text=True, stderr=subprocess.DEVNULL)
        vals = [int(v.strip()) for v in out.splitlines() if v.strip()]
        return max(vals) / 1024 if vals else 0.0  # MiB -> GiB
    except Exception:
        return 0.0


def _ram_gb() -> float:
    """Total system RAM in GiB; 0.0 if it can't be determined."""
    import platform
    import subprocess
    if platform.system() == 'Darwin':
        try:
            out = subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True)
            return int(out.strip()) / (1024 ** 3)
        except Exception:
            return 0.0
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemTotal'):
                    return int(line.split()[1]) / (1024 ** 2)  # kB -> GiB
    except Exception:
        pass
    return 0.0


def _available_ram_gb() -> float:
    """Available (free + reclaimable) system RAM in GiB on Linux; falls back to _ram_gb().

    On a CPU-only host the model runs in system RAM, so *available* memory is
    the right budget — total RAM is misleading when other apps are loaded.
    """
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemAvailable'):
                    return int(line.split()[1]) / (1024 ** 2)  # kB -> GiB
    except Exception:
        pass
    return _ram_gb()



def _resolve_tier(budget_gb: float) -> str:
    """Return the catalog tier key (e.g. '32gb') for the given RAM budget.

    Reads tier thresholds from models-catalog.json — no code change needed
    when thresholds are adjusted.  Picks the highest tier whose minRamGb <= budget.
    """
    tiers = load_catalog_tiers()
    ranked = sorted(tiers.items(), key=lambda kv: kv[1].get('minRamGb', 0), reverse=True)
    for key, cfg in ranked:
        if budget_gb >= cfg.get('minRamGb', 0):
            return key
    return ranked[-1][0] if ranked else '8gb'


def recommended_model() -> str:
    """Most capable catalog model that fits this machine.

    Tier thresholds and per-model tier assignments are read from models-catalog.json.
    Budget detection: VRAM on discrete GPU; unified RAM on Apple Silicon; available
    RAM on CPU-only Linux.
    """
    import platform
    catalog = load_catalog()
    if not catalog:
        return ''
    vram = _vram_gb()
    if vram > 0:
        budget = vram
    elif platform.system() == 'Darwin':
        budget = _ram_gb()
    else:
        budget = _available_ram_gb()
    if budget <= 0:
        return catalog[0].get('id', '')

    tier = _resolve_tier(budget)
    for spec in catalog:
        if spec.get('tier') == tier:
            return spec.get('id', '')
    # No model in the matched tier — fall back to the first available
    return catalog[0].get('id', '')


def _mu_config_path():
    from pathlib import Path
    return Path.home() / '.mu' / 'config.json'


def preferred_model() -> str:
    """Model ID persisted by `mu model` / `mu model load` selections.

    Returns '' when no preference has been saved yet.
    """
    import json
    try:
        p = _mu_config_path()
        return json.loads(p.read_text()).get('model', '') if p.exists() else ''
    except Exception:
        return ''


def save_preferred_model(model_id: str) -> None:
    import json
    p = _mu_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        cfg = json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        cfg = {}
    cfg['model'] = model_id
    p.write_text(json.dumps(cfg, indent=2))


def load_context_size() -> int:
    """Context window to load the model with: exactly MU_NUM_CTX.

    MU_NUM_CTX is the machine-safety knob: it caps the KV-cache footprint the
    user has validated for their RAM. Loading above it is not safe headroom —
    a 7B loaded at MU_NUM_CTX+2048 (8048) on an 8GB M2 thrashed swap and hard-
    rebooted the machine 20 minutes into a collection run. A prompt that grows
    past the window now gets a clean HTTP 400 (surfaced with the server's
    reason by chat()) instead of risking the host.

    Overridable via MU_LOAD_CTX for machines with RAM to spare.
    """
    override = os.environ.get("MU_LOAD_CTX")
    if override and override.isdigit():
        return int(override)
    return _NUM_CTX


# Tokens reserved for the completion inside the loaded window. The window
# bounds prompt + generation TOGETHER: a prompt budgeted to the full window
# leaves zero room to generate and the request 400s ("Context size has been
# exceeded") — 36 occurrences in the 2026-06-12 run-5 collection, mostly
# stage-planner and writer calls whose prompts approached the window.
_GEN_RESERVE = 1536


def max_prompt_tokens() -> int:
    """Effective max prompt budget: the loaded window minus generation room."""
    return max(_NUM_CTX - _GEN_RESERVE, 1024)


def _fuzzy_match_model(query: str, candidates: list[str]) -> str | None:
    """Return the best candidate whose path contains `query` as a substring (case-insensitive)."""
    q = query.lower()
    matches = [c for c in candidates if q in c.lower()]
    if not matches:
        return None
    # Prefer exact basename match, then shortest path (most specific without a quant suffix)
    def _score(c: str) -> tuple:
        base = c.split('/')[-1].split('@')[0].lower()
        return (base != q, len(c))
    return sorted(matches, key=_score)[0]


def _extract_available_paths(err_str: str) -> list[str]:
    """Parse `availablePathsSample` from an LM Studio error string."""
    import re
    # The SDK embeds JSON-like data in the exception message; find the first [...] after the key
    m = re.search(r'"availablePathsSample"\s*:\s*(\[.*?\])', err_str, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except Exception:
        return []


def _loaded_llm_handles():
    """Return (client, list_of_handles) for all currently loaded LLMs via SDK.

    Returns (None, []) on any error so callers can safely ignore failures.
    """
    try:
        c = _lms_client()
        handles = list(c.llm.list_loaded())
        return c, handles
    except Exception:
        return None, []


def _unload_others(client, handles, keep_identifier: str) -> None:
    """Unload every loaded LLM whose identifier doesn't match *keep_identifier*."""
    for h in handles:
        ident = getattr(h, 'identifier', None)
        if ident and ident != keep_identifier:
            try:
                print(f"Unloading {ident} …")
                client.llm.unload(ident)
            except Exception as e:
                print(f"  Warning: could not unload {ident}: {e}")


def load_model(model_id: str, _retry: bool = True) -> bool:
    """Load a model persistently via the LM Studio Python SDK, with progress.

    Before loading, checks whether the requested model is already the sole
    loaded model (skips load if so) and unloads any other models that are
    currently loaded.

    If the exact ``model_id`` is not found, the error response from LM Studio
    often includes ``availablePathsSample``.  We fuzzy-match against that list
    and retry once with the best candidate.
    """
    try:
        client, handles = _loaded_llm_handles()

        if client is not None:
            # Check if the desired model is already loaded (bare-name match).
            # normalize_model_bare strips path prefix, .gguf extension, and
            # quantization suffix so that the full file path matches the short
            # display identifier LM Studio assigns after loading.
            bare_target = normalize_model_bare(model_id)
            already = next(
                (h for h in handles
                 if normalize_model_bare(getattr(h, 'identifier', '')) == bare_target),
                None,
            )
            if already:
                ident = getattr(already, 'identifier', model_id)
                # A resident model may have been loaded with a smaller context
                # window than we need (e.g. LM Studio's JIT default 4096, or a
                # previous run with a lower MU_NUM_CTX). Trusting it means every
                # request larger than that window is hard-rejected with HTTP 400
                # mid-run (observed: 153 rejections in one 3h collection run).
                # Verify the actual context before skipping the load.
                actual = None
                try:
                    info = already.get_info()
                    actual = (getattr(info, 'context_length', None)
                              or getattr(info, 'contextLength', None))
                except Exception:
                    pass
                if actual and actual < _NUM_CTX:
                    print(f"Model already loaded: {ident} — but its context "
                          f"{actual} < MU_NUM_CTX {_NUM_CTX}; reloading with "
                          f"{load_context_size()}.")
                    _unload_others(client, handles, '')  # incl. the undersized one
                else:
                    print(f"Model already loaded: {ident}"
                          + (f" (context: {actual})" if actual else ''))
                    # Unload any other models that snuck in alongside it.
                    _unload_others(client, handles, ident)
                    return True
            else:
                # Unload all currently loaded models before loading the new one.
                _unload_others(client, handles, '')

        bar_len = 30
        progress_received = threading.Event()

        def _on_progress(prog):
            pct = getattr(prog, 'progress', None)
            if pct is not None:
                progress_received.set()
                filled = int(bar_len * pct)
                bar = '█' * filled + '░' * (bar_len - filled)
                print(f"\r  [{bar}] {pct:.0%}  ", end='', flush=True)

        def _spinner():
            frames = itertools.cycle('⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏')
            while not progress_received.wait(timeout=0.1):
                print(f"\r  {next(frames)} waiting for LM Studio…", end='', flush=True)
            # clear spinner line; progress bar will overwrite
            print(f"\r  {' ' * (bar_len + 20)}", end='', flush=True)

        print(f"Loading {model_id} …")
        spin = threading.Thread(target=_spinner, daemon=True)
        spin.start()
        # Load with an explicit context window of MU_NUM_CTX. Without this,
        # LM Studio's JIT default (often 4096) caps the model below _NUM_CTX,
        # so any prompt above the default is hard-rejected with HTTP 400
        # mid-run — invisible until the repair loop's accumulated history
        # (the largest prompt) hits it. Never load above MU_NUM_CTX by
        # default: the KV cache for the extra window can push a small-RAM
        # host into swap (see load_context_size).
        load_ctx = load_context_size()
        config: dict = {"contextLength": load_ctx}
        # Throughput knobs (opt-in via env): flash attention speeds up
        # attention and reduces compute-buffer memory; q8_0 KV cache halves
        # the KV footprint — both matter on a RAM-starved host where the
        # model barely fits the GPU working set. KV quantization requires
        # flash attention, so MU_LOAD_KV_QUANT implies it.
        if os.environ.get("MU_LOAD_FLASH_ATTN") == "1":
            config["flashAttention"] = True
        kvq = os.environ.get("MU_LOAD_KV_QUANT", "")
        if kvq:
            config["flashAttention"] = True
            config["llamaKCacheQuantizationType"] = kvq
            config["llamaVCacheQuantizationType"] = kvq
        try:
            handle = _lms_client().llm.load_new_instance(
                model_id, ttl=None, on_load_progress=_on_progress,
                config=config,
            )
        except TypeError:
            # Older SDK without a `config` kwarg — fall back to a plain load.
            handle = _lms_client().llm.load_new_instance(
                model_id, ttl=None, on_load_progress=_on_progress
            )
        progress_received.set()  # stop spinner if no progress events fired
        spin.join(timeout=1)
        print()  # newline after progress bar
        info = handle.get_info()
        # Read back the context the model actually loaded with and warn if LM
        # Studio clamped it below our request budget (e.g. config ignored, or a
        # model max smaller than asked) — otherwise the clamp is silent until 400s.
        actual = getattr(info, 'context_length', None) or getattr(info, 'contextLength', None)
        print(f"Loaded: {getattr(info, 'identifier', model_id)}"
              + (f"  (context: {actual})" if actual else ''))
        if actual and actual < _NUM_CTX:
            print(f"  WARNING: loaded context {actual} < MU_NUM_CTX {_NUM_CTX} — "
                  f"prompts above {actual} tokens will be rejected. Lower MU_NUM_CTX "
                  f"or load this model with a larger context window.")
        return True
    except ImportError:
        print("lmstudio SDK not installed — run: pip install lmstudio  (in the mu venv)")
        return False
    except Exception as e:
        err_str = str(e)
        if _retry:
            candidates = _extract_available_paths(err_str)
            matched = _fuzzy_match_model(model_id, candidates) if candidates else None
            if matched:
                print(f"\n  '{model_id}' not found — trying '{matched}' …")
                return load_model(matched, _retry=False)
            # Model not downloaded yet — try to fetch it from the hub first.
            if 'pathNotFound' in err_str or 'not found' in err_str.lower():
                print(f"\n  '{model_id}' not downloaded — fetching from LM Studio hub …")
                downloaded_key = download_model(model_id)
                if downloaded_key:
                    return load_model(downloaded_key, _retry=False)
        print(f"\nError loading model: {e}")
        return False


def download_model(model_id: str, on_progress=None) -> str:
    """Search the LM Studio hub for `model_id` and download the recommended quant.

    Catalog ids (e.g. ``qwen/qwen2.5-coder-7b-instruct``) are the *served* names,
    not hub artifact paths, so they can't be passed to ``lms get`` directly. We
    search the hub by the bare model name and take the option flagged
    ``recommended`` for this hardware. Requires LM Studio to be running.
    Returns the downloaded model key, or '' on failure.
    """
    try:
        client = _lms_client()
        term = model_id.split('/')[-1]
        results = client.repository.search_models(term, limit=5)
        if not results:
            print(f"No LM Studio hub match for '{model_id}'")
            return ''
        opts = results[0].get_download_options()
        if not opts:
            print(f"No download options for '{model_id}'")
            return ''
        opt = next((o for o in opts if getattr(o, 'recommended', False)), opts[0])
        key = opt.download(on_progress=on_progress) if on_progress else opt.download()
        return key or ''
    except ImportError:
        print("lmstudio SDK not installed — run: pip install lmstudio  (in the mu venv)")
        return ''
    except Exception as e:
        print(f"Error downloading {model_id}: {e}")
        return ''


_KNOWN_TOOLS = frozenset(('Write', 'Edit', 'Bash', 'Read'))
# Markers various small models wrap text-format tool calls in. Stripped before
# JSON decoding. The opening tag is often consumed as a special token by the
# chat template, leaving only the closing tag — so we strip each independently.
_TOOLCALL_MARKERS = ('<tool_call>', '</tool_call>', '<|tool_call|>',
                     '<|tool_calls|>', '[TOOL_CALLS]', '<tools>', '</tools>')


def _extract_text_tool_calls(content: str) -> list[dict]:
    """Parse tool calls that a model emitted as plain text in the content field.

    Some models (e.g. IBM Granite, Hermes-style) emit tool calls as JSON in the
    message body — ``{"name": "Write", "arguments": {...}}`` optionally wrapped
    in ``<tool_call>``/``</tool_call>`` markers — instead of populating the
    OpenAI ``tool_calls`` field. LM Studio does not always re-parse these, so
    the agent sees an empty ``tool_calls`` and assumes the model produced prose.

    This is a general model-compatibility shim, not specific to any task. It is
    fail-soft: malformed or truncated JSON (e.g. a large file that hit the
    generation limit) yields ``[]`` so the caller's existing nudge/retry path
    fires instead of crashing.

    Uses ``raw_decode`` rather than brace-counting because file contents inside
    the ``arguments`` string are full of ``{`` and ``}`` that would defeat a
    naive balanced-brace scan.
    """
    if not content or '{' not in content:
        return []
    text = content
    for marker in _TOOLCALL_MARKERS:
        text = text.replace(marker, ' ')
    decoder = json.JSONDecoder()
    calls: list[dict] = []
    idx = 0
    n = len(text)
    while idx < n:
        start = text.find('{', idx)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            # Not a valid object at this brace — advance past it and retry.
            # A truncated final object simply yields no further calls.
            idx = start + 1
            continue
        idx = end
        if not isinstance(obj, dict):
            continue
        name = obj.get('name')
        args = obj.get('arguments')
        # Validate: must name a real tool and carry an arguments object.
        if name in _KNOWN_TOOLS and isinstance(args, dict):
            calls.append({
                'id': f'call_{len(calls)}',
                'type': 'function',
                'function': {'name': name, 'arguments': json.dumps(args)},
            })
    return calls


def message_chars(m: dict) -> int:
    """Approximate prompt weight of one chat message, in characters.

    Counts content plus tool-call arguments — an assistant turn that Writes a
    whole file carries the file in its arguments, usually the heaviest part of
    a repair unit. +80 covers the role/JSON framing. The single owner of this
    estimate; session.py's repair-budget trimming calls it too.
    """
    n = len(str(m.get('content') or ''))
    for tc in m.get('tool_calls') or []:
        n += len(str(tc.get('function', {}).get('arguments') or ''))
    return n + 80


def _est_tokens(messages: list[dict]) -> int:
    """Rough prompt size in tokens: total message chars at 4 chars ≈ 1 token."""
    return sum(message_chars(m) for m in messages) // 4


def _shrink_oversized(messages: list[dict]) -> list[dict]:
    """Last-resort guard: cut the middle of the largest message contents until
    the estimated prompt fits the budget.

    Callers are supposed to budget their own prompts (repair_loop does), but
    writer/stage-planner prompts assembled from skills + reference files can
    still approach the window; the server then hard-rejects with HTTP 400
    and the whole call (and its retries) is wasted. Content-only edits keep
    the tool-call pairing intact. Head and tail are kept — instructions lead,
    the newest context trails.
    """
    budget = max_prompt_tokens()
    if _est_tokens(messages) <= budget:
        return messages
    msgs = [dict(m) for m in messages]
    for _ in range(8):
        over_chars = (_est_tokens(msgs) - budget) * 4
        if over_chars <= 0:
            break
        idx = max(range(len(msgs)),
                  key=lambda i: len(str(msgs[i].get('content') or '')))
        content = str(msgs[idx].get('content') or '')
        if len(content) < 1200:
            break  # nothing meaningfully shrinkable left
        cut = min(over_chars + 200, len(content) - 800)
        head = content[:(len(content) - cut) * 2 // 3]
        tail = content[-((len(content) - cut) - len(head)):]
        msgs[idx]['content'] = head + '\n…[trimmed to fit context]…\n' + tail
    est = _est_tokens(msgs)
    print(f"==> [mu-agent] chat: prompt trimmed to ~{est} tokens to fit the "
          f"context window (budget {budget}).", flush=True)
    return msgs


def chat(model: str, messages: list[dict], tools: Optional[list[dict]],
         timeout: float, tool_choice: str = 'auto') -> tuple[dict, ChatStats]:
    import httpx
    messages = _shrink_oversized(messages)
    body: dict = {
        'model': model,
        'messages': messages,
        'temperature': 0.1,
        'stream': False,
        # llama.cpp/LM Studio: reuse the KV cache for the longest common prompt
        # prefix across requests (default-on upstream; sent explicitly here, and
        # ignored harmlessly by endpoints that don't recognize it).
        'cache_prompt': True,
    }
    # Override the LM Studio UI context setting so the right value is used
    # regardless of what was set when the model was loaded.
    body['num_ctx'] = _NUM_CTX
    # Suppress degenerate repetition loops (see _REPEAT_PENALTY). Omit when set to
    # the neutral 1.0 so a disabled penalty isn't sent at all.
    if _REPEAT_PENALTY and _REPEAT_PENALTY != 1.0:
        body['repeat_penalty'] = _REPEAT_PENALTY
    # Measurement mode (see _SEED): pin the RNG and decode greedily so the same
    # input reproduces the same output for clean A/B testing.
    if _SEED is not None:
        body['seed'] = int(_SEED)
        body['temperature'] = 0.0
    if tools:
        body['tools'] = tools
        # 'required' forces the model to emit a real tool call instead of prose.
        # Small models (e.g. Granite) otherwise drift into 228-token explanations
        # for whole writer turns, or emit the call as unparsed text; forcing it
        # routes them through LM Studio's native tool-call path. Callers that
        # genuinely may not need a tool (none today) can pass 'auto'.
        body['tool_choice'] = tool_choice
    r = httpx.post(f"{LMS_HOST}/v1/chat/completions", json=body,
                   timeout=max(timeout, 10.0))
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        # Surface the server's reason ("request exceeds the available context
        # size", "model not loaded", …) — the bare status line is undiagnosable
        # and the body never reaches any log otherwise.
        detail = (r.text or '').strip().replace('\n', ' ')[:300]
        err_text = f"{e}\n  server detail: {detail}" if detail else str(e)
        _record_transcript(messages, None, error=err_text)
        raise httpx.HTTPStatusError(
            err_text, request=e.request, response=e.response) from None
    data = r.json()
    msg = data['choices'][0]['message']
    usage = data.get('usage', {})
    stats = ChatStats(usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0))
    _token_log.append({
        'phase': _chat_phase,
        'task_file': _chat_task,
        'prompt_tokens': stats.prompt_tokens,
        'generated_tokens': stats.generated_tokens,
        'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    })
    _record_transcript(messages, msg)
    tool_calls = []
    for tc in msg.get('tool_calls') or []:
        fn = tc.get('function', {})
        raw_args = fn.get('arguments', '{}')
        try:
            parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            parsed = {}
        # Store arguments as a JSON *string* — the OpenAI schema requires a string,
        # and this assistant message is re-sent verbatim on later turns. A dict here
        # makes LM Studio reject the whole request with HTTP 400, which silently kills
        # the multi-turn repair loop. Consumers (tools.dispatch/log_call) parse it back.
        tool_calls.append({
            'id': tc.get('id', ''),
            'type': 'function',
            'function': {'name': fn.get('name', ''), 'arguments': json.dumps(parsed)},
        })
    content = msg.get('content') or ''
    # Fallback: some models (Granite, Hermes-style) emit the tool call as text
    # in the content field instead of the OpenAI tool_calls field. Parse it so
    # the agent loop sees a real tool call rather than treating it as prose.
    if not tool_calls and tools:
        recovered = _extract_text_tool_calls(content)
        if recovered:
            tool_calls = recovered
            # Drop the raw JSON from content — the call now lives in tool_calls,
            # and re-sending the JSON body as assistant text would confuse the
            # model on later turns.
            content = ''
    return {
        'role': 'assistant',
        'content': content,
        'tool_calls': tool_calls,
    }, stats


def chat_or_retry(model: str, messages: list[dict], tools: Optional[list[dict]],
                  deadline: float, tool_choice: str = 'auto') -> tuple[dict, ChatStats]:
    last_err: Optional[Exception] = None
    for attempt in range(3):
        remaining = deadline - time.time()
        if remaining <= 0:
            raise last_err or TimeoutError("deadline exceeded")
        t0 = time.time()
        try:
            msg, stats = chat(model, messages, tools, remaining, tool_choice)
        except Exception as e:
            if attempt < 2:
                print(f"==> [mu-agent] Chat error — retrying in 5s (retry {attempt + 1}/2): {e}")
                time.sleep(5.0)
                last_err = e
                continue
            raise
        elapsed = time.time() - t0
        print(f"==> [mu-agent] chat: prompt={stats.prompt_tokens} "
              f"gen={stats.generated_tokens} time={elapsed:.1f}s")
        return msg, stats
    raise last_err  # type: ignore
