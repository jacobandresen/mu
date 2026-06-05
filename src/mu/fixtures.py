"""Fixture mode + competence routing — problem-space minimization.

The dojo's variance is mostly self-inflicted (docs/PROBLEM_SPACE.md): we hand a
weak model boilerplate it gets wrong, then measure the noise. Two levers here:

- **Fixtures** — files a problem ships in ``dojo/fixtures/<id>/`` that are GIVEN
  to the model (a correct Makefile, manifest, or test). ``apply()`` copies them
  into the work dir before the agent runs; the agent marks a provided file's task
  done so the writer skips it. A given file can't be written wrong, so its whole
  failure class disappears (this is the L2–L4 mechanism in the report).
- **Routing** — ``competence()`` reads the model's measured pass rate for a
  toolchain from the reflex KB. ``should_skip()`` says don't run a problem whose
  toolchain the chosen model is hopeless at (≈0), so rounds aren't burned
  generating noise (granite is 0.0 on python/rust/go).

Both keep the same source of truth: the committed fixtures and the model_profile
table the KB already builds.
"""

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Optional

_FIXTURES_ROOT = Path('dojo/fixtures')
_DEFAULT_DB = os.path.expanduser('~/.mu/mu.db')

# Skip a problem when the model's measured competence for its toolchain is at or
# below this and we have enough evidence — pure noise otherwise.
_HOPELESS = 0.05


def fixture_dir(problem_id: str) -> Path:
    return _FIXTURES_ROOT / problem_id


def apply(problem_id: str, work_dir: str = '.') -> list[str]:
    """Copy a problem's committed fixtures into *work_dir*. Returns the relative
    paths provided (empty if the problem has no fixtures)."""
    src = fixture_dir(problem_id)
    if not src.is_dir():
        return []
    provided: list[str] = []
    for f in sorted(src.rglob('*')):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        dst = Path(work_dir) / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        provided.append(str(rel))
    return provided


def _model_family(model: str) -> str:
    r = (model or '').lower()
    if 'granite' in r:
        return 'granite'
    if 'qwen2.5' in r:
        return 'qwen2.5'
    if 'devstral' in r:
        return 'devstral'
    if 'mistral' in r:
        return 'mistral'
    return model or 'unknown'


def competence(model: str, toolchain: str, db_path: str = _DEFAULT_DB) -> Optional[float]:
    """Measured pass rate for *model* on *toolchain*, from the KB's model_profile,
    or None if not enough data. Read-only; never builds the DB."""
    if not Path(db_path).exists():
        return None
    try:
        con = sqlite3.connect(db_path)
        row = con.execute(
            "SELECT competence_by_toolchain FROM model_profile WHERE model_family=?",
            (_model_family(model),)).fetchone()
        con.close()
    except sqlite3.Error:
        return None
    if not row or not row[0]:
        return None
    return json.loads(row[0]).get(toolchain)


def should_skip(model: str, toolchain: str, db_path: str = _DEFAULT_DB) -> bool:
    """True when the model is measured hopeless (≈0) on this toolchain — routing
    says don't waste a round. Conservative: needs a competence value to skip."""
    c = competence(model, toolchain, db_path)
    return c is not None and c <= _HOPELESS


def _problem_toolchains(problem_id: str, catalog_path: str = 'problems-catalog.json') -> list[str]:
    try:
        from mu.toolchain import load_problems_catalog
        for p in load_problems_catalog(catalog_path):
            if p['id'] == problem_id:
                return p.get('toolchains', [])
    except Exception:
        pass
    return []


def should_skip_problem(model: str, problem_id: str,
                        catalog_path: str = 'problems-catalog.json',
                        db_path: str = _DEFAULT_DB) -> bool:
    """Routing at the problem level: skip if the model is hopeless on EVERY one
    of the problem's toolchains (and we have evidence for at least one)."""
    tcs = _problem_toolchains(problem_id, catalog_path)
    if not tcs:
        return False
    verdicts = [should_skip(model, tc, db_path) for tc in tcs]
    evidence = [competence(model, tc, db_path) is not None for tc in tcs]
    return any(evidence) and all(v for v, e in zip(verdicts, evidence) if e)


if __name__ == '__main__':
    import sys
    # CLI for sit.sh: `python -m mu.fixtures apply <id> [work_dir]`
    #                 `python -m mu.fixtures skip <model> <toolchain>` -> exit 0=skip
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'apply':
        for p in apply(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '.'):
            print(p)
    elif cmd == 'skip':  # skip <model> <problem-id>  -> exit 0 = skip this problem
        sys.exit(0 if should_skip_problem(sys.argv[2], sys.argv[3]) else 1)
    else:
        sys.exit("usage: mu.fixtures apply <id> [dir] | skip <model> <problem-id>")
