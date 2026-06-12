"""Model-stratified observations: was a failure mode recorded under granite or
qwen, and is it valid for each?

A weak model's mistakes are model-specific — granite emits tool calls as text and
falls into token loops; qwen over-engineers plans and mixes ESM/CJS. So a lesson
(a failure cause, a reflex's relevance) learned from one model may not hold for
another. This module reads the session archive — each ``meta.json`` records the
``model`` that produced it (see archive.AgentSession) — groups observations by
model, and estimates, with a credible interval, how often each observation occurs
*for that model*. That lets a reader argue: "this is a qwen failure mode (0.55
[0.34, 0.74], n=20), not a granite one (0.05 [0.00, 0.21], n=18)."

The estimate is a Beta-Binomial posterior with a weak prior toward the model's
own base rate (so a lucky 3/3 doesn't masquerade as certainty). This is
*observational* evidence — it says where a pattern *occurs*, not that a reflex
*causes* a fix; the causal test stays `mu dojo measure` ablation (docs/REFLEX_KB.md §9).
"""

import glob
import json
import math
import os
import re as _re
from dataclasses import dataclass
from pathlib import Path

# Below this many observations for a (model, key) cell, we don't claim anything —
# the interval is too wide to argue validity either way.
_MIN_N = 5


def _model_key(raw: str) -> str:
    """Collapse a full model id to a short, stable family name."""
    r = (raw or '').lower()
    if 'granite' in r:
        return 'granite'
    if 'qwen2.5' in r or 'qwen2_5' in r:
        return 'qwen2.5'
    if 'devstral' in r:
        return 'devstral'
    if 'mistral' in r:
        return 'mistral'
    return raw or 'unknown'


@dataclass
class Posterior:
    """A rate estimate with uncertainty: mean and a 95% credible interval."""
    rate: float   # posterior mean
    lo: float     # 2.5% credible bound
    hi: float     # 97.5% credible bound
    n: int        # observations the estimate is based on

    @property
    def enough(self) -> bool:
        return self.n >= _MIN_N

    def __str__(self) -> str:
        if not self.enough:
            return f"insufficient data (n={self.n})"
        return f"{self.rate:.2f} [{self.lo:.2f}, {self.hi:.2f}] (n={self.n})"


def beta_binomial(hits: int, n: int, base_rate: float = 0.5) -> Posterior:
    """Posterior rate of a Bernoulli event from *hits*/*n*, shrunk toward
    *base_rate* by a weak Beta prior worth ~2 pseudo-observations.

    The 95% interval uses scipy's exact Beta quantiles when available, else a
    normal approximation to the Beta posterior (clamped to [0, 1]) — adequate for
    a report and dependency-free.
    """
    a0, b0 = 2 * base_rate, 2 * (1 - base_rate)
    a, b = a0 + hits, b0 + (n - hits)
    mean = a / (a + b)
    try:
        from scipy.stats import beta as _beta  # optional, exact
        lo, hi = _beta.ppf(0.025, a, b), _beta.ppf(0.975, a, b)
    except Exception:
        var = a * b / ((a + b) ** 2 * (a + b + 1))
        sd = math.sqrt(var)
        lo, hi = max(0.0, mean - 1.96 * sd), min(1.0, mean + 1.96 * sd)
    return Posterior(rate=mean, lo=lo, hi=hi, n=n)


