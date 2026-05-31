"""HTTP client for the LM Studio / OpenVINO OpenAI-compatible API."""

import json
import os
import re
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
# without triggering swap (8192 causes 6x slowdown per TUNING.md).
_NUM_CTX = int(os.environ.get("MU_NUM_CTX", "6000"))


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


def is_running() -> bool:
    try:
        import httpx
        return httpx.get(f"{LMS_HOST}/v1/models", timeout=5.0).status_code == 200
    except Exception:
        return False


def is_running_at(host: str) -> bool:
    """Check if an OpenAI-compatible server is reachable at an explicit host URL."""
    try:
        import httpx
        return httpx.get(f"{host}/v1/models", timeout=5.0).status_code == 200
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


def load_catalog() -> list[dict]:
    """Curated model specs shipped alongside the package."""
    import os
    from pathlib import Path
    default = Path(__file__).parent.parent.parent / 'models-catalog.json'
    path = Path(os.environ.get('MU_MODELS_CATALOG', '') or default)
    try:
        return json.loads(path.read_text(encoding='utf-8')).get('models', [])
    except Exception:
        return []


def catalog_for_backend(backend: str = '') -> list[dict]:
    """Catalog entries for a specific backend (defaults to the persisted backend).

    Models without a 'backend' field are treated as 'lmstudio' for backward
    compatibility.
    """
    if not backend:
        backend = load_backend().get('backend', 'lmstudio')
    return [m for m in load_catalog() if m.get('backend', 'lmstudio') == backend]


def ov_models_dir():
    """Default local directory where OpenVINO models are stored."""
    from pathlib import Path
    return Path.home() / '.mu' / 'models'


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



# VRAM thresholds (GiB) that determine which model tier to select.
_VRAM_THRESHOLD_32GB = 30
_VRAM_THRESHOLD_16GB = 14

# Context-window sizes (tokens) that bound each tier.
# 8 GB tier: ≤32K ctx  |  16 GB tier: 32K–128K ctx  |  32 GB tier: >128K ctx
_CTX_MAX_8GB_TIER  = 32_768   # 32K
_CTX_MAX_16GB_TIER = 131_072  # 128K


def recommended_model() -> str:
    """Most capable catalog model for the current backend that fits this machine.

    For the lmstudio backend: uses VRAM/RAM budget to pick a tier.
    For the openvino backend: uses available RAM (CPU inference) to pick a tier.
    Context window stands in for model size:
      8 GB tier: ≤32K  |  16 GB tier: 32K–128K  |  32 GB tier: >128K
    """
    import platform
    catalog = catalog_for_backend()
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
    if budget >= _VRAM_THRESHOLD_32GB:
        tier = 32
    elif budget >= _VRAM_THRESHOLD_16GB:
        tier = 16
    else:
        tier = 8
    for spec in catalog:
        ctx = spec.get('contextWindow', 0)
        if tier == 8  and ctx <= _CTX_MAX_8GB_TIER:
            return spec.get('id', '')
        if tier == 16 and _CTX_MAX_8GB_TIER < ctx <= _CTX_MAX_16GB_TIER:
            return spec.get('id', '')
        if tier >= 32 and ctx > _CTX_MAX_16GB_TIER:
            return spec.get('id', '')
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


def save_backend(backend: str, host: str, model: str = '', pid: int = 0) -> None:
    """Persist backend selection to ~/.mu/config.json.

    backend: 'lmstudio' | 'openvino'
    host:    API base URL (e.g. 'http://localhost:8765')
    model:   model path / ID
    pid:     PID of background server process (0 for external servers like LM Studio)
    """
    p = _mu_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        cfg = json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        cfg = {}
    cfg['backend'] = backend
    cfg['host'] = host if backend != 'lmstudio' else ''  # only persist for non-default backends
    if model:
        cfg['model'] = model
    if pid:
        cfg['ov_pid'] = pid
    elif 'ov_pid' in cfg and backend == 'lmstudio':
        del cfg['ov_pid']
    p.write_text(json.dumps(cfg, indent=2))


def load_backend() -> dict:
    """Return persisted backend config keys: backend, host, model, ov_pid."""
    try:
        p = _mu_config_path()
        cfg = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        return {
            'backend': cfg.get('backend', 'lmstudio'),
            'host':    cfg.get('host', ''),
            'model':   cfg.get('model', ''),
            'ov_pid':  cfg.get('ov_pid', 0),
        }
    except Exception:
        return {'backend': 'lmstudio', 'host': '', 'model': '', 'ov_pid': 0}


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
                print(f"Model already loaded: {ident}")
                # Unload any other models that snuck in alongside it.
                _unload_others(client, handles, ident)
                return True

            # Unload all currently loaded models before loading the new one.
            _unload_others(client, handles, '')

        def _on_progress(prog):
            pct = getattr(prog, 'progress', None)
            if pct is not None:
                bar_len = 30
                filled = int(bar_len * pct)
                bar = '█' * filled + '░' * (bar_len - filled)
                print(f"\r  [{bar}] {pct:.0%}", end='', flush=True)

        print(f"Loading {model_id} …")
        handle = _lms_client().llm.load_new_instance(
            model_id, ttl=None, on_load_progress=_on_progress
        )
        print()  # newline after progress bar
        info = handle.get_info()
        print(f"Loaded: {getattr(info, 'identifier', model_id)}")
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


def chat(model: str, messages: list[dict], tools: Optional[list[dict]],
         timeout: float) -> tuple[dict, ChatStats]:
    import httpx
    body: dict = {
        'model': model,
        'messages': messages,
        'temperature': 0.1,
        'stream': False,
        # llama.cpp/LM Studio: reuse the KV cache for the longest common prompt
        # prefix across requests (default-on upstream; sent explicitly here, and
        # ignored harmlessly by endpoints that don't recognize it).
        'cache_prompt': True,
        # Override the LM Studio UI context setting so the right value is used
        # regardless of what was set when the model was loaded.
        'num_ctx': _NUM_CTX,
    }
    if tools:
        body['tools'] = tools
        body['tool_choice'] = 'auto'
    r = httpx.post(f"{LMS_HOST}/v1/chat/completions", json=body,
                   timeout=max(timeout, 10.0))
    r.raise_for_status()
    data = r.json()
    msg = data['choices'][0]['message']
    usage = data.get('usage', {})
    stats = ChatStats(usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0))
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
    return {
        'role': 'assistant',
        'content': msg.get('content') or '',
        'tool_calls': tool_calls,
    }, stats


def chat_or_retry(model: str, messages: list[dict], tools: Optional[list[dict]],
                  deadline: float) -> tuple[dict, ChatStats]:
    last_err: Optional[Exception] = None
    for attempt in range(3):
        remaining = deadline - time.time()
        if remaining <= 0:
            raise last_err or TimeoutError("deadline exceeded")
        t0 = time.time()
        try:
            msg, stats = chat(model, messages, tools, remaining)
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
