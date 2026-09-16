"""In-memory implementations of the six boundaries, and the broken ones that prove the suites bite.

These live in the test tree and never in ``src/``. A fake in the distribution is an invitation to
import it from production code "just for now", and the in-memory archive is the tempting one — it
is thirty lines and it loses history on exit (specs/007-boundary-interfaces/research.md R12,
FR-027).

They exist for two reasons: each is the first proof that its interface is implementable by
something other than the eventual real thing, and together they are what the pipeline tests of
#19 and the implementation tests of #10 through #16 run against instead of re-inventing one each.
"""