def load_sessions(sessions_dir: str | None = None) -> list[dict]:
    """Return finalized session metas that record a model, newest first."""
    sessions_dir = sessions_dir or os.path.expanduser('~/.mu/sessions')
    out = []
    for meta_path in glob.glob(os.path.join(sessions_dir, '*', 'meta.json')):
        try:
            m = json.loads(Path(meta_path).read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not m.get('model') or m.get('outcome') in (None, 'unknown'):
            continue
        m['_model'] = _model_key(m['model'])
        m['_problem'] = os.path.basename(m.get('project_dir', '')) or '?'
        out.append(m)
    out.sort(key=lambda m: m.get('start_time', ''), reverse=True)
    return out


def failure_rate_by_model(sessions: list[dict], key: str = '_problem'
                          ) -> dict[str, dict[str, Posterior]]:
    """For each model, the failure-rate posterior of each observation *key*
    (default: per dojo problem). ``result[model][key] -> Posterior``."""
    # group: model -> key -> [is_failure]
    cells: dict[str, dict[str, list[int]]] = {}
    base: dict[str, list[int]] = {}
    for s in sessions:
        model = s['_model']
        failed = 0 if s.get('outcome') == 'success' else 1
        base.setdefault(model, []).append(failed)
        cells.setdefault(model, {}).setdefault(s.get(key, '?'), []).append(failed)
    result: dict[str, dict[str, Posterior]] = {}
    for model, keys in cells.items():
        base_rate = sum(base[model]) / len(base[model])
        result[model] = {
            k: beta_binomial(sum(v), len(v), base_rate) for k, v in keys.items()
        }
    return result


def argue_validity(sessions: list[dict], key: str = '_problem') -> str:
    """Human-readable report arguing, per observation, which models it is valid
    for — i.e. where the failure occurs with enough evidence to claim it."""
    rates = failure_rate_by_model(sessions, key)
    models = sorted(rates)
    if not models:
        return ("No model-tagged sessions yet. Run the dojo with the new code "
                "(meta.json now records 'model'); e.g.\n"
                "  mu dojo practice --model ibm/granite-4.1-3b\n"
                "  mu dojo practice --model qwen/qwen2.5-coder-7b-instruct")
    # union of observation keys
    keys = sorted({k for m in models for k in rates[m]})
    lines = [f"Failure-rate by model (observation = {key.lstrip('_')}), "
             f"models: {', '.join(models)}", ""]
    for k in keys:
        lines.append(f"## {k}")
        verdict = []
        for m in models:
            p = rates[m].get(k)
            if p is None:
                lines.append(f"  {m:10} (not run)")
                continue
            lines.append(f"  {m:10} {p}")
            if p.enough and p.lo > 0.25:
                verdict.append(m)
        if verdict:
            lines.append(f"  → a {', '.join(verdict)} failure mode")
        lines.append("")
    return '\n'.join(lines)


def _cause_signature(focus: str) -> str:
    """Normalize a distilled FOCUS cause to a *class* signature so near-identical
    failures group together: drop the quoted identifier, the file, and the line
    numbers, keeping the shape (e.g. "undefined name 'json'" and "undefined name
    'app'" both become "undefined name 'X'")."""
    # FOCUS format: "FOCUS (most likely causes, in order):\n  - <cause>\n  - ..."
    # The first line is just the header; extract the first bullet for the signature.
    lines = focus.splitlines()
    raw = ''
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- '):
            raw = stripped[2:]
            break
    if not raw:
        # Fallback: strip FOCUS header from first line (old single-line format)
        raw = _re.sub(r'^FOCUS[^:]*:\s*', '', lines[0])
    s = _re.sub(r"'[^']*'", "'X'", raw)
    s = _re.sub(r'`[^`]*`', '`X`', s)
    s = _re.sub(r'\S+\.\w+:\d+', 'FILE:N', s)
    s = _re.sub(r'\b\d+\b', 'N', s)
    return s.strip()[:90]


def _distill_session(session_dir: str) -> str:
    """Distilled cause signature for a failed session, from its newest log."""
    from mu.diagnose import distill_test_errors
    logs = sorted(glob.glob(os.path.join(session_dir, 'logs', 'tests*.log')) +
                  glob.glob(os.path.join(session_dir, 'logs', 'lint*.log')),
                  key=lambda p: os.path.getmtime(p), reverse=True)
    # Lowest priority: the teed agent event log. Sessions that die before the
    # test phase (planner HTTP errors, writer stalls) leave no tests*/lint*
    # logs at all — agent.log is the only distillable record they have.
    logs += sorted(glob.glob(os.path.join(session_dir, 'logs', 'agent*.log')))
    if not logs:
        return '(no test log)'
    blank_seen = False
    for log in logs:
        try:
            text = Path(log).read_text(errors='replace')
        except OSError:
            continue
        if not text.strip():
            blank_seen = True
            continue
        focus = distill_test_errors(text)
        if focus:
            return _cause_signature(focus)
    if blank_seen:
        return '(test log empty)'
    return '(no distilled cause)'


def failure_causes_by_model(sessions_dir: str | None = None
                            ) -> dict[str, dict[str, int]]:
    """For each model, count how often each distilled cause *signature* appears
    among its FAILED sessions. The candidate-finder: a signature that recurs for
    a model and is deterministically fixable is the next reflex to write."""
    sessions_dir = sessions_dir or os.path.expanduser('~/.mu/sessions')
    by_model: dict[str, dict[str, int]] = {}
    for s in load_sessions(sessions_dir):
        if s.get('outcome') == 'success':
            continue
        sig = _distill_session(os.path.join(sessions_dir, s['session_id']))
        by_model.setdefault(s['_model'], {}).setdefault(sig, 0)
        by_model[s['_model']][sig] += 1
    return by_model


def causes_report(sessions_dir: str | None = None) -> str:
    """Ranked per-model failure-cause signatures — what to turn into reflexes."""
    by_model = failure_causes_by_model(sessions_dir)
    if not by_model:
        return "No model-tagged failures yet."
    out = ["# Failure causes by model (candidate reflexes)", ""]
    for model in sorted(by_model):
        out.append(f"## {model}")
        for sig, n in sorted(by_model[model].items(), key=lambda kv: -kv[1]):
            out.append(f"  {n:3}  {sig}")
        out.append("")
    return '\n'.join(out)


if __name__ == '__main__':
    print(argue_validity(load_sessions()))
    print()
    print(causes_report())
