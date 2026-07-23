# PSTAR reference-domain audit

## Scope

This review covers the reference-energy domain used by
`scripts/single_stave/compare_stopping_power.py`. It does not establish a
Geant4 stopping-power closure. The script still compares a local deposited-
energy proxy with a PSTAR total-stopping-power reference and labels the result
`DIAGNOSTIC_ONLY`.

## Confirmed defect

The previous interpolation routine silently clamped every lookup outside the
committed PSTAR energy range to the nearest endpoint. Consequently, a
simulation point below or above the table could be assigned an unrelated edge
stopping power and could pass the numerical tolerance.

For deuterons the relevant lookup is the proton-equivalent energy `E/2`, so a
deuteron energy can be inside an apparent beam-energy range while its reference
lookup is outside the committed proton table.

Synthetic reproduction with a two-point reference covering 1--10 MeV:

```text
old lookup 0.5 MeV -> reused 1 MeV endpoint
old lookup 20 MeV  -> reused 10 MeV endpoint
```

The endpoint reuse is not interpolation and supplies no reference support for
the requested energy.

## Validated correction

The comparison now:

- requires a finite, positive reference lookup energy;
- accepts exact table endpoints;
- performs log-log interpolation only inside the table domain;
- rejects lower- and upper-domain extrapolation instead of clamping;
- reports deuteron beam energy and proton-equivalent lookup energy together in
  failures;
- writes lookup energy and reference-domain bounds into the output CSV;
- returns CLI status 2 without printing a numerical PASS when the range gate
  fails.

## Reproducible validation

Executed on an exact reconstruction of the pre-change script plus the focused
patch, using a minimal static reference fixture:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py

python -m pytest \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py -q

7 passed in 1.15s
```

The reconstructed unmodified script had Git blob
`d9282a5c26b8bc86427356f51dfe7e5ecba769d8`, exactly matching the current-main
blob before this correction. Both changed Python files had no line longer than
100 characters.

## Visual evidence

`stopping_power_reference_domain.svg` distinguishes the supported interpolation
interval from the formerly clamped, unsupported regions. It is a schematic of
the regression condition, not detector data.

## Scientific boundary

This gate prevents unsupported reference reuse. It does not resolve the larger
closure questions:

- local deposited energy can differ from projectile energy loss when generated
  secondaries escape;
- projectile energy evolves along the scored path;
- production cuts, material definition, density, and physics list matter;
- `S_d(E) ~= S_p(E/2)` is an approximation, not a direct deuteron PSTAR table.

Accepted closure remains blocked under `BLK-G4-SP-001` and requires the methods
and provenance listed there.
