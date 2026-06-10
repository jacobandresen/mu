"""The reflex knowledge base: a rebuildable SQLite store over the session archive.

Four tables (docs/REFLEX_KB.md §6; model profiles: docs/MODELS.md):
  reflex         — the static catalog (from reflexes.registry)
  session        — one row per finalized episode, tagged with its model
  firing         — one row per reflex application (mined from firings.jsonl)
  model_profile  — per-model aggregates: pass rate + failure fingerprint

The DB (`~/.mu/mu.db` by default) is **derived and rebuildable**: the session
archive stays the source of truth, so `build()` can always be re-run from
scratch. Pure stdlib `sqlite3`; the Beta-Binomial intervals come from
`observe.py` (scipy optional).

Layers depend one way: archive (facts) → session/firing (counts) →
model_profile (beliefs). Nothing reaches back up.
"""

import json
import os
import sqlite3
from pathlib import Path

from mu.reflexes.registry import discover
from mu import observe

DEFAULT_DB = os.path.expanduser('~/.mu/mu.db')

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reflex (
  id TEXT PRIMARY KEY, toolchain TEXT, error_class TEXT,
  trigger TEXT, scope TEXT, summary TEXT,
  artifact TEXT,                                   -- curated: target file type
  phase TEXT,                                      -- derived: write/repair/plan
  idempotent INT,                                  -- measured: 1/0/NULL
  risk TEXT,                                       -- curated: low/medium/high
  evidence TEXT,                                   -- curated: motivating problem ids
  efficacy REAL                                    -- mean Δ across ≥3 ablation seeds
);
CREATE TABLE IF NOT EXISTS session (
  session_id TEXT PRIMARY KEY, problem_id TEXT, model TEXT, model_family TEXT,
  outcome TEXT, success INT, repair_iters INT, first_try INT,
  tasks_total INT, prompt_tokens INT, ts TEXT
);
CREATE TABLE IF NOT EXISTS firing (
  session_id TEXT, reflex_id TEXT, file TEXT, pass_index INT,
  phase TEXT,                                      -- derived: write (pass 0) or repair
  ts TEXT,                                         -- session start_time
  FOREIGN KEY(session_id) REFERENCES session(session_id)
);
CREATE TABLE IF NOT EXISTS model_profile (
  model_family TEXT PRIMARY KEY, n_sessions INT,
  pass_rate REAL, pass_lo REAL, pass_hi REAL,
  first_try_rate REAL, avg_repair_iters REAL,
  competence_by_toolchain TEXT,   -- json {toolchain: pass_rate}
  error_class_propensity TEXT,    -- json {error_class: firing_rate}  (fingerprint)
  updated TEXT
);
CREATE TABLE IF NOT EXISTS efficacy_run (
  reflex_id TEXT, seed TEXT,
  baseline_hits INT, baseline_n INT,
  disabled_hits INT, disabled_n INT,
  delta REAL, ts TEXT
);
CREATE INDEX IF NOT EXISTS firing_session ON firing(session_id);
CREATE INDEX IF NOT EXISTS firing_reflex  ON firing(reflex_id);
"""


def connect(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    return con


# ── builders (archive → tables) ───────────────────────────────────────────────

def _load_reflex_catalog(con: sqlite3.Connection) -> None:
    con.executemany(
        "INSERT OR REPLACE INTO reflex"
        "(id,toolchain,error_class,trigger,scope,summary,artifact,phase,idempotent,risk,evidence)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(r.id, r.toolchain, r.error_class, r.trigger, r.scope, r.summary,
          r.artifact, r.phase,
          (1 if r.idempotent else 0) if r.idempotent is not None else None,
          r.risk, r.evidence)
         for r in discover()])


def _load_sessions(con: sqlite3.Connection, sessions: list[dict]) -> None:
    rows = [(
        s['session_id'], s.get('_problem', '?'), s.get('model', ''),
        s.get('_model', ''), s.get('outcome', ''),
        1 if s.get('outcome') == 'success' else 0,
        s.get('repair_iters', 0), 1 if s.get('first_try_pass') else 0,
        s.get('tasks_total', 0), s.get('total_prompt_tokens', 0),
        s.get('start_time', ''),
    ) for s in sessions]
    con.executemany(
        "INSERT OR REPLACE INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)


def _load_firings(con: sqlite3.Connection, sessions_dir: str,
                  session_ts: dict[str, str] | None = None) -> None:
    """Mine firings.jsonl (written by run_reflexes) from each session dir."""
    rows = []
    session_ts = session_ts or {}
    for s_dir in Path(sessions_dir).glob('*'):
        fj = s_dir / 'firings.jsonl'
        if not fj.exists():
            continue
        sid = s_dir.name
        ts = session_ts.get(sid, '')
        for line in fj.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            pass_index = e.get('pass_index', 0)
            phase = 'write' if pass_index == 0 else 'repair'
            rows.append((sid, e.get('reflex_id', ''), e.get('file', ''),
                         pass_index, phase, ts))
    if rows:
        con.executemany("INSERT INTO firing VALUES (?,?,?,?,?,?)", rows)


def _problem_toolchain(con: sqlite3.Connection) -> dict[str, str]:
    """Best-effort toolchain per problem id (from problems-catalog.json)."""
    try:
        from mu.toolchain import load_problems_catalog
        cat = load_problems_catalog(os.path.join(os.getcwd(), 'problems-catalog.json'))
        return {p['id']: (p.get('toolchains') or ['?'])[0] for p in cat}
    except Exception:
        return {}


def _build_model_profiles(con: sqlite3.Connection) -> None:
    """Aggregate per-model: pass-rate (with interval), competence-by-toolchain,
    and the error_class firing fingerprint."""
    import datetime
    p_tool = _problem_toolchain(con)
    families = [r['model_family'] for r in
                con.execute("SELECT DISTINCT model_family FROM session "
                            "WHERE model_family != ''")]
    for fam in families:
        sess = con.execute(
            "SELECT * FROM session WHERE model_family=?", (fam,)).fetchall()
        n = len(sess)
        succ = sum(s['success'] for s in sess)
        post = observe.beta_binomial(succ, n, 0.5)
        first = sum(s['first_try'] for s in sess) / n if n else 0
        avg_rep = sum(s['repair_iters'] for s in sess) / n if n else 0

        # competence per toolchain
        comp: dict[str, list[int]] = {}
        for s in sess:
            tc = p_tool.get(s['problem_id'], '?')
            comp.setdefault(tc, []).append(s['success'])
        competence = {tc: round(sum(v) / len(v), 3) for tc, v in comp.items()}

        # failure fingerprint: error_class firing rate (firings per session)
        fp = {row['error_class']: round(row['c'] / n, 3) for row in con.execute(
            "SELECT r.error_class, COUNT(*) c FROM firing f "
            "JOIN session s USING(session_id) JOIN reflex r ON r.id=f.reflex_id "
            "WHERE s.model_family=? GROUP BY r.error_class", (fam,))} if n else {}

        con.execute(
            "INSERT OR REPLACE INTO model_profile VALUES (?,?,?,?,?,?,?,?,?,?)",
            (fam, n, round(post.rate, 3), round(post.lo, 3), round(post.hi, 3),
             round(first, 3), round(avg_rep, 2),
             json.dumps(competence), json.dumps(fp),
             datetime.datetime.now().isoformat(timespec='seconds')))


def _restore_efficacy_summaries(con: sqlite3.Connection) -> None:
    """Recompute reflex.efficacy from efficacy_run after a rebuild.
    efficacy_run is not dropped on rebuild (it's manually recorded data, not
    derived from the session archive), so this re-applies its summaries."""
    rows = con.execute(
        "SELECT reflex_id, AVG(delta) eff FROM efficacy_run "
        "GROUP BY reflex_id HAVING COUNT(*) >= 3").fetchall()
    for r in rows:
        con.execute("UPDATE reflex SET efficacy=? WHERE id=?", (r['eff'], r['reflex_id']))


def build(db_path: str = DEFAULT_DB, sessions_dir: str | None = None) -> dict:
    """(Re)build the whole KB from the session archive. Idempotent."""
    sessions_dir = sessions_dir or os.path.expanduser('~/.mu/sessions')
    sessions = observe.load_sessions(sessions_dir)
    con = connect(db_path)
    # Drop + recreate the derived tables (not efficacy_run — that holds manually
    # recorded ablation data that must survive a rebuild).
    con.executescript("DROP TABLE IF EXISTS reflex; DROP TABLE IF EXISTS session; "
                      "DROP TABLE IF EXISTS firing; DROP TABLE IF EXISTS model_profile;")
    con.executescript(_SCHEMA)
    _load_reflex_catalog(con)
    _load_sessions(con, sessions)
    session_ts = {s['session_id']: s.get('start_time', '') for s in sessions}
    _load_firings(con, sessions_dir, session_ts)
    _build_model_profiles(con)
    _restore_efficacy_summaries(con)
    con.commit()
    counts = {t: con.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()['c']
              for t in ('reflex', 'session', 'firing', 'model_profile', 'efficacy_run')}
    con.close()
    return counts


# ── efficacy ──────────────────────────────────────────────────────────────────

def sz5_gate(deltas: list[float]) -> bool:
    """§5z: return True if the 95% CI of per-seed Δ values excludes 0.

    Requires ≥3 seeds. Uses a normal approximation to the sampling distribution
    of the mean — adequate for ablation decisions at this N. A pure function:
    no DB, no LLM, testable on synthetic data."""
    if len(deltas) < 3:
        return False
    import math
    n = len(deltas)
    mean = sum(deltas) / n
    variance = sum((d - mean) ** 2 for d in deltas) / (n - 1) if n > 1 else 0.0
    if variance == 0.0:
        return mean != 0.0
    se = math.sqrt(variance / n)
    lo = mean - 1.96 * se
    hi = mean + 1.96 * se
    return lo > 0.0 or hi < 0.0


def record_efficacy(reflex_id: str, seed: str,
                    baseline_hits: int, baseline_n: int,
                    disabled_hits: int, disabled_n: int,
                    db_path: str = DEFAULT_DB) -> None:
    """Persist one ablation seed's result (baseline vs disabled) into efficacy_run.

    After ≥3 seeds are recorded for a reflex, recomputes and stores the mean Δ
    in reflex.efficacy. Use sz5_gate() to decide whether the Δ is significant."""
    import datetime
    b_rate = baseline_hits / baseline_n if baseline_n else 0.0
    d_rate = disabled_hits / disabled_n if disabled_n else 0.0
    delta = d_rate - b_rate  # negative → reflex helped; positive → reflex hurt
    ts = datetime.datetime.now().isoformat(timespec='seconds')
    con = connect(db_path)
    con.execute("INSERT INTO efficacy_run VALUES (?,?,?,?,?,?,?,?)",
                (reflex_id, seed, baseline_hits, baseline_n,
                 disabled_hits, disabled_n, delta, ts))
    runs = con.execute(
        "SELECT delta FROM efficacy_run WHERE reflex_id=?", (reflex_id,)).fetchall()
    if len(runs) >= 3:
        eff = sum(r['delta'] for r in runs) / len(runs)
        con.execute("UPDATE reflex SET efficacy=? WHERE id=?", (eff, reflex_id))
    con.commit()
    con.close()


# ── reporting ─────────────────────────────────────────────────────────────────

def combination_report(con: sqlite3.Connection) -> list[str]:
    """The §7 combination analysis over the `firing` table: per-reflex conditional
    success (interval-aware, via the Beta-Binomial), which reflexes co-fire, and
    which fire in sequence. Observational and confounded — a ranking of hypotheses
    to ablate (§9), never a causal claim. Returns report lines (empty if no firings).
    """
    if not con.execute("SELECT 1 FROM firing LIMIT 1").fetchone():
        return []
    base = con.execute("SELECT AVG(success) r FROM session").fetchone()['r'] or 0.5
    out = ["", "## Combination analysis",
           "_Observational (a reflex fires *because* the model erred) — hypotheses to "
           "ablate, not proof. See §9._",
           "", f"### Conditional success P(✓ | reflex)  ·  base rate {base:.2f}"]

    # One (session, reflex, outcome) row per session a reflex fired in (a reflex can
    # fire several times per session — collapse to distinct sessions before averaging).
    summaries = {row['id']: row['summary']
                 for row in con.execute("SELECT id, summary FROM reflex")}
    rows = con.execute(
        "SELECT reflex_id, SUM(success) hits, COUNT(*) n FROM ("
        "  SELECT DISTINCT f.session_id, f.reflex_id, s.success"
        "  FROM firing f JOIN session s USING(session_id)"
        ") GROUP BY reflex_id ORDER BY n DESC").fetchall()
    shortlist = []  # (n, reflex_id): enough data, but effect not yet distinguishable
    for r in rows:
        post = observe.beta_binomial(r['hits'] or 0, r['n'], base)
        desc = summaries.get(r['reflex_id'])
        out.append(f"- `{r['reflex_id']}`  {post}" + (f" — {desc}" if desc else ""))
        if post.enough and post.lo <= base <= post.hi:
            shortlist.append((r['n'], r['reflex_id']))

    if shortlist:
        # The posteriors order which ablations to run first (§8.3, §9): a reflex whose
        # interval still contains the base rate has no *distinguishable* effect in the
        # (confounded) firing data — ablation is the only way to decide. Most-fired
        # first, since ablating those resolves the most.
        risks = {row['id']: row['risk'] for row in
                 con.execute("SELECT id, risk FROM reflex")}
        out += ["", "### Ablation shortlist — effect not yet distinguishable from base",
                "_Run a seeded frozen baseline with/without each, compare Δ (§9):_",
                "```sh",
                "mu dojo measure <problem> --runs 5 --seed 42 --disable " + shortlist[0][1],
                "```"]
        for n, rid in sorted(shortlist, reverse=True):
            risk = risks.get(rid, 'low')
            risk_tag = f" ⚠ risk={risk}" if risk != 'low' else ''
            out.append(f"- `{rid}` (fired in {n} sessions){risk_tag}")

    pairs = con.execute(
        "SELECT a.reflex_id x, b.reflex_id y, COUNT(DISTINCT a.session_id) n "
        "FROM firing a JOIN firing b "
        "  ON a.session_id=b.session_id AND a.reflex_id < b.reflex_id "
        "GROUP BY 1,2 ORDER BY n DESC LIMIT 10").fetchall()
    if pairs:
        out += ["", "### Co-occurrence (reflexes that fire together, top 10)"]
        out += [f"- `{p['x']}` + `{p['y']}`  ×{p['n']}" for p in pairs]

    seq = con.execute(
        "SELECT a.reflex_id before_, b.reflex_id after_, COUNT(DISTINCT a.session_id) n "
        "FROM firing a JOIN firing b "
        "  ON a.session_id=b.session_id AND a.pass_index < b.pass_index "
        "     AND a.reflex_id != b.reflex_id "
        "GROUP BY 1,2 ORDER BY n DESC LIMIT 10").fetchall()
    if seq:
        out += ["", "### Sequence (A fires on an earlier pass than B, top 10)"]
        out += [f"- `{s['before_']}` → `{s['after_']}`  ×{s['n']}" for s in seq]
    return out


def report(db_path: str = DEFAULT_DB) -> str:
    con = connect(db_path)
    out = ["# Reflex KB", ""]
    n_reflex = con.execute("SELECT COUNT(*) c FROM reflex").fetchone()['c']
    out.append(f"{n_reflex} reflexes cataloged, by error_class:")
    for row in con.execute("SELECT error_class, COUNT(*) c FROM reflex "
                           "GROUP BY 1 ORDER BY c DESC"):
        out.append(f"  {row['c']:2}  {row['error_class']}")

    prof = con.execute("SELECT * FROM model_profile ORDER BY n_sessions DESC").fetchall()
    if prof:
        out += ["", "## Model profiles"]
        for p in prof:
            out.append(f"- **{p['model_family']}**  n={p['n_sessions']}  "
                       f"pass {p['pass_rate']:.2f} [{p['pass_lo']:.2f},{p['pass_hi']:.2f}]  "
                       f"first-try {p['first_try_rate']:.2f}  "
                       f"avg-repair {p['avg_repair_iters']:.1f}")
            out.append(f"    competence: {p['competence_by_toolchain']}")
            out.append(f"    fingerprint: {p['error_class_propensity']}")
    else:
        out += ["", "_No model-tagged sessions yet — run the dojo with the new "
                "code (each session now records its model)._"]

    # Efficacy summary — only show rows with recorded ablation data
    eff_rows = con.execute(
        "SELECT r.id, r.efficacy, COUNT(e.reflex_id) seeds "
        "FROM reflex r LEFT JOIN efficacy_run e ON e.reflex_id=r.id "
        "WHERE r.efficacy IS NOT NULL GROUP BY r.id "
        "ORDER BY r.efficacy").fetchall()
    if eff_rows:
        out += ["", "## Ablation efficacy (mean Δ = disabled − baseline, ≥3 seeds)"]
        for row in eff_rows:
            direction = "helped" if row['efficacy'] < 0 else "hurt"
            out.append(f"- `{row['id']}`  Δ={row['efficacy']:+.3f}  "
                       f"({row['seeds']} seeds, {direction})")

    out += combination_report(con)
    con.close()
    return '\n'.join(out)


if __name__ == '__main__':
    counts = build()
    print("built KB:", counts, "\n")
    print(report())
