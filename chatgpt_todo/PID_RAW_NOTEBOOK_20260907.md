# Raw PID notebook handoff — 2026-09-07

## Evidence state

User requested a from-raw-data E–delta E proton/deuteron analysis in a step-by-step Jupyter notebook. Delivery is **PARTIAL / RAW EXECUTION BLOCKED**, not a new beam-data result. Existing scheduled ACTIVE_TASK ownership and all production/public-claim gates remain untouched.

Repository source inspected: `cec9edc28257e0699c70c17fa9b2e8d806a3d42a`. HF dataset: `billyyiu747/ccb-testbeam`, revision `0b25f28e0144a3d1597afcdd3446ad1abd3d2d74`.

## Operations actually performed

- HF account/dataset metadata, raw-file schema, run-file listing and converter source were read.
- Local HTTP failed with a DNS/network error; the authorized raw-sample binary download also failed.
- A connected HF CPU job request, capped at five minutes, returned `402 Payment Required`. No job started; no credit/payment purchase was made.
- `01_raw_pid_analysis.ipynb` executed its blocked-input/status path only. No real events were processed and no fake raw-data plot was substituted.
- `02_SYNTHETIC_method_demonstration.ipynb` executed 3,780 artificial raw-shaped events across 21 illustrative runs, producing 33 plots explicitly marked SYNTHETIC / NOT BEAM DATA / NOT GEANT4.
- Both final notebook copies executed with no cell errors. Local scoped pytest: **23 passed**. This was not the full repository test suite.
- Original ROOT and raw Parquet readers were NOT exercised on real binary bytes in this environment. Real I/O and decoding validation remain required.

## Delivered artifacts

The conversation artifact `ccb_pid_notebooks_20260907.zip` contains both notebooks, HTML previews, `pid_core.py`, requirements, notebook builder, 23 regression tests, synthetic plots/tables/scores, source/environment manifests and a detailed README. These notebook bytes are delivered to the user, **not committed by this coordination-only change**.

Exact delivered source identities:

| File | SHA-256 |
|---|---|
| `01_raw_pid_analysis.ipynb` | `e622a4724bbc80cc1a785f1705df4c41786cc178143f5405580efd5b47c60fa5` |
| `02_SYNTHETIC_method_demonstration.ipynb` | `502c0bf1723be6d7312d93365f85c4165831963e933335f61e86bf8bf4026286` |
| `pid_core.py` | `2864b31fda526c46d60f192b7d9d433b6d85290e9a14247555446af939961961` |
| `tests/test_pid_core.py` | `e14f34d6cd786526addfbdb8256149b705b6c8002eff12fee249bbf894623c65` |

## Stable continuation tasks

| ID | State | Role and acceptance requirement |
|---|---|---|
| PID-NB-001 | BLOCKED_ACCESS | Data/provenance: acquire original archive or all 21 raw B-arm analysis-run Parquets; preserve immutable source hashes and event counts. A first-200-entry run prefix is not the full population. |
| PID-NB-002 | OPEN | DAQ: verify original 128-word event width, HRDI ordering and ADC semantics. Compare Parquet rows against original ROOT bytes; quantify any converter padding/truncation. Dimension agreement alone is insufficient. |
| PID-NB-003 | OPEN | Detector: establish polarity, channel/sample ordering, pedestal support, readout labels, rail/clip semantics and physical-layer mapping from hardware evidence. Acquisition channel indices 0/2/4/6 are not the G4 physical readout map. |
| PID-NB-004 | READY_UNEXECUTED | Software/statistics: execute the raw notebook on actual bytes; inspect run inventory, all prethreshold amplitudes, censoring counterfactual, depth, baseline and run-held-out component plots. Archive code/config/input/output receipts. |
| PID-NB-005 | BLOCKED_REFERENCE | Physics/statistics: acquire independent beam PID reference labels, or separately validate a full MC track/response/weight adapter. Do not name density components p/d by inspection or train on true entrance energy. |
| PID-NB-006 | SOFTWARE_CHECKED_ONLY | Reviewer: 23 pure regression tests and the synthetic end-to-end path passed. Require actual raw-reader/data falsification and hardware/calibration closure before scientific acceptance. |

## Calculation and inference contract

All four amplitudes must be reconstructed before thresholds. Missing measurements stay NaN; small measured signals stay measured; all-zero raw traces are flagged ambiguous; unknown saturation remains nullable. Use Delta E=A(B2), E=A(B4)+A(B6)+A(B8) in ADC, not MeV. Distinguish local threshold firing from cumulative deepest-active probability. Keep a fixed event anchor when comparing threshold scans.

The unlabelled density-discovery routine selects 1–4 components with inner run-disjoint validation and a separate held-out run; components are not species. The reference benchmark receives only reconstructed readout features, never truth energy/run/event/PDG inputs. Raw-mode scoring requires exact-key independent beam labels. Standard tie-aware ROC/AP functions and a training-run label-shuffle control are included. Nonunit reference weights are rejected rather than silently ignored. Conditional run-bootstrap intervals do not include detector/model systematics or full training-refit uncertainty.

The separate physical-sum check uses unique `edep_layer_0..7` deposits and an explicit ordered readout map. For (1,3,5,7), a synthetic [1,...,8] MeV fixture yields sparse E=18 and full E=33. It is an arithmetic test, not a production energy correction.

## Newly identified source caution

HF `parquet/convert_root_to_parquet.py` contains a padding/truncation fallback for irregular raw vectors and builds `sample/events_sample.parquet` from each run's first 200 entries. The event Parquet lacks original HRDI/row-length proof. This establishes a possible provenance loss and prefix-sampling design, **not** that actual production rows are malformed. Original-byte comparison remains necessary.

Sources: dataset card and `parquet/README.md` / `parquet/convert_root_to_parquet.py` at the pinned HF revision; repository `configs/s00_reproduction.yaml`, `tools/audit/validate_hrd_waveform_contract.py`, and `publication/chapters/07_deltae_e.tex` at the inspected repository revision.

## Next-session instructions

Retrieve the delivered ZIP, verify the hashes above, install `requirements.txt`, and run `python -m pytest -q tests`. Place `ccb_data_hrd.zip` under `data/` and select `INPUT_MODE='root_zip'`, or use the pinned raw-Parquet loader. Run from a clean kernel on all prespecified runs. Do not use the synthetic notebook as a download-failure fallback. Preserve all evidence gaps and leave species unassigned unless independent evidence exists. This file is transported on existing review PR #1624; neither notebook delivery nor PR transport is a main-branch scientific acceptance claim.
