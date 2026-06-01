#!/usr/bin/env python3
"""Detect Intel hardware, install OpenVINO, download the right Mistral model,
and configure mu's backend.

Called by `make openvino` and `mu setup` on Intel Linux systems.
Safe to re-run: skips download when the model is already present.
"""
import sys
from pathlib import Path

# Allow running outside the installed venv (e.g. directly from the repo root).
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def _best_device() -> str:
    """Return the default OpenVINO device (CPU).

    CPU works on all hardware without driver setup. To use the Intel NPU,
    first run ``scripts/install-npu-driver.sh``, then ``mu device npu``.
    """
    return 'CPU'


def _is_intel_cpu() -> bool:
    try:
        return 'GenuineIntel' in Path('/proc/cpuinfo').read_text()
    except Exception:
        return False


def setup(yes: bool = False) -> int:
    """Run the full OpenVINO setup. Returns 0 on success, 1 on error."""
    import importlib.util

    if not _is_intel_cpu():
        print("  Skipping OpenVINO setup (no Intel CPU detected).")
        return 0

    # ── 1. Check / install packages ──────────────────────────────────────────
    if importlib.util.find_spec('openvino_genai') is None:
        print("  openvino-genai not installed.")
        if not yes:
            try:
                ans = input("  Install OpenVINO stack now? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = ''
            if ans != 'y':
                print("  Skipped. Run `make openvino` to install later.")
                return 0
        print("  Installing openvino stack…")
        import subprocess
        r = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--quiet', '-e',
             str(Path(__file__).parent.parent) + '[openvino]'],
        )
        if r.returncode != 0:
            print("  ERROR: pip install failed.", file=sys.stderr)
            return 1
        print("  Packages installed.")

    # ── 2. Detect best device ─────────────────────────────────────────────────
    device = _best_device()
    print(f"  Device: {device}")

    # ── 3. Pick model ─────────────────────────────────────────────────────────
    if device == 'NPU':
        model_id  = 'Mistral-7B-Instruct-v0.3-int4-cw-ov'
        hf_repo   = 'OpenVINO/Mistral-7B-Instruct-v0.3-int4-cw-ov'
    else:
        model_id  = 'Mistral-7B-Instruct-v0.3-int4-ov'
        hf_repo   = 'OpenVINO/Mistral-7B-Instruct-v0.3-int4-ov'

    models_dir = Path.home() / '.mu' / 'models'
    model_dir  = models_dir / model_id

    # ── 4. Download model ─────────────────────────────────────────────────────
    if (model_dir / 'openvino_model.xml').exists():
        print(f"  Model already present: {model_dir}")
    else:
        print(f"  Model: {hf_repo}  (~3.6 GB)")
        if not yes:
            try:
                ans = input(f"  Download {model_id} now? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = ''
            if ans != 'y':
                print("  Skipped. Run `make openvino` to download later.")
                return 0
        print(f"  Downloading {hf_repo}…")
        try:
            import huggingface_hub as hf
            hf.snapshot_download(
                hf_repo,
                local_dir=str(model_dir),
                ignore_patterns=['*.msgpack', '*.h5', 'flax_model*'],
            )
            print(f"  Downloaded: {model_dir}")
        except Exception as e:
            print(f"  ERROR: Download failed: {e}", file=sys.stderr)
            return 1

    # ── 5. Save backend config (no server started here) ───────────────────────
    try:
        from mu.client import save_backend
        save_backend('openvino', 'http://localhost:8765', str(model_dir), 0, device)
        print(f"  Backend configured → openvino / {device}")
    except Exception as e:
        print(f"  Warning: could not save backend config: {e}")

    print()
    print(f"  Start the inference server:")
    print(f"    mu model load '{model_dir}' --backend openvino --device {device}")
    print(f"  To switch to Intel NPU later:  mu device npu")
    print(f"  Then run: mu agent \"your goal\"")
    return 0


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('-y', '--yes', action='store_true', help='Skip confirmation prompts')
    args = p.parse_args()
    sys.exit(setup(yes=args.yes))
