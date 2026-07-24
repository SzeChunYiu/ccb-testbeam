# Public claim audit v3

## State

The public wiki, executive chapter and project report are not synchronized with the repository's current audit records. They continue to call several quarantined or blocked values `VALIDATED`.

## Required immediate corrections

### Rmax

Remove `3.044–3.05 MHz` as an accepted pile-up tolerance. The CL-010 audit records that `0.38` is a duty factor and that the simulated recovery curve never crosses the recorded failure ceiling. Current accepted value: none; state: `BLOCKED`.

### Digitizer gain

Remove `92 ± 28 ADC/MeV` as a validated calibration. The central calculation is traceable, but the producing method, reproduce CLI, input requirements, output schema and uncertainty chain are not mutually reproducible. State: `BLOCKED`.

### Timing

Retain timing estimates only as data/digitizer diagnostics until exact result bundles, intervals, covariance and the dependent gain chain are repaired. Do not label the raw timing pull validated merely because one pull arithmetic is near one sigma.

### PID and C12

Keep PID AUC/purity and C12 fractions strictly `TRUTH_LEVEL_MC_ONLY`. The real-data transfer/identity is not validated.

### Stopping depth and stopping power

Stopping-depth is a failed model comparison, not a calibration. Stopping-power software checks are diagnostic only until projectile energy-loss closure, escaping secondaries, cuts and real immutable exports are handled.

## Superseded MC chapter

`docs/academic_chapters/10_mc_validation.md` must be removed from publication navigation and marked `SUPERSEDED / NOT FOR QUANTITATIVE USE`. It retains:

- an old `245.6 ± 12.3 ± 73.7 ADC/MeV` chain;
- unsupported bootstrap/likelihood claims;
- Rmax validation language contradicted by CL-010;
- C12 closure language beyond truth-level evidence;
- unsupported `ACCEPTED by nature-reviewer (3/3)` wording.

## Generation architecture

Public claim surfaces must be generated from one strict normalized claim object. Tooling must fail if:

- the ledger row width is wrong;
- the result/source artifact is missing or hash-mismatched;
- the status is not approved for the target surface;
- an uncertainty, truth type or applicability field is absent;
- a quarantined literal is reintroduced.

Wiki, chapters, status dashboards and figures must consume the same normalized claim record. Superseded history belongs in a separate correction log.
