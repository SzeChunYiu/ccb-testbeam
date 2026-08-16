# ADR-0008: Step-size convergence for Birks/range response is BLOCKED

**Status:** accepted (infrastructure); physical closure **BLOCKED**  
**Date:** 2026-08-11  
**Lane:** Wave C Lane 05  
**Issues:** #1095

## Context

Geant4 condensed-history transport partitions continuous energy loss into steps.
Birks response is a nonlinear functional of local `dE/dx`, so coarse steps near
Bragg stopping need not equal a finer partition. The application currently
inherits the physics-list step policy with no documented convergence study.

## Decision

1. Publish named **HYPOTHESIS** profiles under `configs/step_convergence/`.
2. Fail closed when `step_convergence_profile_id` is unset for authorizing paths
   (`require_step_convergence_profile`).
3. **Do not invent** `G4UserLimits` max-step values or StepFunction parameters
   in this wave.
4. Promote to `APPROVED` only after a recorded step-size / visible-energy
   convergence campaign near Bragg stopping for the relevant species/material.

## Consequences

- Authorizing Bragg/quenching claims without a profile raise `StudyBlockedError`.
- Executable Geant4 step policy is unchanged until an APPROVED study lands.
