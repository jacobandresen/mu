"""Minimal OpenAI-compatible HTTP server backed by OpenVINO GenAI.

Start with:  mu serve [model_dir] [--port PORT] [--device DEVICE]
Point mu at: MU_LMSTUDIO_HOST=http://localhost:<PORT> mu agent "..."

The server exposes two endpoints:
  GET  /v1/models              — returns the loaded model name
  POST /v1/chat/completions    — non-streaming chat completions
"""

import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


def _build_handler(pipeline, model_name: str):
    """Return a handler class that closes over the loaded pipeline."""

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default access log
            pass

        def _send_json(self, code: int, body: Any) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/v1/models":
                self._send_json(200, {
                    "object": "list",
                    "data": [{"id": model_name, "object": "model", "owned_by": "openvino"}],
                })
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                self._send_json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                self._send_json(400, {"error": "invalid json"})
                return

            messages = body.get("messages", [])
            max_tokens = int(body.get("max_tokens", 1024))
            temperature = float(body.get("temperature", 0.1))

            try:
                import openvino_genai as ov_genai

                config = ov_genai.GenerationConfig()
                config.max_new_tokens = max_tokens
                if temperature > 0:
                    config.temperature = temperature
                    config.do_sample = True

                tokenizer = pipeline.get_tokenizer()
                prompt = tokenizer.apply_chat_template(
                    messages, add_generation_prompt=True
                )

                t0 = time.time()
                raw = pipeline.generate(prompt, config)
                elapsed = time.time() - t0

                # generate() returns a string when given a string prompt
                text = raw if isinstance(raw, str) else (
                    raw.texts[0] if hasattr(raw, "texts") else str(raw)
                )

                print(f"  [{model_name}] {len(text.split())} words in {elapsed:.1f}s")

            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
                return

            prompt_tokens = len(prompt.split())
            gen_tokens = len(text.split())
            self._send_json(200, {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_name,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": gen_tokens,
                    "total_tokens": prompt_tokens + gen_tokens,
                },
            })

    return _Handler


def serve(model_dir: str, port: int = 1234, device: str = "CPU",
          num_threads: int = 0) -> None:
    """Load the OpenVINO model and start the server (blocks until Ctrl-C).

    num_threads: CPU inference threads (0 = half of os.cpu_count()); ignored
    for non-CPU devices such as GPU or NPU.
    """
    try:
        import openvino_genai as ov_genai
    except ImportError:
        raise SystemExit(
            "openvino-genai not installed — run: pip install openvino-genai"
        )

    model_path = str(Path(model_dir).resolve())
    model_name = Path(model_dir).name

    # Fail fast — check port before spending time loading the model.
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _s:
        _s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            _s.bind(("localhost", port))
        except OSError:
            raise SystemExit(
                f"mu serve: port {port} is already in use — "
                f"stop the existing server or choose another port with --port"
            )

    props: dict = {}
    if device.upper() == "CPU":
        if num_threads <= 0:
            num_threads = max(1, (os.cpu_count() or 2) // 2)
        props["INFERENCE_NUM_THREADS"] = num_threads
        print(f"Loading {model_name} on {device} (threads={num_threads}) …")
    elif device.upper() == "NPU":
        cache_dir = Path.home() / '.mu' / 'ov_cache'
        cache_dir.mkdir(parents=True, exist_ok=True)
        props = {
            "MAX_PROMPT_LEN": 1024,
            "MIN_RESPONSE_LEN": 128,
            "GENERATE_HINT": "BEST_PERF",
            "CACHE_DIR": str(cache_dir),
        }
        print(f"Loading {model_name} on {device} (max_prompt=1024, cache={cache_dir}) …")
        print("  Note: first load compiles model shapes — this may take 1–2 minutes.")
    else:
        print(f"Loading {model_name} on {device} …")

    pipeline = ov_genai.LLMPipeline(model_path, device, props)
    print("Model loaded.")

    handler = _build_handler(pipeline, model_name)
    server = HTTPServer(("localhost", port), handler)
    url = f"http://localhost:{port}"
    print(f"OpenVINO server listening at {url}")
    print(f"  Use with mu:  MU_LMSTUDIO_HOST={url} mu agent \"...\"")
    print("  Press Ctrl-C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
