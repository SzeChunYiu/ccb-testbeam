# ADR-0005: Explicit Geant4 step policy and neutron time-cut provenance

**Status:** accepted (provenance pins); empirical closure **BLOCKED**  
**Date:** 2026-08-11  
**Lane:** Wave B Lane 06  
**Issues:** #1095, #1091 (related #1006, #1089, #1090, #986)

## Context

### Step / Birks convergence (#1095)

The single-stave application inherits EM stepping from `QGSP_BIC` without an
application `G4UserLimits` / StepFunction contract. `SteppingAction` sums
`VisibleEnergyDepositionAtAStep`. Near Bragg stopping, nonlinear Birks
response can be step-policy dependent:
`f(mean(dE/dx)) != mean(f(dE/dx))` for `f(z)=z/(1+kB z)`.

### Neutron tracking-time cut (#1091)

QGSP_BIC carries an implicit **10 µs** neutron tracking-time cut (Geant4
Physics List Guide). The application neither configures nor records it.
Full-event truth can therefore inherit an undocumented late-neutron boundary
distinct from production cuts (#1089) and DAQ windows (#1090).

## Decision

1. Publish versioned registries:
   - `configs/transport/step_policy_registry.json`
   - `configs/transport/neutron_timecut_registry.json`
2. **Fail closed** when `step_policy_id` or `neutron_timecut_policy_id` is
   unset for studies that assert transport provenance.
3. Pin reference defaults explicitly:
   - `pin_qgsp_bic_inherited_em_stepfunction`
   - `pin_qgsp_bic_default_10us` (`neutron_time_cut_us = 10.0`)
4. `claims_authorized: false` until registered convergence / sensitivity
   study digests exist.
5. `authorize_step_convergence_claim` and
   `authorize_neutron_timecut_sensitivity_claim` raise `StudyBlockedError`
   without those digests — negative closure (H1) is allowed only after the
   study, not by assertion.
6. Do not silently extend neutron tracking or shrink steps in production
   without cost/observable justification recorded in the physics digest.

## Current registry state

| policy | issue | status | authorizing? |
|---|---|---|---|
| `pin_qgsp_bic_inherited_em_stepfunction` | #1095 | PINNED_REFERENCE_DEFAULT | no |
| `diagnostic_stricter_light_ion_stepfunction` | #1095 | HYPOTHESIS | no |
| `pin_qgsp_bic_default_10us` | #1091 | PINNED_REFERENCE_DEFAULT | no |
| `diagnostic_extended_or_disabled` | #1091 | HYPOTHESIS | no |

## Consequences

- Physics digests / study configs must name the pinned policies.
- “Step-converged” and “delayed neutrons negligible” claims remain
  **BLOCKED** until ladder digests are registered.
- Distinct from production-cut atom #1089 and DAQ-window atom #1090.

## Alternatives considered

1. **Add arbitrary tiny `G4UserLimits` as production** — rejected pending
   charged-particle lead review; may be diagnostic only.
2. **Leave QGSP_BIC unnamed for neutron cut** — rejected; provenance gap.
3. **Disable neutron time cut in production without sensitivity study** —
   rejected; CPU and physics impact unknown.
