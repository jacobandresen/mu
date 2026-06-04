"""Simple-reflex condition-action rules (effectors) applied after model writes.

The agent's reflex layer — condition → action rules with no memory that repair
general-class errors in model output before the lint/test gates run. These are
*effectors*, not sensors: they change the world (rewrite files) rather than
observe it. The real sensors (percepts) live in ``tools._read`` and gate stdout.

Each function corrects a *general class* of model error, independent of any
specific dojo problem. The honesty test: would you write this fix for any
program in this language or build system? If the answer is "no, only because
problem X needs it," the reflex is overfit — don't add it.

This package groups the reflexes by language / build system. ``core`` holds the
:func:`run_reflexes` fixpoint runner and the language-agnostic fixers; each
other module owns one language's fixers and re-exports through the star imports
below so callers keep importing everything from ``mu.reflexes``.
"""

from mu.reflexes.core import *  # noqa: F401,F403
from mu.reflexes.python import *  # noqa: F401,F403
from mu.reflexes.rust import *  # noqa: F401,F403
from mu.reflexes.csharp import *  # noqa: F401,F403
from mu.reflexes.go import *  # noqa: F401,F403
from mu.reflexes.javascript import *  # noqa: F401,F403
from mu.reflexes.makefile import *  # noqa: F401,F403
from mu.reflexes.plan_reflexes import *  # noqa: F401,F403
