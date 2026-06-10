# S16h: audit reduced-ROOT conversion for dropped non-beam trigger entries

- **Ticket:** `1781033977.1241.0d665665`
- **Author:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Depends on:** S00, S16f/S16g, S16h sorted-baseline benchmark
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `740e2e69da75d83e2c8fb40b3385adcd82b44616`
- **Config:** `configs/s16h_1781033977_1241_0d665665_reduced_root_trigger_filter_audit.json`

## Abstract

This study tests whether forced/random or other non-beam HRD entries are visible anywhere in the
mounted data path, and whether the reduced `h101` ROOT files lose entries when converted to the
sorted ROOT representation used by downstream analyses. The visible `h101` mirror is already
`TRIGGER==1` only: across all mounted HRDA/HRDB reduced ROOT files I find zero non-beam trigger
entries and zero trigger-like metadata branches beyond `TRIGGER`. The raw `h101` to sorted ROOT
comparison is entry preserving: every non-empty common HRDA/HRDB file has matching entry counts
and `EVT == hrdEvtNo` order. Four zero-entry HRDA placeholders (`run_0000` to `run_0003`) have no
sorted partner and do not contribute events. Therefore the sorted conversion did not drop
additional visible entries, but the data bundle does not contain upstream DAQ files or conversion
source code capable of proving whether non-beam triggers were filtered before `root.zip` was
produced.

## 0. Question

Did the reduced-ROOT production path drop forced/random or other non-beam HRD trigger entries before
the S16f inputs were created? The atomic tests are:

1. Reproduce the B-stack selected-pulse count directly from raw `h101/HRDv`.
2. Count `TRIGGER != 1` entries and trigger-like metadata branches in the current reduced `h101` mirror.
3. Compare reduced `h101` entries to sorted ROOT entries by run and event number.
4. Inventory visible archives/files for conversion source code or upstream raw files.
5. Benchmark the strong deterministic conversion audit against ML/NN methods where labels are estimable.

## 1. Reproduction Gate

For B-stack run \(r\), stave channel \(c\in\{B2,B4,B6,B8\}\), and waveform sample \(t\),
the raw pedestal seed and amplitude gate are

\[
p_{irc} = \operatorname{median}\left(x_{irc0}, x_{irc1}, x_{irc2}, x_{irc3}\right),
\qquad
A_{irc} = \max_t\left(x_{irct} - p_{irc}\right).
\]

The selected pulse indicator is \(I_{irc} = \mathbf{1}[A_{irc}>1000\;\mathrm{ADC}]\).

| quantity                                      |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| selected B-stave pulses from raw HRDv         |         640737 |       640737 |       0 |           0 | True   |
| non-beam trigger entries in visible h101 ROOT |              0 |            0 |       0 |           0 | True   |
| non-beam selected B-stave pulses              |              0 |            0 |       0 |           0 | True   |
| raw h101 to sorted entry drops or insertions  |              0 |            0 |       0 |           0 | True   |
| raw EVT to sorted hrdEvtNo mismatches         |              0 |            0 |       0 |           0 | True   |

The headline reproduction is exact: `640737` selected B-stave pulse records, matching the
project anchor `640737`. Among those selected pulses and among all audited `h101` entries, the
non-beam trigger count is zero.

## 2. Traditional Non-ML Method

The strong traditional method is a deterministic metadata and event-number audit. For every visible
ROOT file I compute

\[
N_{\mathrm{nonbeam}} = \sum_i \mathbf{1}[\mathrm{TRIGGER}_i \ne 1],
\]

then test the sorted conversion by

\[
D_r = |N^{\mathrm{sorted}}_r - N^{h101}_r| +
      \sum_i \mathbf{1}[\mathrm{EVT}^{h101}_{ri} \ne
      \mathrm{hrdEvtNo}^{\mathrm{sorted}}_{ri}].
\]

This method is preferred for the conversion-drop endpoint because it is exact, interpretable, and
does not require a positive training class.

### Trigger Summary

| stack   |   files |   entries |   non_beam_trigger_entries |   files_with_tag_like_branch |
|:--------|--------:|----------:|---------------------------:|-----------------------------:|
| hrda    |      57 |   1652508 |                          0 |                            0 |
| hrdb    |      53 |   1649802 |                          0 |                            0 |

### h101-to-Sorted Alignment Summary

| stack   |   files |   raw_entries |   sorted_entries |   entry_delta_sum |   evt_mismatch_count |
|:--------|--------:|--------------:|-----------------:|------------------:|---------------------:|
| hrda    |      57 |       1652508 |      1652508.000 |             0.000 |                0.000 |
| hrdb    |      53 |       1649802 |      1649802.000 |             0.000 |                0.000 |

### Alignment Status Counts

