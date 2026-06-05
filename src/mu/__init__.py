__version__ = "0.10.4"

# ── AIMA role aliases (Stage 2) ───────────────────────────────────────────────
# Thin import-time aliases so contributors can use AIMA vocabulary alongside the
# canonical module names. Physical renames ship only after tests cover the paths.
#
#   mu.learner  → mu.reflect   (learning element — offline: TELLs the KB)
#   mu.recall   → mu.enrich    (learning element — retrieval: ASKs the archive)
#   mu.memory   → mu.archive   (episodic memory — the experience store)
#
# Usage: `from mu import learner` or `import mu.learner`.
def _alias(aima_name: str, canonical: str):
    import sys
    from importlib import import_module
    mod = import_module(canonical)
    sys.modules.setdefault(aima_name, mod)
    return mod

learner = _alias('mu.learner', 'mu.reflect')
recall  = _alias('mu.recall',  'mu.enrich')
memory  = _alias('mu.memory',  'mu.archive')

del _alias
