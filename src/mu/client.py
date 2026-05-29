"""HTTP client for the LM Studio OpenAI-compatible API."""

import json
import os
import time
from dataclasses import dataclass
from typing import Optional

LMS_HOST = os.environ.get("MU_LMSTUDIO_HOST", "http://localhost:1234")


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


def recommended_model() -> str:
    """Most capable catalog model that fits this machine's GPU VRAM.

    Coding models must fit in GPU memory to run at usable speed, so VRAM is the
    budget; system RAM is only a fallback when VRAM can't be detected (e.g. a
    CPU-only host). Context window stands in for model size: the 8 GB tier caps
    at 32k, the 16 GB tier at 128k, the 32 GB tier above that.
    """
    catalog = load_catalog()
    if not catalog:
        return ''
    budget = _vram_gb() or _ram_gb()
    if budget <= 0:
        return catalog[0].get('id', '')
    if budget >= 30:
        tier = 32
    elif budget >= 14:
        tier = 16
    else:
        tier = 8
    for spec in catalog:
        ctx = spec.get('contextWindow', 0)
        if tier == 8 and ctx <= 32768:
            return spec.get('id', '')
        if tier == 16 and 32768 < ctx <= 131072:
            return spec.get('id', '')
        if tier >= 32 and ctx > 131072:
            return spec.get('id', '')
    return catalog[0].get('id', '')


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
            bare_target = model_id.split('/')[-1].split('@')[0].lower()
            already = next(
                (h for h in handles
                 if getattr(h, 'identifier', '').split('/')[-1].split('@')[0].lower() == bare_target),
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
        print("lmstudio SDK not installed — run: pip3 install lmstudio --break-system-packages")
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
        print("lmstudio SDK not installed — run: pip3 install lmstudio --break-system-packages")
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
