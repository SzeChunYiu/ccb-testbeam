# ADR-WAVE-D-LANE05: Chord/arithmetic-beta TOF is a non-authorising surrogate

**Status:** accepted (label + gate); path-integral closure **BLOCKED**
**Date:** 2026-08-12
**Lane:** Wave D Lane 05
**Issues:** #1127 (related #992, #1095, #1006)

## Context

S12a currently predicts `pred_truth_kinematic_tof = distance_cm / (c * beta_mid)`
using the Euclidean chord between stored layer-entry points and the arithmetic
mean of endpoint betas. That quantity is **not** the laboratory time along the
charged-particle trajectory.

## Decision

1. Do not invent a path-integral implementation without deposited-step truth
   dumps that close the integral.
2. Label the existing predictor as a SURROGATE in code/metadata helpers.
3. Fail closed when a caller requests authorising use of the chord surrogate
   (`require_authorising_tof_predictor`).
4. Path-integral closure remains BLOCKED pending transport-step truth products.

## Consequences

ML-vs-physics benchmarks may still use the surrogate under an explicit
non-authorising flag. Authorising TOF claims cannot cite the chord formula as
truth.
