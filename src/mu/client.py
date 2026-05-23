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


def load_model(model_id: str) -> bool:
    """Load a model via the LM Studio Python SDK."""
    try:
        handle = _lms_client().llm.model(model_id)
        info = handle.get_info()
        print(f"Loaded: {getattr(info, 'identifier', model_id)}")
        return True
    except ImportError:
        print("lmstudio SDK not installed — run: pip3 install lmstudio --break-system-packages")
        return False
    except Exception as e:
        print(f"Error loading model: {e}")
        return False


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
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            args = {}
        tool_calls.append({
            'id': tc.get('id', ''),
            'type': 'function',
            'function': {'name': fn.get('name', ''), 'arguments': args},
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
