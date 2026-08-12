# ADR-WAVE-D-LANE03: Analysed-stave spacing still BLOCKED for TOF claims

**Status:** accepted (gate); physical closure **BLOCKED**
**Date:** 2026-08-12
**Lane:** Wave D Lane 03
**Issues:** #992 (extends ADR-0002)

## Context

Wave A registered 2 cm and 4 cm analysed-stave spacing as mutually contradictory
HYPOTHESIS profiles. No hardware/CAD/beam-log ledger has yet promoted either
profile to APPROVED. TOF and range interpretation still require a single
mechanical spacing.

## Decision

1. Keep both spacing profiles as HYPOTHESIS / `claims_authorized: false`.
2. Add `require_spacing_hypothesis_for_tof` so authorising TOF/range callers
   fail closed instead of silently consuming a hypothesis spacing.
3. Do **not** invent which of 2 cm or 4 cm is true.

## Consequences

Studies may still name a spacing hypothesis for sensitivity work. They must
not publish authorising TOF/range claims until an APPROVED spacing profile
exists with evidence digests.
