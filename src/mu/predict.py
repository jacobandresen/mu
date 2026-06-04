"""Doomed-session predictor: estimate P(success) from features known *before*
the expensive work, so a caller can abort or down-scope a run unlikely to pass.

Honest by construction: features come only from the goal text, the planned task
count, and the iteration budget — all available at plan time. Outcome-derived
fields (tasks_done, repair_iters, durations, token totals) are deliberately
excluded; using them would leak the label and inflate accuracy.

Optional dependency: scikit-learn. ``train`` and ``predict_success_proba`` raise
a clear message if it is not installed; the agent never imports this at runtime
unless MU_PREDICT is set.
"""

import json
import os
import re
from pathlib import Path

_MODEL_PATH = Path.home() / '.mu' / 'predictor.pkl'

# Signals scanned in the goal text. Kept explicit and interpretable rather than
# learned embeddings — the dataset is ~1k rows, so a compact hand-built feature
# vector generalizes better and stays debuggable.
_LANG_SIGNALS = ('python', 'flask', 'pytest', 'sqlite', ' c ', 'clang', 'sdl2',
                 'c#', 'csharp', 'dotnet', '.net', 'go ', 'gin', 'rust', 'cargo',
                 'javascript', 'node', 'jest', 'typescript', 'vue', 'vite',
                 'vitest', 'react')
_COMPLEXITY_SIGNALS = ('api', 'database', 'server', 'rest', 'endpoint', 'test',
                       'webapp', 'web app', 'blog', 'full-stack', 'frontend',
                       'backend', 'multiple', 'crud')

FEATURE_NAMES = (
    ['tasks_total', 'max_iterations', 'goal_words', 'goal_len',
     'n_complexity', 'n_lang_signals']
    + [f'lang::{s.strip()}' for s in _LANG_SIGNALS]
)


def featurize(goal: str, tasks_total: int, max_iterations: int) -> list[float]:
    """Build the fixed numeric feature vector for one (prospective) run."""
    g = (goal or '').lower()
    lang_flags = [1.0 if s in g else 0.0 for s in _LANG_SIGNALS]
    n_complexity = sum(1 for s in _COMPLEXITY_SIGNALS if s in g)
    return [
        float(tasks_total or 0),
        float(max_iterations or 0),
        float(len(re.findall(r'\w+', g))),
        float(len(g)),
        float(n_complexity),
        float(sum(lang_flags)),
        *lang_flags,
    ]


def _iter_sessions(sessions_dir: Path):
    for meta in sessions_dir.glob('*/meta.json'):
        try:
            yield json.loads(meta.read_text())
        except (OSError, json.JSONDecodeError):
            continue


def load_dataset(sessions_dir: Path | None = None):
    """Return (X, y) where y=1 for success, 0 otherwise. Skips rows missing the
    early features so the matrix is clean."""
    sessions_dir = sessions_dir or (Path.home() / '.mu' / 'sessions')
    X, y = [], []
    for d in _iter_sessions(sessions_dir):
        outcome = d.get('outcome')
        if outcome not in ('success', 'stalled', 'error', 'max_iterations'):
            continue  # skip interrupted/unknown — not a clean win/loss label
        if d.get('tasks_total') is None:
            continue
        X.append(featurize(d.get('goal', ''), d.get('tasks_total', 0),
                           d.get('max_iterations', 0)))
        y.append(1 if outcome == 'success' else 0)
    return X, y


