"""Rule-based PLAN.md linter (the spaCy plan-lint arm).

`lint_plan` returns a list of human-readable warnings that the planner
critique loop feeds back to the LLM for a second pass. Warnings are
*generic*: they describe shapes of underspecification, never per-problem
fixes.

Checks (in descending order of value):

  1. Cross-task entity inconsistency. If task A names `TodoManager` and
     task B names `TodoStore`, the writer often hallucinates the wrong
     class. We collect capitalised tokens (CamelCase or snake_case
     identifiers) per task description, and warn on near-string-match
     pairs that appear in different tasks.

  2. Vague action verbs (`handle`, `support`, `manage`, `process`,
     `deal with`) without a direct object. Detected with spaCy
     dependency parse when available, else a regex fallback that flags
     the verb alone.

  3. Pronouns crossing task boundaries — `it`/`this`/`that` at the start
     of a task description with no antecedent in the same description.

  4. Task descriptions shorter than _MIN_DESC_TOKENS tokens.

spaCy is lazy-imported. If the model isn't installed, checks (2) and
(3) downgrade to regex heuristics; (1) and (4) are dependency-free.
"""

from __future__ import annotations

import re

from mu.plan import Task, parse

_VAGUE_VERBS = ('handle', 'support', 'manage', 'process', 'deal')
_LEADING_PRONOUNS = ('it', 'this', 'that', 'these', 'those')
_MIN_DESC_TOKENS = 5
_IDENT_RE = re.compile(r'\b([A-Z][A-Za-z0-9]*[A-Za-z0-9]|[a-z]+_[a-z_0-9]+)\b')
_CAMEL_SPLIT = re.compile(r'[A-Z][a-z0-9]*|[a-z0-9]+')
# Tail words that mean "the thing that owns/holds/handles the domain
# object". Two identifiers that share a head and have tails from this
# set are almost certainly the same concept named two different ways —
# the classic failure mode this check targets (e.g. TodoManager vs
# TodoStore). Unrelated entities like UserAuth/UserProfile have tails that
# aren't in this set, so they're left alone. Keep the vocabulary small
# and language-generic; growing it problem-by-problem violates the
# honesty principle.
_ROLE_TAILS = frozenset({
    'manager', 'store', 'repo', 'repository', 'handler', 'service',
    'controller', 'db', 'database', 'client', 'registry', 'factory',
    'builder', 'provider', 'helper', 'util', 'utils', 'cache', 'state',
    'worker', 'agent', 'runner', 'script', 'engine', 'driver',
    'broker', 'dispatcher', 'router', 'listener', 'monitor', 'tracker',
})


def _nlp():
    try:
        import spacy  # type: ignore
    except ImportError:
        return None
    cached = getattr(_nlp, '_cached', None)
    if cached is None:
        try:
            cached = spacy.load('en_core_web_sm', disable=['ner'])
        except Exception:
            return None
        _nlp._cached = cached  # type: ignore[attr-defined]
    return cached


def lint_plan(plan_path: str = 'PLAN.md') -> list[str]:
    """Return ordered warnings for the plan, [] if it looks well-specified."""
    p = parse(plan_path)
    if not p.tasks:
        return []
    out: list[str] = []
    out.extend(_check_entity_consistency(p.tasks))
    out.extend(_check_vague_verbs(p.tasks))
    out.extend(_check_leading_pronouns(p.tasks))
    out.extend(_check_short_descriptions(p.tasks))
    return out


def _extract_identifiers(text: str) -> set[str]:
    return {m.group(1) for m in _IDENT_RE.finditer(text or '')}


def _split_ident(ident: str) -> list[str]:
    """Lowercased word parts of a Camel/snake identifier."""
    if '_' in ident:
        return [p for p in ident.lower().split('_') if p]
    return [m.group(0).lower() for m in _CAMEL_SPLIT.finditer(ident)]


