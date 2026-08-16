# ARU — HRD width contract and raw-digest provenance re-audit

## Selected atomic universes

1. `raw HRDv event -> declared samples/channel -> per-event width validation -> S00 pulse extraction` (#952)
2. `16-sample raw product -> provenance manifest -> claimed relationship to 18-sample product` (#993)

## Repository state inspected

- `main@9c68115e1d374c61dad8b83dfc99569c8b0fb84b` after merged PR #1146.
- `configs/s00_reproduction.yaml`: canonical S00 still declares `samples_per_channel: 18`.
- `reports/studies/data_side/REPORT.md`: located raw ROOT payload described as `8 x 16 = 128` words/event.
- `tools/audit/validate_hrd_waveform_contract.py`: per-event scalar-width gate rejects mismatches before stack/reshape.
- `reports/studies/data_side/provenance.json`: `raw_input_sha256_count = 33` while only three digest records are serialized.
- `scripts/studies/data_side_real_beam.py`: provenance producer deliberately wrote `digests[:3]`, creating the count/list contradiction.
- `docs/claim_ledger.csv`: CL-001 remains `GATED`, blocked by `#952;#953;#954`.

## #952 narrow mechanism closure versus parent closure

PR #1146 correctly removes the aggregate reshape failure mode. For event rows `r_e`, each row now must satisfy

`|r_e| = n_channels * samples_per_channel`

before stacking. This rejects the hostile equality

`9 * (8*16) = 8 * (8*18)`

as a cross-event interpretation because every 128-word event is tested against the declared 144-word contract independently.

The parent issue was nevertheless reopened because its original acceptance contract also requires:

- malformed-event quarantine keyed by `(run, EVENTNO, EVT, original_length, reason)`;
- short/long/final-channel/reorder/duplicate hostile controls and a valid 8x16 fixture;
- all-run real-data width census with immutable hashes and zero unexplained mismatches;
- exact source-hash binding in downstream manifests;
- no 16<->18 equivalence language without the separate lineage proof in #993.

The current validator raises immediately on a bad row. Therefore the subsequent producer branch `if hrd_summary.malformed_events:` cannot produce malformed-row provenance: on malformed input, no `BatchValidation` object returns from `validate_and_reshape_rows()`.

## #993 provenance contradiction

The data-side producer hashes every available raw run but previously persisted only `digests[:3]`, while persisting the full `len(digests)` as `raw_input_sha256_count`. Current tracked provenance consequently exposes three digest records but reports a count of 33.

This is not a statistical discrepancy. It is an exact serialization/provenance mismatch:

`len(raw_input_sha256) != raw_input_sha256_count`.

The report's feature-level overlap (baseline/amplitude/peak agreement for many matched pulses) does not identify the missing two-sample mechanism. Competing worlds still include genuine trailing acquisition samples, a separate conversion product, padding/reconstruction, population drift, and transforms that preserve early-sample features while changing tails.

## Implemented bounded repair on branch

Branch `fix/data-side-complete-raw-digest-manifest`:

- adds `collect_raw_input_digests()` to return every available digest plus explicit missing canonical runs;
- removes the presentation truncation from the provenance field;
- adds `raw_input_missing_runs` and `raw_input_sha256_complete` so partial raw availability is explicit rather than implied complete;
- adds regression tests that create synthetic raw files and require list/count equality, exact hashes, stable run ordering, missing-run reporting, and persisted-manifest equality.

This branch does **not** invent the absent 30 historical digest values and does not modify the tracked measured-data `provenance.json`. The real artifact must be regenerated on the data host with the original files.

## Four sequential expert passes

### DAQ/data-contract lead — REVISE #952 closure

Evidence: merged producer gate, canonical 18-sample config, located 16-sample raw report.

Strongest counter-hypothesis: the canonical 18-sample product is a separate legitimate acquisition/conversion product. Required falsifier: exact producer/source lineage and event/channel/sample mapping.

Vote: **ACCEPT narrow per-event gate / REVISE full #952 closure**.

### Adversarial mechanism reviewer — BLOCK 16<->18 equivalence

Feature agreement on the first-four baseline and amplitude cannot distinguish tail construction or product population mechanisms. The canonical-only population demonstrates that tails/product differences can affect selection or downstream observables.

Vote: **BLOCK provenance equivalence**.

### Independent statistics/validation reviewer — ACCEPT deterministic digest repair / BLOCK empirical closure

The digest list/count inconsistency is exact and unit-testable. The real all-run width census and full regenerated digest set are unavailable in this runtime.

Vote: **ACCEPT branch repair pending CI / BLOCK real-data closure**.

### Claims/provenance reviewer — ACCEPT reopening / no CL-001 promotion

CL-001 is already GATED and names #952/#953/#954 blockers. Reopening #952 restores consistency between issue state and ledger semantics. #993 remains the authority for any 16<->18 lineage claim.

Vote: **ACCEPT governance correction**.

## Child atoms / dependencies

- #952: quarantine/census artifact and full hostile fixture set.
- #993: complete regenerated raw digest manifest and exact 16<->18 stage-by-stage mapping.
- #953: raw-to-sorted exact event/channel/sample closure remains open.
- #954: per-channel polarity remains open.

## Scientific boundary

No raw ROOT file was available to this runtime. No waveform count, timing, PID, energy, penetration, pile-up, calibration, Geant4, or detector-performance quantity was regenerated or promoted.