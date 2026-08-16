# Stopping-power point-estimate uncertainty gate

## Scope

This audit reviews the acceptance logic in
`scripts/single_stave/compare_stopping_power.py`. The script remains a
`DIAGNOSTIC_ONLY` local-deposited-energy proxy; this change does not create an
accepted Geant4/PSTAR closure.

## Confirmed defect

The previous code accepted a direct proton row when three conditions held:

1. the simulation field was labelled unquenched raw energy deposit;
2. the reference was direct proton PSTAR;
3. the point-estimate ratio lay inside a user-selected percentage tolerance.

It did not evaluate statistical or systematic uncertainty. A synthetic one-event
case with ratio exactly `1.0` therefore set `within_tolerance=true`, printed
`NUMERICAL TOLERANCE: PASS`, and returned status `0`. Repeating the same synthetic
row forty times produced the same acceptance without establishing an uncertainty
model.

The exact pre-change script blob was
`8b9c0c530b6414c774601286a0d67f13500aa532`. Running the new four-test regression
against those exact bytes produced four failures, demonstrating the former
fail-open behavior.

## Methodological basis

NIST Technical Note 1297 states that a result is complete only when accompanied
by a quantitative uncertainty statement and separates statistically evaluated
components from components evaluated by other means. The publication is used
here as a methodological reporting standard, not as a claim that this simulation
diagnostic is itself a physical measurement.

Primary source:

- B. N. Taylor and C. E. Kuyatt, *Guidelines for Evaluating and Expressing the
  Uncertainty of NIST Measurement Results*, NIST Technical Note 1297 (1994),
  DOI: `10.6028/NIST.tn.1297`.
- Supporting sections: NIST TN 1297 sections 2, 5, and 7.

## Validated correction

The comparison now separates a numerical point-estimate diagnostic from
scientific acceptance:

- `numeric_within_tolerance` retains the arithmetic tolerance result;
- `uncertainty_method` is explicitly `NOT_EVALUATED`;
- `uncertainty_evaluated` is `false`;
- `acceptance_status` is one of
  `NONCOMPARABLE_INPUT_OR_REFERENCE`, `POINT_ESTIMATE_OUTSIDE_TOLERANCE`, or
  `NOT_ACCEPTED_NO_UNCERTAINTY`;
- `within_tolerance` remains false until a future validated uncertainty method is
  implemented;
- direct proton point matches are printed as `POINT_ONLY`, never `PASS`;
- the CLI returns status `1` for a point-estimate-only result;
- the synthetic self-test remains an arithmetic/path-wiring test and may return
  success, but it prints the non-accepting scientific state.

## Future acceptance requirements

An accepted stopping-power comparison must preregister and propagate, as
applicable:

- event-level or replicate-level Type A uncertainty;
- between-seed, run, and configuration variation;
- covariance between deposited energy and scored path length;
- material-density uncertainty;
- reference-table precision/interpolation uncertainty;
- production-cut, physics-list, geometry, and material-model sensitivity;
- projectile-energy evolution and generated-secondary escape;
- an accepted projectile-energy-loss observable rather than local deposit alone.

The tolerance and uncertainty model must be fixed before inspecting final closure
results. Repeated identical rows do not substitute for independent stochastic or
systematic information.

## Validation

Executed on exact local reconstructions of the committed implementation and
focused tests:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/validate_pstar_component_sum.py \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_compare_stopping_power_uncertainty_gate.py \
  tests/test_compare_stopping_power_energy_grouping.py \
  tests/test_compare_stopping_power_quenched_proxy.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_deuteron_proxy.py

python -m pytest \
  tests/test_compare_stopping_power_uncertainty_gate.py \
  tests/test_compare_stopping_power_energy_grouping.py \
  tests/test_compare_stopping_power_quenched_proxy.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_deuteron_proxy.py -q

19 passed in 3.77s
```

Additional checks:

- exact pre-change Git blob identity confirmed;
- new regression against exact old bytes: `4 failed` as expected;
- all changed Python files compiled;
- maximum changed Python line length: 97 characters;
- validation JSON parsed;
- SVG parsed as XML.

## Evidence boundary

No real Geant4 event table, ROOT output, accepted uncertainty budget, projectile
entry/exit-energy closure, `G4EmCalculator` result, calibration, or detector
performance result was produced. The numerical ratios remain point estimates and
the script remains `DIAGNOSTIC_ONLY`.
