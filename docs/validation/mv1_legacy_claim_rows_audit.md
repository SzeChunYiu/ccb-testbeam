# Legacy MV1 PID claim-row audit

## Scope and scientific question

This unit reconstructs canonical claim-ledger rows `CL-017` and `CL-018` from the
exact tracked legacy MV1 producer and its fixed truth-MC output. The question is not
whether the recorded numbers exist. They do. The question is whether they may be
represented as an accepted proton/deuteron PID ceiling or detector-performance result.

The answer is **no**. The values are fixed legacy simulation outputs, but their
validation design does not satisfy the repository's current production ML contract.
They are therefore retained as `GATED` truth-MC diagnostics rather than promoted to
`VALIDATED` performance claims.

## Exact repository evidence

| Item | Repository path / identifier | Exact evidence |
|---|---|---|
| Legacy producer | `scripts/mv1_mv2_truth_pid_energy.py` | Git blob `4f3632e59ede59bcf27e053265908ddca77b4386`; 10,508 bytes; SHA-256 `534c70a754dba6a7017b35bc9074111d7d8db8e43795240848ea312a25c6e6ee` |
| Legacy output | `reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json` | Git blob `9e49af48025b9699d957e932d06901dd47a45321`; 4,129 bytes; SHA-256 `ecf7c6209728899b641484a0409a3f4e2d2e403491d2c113b0e5a29f0f2df4bb` |
| Introducing commit | `3539ae3aad222284bd7be100802a2651c0e064de` | Added the producer and exact result; commit message advertises AUC 0.986 and 96% purity at 90% efficiency |
| Current corrected implementation | `src/ccb_mc_validation/studies/mv1_pid.py` | Uses group-disjoint event splitting, explicit estimator seeds, recorded versions, and fail-closed status handling |
| Corrective engineering commit | `ee3d9f93ab8b12757e5bfc5006dda7be74bb4c33` | Documents the row-index/group leakage defect and current ML-001 through ML-004 controls |

The legacy output records:

| Quantity | Fixed output |
|---|---:|
| All charged B-arm tracks | 400,369 |
| Proton tracks | 150,130 |
| Deuteron tracks | 146,842 |
| Binary p/d sample | 296,972 |
| HGB ROC AUC | 0.9859658513538254 |
| HGB purity at nominal 90% deuteron efficiency | 0.9644090769970706 |

These are simulation outputs from PDG truth labels and four truth-derived features:
first-layer deposit, second-layer deposit, total deposit, and stopping layer. They are
not measurements on beam data.

## Confirmed defects and limitations

### 1. Row-index parity is not an event-group-disjoint split

The legacy producer creates multiple track rows inside an event, then splits the
binary sample with `idx % 2 == 0` for training and the complement for testing. It does
not retain `event_id` in the record table. If an event contributes multiple charged
tracks, rows from that event can be present on both sides of the split. Event-correlated
generator or detector features can therefore leak from training into evaluation.

The repository's current MV1 implementation specifically replaces this with a
group-disjoint holdout keyed by `event_id`. The old 400,369-track source has not been
rerun through that corrected path, so the old values cannot inherit the current
implementation's validation status.

### 2. The HGB run is not completely deterministic or environment-bound

The legacy `HistGradientBoostingClassifier` call does not specify `random_state`. The
output also records no Python, NumPy, or scikit-learn versions and has no manifest
binding the producer, environment, exact ROOT input, and output. The JSON contains an
absolute source path, but no input byte size or digest.

### 3. No uncertainty is available

The AUC has no DeLong interval, grouped bootstrap, repeated split, seed ensemble, or
run/configuration sensitivity. The purity output records neither the held-out selected
count nor the true-positive count, so a Wilson interval cannot be reconstructed from
the committed summary. The nominal 90% efficiency threshold is a point construction,
not an uncertainty-aware operating point.

### 4. The current ledger rows were malformed and cited nonexistent paths

