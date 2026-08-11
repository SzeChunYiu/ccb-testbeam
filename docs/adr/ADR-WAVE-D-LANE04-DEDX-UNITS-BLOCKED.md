# ADR-WAVE-D-LANE04: `dedx_p_in_CD2` units/metadata provenance BLOCKED

**Status:** accepted (parser fail-closed exists); full scientific closure **BLOCKED**
**Date:** 2026-08-12
**Lane:** Wave D Lane 04
**Issues:** #1058

## Context

`ScatteringGenerator::LoadELossTable` now fails closed on open/parse/domain/order
errors. The remaining open atom is *scientific provenance of the conversion
laws*:

- energy column treated as MeV/u and scaled by `938.28/931.5`
- dE/dx column scaled by `×1000` (commented as µm→mm)
- material/density identity of the table file itself

Those conversion constants are not presently bound to an immutable metadata
header or external certificate. Inventing a preferred unit system would bake an
unverified beam-energy shift into every p+d kinematic.

## Decision

1. Keep the fail-closed parser.
2. Require authorising campaigns to supply a provenance header contract via
   `ccb_mc_validation.source.dedx_table_provenance.require_dedx_provenance_headers`
   before treating stopping-corrected beam energy as claim-authorising.
3. Leave physical unit/material closure **BLOCKED** until a sourced table with
   explicit units/material/density digests is ledgered. Do not invent numbers.

## Consequences

Authorising weight/kinematics claims that depend on CD2 stopping must either
carry validated provenance headers or remain BLOCKED. Diagnostic development
may still load the historical table under non-authorising mode.
