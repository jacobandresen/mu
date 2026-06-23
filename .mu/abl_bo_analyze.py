#!/usr/bin/env python
"""Analyze the MU_BUILD_ORDER A/B → KEEP/DROP (plan Step 0.6 / S6).

Per-problem Beta-Binomial posterior-difference sampling (stdlib), summed for the
set objective E[#solved]. Reports pass-rate (P1/P2) and the efficiency secondary
(repair-iters), since build-order's plausible payoff on easy problems is fewer
redundant gate runs, not higher pass-rate.
"""
import json
import random
from pathlib import Path

MU = Path(__file__).resolve().parent
PROBLEMS = ['p1-helloworld', 'p2-sqlite', 'p3-sdl2']
CONTROLS = {'p1-helloworld'}
DRAWS = 60000
random.seed(0)


def load(pid, arm):
    p = MU / f'abl_bo_{pid}_{arm}.json'
    return json.loads(p.read_text()) if p.exists() else None


def _beta_ab(hits, n, base=0.5):
    return 2 * base + hits, 2 * base + (n - hits)


def diff_samples(h_on, n_on, h_off, n_off):
    a1, b1 = _beta_ab(h_on, n_on)
    a0, b0 = _beta_ab(h_off, n_off)
    return [random.betavariate(a1, b1) - random.betavariate(a0, b0)
            for _ in range(DRAWS)]


def pct(sorted_s, q):
    return sorted_s[int(q * len(sorted_s))]


def main():
    out = ['# MU_BUILD_ORDER A/B result — plan Step 0.6 / S6\n',
           'model `qwen2.5-coder-7b-instruct` · N per arm as recorded\n',
           '\n| problem | ON | OFF | Δpass | 95% CI | Δrepair-iters |\n|---|---|---|---|---|---|']
    set_diff = [0.0] * DRAWS
    complete = True
    control_ok = True
    for pid in PROBLEMS:
        on, off = load(pid, 'on'), load(pid, 'off')
        if not on or not off:
            out.append(f'| {pid} | — | — | INCOMPLETE | | |')
            complete = False
            continue
        ds = diff_samples(on['hits'], on['n'], off['hits'], off['n'])
        s = sorted(ds)
        d, lo, hi = sum(ds) / DRAWS, pct(s, 0.025), pct(s, 0.975)
        for i in range(DRAWS):
            set_diff[i] += ds[i]
        dr = on['avg_repair_iters'] - off['avg_repair_iters']
        tag = ' (control)' if pid in CONTROLS else ''
        out.append(f'| {pid}{tag} | {on["hits"]}/{on["n"]} | {off["hits"]}/{off["n"]} | '
                   f'{d:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {dr:+.2f} |')
        # P2: no regression (point Δ ≥ −0.05 ∧ no proven harm)
        if not (d >= -0.05 and hi >= -0.05):
            control_ok = False

    if complete:
        ss = sorted(set_diff)
        es, es_lo, es_hi = sum(set_diff) / DRAWS, pct(ss, 0.025), pct(ss, 0.975)
        out.append(f'\n**ΔE[#solved] = {es:+.3f}  95% CI [{es_lo:+.3f}, {es_hi:+.3f}]**')
        p1_pass = es_lo > 0
        out.append('\n## Verdict\n')
        out.append(f'- P1 (ΔE[#solved] CI lo > 0): {"PASS" if p1_pass else "FAIL"} (lo={es_lo:+.3f})')
        out.append(f'- P2 (no problem regressed): {"PASS" if control_ok else "FAIL"}')
        if p1_pass and control_ok:
            verdict = 'KEEP — MU_BUILD_ORDER on by default'
        elif control_ok:
            verdict = ('NO pass-rate lift on these easy problems (expected, prereg) — '
                       'stays opt-in; check the Δrepair-iters column for the efficiency '
                       'story, and re-test on hard multi-layer goals once p10 builds')
        else:
            verdict = 'REGRESSION detected — keep opt-in, investigate'
        out.append(f'\n**{verdict}**')
    else:
        out.append('\nINCOMPLETE — rerun missing arms.')

    text = '\n'.join(out) + '\n'
    (MU / 'abl_bo_verdict.md').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