| stack   | status              |   files |   raw_entries |
|:--------|:--------------------|--------:|--------------:|
| hrda    | missing_sorted_file |       4 |             0 |
| hrda    | pass                |      53 |       1652508 |
| hrdb    | pass                |      53 |       1649802 |

The complete per-file outputs are `root_trigger_branch_audit.csv` and
`raw_to_sorted_alignment.csv`. All non-empty common files pass; the only missing sorted partners
are zero-entry HRDA placeholders. Missing upstream evidence remains important: `root.zip`,
`sorted-a.zip`, and `sorted-b.zip` contain ROOT payloads, not the source DAQ files or the
converter implementation.

## 3. ML and NN Methods

The pre-registered ML candidates were ridge, gradient-boosted trees, MLP, 1D-CNN, and a residual
CNN architecture. For the direct conversion-drop endpoint their labels are not identifiable: every
observed `TRIGGER` value is 1, every `h101` to sorted B-stack held-out entry is present, and every
event-number comparison is aligned. Training a supervised model on constant-zero labels would only
learn the class prior and would not test whether unseen forced/random triggers were filtered before
`root.zip`.

To still record a reduced-metadata benchmark against the same family of methods, this report links
the existing S16h run-held-out benchmark on the same `h101`/sorted mapping: predicting the raw
pretrigger median from sorted metadata and trapezoid waveforms. That benchmark is not used as proof
of non-beam trigger preservation; it is an information-loss benchmark for the reduced/sorted
representation. Its split is by run, with calibration runs 56/64, held-out runs 57/65, and
run-block bootstrap CIs.

| method                                 | family           |     n |   mae_adc |   mae_ci_low_adc |   mae_ci_high_adc |   bias_adc |   rmse_adc |
|:---------------------------------------|:-----------------|------:|----------:|-----------------:|------------------:|-----------:|-----------:|
| hist_gradient_boosted_trees            | ml               | 26871 |    20.366 |           15.218 |            25.218 |      0.141 |     93.107 |
| mlp                                    | ml               | 26871 |    35.173 |           28.732 |            41.243 |     -2.091 |    126.761 |
| sorted_residual_net                    | new_architecture | 26871 |    86.291 |           40.242 |           129.693 |    -31.844 |    412.582 |
| one_dimensional_cnn                    | ml               | 26871 |   120.403 |           71.383 |           166.607 |    -21.125 |    469.078 |
| ridge                                  | ml               | 26871 |   169.768 |          157.941 |           180.916 |     13.303 |    294.738 |
| traditional_calibrated_sorted_baseline | traditional      | 26871 |   190.234 |          118.922 |           257.447 |   -121.318 |    886.897 |
| sorted_baseline_direct                 | traditional      | 26871 |   332.962 |          202.240 |           456.171 |   -332.962 |   1226.818 |

## 4. Head-to-Head Benchmark

### Direct Conversion-Drop Endpoint

| method                         | family           | target                                                             | status           | metric                 |   value |   ci_low |   ci_high | notes                                                                                      |
|:-------------------------------|:-----------------|:-------------------------------------------------------------------|:-----------------|:-----------------------|--------:|---------:|----------:|:-------------------------------------------------------------------------------------------|
| deterministic_exact_event_join | traditional      | h101-to-sorted dropped/misaligned entries on held-out B-stack runs | estimable        | drop_or_mismatch_count |   0.000 |    0.000 |     0.000 | Exact ROOT event-number join; no supervised labels needed.                                 |
| ridge                          | ml               | h101-to-sorted dropped/misaligned entries on held-out B-stack runs | not_identifiable | drop_or_mismatch_count | nan     |  nan     |   nan     | All observed drop labels are zero; supervised training would be a constant-label exercise. |
| hist_gradient_boosted_trees    | ml               | h101-to-sorted dropped/misaligned entries on held-out B-stack runs | not_identifiable | drop_or_mismatch_count | nan     |  nan     |   nan     | All observed drop labels are zero; supervised training would be a constant-label exercise. |
| mlp                            | ml               | h101-to-sorted dropped/misaligned entries on held-out B-stack runs | not_identifiable | drop_or_mismatch_count | nan     |  nan     |   nan     | All observed drop labels are zero; supervised training would be a constant-label exercise. |
| one_dimensional_cnn            | ml               | h101-to-sorted dropped/misaligned entries on held-out B-stack runs | not_identifiable | drop_or_mismatch_count | nan     |  nan     |   nan     | All observed drop labels are zero; supervised training would be a constant-label exercise. |
| sorted_residual_net            | new_architecture | h101-to-sorted dropped/misaligned entries on held-out B-stack runs | not_identifiable | drop_or_mismatch_count | nan     |  nan     |   nan     | All observed drop labels are zero; supervised training would be a constant-label exercise. |

