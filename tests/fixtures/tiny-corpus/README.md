# Tiny corpus

A two-module toy package used as build.py's test input.

`alpha.greet` normalizes its argument through `beta.normalize` before formatting it,
so the extracted graph contains at least one cross-file edge.

This file exists so the corpus counts as *mixed* (code + docs) and both branches of
`build.py` — code-only and semantic — are reachable from one fixture.
