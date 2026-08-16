# ADR-0011: Template-phase grid quantization is a measurement component

**Status:** accepted (contract); sub-grid interpolation **BLOCKED** / unimplemented  
**Date:** 2026-08-11  
**Lane:** Wave C Lane 05  
**Issues:** #1064

## Context

`template_phase_time` returns the discrete SSE-minimizing grid node (default
0.05 sample ≈ 0.5 ns at a 10 ns analysis period). Sub-ns performance claims
that ignore this lattice are not identified.

## Decision

1. Record grid step in provenance (`TemplateGridContract`).
2. Fail closed when an authorizing claimed resolution is finer than
   `grid_step_ns` under `interpolation=none`.
3. Do **not** invent a parabolic/continuous estimator as production truth in
   this wave; those remain alternate hypotheses.
4. Hardware sample-period lock remains owned by #1014/#993.

## Consequences

- Discrete-grid claims at or coarser than the lattice may proceed.
- Finer claims require an implemented interpolation hypothesis + closure study.
