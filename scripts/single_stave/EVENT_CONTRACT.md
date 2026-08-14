# Current Geant4 event-tree contract

## Status

The `events` tree written by `geant4/single_stave/src/RunAction.cc` and the
normalized table consumed by `analyze_single_stave.py` use different branch
names and units. Do not bypass the explicit adapter.

`adapt_geant4_events.py` provides the fail-closed mapping. Analyzer version
2.1.0 now preserves the scintillation, WLS, and Cerenkov counters and uses the
exact total-optical count for arrival bounds and collection-efficiency plots.
This establishes schema and bookkeeping compatibility; it is not detector
calibration or real-ROOT physics closure.

## Explicit mapping

| Current `events` branch | Normalized field | Meaning |
|---|---|---|
| `event` | `event_id` | Event identifier within the assigned run ID |
| `particle` | `particle_pdg` | Exact map: proton → 2212, deuteron → 1000010020 |
| `ke_MeV` | `kinetic_energy_MeV` | Configured primary kinetic energy [MeV] |
| `arrival_readout` | `n_end_selected` | Fibre 1, +x physical-readout arrivals |
| `detected_readout` | `n_detected_pe` | PDE/coupling detections at the same sensor |
| `track_len_scint_mm` | `track_length_scint_cm` | Explicit unit conversion, mm / 10 |

The adapter retains the producer component counters and adds

```text
n_optical_generated_total =
    n_scint_generated + n_wls_generated + n_cerenkov_generated
```

The analyzer requires all three components and the declared total whenever any
current-contract optical field is present. It verifies the exact row-wise sum,
then applies

```text
n_end_selected <= n_optical_generated_total
n_detected_pe <= n_end_selected
```

The G4S-03 source table and plot metadata record the denominator and contract.
Legacy tables lacking WLS/Cerenkov fields remain readable only under the
explicit `LEGACY_SCINTILLATION_ONLY` label.

## Reproduce the normalized path

```bash
python scripts/single_stave/adapt_geant4_events.py \
  --input stave_p100.root \
  --tree events \
  --run-id proton_100MeV_seed1 \
  --output stave_p100.normalized.parquet \
  --metadata stave_p100.normalized.meta.json

python scripts/single_stave/analyze_single_stave.py \
  --input stave_p100.normalized.parquet \
  --output analysis/proton_100MeV_seed1
```

The adapter records input/output SHA-256, byte counts, row count, selected
sensor, exact mapping, and generated-track bound. The analyzer records its
policy/version, exact input identity, component/total summaries, denominator,
source tables, result, and output hashes.

## Remaining scientific blocker

The complete adapter-to-analyzer path is regression-tested with synthetic
current-contract tables. It still must be executed on immutable real ROOT bytes
with producer commit, sidecar, ROOT hash, normalized-table hash, row-count
closure, result/manifest hashes, and review of the generated plots before any
optical-yield, calibration, resolution, PID, or detector-performance claim is
accepted.

## Primary vs event-total stopping estimators (#1007)

The producer now distinguishes:

| Branch | Meaning |
|---|---|
| `edep_scint_raw_MeV` / `track_len_scint_mm` | All non-optical particles (calorimetric diagnostic) |
| `primary_edep_scint_raw_MeV` / `primary_track_len_scint_mm` | Primary only (`ParentID==0`) |
| `secondary_*` / `secondary_scint_activity` | Non-primary scintillator activity gate |

Authorising PSTAR / primary stopping-power comparisons must use the primary
estimator and exclude `secondary_scint_activity!=0`. Full regenerated closure
remains BLOCKED on material (#1000) and physics-list (#1006) resolution — see
`docs/mc_validation/adr/ADR-1007-primary-stopping-estimators.md`.
