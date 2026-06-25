"""``mu dojo`` — argparse front end for the dojo test rig.

A normal CLI surface (subcommands, ``--flags``, ``--help``) over the rig. Flags
are the primary interface; each one *defaults* from the long-standing env var
(``N``, ``ROUNDS``, ``MU_SEED`` …) so the shell-era contract still works and a
flag simply overrides it. The resolved values are written back to the
environment before dispatch, because some (``MU_SEED``, ``MU_AGENT_MODEL``) must
reach the ``mu agent``/``mu iterate`` subprocesses the rig spawns.

Reached two ways, same parser:
    mu dojo measure p9-vue-todo --runs 5 --seed 42
    python -m mu.dojo measure p9-vue-todo --runs 5
"""

import argparse
import os
from typing import Optional

from .. import fixtures


def _env_flag(name: str) -> bool:
    return bool(os.environ.get(name))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='mu dojo',
        description='Dojo test rig — exercise mu against the practice problems '
                    '(harness, not part of the shipped workflow).')
    sub = p.add_subparsers(dest='cmd', required=True)

    # -- measure ------------------------------------------------------------
    m = sub.add_parser('measure', help='measure one problem over N runs (fresh plan each run)')
    m.add_argument('problem_id', help='catalog id, e.g. p7-flask')
    m.add_argument('-n', '--runs', type=int, default=int(os.environ.get('N', '5')),
                   help='number of runs (default 5, or $N)')
    m.add_argument('--seed', default=os.environ.get('MU_SEED', ''),
                   help='pin the writer RNG (greedy, near-deterministic); $MU_SEED')
    m.add_argument('--disable', default=os.environ.get('MU_DISABLE_REFLEX', ''),
                   metavar='ID[,ID...]',
                   help='ablation: switch off these reflex(es) for the run, to '
                        'measure their efficacy (docs/REFLEX_KB.md §9)')
    m.add_argument('--emit-json', default='', metavar='PATH',
                   help='write structured result JSON to PATH (for record_efficacy)')

    # -- board --------------------------------------------------------------
    b = sub.add_parser('board', help='measure ALL problems and print the capability '
                                     'board (per-layer q̂, p_solve, E[#solved])')
    b.add_argument('-n', '--runs', type=int, default=int(os.environ.get('N', '5')),
                   help='runs per problem (fresh plan each)')
    b.add_argument('--emit-json', default='', metavar='PATH',
                   help='write the board JSON to PATH (the loop reads this)')

    # -- run ----------------------------------------------------------------
    r = sub.add_parser('run', help='run one problem, or all available')
    r.add_argument('problem_id', nargs='?', default='',
                   help='catalog id; omit to run every available problem')
    r.add_argument('--model', default=os.environ.get('MU_AGENT_MODEL', ''),
                   help='model id for the agent and for routing; $MU_AGENT_MODEL')
    r.add_argument('--route', action='store_true', default=_env_flag('MU_ROUTE'),
                   help='skip problems the model is measured hopeless on (needs --model)')
    r.add_argument('--no-shuffle', action='store_true', default=_env_flag('SIT_NO_SHUFFLE'),
                   help='run in catalog order instead of shuffled')
    r.add_argument('--keep', action='store_true', default=_env_flag('SKIP_CLEAN'),
                   help='keep dojo work dirs instead of cleaning up after')

    # -- practice -----------------------------------------------------------
    pr = sub.add_parser('practice', help='repeated rounds with per-round learning')
    pr.add_argument('--rounds', type=int, default=int(os.environ.get('ROUNDS', '100')))
    pr.add_argument('--stop-after-barren', type=int,
                    default=int(os.environ.get('STOP_AFTER_BARREN', '5')),
                    help='bail after N rounds with zero successes')
    pr.add_argument('--round-timeout', type=int,
                    default=int(os.environ.get('ROUND_TIMEOUT', '1800')),
                    help='kill any single round exceeding this many seconds')
    pr.add_argument('--reflect-limit', type=int,
                    default=int(os.environ.get('REFLECT_LIMIT', '10')),
                    help='max lessons written per reflect call')
    pr.add_argument('--model', default=os.environ.get('MU_AGENT_MODEL', ''),
                    help='model id for the agent; $MU_AGENT_MODEL')
    pr.add_argument('--no-reflect', action='store_true', default=_env_flag('SKIP_REFLECT'),
                    help='skip the post-round reflect step')
    pr.add_argument('--autocommit', action='store_true', default=False,
                    help='commit the problem index + docs/challenges/README.md after each round')
    pr.add_argument('--no-preflight', action='store_true', default=_env_flag('SKIP_PREFLIGHT'),
                    help='skip the LM Studio reachability check')

    # -- fixture ------------------------------------------------------------
    f = sub.add_parser('fixture', help='inspect/apply committed problem fixtures')
    fsub = f.add_subparsers(dest='fcmd', required=True)
    fa = fsub.add_parser('apply', help='copy a problem\'s fixtures into a work dir')
    fa.add_argument('problem_id')
    fa.add_argument('dir', nargs='?', default='.')
    fs = fsub.add_parser('skip', help='exit 0 if the model should skip this problem')
    fs.add_argument('model')
    fs.add_argument('problem_id')

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == 'measure':
        os.environ['N'] = str(args.runs)
        if args.seed:
            os.environ['MU_SEED'] = args.seed
        if args.disable:
            os.environ['MU_DISABLE_REFLEX'] = args.disable  # reaches the iterate subprocess
        from . import measure
        return measure.run(args.problem_id, emit_json=args.emit_json)

    if args.cmd == 'board':
        os.environ['N'] = str(args.runs)
        from . import measure
        return measure.board(emit_json=args.emit_json, runs=args.runs)

    if args.cmd == 'run':
        if args.model:
            os.environ['MU_AGENT_MODEL'] = args.model
        _set_flag('MU_ROUTE', args.route)
        _set_flag('SIT_NO_SHUFFLE', args.no_shuffle)
        _set_flag('SKIP_CLEAN', args.keep)
        from . import runner
        return runner.run(args.problem_id)

    if args.cmd == 'practice':
        if args.model:
            os.environ['MU_AGENT_MODEL'] = args.model
        os.environ['ROUNDS'] = str(args.rounds)
        os.environ['STOP_AFTER_BARREN'] = str(args.stop_after_barren)
        os.environ['ROUND_TIMEOUT'] = str(args.round_timeout)
        os.environ['REFLECT_LIMIT'] = str(args.reflect_limit)
        _set_flag('SKIP_REFLECT', args.no_reflect)
        _set_flag('SKIP_AUTOCOMMIT', not args.autocommit)
        _set_flag('SKIP_PREFLIGHT', args.no_preflight)
        from . import practice
        return practice.run()

    if args.cmd == 'fixture':
        if args.fcmd == 'apply':
            for rel in fixtures.apply(args.problem_id, args.dir):
                print(rel)
            return 0
        if args.fcmd == 'skip':
            return 0 if fixtures.should_skip_problem(args.model, args.problem_id) else 1

    return 2


def _set_flag(env_name: str, on: bool) -> None:
    """Mirror a boolean flag into the env contract (set or clear), so the rig
    functions and any subprocess see a consistent value."""
    if on:
        os.environ[env_name] = '1'
    else:
        os.environ.pop(env_name, None)