The winner for this ticket's endpoint is `deterministic_exact_event_join`. ML/NN methods are
reported as not identifiable, not as underperforming, because the visible data provide no positive
drop or non-beam-trigger labels.

### Auxiliary Reduced-Metadata Benchmark

| method                      |   delta_mae_vs_traditional_adc |   ci_low_adc |   ci_high_adc |
|:----------------------------|-------------------------------:|-------------:|--------------:|
| hist_gradient_boosted_trees |                       -169.868 |     -232.229 |      -103.704 |
| mlp                         |                       -155.061 |     -216.204 |       -90.190 |
| sorted_residual_net         |                       -103.943 |     -127.753 |       -78.680 |
| one_dimensional_cnn         |                        -69.830 |      -90.840 |       -47.539 |
| ridge                       |                        -20.466 |      -76.531 |        39.019 |
| sorted_baseline_direct      |                        142.728 |       83.318 |       198.724 |

For the auxiliary raw-pretrigger reconstruction endpoint, `hist_gradient_boosted_trees` is the
best reduced-metadata model and beats the calibrated sorted-baseline traditional method. This
supports the narrower statement that sorted metadata contain substantial pedestal information, but
it does not resolve the upstream-filter question.

## 5. Falsification

- **Pre-registration:** primary metric was the number of visible `TRIGGER!=1` h101 entries and
  the number of h101-to-sorted drops/mismatches. The win rule was to use the deterministic audit
  unless non-constant labels made supervised ML estimable.
- **Falsification test:** one non-zero `TRIGGER!=1` entry, one trigger-like branch proving a
  forced/random tag, one raw-to-sorted entry drop, or one visible converter/source file with a
  `TRIGGER==1` filter would falsify the strong conclusion.
- **Result:** all direct counts are zero in the visible mirror. No multiple-comparison p-value is
  quoted because this is an exhaustive file audit over mounted artifacts, not a sampled
  hypothesis test. The auxiliary ML benchmark scanned seven methods and reports paired
  run-block bootstrap CIs rather than claiming a new p-value.

## 6. Threats to Validity

- **Benchmark/selection:** the deterministic exact join is the right baseline for entry drops. It
  is not a strawman against ML; it directly evaluates the conversion endpoint.
- **Data leakage:** the selected-pulse reproduction uses raw `HRDv` only. The auxiliary benchmark
  is inherited from S16h and split by run; no event-level shuffle is used.
- **Metric misuse:** drop counts and event-number mismatches are full-population counts over visible
  files. The auxiliary regression reports MAE, bias, RMSE, residual quantiles, and run-block CIs.
- **Post-hoc selection:** the negative supervised-label decision follows from zero label entropy,
  not from model outcomes.

## 7. Provenance Manifest

Machine-readable provenance is in `manifest.json`. Input archive and artifact checksums are in
`input_sha256.csv`. Commands to regenerate this report are listed in Section 9.

## 8. Systematics and Caveats

- This is an absence-in-visible-artifacts result. It does not prove forced/random pedestal events
  were never recorded by the DAQ.
- The current `h101` files are reduced ROOT files, not raw binary DAQ streams. If a converter
  filtered `TRIGGER!=1` while producing `root.zip`, that filter is upstream of the available data.
- The sorted ROOT files preserve the current `h101` entry stream; they cannot recover entries that
  were removed before `h101`.
- The archive inventory found ROOT members and a PDF note, but no conversion source script in the
  mounted data bundle. The absence of source code blocks a code-level proof of filter semantics.
- Trigger semantics follow prior S16 work: `TRIGGER==1` is treated as the beam trigger and
  non-beam truth would require a different value or a dedicated tag branch.

## 9. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s16h_1781033977_1241_0d665665_reduced_root_trigger_filter_audit.py \
  --config configs/s16h_1781033977_1241_0d665665_reduced_root_trigger_filter_audit.json
```

Artifacts written:

- `result.json`
- `REPORT.md`
- `manifest.json`
- `input_sha256.csv`
- `selected_count_by_run.csv`
- `reproduction_match_table.csv`
- `root_trigger_branch_audit.csv`
- `raw_to_sorted_alignment.csv`
- `archive_inventory.csv`
- `filesystem_source_inventory.csv`
- `conversion_drop_benchmark.csv`
- `auxiliary_reduced_metadata_benchmark.csv`
- `auxiliary_reduced_metadata_deltas.csv`

## Findings and Next Step

The sorted conversion did not drop visible h101 events, and the current h101 mirror contains zero
non-beam entries. The unresolved scientific question is upstream: whether the DAQ or h101 converter
ever had forced/random trigger records and filtered them before `root.zip`. The most informative
next action is to obtain the original converter/source manifest or DAQ run log for the HRD reduced
ROOT production and grep/test it for trigger selection logic. This follow-up was appended as
`1781111822.1151.67af3b17`.
