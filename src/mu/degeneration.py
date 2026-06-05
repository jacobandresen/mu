"""Degeneration guard: detect a writer that fell into a token-repetition loop.

The dominant failure mode for small local models (see CHALLENGES.md #1) is
*degeneration*: at near-greedy temperature the model gets stuck emitting the same
short fragment forever — ``print(f"{task[print(f"{task[…`` — and the file it
writes is corrupt from the first token. A reflex cannot repair this (you cannot
reconstruct intent from a loop); the only honest response is to refuse the
corrupt artifact and let the writer *resample* (a fresh sample, which is what
``repeat_penalty`` tries to prevent in the first place — this is the safety net
for when it slips through).

This module is the detector. It flags only **tight consecutive repetition** — a
short unit repeated back-to-back enough times to dominate the output. That is the
discriminator between degeneration and the *distant* repetition real code is full
of (indentation, ``self.``, dict keys), which must never be flagged or every run
regresses. The guard is conservative by design: it prefers a missed loop to a
false positive on working code, and can be disabled with ``MU_DEGEN_GUARD=0``.
"""

import os

# A loop's period is short (the model repeats a few tokens), matching llama.cpp's
# repeat_last_n=64 window. A unit must repeat at least _MIN_REPEATS times *and*
# the run must cover at least _MIN_COVERAGE of the output — both, so a small
# legitimately-repeated block (a few identical config lines) stays under the bar.
_MIN_LEN = 200        # below this the output is too short to judge
_MAX_PERIOD = 64      # longest repeating unit we treat as a loop
_MIN_REPEATS = 12     # a unit repeated fewer times than this is not a loop
_MIN_COVERAGE = 0.5   # the repeating run must dominate at least half the output


def guard_enabled() -> bool:
    """The guard is on by default; ``MU_DEGEN_GUARD=0`` disables it."""
    return os.environ.get("MU_DEGEN_GUARD", "1") != "0"


def is_degenerate(text: str) -> bool:
    """True if *text* is dominated by a short unit repeated back-to-back.

    Scans every period length up to ``_MAX_PERIOD`` for the longest run of an
    identical unit. A whitespace-only unit is skipped — a blank-line run is not a
    file-corrupting loop. Returns as soon as one run clears both thresholds.
    """
    n = len(text)
    if n < _MIN_LEN:
        return False
    min_run = max(_MIN_REPEATS * 1, int(_MIN_COVERAGE * n))
    for p in range(1, _MAX_PERIOD + 1):
        i = 0
        while i + p * _MIN_REPEATS <= n:
            unit = text[i:i + p]
            if not unit.strip():            # whitespace loop — not corrupting
                i += p
                continue
            j = i + p
            while j + p <= n and text[j:j + p] == unit:
                j += p
            run = j - i
            if run >= p * _MIN_REPEATS and run >= min_run:
                return True
            i = j if j > i + p else i + p   # skip past a run, else step by one period
    return False
