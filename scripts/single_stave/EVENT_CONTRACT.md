# Current Geant4 event-tree contract

## Status

The event tree written by `geant4/single_stave/src/RunAction.cc` and the
normalized table consumed by `analyze_single_stave.py` are different contracts.
Do not point the current ROOT file directly at the analyzer and interpret a
schema failure or a passing legacy fixture as scientific validation.

`adapt_geant4_events.py` provides an explicit, fail-closed conversion layer.
It is validated for schema and bookkeeping semantics only; it is not a detector
calibration or a validation of the existing analyzer's calibration model.

## Explicit mapping

| Current `events` branch | Normalized field | Meaning |
|---|---|---|
| `event` | `event_id` | Event identifier within the assigned run ID |
| `particle` | `particle_pdg` | Exact map: proton → 2212, deuteron → 1000010020 |
| `ke_MeV` | `kinetic_energy_MeV` | Configured primary kinetic energy [MeV] |
| `arrival_readout` | `n_end_selected` | Fibre 1, +x physical-readout arrivals |
| `detected_readout` | `n_detected_pe` | PDE/coupling detections at the same sensor |
| `track_len_scint_mm` | `track_length_scint_cm` | Explicit unit conversion, mm / 10 |

The adapter retains the producer's scintillation, WLS, and Cerenkov counters and
adds

```text
n_optical_generated_total =
    n_scint_generated + n_wls_generated + n_cerenkov_generated
```

The defensible arrival-count bookkeeping gate is
`n_end_selected <= n_optical_generated_total`, followed by
`n_detected_pe <= n_end_selected`. It is not valid to bound all readout arrivals
against the scintillation-only counter when WLS and Cerenkov optical tracks are
also recorded.

## Reproduce the conversion

```bash
python scripts/single_stave/adapt_geant4_events.py \
  --input stave_p100.root \
  --tree events \
  --run-id proton_100MeV_seed1 \
  --output stave_p100.normalized.parquet \
  --metadata stave_p100.normalized.meta.json
```

The converter records the input and output SHA-256, byte counts, row count,
selected-sensor semantics, exact field mapping, and the generated-track bound.
It rejects missing or ambiguous columns, nonfinite/noninteger counts, negative
counts, duplicate event keys, invalid count ordering, changed input bytes,
destructive path aliases, and accidental overwrite.

## Remaining downstream blocker

The existing analyzer still checks `n_end_selected <= n_scint_generated` and
uses that scintillation-only denominator in a collection-efficiency plot. The
adapter therefore reports `analysis_compatibility=SCHEMA_ADAPTER_ONLY`. Before a
current Geant4 ROOT file is accepted for scientific analysis, the analyzer must
be updated to use the explicit total-optical counter (while retaining the three
component counters), and that integrated path must be exercised on immutable
real ROOT bytes.

## Validation scope

Focused synthetic tests bind the adapter to the exact current `RunAction.cc`
branch declarations and cover mapping, unit conversion, WLS-inclusive count
semantics, malformed counts, ambiguity, atomic output, and alias/overwrite
protection. No Geant4 event, ROOT production sample, calibration, optical yield,
resolution, or detector-performance quantity is produced by this contract unit.
