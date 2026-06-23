#!/usr/bin/env python
"""Analyze the ASP.NET entry-point lever A/B arms → KEEP/DROP (plan Step 0.4).

Reuses the project's Beta-Binomial prior (matching observe.beta_binomial) and the
CI of the ON−OFF difference by posterior-difference sampling (stdlib only) — same
machinery as .mu/abl_s2b_analyze.py / abl_msb_analyze.py.
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


def main():
    p10_on, p10_off = load('abl_ep_p10_on.json'), load('abl_ep_p10_off.json')
    p4_on, p4_off = load('abl_ep_p4_on.json'), load('abl_ep_p4_off.json')

    out = ['# ASP.NET entry-point lever A/B — plan Step 0.4 backend_build\n',
           'model `qwen2.5-coder-7b-instruct` · level L0 (I3) · '
           'ON = MU_ASPNET_ENTRYPOINT=1 · OFF = unset · S2 held off\n']

    keep1 = keep2 = None
    gate1_lo = None

    if p10_on and p10_off:
        out.append('\n## p10-dotnet-vue-blog — per-layer q̂ (ON = entry-point task injected)\n')
        out.append('| layer | ON clears | OFF clears | Δq̂ (ON−OFF) | 95% CI |\n|---|---|---|---|---|')
        lon, loff = p10_on.get('layers', {}), p10_off.get('layers', {})
        for layer in ('backend_build', 'backend_test', 'frontend_build', 'frontend_test'):
            so, sf = lon.get(layer, {}), loff.get(layer, {})
            ho, no = so.get('clears', 0), so.get('n', p10_on['n'])
            hf, nf = sf.get('clears', 0), sf.get('n', p10_off['n'])
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

    if p4_on and p4_off:
        d, lo, hi = diff_ci(p4_on['hits'], p4_on['n'], p4_off['hits'], p4_off['n'])
        # Powered control (pre-registered, §4.5): veto only on DEMONSTRATED harm —
        # at N=15 the binary-pass-rate CI is ~±0.28, so strict CI-lo ≥ −0.05 is
        # unachievable even at Δ=0; operative gate = point Δ ≥ −0.05 ∧ hi ≥ −0.05.
        keep2 = (d >= -0.05) and (hi >= -0.05)
        strict2 = lo >= -0.05
        out.append('\n## p4-fibonacci (dotnet control; no EF ⇒ lever never fires) — pass-rate\n')
        out.append(f'ON {p4_on["hits"]}/{p4_on["n"]} ({p4_on["pass_rate"]:.2f}) vs '
                   f'OFF {p4_off["hits"]}/{p4_off["n"]} ({p4_off["pass_rate"]:.2f}) · '
                   f'Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]')
        out.append(f'control gate (point Δ ≥ −0.05 ∧ no proven harm): '
                   f'{"PASS" if keep2 else "FAIL"} · strict §4.1 (underpowered): '
                   f'{"pass" if strict2 else "n/a"}')
    else:
        out.append('\n## p4 — INCOMPLETE (arm JSON missing)')

    out.append('\n## Verdict\n')
    if keep1 is None or keep2 is None:
        out.append('INCOMPLETE — rerun missing arms before deciding.')
    else:
        out.append(f'- Gate 1 (p10 backend_build Δq̂ CI lo > 0): '
                   f'{"PASS" if keep1 else "FAIL"} (lo={gate1_lo:+.3f})')
        out.append(f'- Gate 2 (p4 control: no observed/proven regression): '
                   f'{"PASS" if keep2 else "FAIL"}')
        if keep1 and keep2:
            out.append('\n**KEEP — entry-point lever lifts backend_build (CS0246 was the '
                       'binder); flip MU_ASPNET_ENTRYPOINT on by default, record efficacy '
                       'Δ. Re-run the S2 re-eval with the lever ON.**')
        elif keep2:
            out.append('\n**STAYS OPT-IN — lever no significant backend_build lift: CS0101 '
                       '(S2 target, held off) likely re-binds once Program exists. Check '
                       'the mechanistic secondary (did CS0246 drop?); if so, S2 is next.**')
        else:
            out.append('\n**REVERT — p4 control regressed (unexpected; the gate is guarded '
                       'on needs_ef and should not fire on p4).**')

    text = '\n'.join(out) + '\n'
    (MU / 'abl_ep_verdict.md').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
