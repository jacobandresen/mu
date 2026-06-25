#!/usr/bin/env python
"""Analyze the SCAFFOLD lever A/B arms → KEEP/DROP (scaffolding.md §5).

Reuses the project's Beta-Binomial prior (matching observe.beta_binomial) and the CI of
the ON−OFF difference by posterior-difference sampling (stdlib only) — same machinery as
.mu/abl_tfm_analyze.py / abl_ep_analyze.py. Quantitative gates only; the mechanistic NU1202
first-error scan is the separate zero-LLM secondary (nu1202_diagnosis.md).
"""
import json
import random
from pathlib import Path

MU = Path(__file__).resolve().parent
DRAWS = 60000
random.seed(0)


def load(name):
    p = MU / name
    return json.loads(p.read_text()) if p.exists() else None


def _beta_ab(hits, n, base=0.5):
    return 2 * base + hits, 2 * base + (n - hits)


def diff_ci(h_on, n_on, h_off, n_off):
    a1, b1 = _beta_ab(h_on, n_on)
    a0, b0 = _beta_ab(h_off, n_off)
    s = sorted(random.betavariate(a1, b1) - random.betavariate(a0, b0)
               for _ in range(DRAWS))
    return sum(s) / DRAWS, s[int(0.025 * DRAWS)], s[int(0.975 * DRAWS)]


def _layer(stat, layer, default_n):
    s = stat.get('layers', {}).get(layer, {})
    return s.get('clears', 0), s.get('n', stat.get('n', default_n))


def control(out, title, on, off, must_not_fire=False):
    """No-regression gate (pre-registered §4.5): veto only on demonstrated harm — at N=15
    the binary pass-rate CI is ~±0.28, so operative gate = point Δ ≥ −0.05 ∧ CI hi ≥ −0.05."""
    if not (on and off):
        out.append(f'\n## {title} — INCOMPLETE (arm JSON missing)')
        return None
    d, lo, hi = diff_ci(on['hits'], on['n'], off['hits'], off['n'])
    ok = (d >= -0.05) and (hi >= -0.05)
    out.append(f'\n## {title} — pass-rate\n'
               f'ON {on["hits"]}/{on["n"]} ({on["pass_rate"]:.2f}) vs '
               f'OFF {off["hits"]}/{off["n"]} ({off["pass_rate"]:.2f}) · '
               f'Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}] · '
               f'{"PASS" if ok else "FAIL"}')
    if must_not_fire:
        out.append('  _recipe-never-fires check: confirm `meta.json.scaffold` is null on '
                   'every ON-arm run (non-dotnet ⇒ no recipe matches)._')
    return ok


