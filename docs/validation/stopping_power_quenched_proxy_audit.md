# Stopping-Power Quenched-Proxy Acceptance Audit

## Scope

This audit reviews only the energy-deposit input semantics in
`scripts/single_stave/compare_stopping_power.py`. It does not establish a
Geant4-to-PSTAR physics closure.

## Confirmed defect

The pre-change reader silently fell back from the unquenched fields
`edep_scint_raw_MeV` / `edep_raw_MeV` to the quenched visible-energy fields
`edep_scint_MeV` / `edep_MeV`. It printed a warning but continued through the
same numerical tolerance gate. A quenched-only synthetic event was therefore
able to produce ratio `1.0` and `within_tolerance=True` against a raw PSTAR
reference.

This is not a valid substitution. Geant4 documents Birks quenching as a
nonlinear conversion from deposited energy to observed detector signal, with
proportionally less signal at higher deposited-energy density. NIST defines
PSTAR total stopping power as the sum of collision and nuclear energy loss per
unit path length. A quenched visible-energy proxy is therefore not directly
comparable to PSTAR total stopping power.

Primary references:

- Geant4 Collaboration, *Birks Quenching*, Book for Application Developers
  11.4: <https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/birks.html>
- NIST, *Description of PSTAR and ASTAR databases*:
  <https://physics.nist.gov/PhysRefData/Star/Text/programs.html>
- NIST, *Significance of Calculated Quantities*:
  <https://physics.nist.gov/PhysRefData/Star/Text/appendix.html>

## Acceptance rule

1. Raw unquenched energy deposit remains eligible for the existing numerical
   diagnostic, subject to all other scientific limitations.
2. Quenched-only input is rejected by default with input-error status 2.
3. `--allow-quenched-proxy` permits labelled diagnostic output only.
4. Quenched-proxy output records:
   - `energy_deposit_basis=QUENCHED_PROXY`;
   - `raw_pstar_comparable=False`;
   - the arithmetic-only `numeric_within_tolerance` value;
   - `within_tolerance=False` regardless of the arithmetic ratio.
5. The CLI exits nonzero and prints
   `NUMERICAL TOLERANCE: NOT_ACCEPTED_QUENCHED_PROXY`.
6. A file mixing raw and quenched rows is rejected because the aggregate has no
   single physical energy-deposit convention.

## Reproduction

Pre-change fallback-path reproduction:

```text
WARNING: edep_scint_raw_MeV absent -- using the QUENCHED edep_scint_MeV;
ratios vs raw PSTAR will look low.
rows=1 ratio=1.0 within_tolerance=True
```

Post-change focused validation:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_compare_stopping_power_quenched_proxy.py

python -m pytest \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_compare_stopping_power_quenched_proxy.py -q

18 passed in 2.86s
```

The local reference fixture used only the energies needed by the existing
self-test. The complete committed PSTAR table and real Geant4 event files were
not executed in this environment.

## Scientific boundary

This gate prevents a quenched detector-response proxy from being accepted as
raw stopping-power agreement. It does not resolve:

- secondary-particle escape from the scored volume;
- projectile energy evolution along the track;
- material, density, production-cut, or physics-list dependence;
- the approximate deuteron velocity-scaling relation;
- external PSTAR transcription provenance;
- real simulation or detector-data agreement.