def train(sessions_dir: Path | None = None, verbose: bool = True) -> dict:
    """Train, cross-validate, and persist the model. Returns a metrics dict.

    Reports against the majority-class baseline so the model's real lift (or lack
    of it) is visible rather than hidden behind a raw accuracy number.
    """
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_predict, cross_val_score
        from sklearn.metrics import roc_auc_score, classification_report
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        import joblib
    except ImportError as e:
        raise RuntimeError(f"scikit-learn not installed: {e}. "
                           f"Run: pip install scikit-learn joblib") from e

    X, y = load_dataset(sessions_dir)
    if len(X) < 50:
        raise RuntimeError(f"only {len(X)} labeled sessions — too few to train")
    X, y = np.array(X), np.array(y)
    baseline = max(y.mean(), 1 - y.mean())  # majority-class accuracy

    candidates = {
        'logreg': make_pipeline(StandardScaler(),
                                LogisticRegression(max_iter=1000, class_weight='balanced')),
        'rf': RandomForestClassifier(n_estimators=200, max_depth=8,
                                     class_weight='balanced', random_state=0),
    }
    results = {}
    for name, model in candidates.items():
        acc = cross_val_score(model, X, y, cv=5, scoring='accuracy').mean()
        proba = cross_val_predict(model, X, y, cv=5, method='predict_proba')[:, 1]
        auc = roc_auc_score(y, proba)
        results[name] = {'cv_accuracy': float(acc), 'cv_auc': float(auc)}

    best = max(results, key=lambda n: results[n]['cv_auc'])
    model = candidates[best].fit(X, y)
    _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': model, 'features': FEATURE_NAMES}, _MODEL_PATH)

    metrics = {
        'n_samples': int(len(y)),
        'success_rate': float(y.mean()),
        'majority_baseline_acc': float(baseline),
        'models': results,
        'best': best,
        'best_auc': results[best]['cv_auc'],
        'best_acc': results[best]['cv_accuracy'],
        'lift_over_baseline': float(results[best]['cv_accuracy'] - baseline),
    }
    if verbose:
        print(f"samples={metrics['n_samples']}  success_rate={metrics['success_rate']:.2%}")
        print(f"majority baseline acc = {baseline:.2%}")
        for name, r in results.items():
            print(f"  {name:7} cv_acc={r['cv_accuracy']:.2%}  cv_auc={r['cv_auc']:.3f}")
        print(f"best={best}  acc lift over baseline = {metrics['lift_over_baseline']:+.2%}")
        proba = cross_val_predict(candidates[best], X, y, cv=5, method='predict_proba')[:, 1]
        print("\nclassification report (stalled=0 / success=1):")
        print(classification_report(y, (proba >= 0.5).astype(int),
                                    target_names=['stalled', 'success'], zero_division=0))
    return metrics


def recommend_plan_expansion(goal: str, tasks_total: int, max_iterations: int = 10,
                             delta: int = 2, min_gain: float = 0.05) -> dict | None:
    """Counterfactual: would a larger plan raise P(success) for this goal?

    Reuses the trained P(success) model, holding the goal fixed and varying only
    the task count. If predicted success rises by at least *min_gain* when the
    plan grows by *delta* tasks, recommend expansion. This is honest about the
    data: plan size is confounded with difficulty, so for most goals the model
    finds little or negative gain — and this function will say so rather than
    reflexively recommending more tasks.

    Returns {'expand': bool, 'current_proba', 'expanded_proba', 'gain',
    'suggested_tasks'} or None if no model is trained.
    """
    base = predict_success_proba(goal, tasks_total, max_iterations)
    if base is None:
        return None
    bigger = predict_success_proba(goal, tasks_total + delta, max_iterations)
    if bigger is None:
        return None
    gain = bigger - base
    return {
        'expand': gain >= min_gain,
        'current_proba': base,
        'expanded_proba': bigger,
        'gain': gain,
        'suggested_tasks': tasks_total + delta if gain >= min_gain else tasks_total,
    }


def predict_success_proba(goal: str, tasks_total: int, max_iterations: int) -> float | None:
    """P(success) for a prospective run, or None if no model is trained."""
    if not _MODEL_PATH.exists():
        return None
    try:
        import joblib
        bundle = joblib.load(_MODEL_PATH)
        return float(bundle['model'].predict_proba(
            [featurize(goal, tasks_total, max_iterations)])[0][1])
    except Exception:
        return None


if __name__ == '__main__':
    train()
