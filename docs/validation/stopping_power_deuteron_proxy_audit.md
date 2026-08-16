# Deuteron PSTAR proxy acceptance audit

## Scope

This audit reviews only the reference-basis acceptance logic in
`scripts/single_stave/compare_stopping_power.py`. It does not establish an
accepted stopping-power closure or a detector-performance result.

## Authoritative basis

- NIST PSTAR states that the program calculates stopping-power and range tables
  for **protons**. It does not provide a deuteron table:
  <https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html>.
- Brolley and Ribe measured 8.86 MeV deuterons and equal-velocity 4.43 MeV
  protons in selected gases, demonstrating that proton/deuteron equal-velocity
  comparisons are an empirical, material-specific question rather than a
  provenance-free identity: DOI `10.1103/PhysRev.98.1112`.

The repository mapping

\[
E_{p,\mathrm{lookup}} = E_d / 2
\]

is therefore retained only as the labelled
`VELOCITY_SCALED_PROTON_PROXY`. It is not a direct PSTAR deuteron reference.

## Confirmed pre-change defect

The pre-change comparison at Git blob
`3c492b172669f2cdca160c52e1acc495a319973e` used only the energy-deposit basis
when setting `within_tolerance`. A raw deuteron row whose numerical ratio was
inside tolerance could therefore set `within_tolerance=true`, produce a
`NUMERICAL TOLERANCE: PASS`, and return process status 0 even though its
reference came from the unvalidated proton-at-half-energy approximation.

Synthetic regression case:

| Quantity | Value |
|---|---:|
| particle | deuteron |
| configured energy | 2 MeV |
| proton PSTAR lookup | 1 MeV |
| simulated proxy | 10 MeV cm2/g |
| proton reference | 10 MeV cm2/g |
| numerical ratio | 1.0 |
| pre-change acceptance | PASS |

The arithmetic is intentionally exact; the failure is semantic authorization,
not interpolation error.

## Validated correction

- Deuteron input fails closed by default before an output CSV or numerical PASS.
- `--allow-deuteron-proxy` permits only labelled, non-accepting diagnostics.
- Result dictionaries and CSVs now include:
  - `reference_basis`;
  - `reference_direct_pstar_comparable`;
  - `physics_comparable`.
- Proton rows use `DIRECT_PSTAR_PROTON` and may retain numerical acceptance.
- Deuteron rows use `VELOCITY_SCALED_PROTON_PROXY`, set
  `physics_comparable=false`, and can never set `within_tolerance=true`.
- A mixed proton/deuteron table is non-accepting even when all numerical ratios
  happen to lie inside tolerance.
- The built-in self-test now uses proton cases only; its scope remains arithmetic
  and committed-reference path validation.

## Reproduction

```bash
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_deuteron_proxy.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_quenched_proxy.py

python -m pytest \
  tests/test_compare_stopping_power_deuteron_proxy.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_quenched_proxy.py -q
```

Focused local reconstruction result: `9 passed in 5.78s`.

Exact changed-file Git blob checks:

- comparison script: `8b9c0c530b6414c774601286a0d67f13500aa532`;
- deuteron regression: `6febfc382a10d11194be1a57f99f41cf85bdcd48`;
- range regression: `026b6a12a4ea27e499f2fc2baf3e98020d65a58a`.

The local reconstruction used API-compatible copies of the unchanged canonical
PSTAR and simulation-table validators. Full repository pytest, ruff, Geant4,
CTest, ROOT processing, real simulation execution, and GitHub Actions were not
run.

## Visual evidence

`stopping_power_deuteron_proxy.svg` is a source-controlled synthetic schematic.
It is not detector data. It contrasts the former numeric-PASS authorization with
the new labelled, non-accepting proxy path.

## Acceptance boundary

This change prevents an approximation from masquerading as a direct PSTAR
validation. It does not show that the equal-velocity approximation is wrong at
all energies, nor that it is accurate for polystyrene. An accepted deuteron
closure still requires a deuteron-specific authoritative calculation or
measurement, immutable material/physics provenance, and comparison against a
validated projectile-energy-loss observable.
