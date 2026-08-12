# ADR-0004: Quenching model is a hypothesis, not validated p/d light-response truth

**Status:** accepted (contract) + **BLOCKED** (multi-model closure)  
**Date:** 2026-08-11  
**Lane:** Wave B Lane 02  
**Issues:** #1008 (related #1000, #1079, #1095)

## Context

The single-stave Geant4 path applies Birks saturation with a nominal
`kB = 0.126 mm/MeV` and systematic grids that vary only that scalar. Primary
literature (Pöschl et al., NIM A 988 (2021) 164865; O'Rielly et al., NIM A 368
(1996) 745–749) shows quenching model *form* (Birks / Chou / Wright / Voltz)
is an open choice for plastic scintillators, not a universal law.

Issue #1000 (CCB bar polymer/batch identity) remains BLOCKED. Without a
source-verified scintillator identity, transferring literature parameters into
the CCB executable as “truth” would invent numbers.

## Decision

1. Name the executable model explicitly:
   - `quenching_model_id = birks_geant4`
   - `quenching_model_status = HYPOTHESIS`
   - `quenching_claims_authorized = false`
2. Treat kB scans as **within-form** nuisance variation only.
3. Do **not** ship Chou/Wright/Voltz coefficients, empirical p/d splines, or
   “validated light-response truth” labels until:
   - scintillator identity is recovered (#1000), and
   - a designated calibration/reference programme fits parameters on held-out
     particle/energy conditions (#1008 programme steps 4–6).
4. Run metadata and physics digests (#986) include the quenching model id and
   status so caches cannot silently equate distinct response hypotheses.

## BLOCKED follow-ups

| Atom | Why blocked |
|---|---|
| Second-order / Chou-like executable model | Needs CCB-bound parameters; inventing coeffs forbidden |
| Literature p/d response table as CCB truth | Material/batch transfer unjustified without #1000 |
| Authorising PID light-response claims from Birks alone | Model-form uncertainty not yet envelope-propagated |

## Consequences

- Consumers must treat quenched light as a named hypothesis.
- Closing #1008 physically requires the programme in the issue body, not a
  silent default change of `kB`.