Before this correction, both rows had 38 fields under a 43-field schema. Their late
truth/status/source/CI fields were therefore withheld by the repository's fail-closed
schema policy. They also cited nonexistent legacy paths `reports/mv1_pid/REPORT.md`,
`scripts/mv1_pid.py`, and `reports/mv1_pid/results.json` rather than the tracked producer
and summary above.

## Better-method comparison

| Method | Leakage control | Determinism / provenance | Uncertainty | Scientific use |
|---|---|---|---|---|
| Legacy row-index parity | None at event-group level | Implicit HGB seed; no version/input manifest | None | Fixed historical diagnostic only |
| Current group-disjoint MV1 | Whole `event_id` groups separated; fail-closed overlap policy | Explicit `random_state=0`; versions recorded | Simple-cut Wilson interval only; ML AUC/purity uncertainty still requires extension | Correct engineering basis for a clean rerun |
| Required acceptance study | Frozen event/run/source groups and independent final holdout | Content-addressed code/config/input/output and repeated seeds | Grouped bootstrap or DeLong-style AUC interval; operating-point count interval; split/seed/config sensitivity | Candidate MC truth ceiling, still not beam-data PID validation |

A newer method is not accepted merely because it is newer. The required comparison is
a clean rerun of the exact source sample or a content-addressed replacement sample,
using group-disjoint evaluation and a preregistered uncertainty/robustness plan.

## Delivered governance correction

`CL-017` and `CL-018` now each have exactly 43 fields and record:

- the full-precision fixed source value;
- `truth_type=mc_truth_only`;
- `status=GATED` and `allowed_status_validated=NO`;
- the real producer, real output, and introducing commit;
- `n_mc=296972` for the binary p/d sample;
- `ci_status=NOT_EVALUATED_LEGACY_ROW_INDEX_SPLIT`;
- blocker `BLK-MV1-001`;
- explicit limitations on event-group leakage, uncertainty, determinism, provenance,
  and beam-data interpretation.

The cumulative ledger state advances from 14/26 to 16/26 exact-width rows. Ten rows
remain malformed and withheld; the global schema audit therefore correctly remains
`FLAWED` rather than being weakened to obtain a pass.

## Reproducible validation and visual evidence

Commands executed against exact reconstructed repository bytes:

```text
python -m py_compile \
  tools/audit/validate_mv1_legacy_claim_rows.py \
  tools/audit/render_mv1_split_leakage_evidence.py \
  tests/test_validate_mv1_legacy_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv1_legacy_claim_rows.py -q

6 passed in 0.82s

PYTHONPATH=. python tools/audit/validate_mv1_legacy_claim_rows.py \
  docs/claim_ledger.csv \
  reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json \
  scripts/mv1_mv2_truth_pid_energy.py \
  --output docs/validation/mv1_legacy_claim_rows_validation.json

python tools/audit/render_mv1_split_leakage_evidence.py \
  docs/validation/mv1_legacy_split_leakage.svg
```

The validator returned `VALIDATED` with zero issues for the corrected two-row contract.
The machine-readable record binds exact byte counts and SHA-256 digests. The SVG is
synthetic software-method evidence: it demonstrates how two-track events can be split
across train/test by row parity and how event-group splitting prevents that failure.
It is not detector data and does not estimate the magnitude of bias in this sample.
JSON parsing, SVG XML parsing, source Git-blob identity, and the repository 100-character
Python line convention passed.

## Acceptance boundary

This unit validates the **governance correction and audit gate**, not the PID numbers as
accepted performance. No ROOT file was rerun, no beam data were processed, no event
leakage magnitude was measured, no confidence interval was computed, and no production
PID model was selected.

Resolving `BLK-MV1-001` requires:

1. immutable input ROOT provenance and event IDs;
2. a clean group-disjoint rerun of the exact or explicitly superseding sample;
3. explicit estimator/library/version/seed provenance;
4. grouped uncertainty for AUC and operating-point purity/efficiency;
5. repeated-seed and split sensitivity plus an independent final holdout;
6. detector-response and physics-list sensitivity for the truth-MC ceiling; and
7. separate beam-data closure before any empirical PID-performance claim.