def main():
    p10_on, p10_off = load('abl_scaffold_p10_on.json'), load('abl_scaffold_p10_off.json')
    p10_tfm = load('abl_scaffold_p10_tfm.json')
    p4_on, p4_off = load('abl_scaffold_p4_on.json'), load('abl_scaffold_p4_off.json')
    p1_on, p1_off = load('abl_scaffold_p1_on.json'), load('abl_scaffold_p1_off.json')
    p2_on, p2_off = load('abl_scaffold_p2_on.json'), load('abl_scaffold_p2_off.json')

    out = ['# SCAFFOLD lever A/B — scaffolding.md §5 backend_build\n',
           'model `qwen2.5-coder-7b-instruct` · level L2 (I3) · '
           'ON = MU_SCAFFOLD=1 (dotnet-webapi,dotnet-xunit) · OFF = unset · '
           'entry-point + S2 + TFM held off\n']

    keep1 = gate1_lo = None
    if p10_on and p10_off:
        out.append('\n## p10-dotnet-vue-blog — per-layer q̂ (ON = scaffolded backend)\n')
        out.append('| layer | ON clears | OFF clears | Δq̂ (ON−OFF) | 95% CI |\n|---|---|---|---|---|')
        for layer in ('backend_build', 'backend_test', 'frontend_build', 'frontend_test'):
            ho, no = _layer(p10_on, layer, p10_on['n'])
            hf, nf = _layer(p10_off, layer, p10_off['n'])
            d, lo, hi = diff_ci(ho, no, hf, nf)
            mark = ' **←gate**' if layer == 'backend_build' else ''
            out.append(f'| {layer}{mark} | {ho}/{no} | {hf}/{nf} | {d:+.3f} | [{lo:+.3f}, {hi:+.3f}] |')
            if layer == 'backend_build':
                keep1, gate1_lo = lo > 0, lo
        out.append(f'\np_solve: ON {p10_on.get("p_solve")} vs OFF {p10_off.get("p_solve")} · '
                   f'pass-rate ON {p10_on["pass_rate"]:.2f} vs OFF {p10_off["pass_rate"]:.2f} · '
                   f'repair-iters ON {p10_on["avg_repair_iters"]:.1f} vs OFF {p10_off["avg_repair_iters"]:.1f}')
    else:
        out.append('\n## p10 — INCOMPLETE (arm JSON missing)')

    # Arm 3 — prevent (scaffold) vs repair (TFM-grounding) at the same wall (reported).
    if p10_on and p10_tfm:
        ho, no = _layer(p10_on, 'backend_build', p10_on['n'])
        ht, nt = _layer(p10_tfm, 'backend_build', p10_tfm['n'])
        d, lo, hi = diff_ci(ho, no, ht, nt)
        out.append('\n## Arm 3 — prevent vs repair (p10 backend_build)\n'
                   f'SCAFFOLD {ho}/{no} vs TFM-grounding {ht}/{nt} · '
                   f'Δq̂ (SCAF−TFM) {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}] '
                   '(reported; ship whichever clears restore more reliably, never both)')

    keep_p4 = control(out, 'p4-fibonacci (dotnet control)', p4_on, p4_off)
    keep_p1 = control(out, 'p1-helloworld (non-dotnet control)', p1_on, p1_off, must_not_fire=True)
    keep_p2 = control(out, 'p2-sqlite (non-dotnet control)', p2_on, p2_off, must_not_fire=True)

    controls = [c for c in (keep_p4, keep_p1, keep_p2) if c is not None]
    keep2 = all(controls) if controls else None

    out.append('\n## Verdict\n')
    if keep1 is None:
        out.append('INCOMPLETE — the p10 headline arms are missing; rerun before deciding.')
    else:
        out.append(f'- Gate 1 (p10 backend_build Δq̂ CI lo > 0): '
                   f'{"PASS" if keep1 else "FAIL"} (lo={gate1_lo:+.3f})')
        if keep2 is None:
            # Headline-only run: P2 was not measured. P1 still decides the *mechanism*; the
            # no-regression check must run before actually flipping the default on.
            out.append('- Gate 2 (controls p4/p1/p2): **not evaluated** (headline-only run)')
            if keep1:
                out.append('\n**PROVISIONAL KEEP — scaffolding lifts p10 backend_build (P1 '
                           'PASS). Run the p4/p1/p2 controls (no-regression + recipe-never-'
                           'fires) before flipping MU_SCAFFOLD on by default; then settle '
                           'Arm 3 (prevent vs repair) vs MU_TFM_GROUNDING.**')
            else:
                out.append('\n**INCONCLUSIVE at N=15 (P1 CI-lo ≤ 0). Check the mechanistic '
                           'secondary (did NU1202/NETSDK1226 drop from the ON arm?): if restore '
                           'cleared but compilation re-binds on CS0246/CS0101, re-run '
                           'entry-point + S2 with the wall now reachable (scaffolding.md §5).**')
        else:
            out.append(f'- Gate 2 (controls p4/p1/p2: no proven regression): '
                       f'{"PASS" if keep2 else "FAIL"}')
            if keep1 and keep2:
                out.append('\n**KEEP — scaffolding lifts backend_build (prevent side clears the '
                           'restore wall); flip MU_SCAFFOLD on by default with '
                           'MU_SCAFFOLD_STACKS=dotnet-webapi,dotnet-xunit, record efficacy Δ. '
                           'Settle Arm 3 (prevent vs repair) before shipping TFM too.**')
            elif keep2:
                out.append('\n**STAYS OPT-IN — no significant backend_build lift at N=15. Check the '
                           'mechanistic secondary (did NU1202/NETSDK1226 drop?): if restore cleared '
                           'but compilation re-binds on CS0246/CS0101, re-run entry-point + S2 with '
                           'the wall now reachable (scaffolding.md §5 close).**')
            else:
                out.append('\n**REVERT — a control regressed; scaffolding is doing harm off the '
                           'dotnet-web path (unexpected — investigate which recipe fired).**')

    text = '\n'.join(out) + '\n'
    (MU / 'abl_scaffold_verdict.md').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
