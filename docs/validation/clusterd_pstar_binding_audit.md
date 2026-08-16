# Cluster D VIS-MC-002 canonical PSTAR binding audit

## Scope and evidence class

This audit reviews the reference-data path and scientific status of Cluster D
`VIS-MC-002`. It is a software/reference-provenance correction. It does not
reprocess the external i885 ROOT campaign and does not establish accepted
stopping-power agreement.

Policy:

`CLUSTERD_VIS_MC_002_MUST_USE_CANONICAL_VALIDATED_PSTAR_REFERENCE`

## Confirmed defects

The campaign helper contained a separate 20-row PSTAR-like table while the
repository already contained a 141-row canonical PSTAR CSV and an exact-decimal
component-identity parser. The historical plot caption incorrectly said that the
canonical CSV was absent. The historical panel also reported a chi-square from
event-level standard errors even though the Geant4 observable is a local
deposited-energy proxy, reference/model uncertainties were absent, and no
accepted stopping-power measurand had been established.

At four shared energies, the former embedded mass-stopping values differ from
the canonical committed total column as follows:

| Proton energy | Former embedded | Canonical total | Former relative bias |
|---:|---:|---:|---:|
| 10 MeV | 50.5 | 45.0 | +12.2222% |
| 50 MeV | 19.8 | 12.21 | +62.1622% |
| 100 MeV | 12.9 | 7.14 | +80.6723% |
| 150 MeV | 9.74 | 5.331 | +82.7049% |

Units for the two stopping-power columns are MeV cm2/g. These are reference
transcription differences, not measured detector effects.

## Validated remediation

- Removed the embedded PSTAR table from the campaign helper.
- Reused `read_validated_pstar_table()` from the canonical exact-decimal parser.
- Bound interpolation to `total_MeV_cm2_g`, the committed 1.060 g/cm3 density,
  and fail-closed reference-domain checks.
- Added a dedicated renderer that records exact reference provenance, external
  run paths, exact-energy event counts, deposit and track-length sums, the
  `RATIO_OF_SUMS_TRACK_LENGTH_WEIGHTED` estimand, compensated summation, and plot
  byte/hash provenance.
- Removed an acceptance chi-square and explicitly records
  `uncertainty_method=NOT_EVALUATED` and `acceptance_statistic=NONE`.
- Quarantined the historical plot as `SUPERSEDED` in the Cluster D summary and
  added the canonical renderer to the reproduction script.
- Added a fail-closed audit and focused regression tests.

## Exact reference provenance

- Repository path: `data/reference/stopping_power/pstar_polystyrene.csv`
- Git blob: `7e953dd346caedcee6da54180fb636b890a64040`
- Bytes: 7,413
- SHA-256: `bc4d8b018115fd0892fe4ea22b6ec3da7be8ab65afa7595337c491ae6ed869dd`
- Validated rows: 141
- Component identity: `total = electronic + nuclear`
- Canonical parser version: 1.1.0

## Validation

Executed in the reconstructed focused checkout:

```text
python -m py_compile \
  scripts/single_stave/campaign_plots/_common.py \
  scripts/single_stave/campaign_plots/vis_mc_002_transport.py \
  tools/audit/validate_clusterd_pstar_binding.py \
  tests/test_clusterd_pstar_binding.py \
  tools/audit/render_clusterd_pstar_binding_evidence.py

PYTHONPATH=. pytest -q tests/test_clusterd_pstar_binding.py

5 passed in 2.08s
```

The exact 141-row reference returned `VALIDATED`; the binding audit returned
`VALIDATED` with zero findings. A reintroduced embedded table failed closed.
Out-of-range lookup, invalid UTF-8, and destructive output aliasing failed
closed. The validation JSON parsed, the SVG parsed as XML, and changed Python
lines were no longer than 97 characters.

## Better-method boundary

The dedicated renderer uses a ratio of separately compensated deposited-energy
and track-length sums at each exact configured energy. This is more traceable
than an unweighted mean of per-event ratios. It still does not make local energy
deposit equivalent to projectile total energy loss. Accepted closure requires
immutable real exports, a validated projectile-loss observable or
`G4EmCalculator`, secondary-escape and energy-evolution studies, and a complete
statistical/systematic uncertainty model under `BLK-G4-SP-001`.

## Unrun checks and limitations

The runtime could not resolve `github.com` for a complete local clone. No
external i885 ROOT file was available, so the new canonical PNG/JSON campaign
artifact was not generated. Repository-wide pytest, ruff, Geant4 build/CTest,
ROOT processing, broad link inventory, and GitHub Actions were not run. No
calibration, detector-performance result, deuteron validation, or accepted
stopping-power closure is claimed.
