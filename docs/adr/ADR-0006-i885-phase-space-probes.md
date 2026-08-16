# ADR-0006: I885 phase-space undercoverage (y and angle)

**Status:** accepted (campaign probes) + **BLOCKED** (data-averaged response)  
**Date:** 2026-08-11  
**Lane:** Wave B Lane 02  
**Issues:** #1092, #1093 (related #885, #1094)

## Context

The historic I885 campaign fixed `hit_y=0` and `theta=phi=0`, measuring

`R(E,x,y=0,θ=0,φ=0)`

while the stave has fibres at `y=±1 cm` and real tracks may arrive at nonzero
angles. That central slice is **not** automatically the data phase-space
expectation

`<R> = ∫ R(E,x,y,θ,φ,…) p_data(…) dΓ`.

The data transverse and angular distributions are not yet recovered in-repo.

## Decision

1. Extend `make_i885_campaign.py` with:
   - a **transverse MC probe** at `y ∈ {0, ±1} cm` for representative energies
     (#1092);
   - an **angular MC sensitivity grid** at `θ ∈ {0,10}°`, `φ ∈ {0,90}°` for a
     single representative point, citing the historical ±10° timing-note range
     as a sensitivity hypothesis only (#1093).
2. Tag campaign comments with
   `DATA_Y_DISTRIBUTION_UNKNOWN` / `DATA_ANGLE_DISTRIBUTION_UNKNOWN`.
3. **CLAIM_GATE:** I885 results MUST NOT be advertised as the data-averaged
   stave response until `p_data(y,θ,φ,…)` is measured or otherwise evidenced.
4. `submit_calibration.sh` accepts optional `theta_deg,phi_deg` columns and
   forwards them to the executable; legacy 6-column rows remain valid.

## BLOCKED

| Claim | Status |
|---|---|
| I885 curve = average physical-stave response | **BLOCKED** until data y/angle distributions exist |
| 10°/90° grid = real beam angular measure | **BLOCKED** (sensitivity hypothesis only) |

## Consequences

- MC phase-space holes for fibre-y and angle are now *probeable*.
- Authorising analysis still requires an explicit data measure, not the probe
  grid alone.