def _check_entity_consistency(tasks: list[Task]) -> list[str]:
    """Flag identifiers that share a head token but diverge in the tail.

    `TodoManager` (head=todo, tail=manager) and `TodoStore` (head=todo,
    tail=store) cross tasks → the writer model picks one name on each
    side and the import never resolves. This is the strongest
    signal of the four checks. Identifiers in the same task are ignored:
    re-using related names within one file is normal.
    """
    by_task: list[tuple[str, set[str]]] = [
        (t.file_path, _extract_identifiers(t.description)) for t in tasks
    ]
    parts: dict[str, list[tuple[str, list[str]]]] = {}
    for fp, idents in by_task:
        for ident in idents:
            sp = _split_ident(ident)
            if len(sp) < 2:
                continue
            parts.setdefault(fp, []).append((ident, sp))

    out: list[str] = []
    flagged: set[tuple[str, str]] = set()
    items = [(fp, ident, sp) for fp, lst in parts.items() for ident, sp in lst]
    for i, (fp_a, ident_a, sp_a) in enumerate(items):
        for fp_b, ident_b, sp_b in items[i + 1:]:
            if fp_a == fp_b or ident_a == ident_b:
                continue
            if sp_a[0] != sp_b[0] or sp_a[-1] == sp_b[-1]:
                continue
            # Only flag when BOTH tails are generic role suffixes.
            # Without this guard the check fires on legitimately
            # distinct entities that happen to share a head token
            # (UserAuth vs UserProfile).
            if sp_a[-1] not in _ROLE_TAILS or sp_b[-1] not in _ROLE_TAILS:
                continue
            pair = tuple(sorted((ident_a, ident_b)))
            if pair in flagged:
                continue
            flagged.add(pair)
            out.append(
                f"entity-mismatch: `{ident_a}` (in {fp_a}) and "
                f"`{ident_b}` (in {fp_b}) share the head `{sp_a[0]}` "
                f"but diverge in the tail — pick one name and use it "
                f"everywhere."
            )
    return out


def _check_vague_verbs(tasks: list[Task]) -> list[str]:
    nlp = _nlp()
    out: list[str] = []
    for t in tasks:
        text = t.description or ''
        if not text:
            continue
        if nlp is not None:
            doc = nlp(text)
            for tok in doc:
                if (tok.pos_ == 'VERB' and tok.lemma_.lower() in _VAGUE_VERBS
                        and not any(c.dep_ in ('dobj', 'pobj', 'attr')
                                    for c in tok.children)):
                    out.append(
                        f"vague-verb: {t.file_path} uses `{tok.text}` "
                        f"with no concrete object — say what it produces."
                    )
                    break
        else:
            low = text.lower()
            for v in _VAGUE_VERBS:
                if re.search(rf'\b{v}s?\b(?!\s+\w)', low):
                    out.append(
                        f"vague-verb: {t.file_path} uses `{v}` "
                        f"with no concrete object — say what it produces."
                    )
                    break
    return out


def _check_leading_pronouns(tasks: list[Task]) -> list[str]:
    out: list[str] = []
    for t in tasks:
        desc = (t.description or '').lstrip()
        if not desc:
            continue
        first = desc.split(None, 1)[0].rstrip(',.;:').lower()
        if first in _LEADING_PRONOUNS:
            out.append(
                f"dangling-pronoun: {t.file_path} starts with `{first}` "
                f"— readers (and the writer model) cannot resolve the "
                f"antecedent across tasks."
            )
    return out


def _check_short_descriptions(tasks: list[Task]) -> list[str]:
    out: list[str] = []
    for t in tasks:
        if len((t.description or '').split()) < _MIN_DESC_TOKENS:
            out.append(
                f"underspecified: {t.file_path} has fewer than "
                f"{_MIN_DESC_TOKENS} description tokens — name the "
                f"functions/types the file must expose."
            )
    return out


def render_warnings(warnings: list[str]) -> str:
    """Format warnings as a critique block to feed back to the planner."""
    if not warnings:
        return ''
    body = '\n'.join(f'- {w}' for w in warnings)
    return (
        "The previous PLAN.md tripped the following deterministic checks. "
        "Revise the plan so every warning is gone, then output the new "
        "PLAN.md only.\n\n"
        f"{body}\n"
    )
