# CCB test-beam paper — Cycle-4 pre-submission falsification audit

**Date:** 2026-08-16
**Scope:** exact main head `abd3b22bb69343eed70ec058128a1aa7c49b912e` (merge of #1380 / #1299 quarantine)
**Purpose:** discharge the #1301/#1305 Cycle-4 acceptance items: an adversarial reviewer reruns on the exact final head, explicitly attempts to falsify every abstract/conclusion numerical claim against its machine-readable artifact, and finds no unresolved central `BLOCK` in `docs/claim_ledger.csv`.

## Decision

**PASS at the falsification bar.** Every numerical claim in `publication/chapters/00_abstract.tex` and `11_conclusions.tex` reproduces exactly from its bound artifact on this head, every quantitative result the manuscript promotes is labelled with its ledger status (GATED results are stated as gated in the abstract itself), and the central-BLOCK scan finds zero BLOCKED ledger rows cited anywhere in the manuscript. The paper remains honest about what it is not: the open peripheral gates (threshold/baseline contract, hardware/run-log source-binding, optical nuisance envelope) are the documented reasons the two headline results stay GATED, and they are named as such.

## Falsification table — abstract/conclusion numbers vs artifacts

Attempted falsification: recompute or re-read each number from the canonical artifact named by the ledger row or chapter text.

| # | Manuscript claim (location) | Bound artifact (this head) | Verified value | Verdict |
|---|------|------|------|------|
| 1 | 33 runs, 1{,}096{,}728 events; Sample I 798{,}694, Sample II 298{,}034 (abstract ¶2, conclusions ¶1) | `reports/studies/paper_1318_depth_profile/manifest_8x16.json` (`events_by_run`, 33 entries, ids 31–65); `results/depth_profile_result_thresh_0.json` (`stave_occupancies`) | occupancies sum 798{,}694+298{,}034=1{,}096{,}728 exactly; 33 run ids | **BOUND** |
| 2 | Sample I B2 87.4% of normalized amplitude (abstract ¶2, conclusions ¶1) | `results/depth_profile_result_thresh_0.json` `normalized_profile_sample_i.B2` | 0.8740035 → 87.4% | **BOUND** |
| 3 | Sample II B2 72.7% (conclusions ¶1; abstract "entrance concentration") | `normalized_profile_sample_ii.B2` | 0.7267330 → 72.7% | **BOUND** |
| 4 | Sample I B8 0.8% / Sample II B8 6.1% (abstract ¶2; 05_data_taking) | `normalized_profile_sample_i.B8`, `normalized_profile_sample_ii.B8` | 0.0080349 / 0.0607753 | **BOUND** |
| 5 | deepest-stave share ≈ 7.6× Sample I (abstract ¶2, conclusions ¶1) | ratio of #4 values | 0.0607753/0.0080349 = 7.56 → ≈7.6× | **BOUND** |
| 6 | threshold scan 500/750/1000 ADC preserves direction, B8 ratio ≈1.3–1.4× (05_data_taking) | `results/threshold_sensitivity.json` | at 500 ADC: 0.23706/0.16952 = 1.398; direction (II>I at B8) preserved at every threshold | **BOUND** |
| 7 | run-block bootstrap, 1{,}000 replicates, seed 1318 (05_data_taking) | `results/depth_profile_result_thresh_0.json` `bootstrap_method`/`bootstrap_reps` | `run_block_bootstrap`, 1000 | **BOUND** |
| 8 | B4–B6 pair residual 8.7 ns, bootstrap 8.3–9.3 ns, 10{,}776 events (abstract ¶4, conclusions ¶2) | `reports/issue_1320_timing/result.json` | 8.748 ns; CI 8.295–9.270; n=10776 | **BOUND** |
| 9 | "supersedes an earlier 38 ns direct-mode diagnostic" (abstract ¶4, conclusions ¶2) | `reports/studies/data_side/REPORT.md:95` | "B4–B6 residual σ68 (ToF-subtracted) \| **38.0 ns** (sampling-limited)" | **BOUND** |
| 10 | located waveform product = 8 channels × 16 samples (abstract ¶4) | `reports/studies/paper_a02_waveform_lineage/manifest.json` | "exactly 16 samples/channel (indices 0–15); samples 16–17 … absent" | **BOUND** |
| 11 | regenerated optical grid 11.78 PE/MeV_vis, offset 0.65 PE, r²=0.976, n=10{,}000 (08_optical_response, inside `\publicationhold`) | `reports/paper_1303_optical_campaign_20260815T2209Z/1303_summary.json` | 11.78 / 0.65 / 0.976 present; chapter labels it `MC_MODEL_DEPENDENT` under publication hold | **BOUND (held)** |
| 12 | legacy 540 ps / sub-ns timing NOT cited as beam-data resolution (post-#1380) | `docs/claim_ledger.csv` CL-004/CL-005 (withheld); `04_timing_analysis.md` quarantine banner | chapters carry the quarantine banner; values framed as legacy/source-absent | **BOUND (quarantined)** |

Rounding note: items 2/3/5/8 are quoted in the manuscript at lower precision than the artifact (87.40035→87.4; 8.748→8.7; 8.295–9.270→8.3–9.3) — correct directional rounding, no claim exceeds its artifact.

## Central-BLOCK scan

Method: `python3 csv.DictReader` over `docs/claim_ledger.csv` (quoted-comma safe; the earlier `awk -F','` field-index attempt was unreliable and is superseded), then grep each BLOCKED claim id across `publication/chapters/*.tex`.

Result: 35 ledger rows; **7** with status `BLOCKED` — CL-005 (combined timing upper-bound withheld), CL-006 (B4–B6 covariance withheld), CL-010 (Rmax pile-up definition unresolved), CL-025 (forced-trigger pedestal unavailable), CL-026 (systematic propagation incomplete), CL-027 (saturation field diagnostic-only), CL-028 (digitizer identity/aperture).

Citation check: **0 of 7** appear anywhere in `publication/chapters/*.tex`. The two numbers the abstract does promote from GATED rows (CL-1318-001 depth profile, CL-1320-001 timing) are *stated as gated in the abstract text itself*. **No unresolved central BLOCK.**

CI cross-check on this head: `check-claims`, `check-status-labels`, `check-claim-links`, `check-numeric-ci`, `check-rmax`, `audit-superseded` all green on the #1380 head run (abd3b22b).

## What remains open (by design, documented in the paper)

These are the peripheral provenance gates behind the GATED statuses; none is a falsified manuscript number:

- threshold/baseline contract for the depth profile (CL-1318-001 `allowed_status_validated=NO`); abstract already says "the quantitative result remains gated".
- primary run-log / hardware-trigger source-binding (#1296 family).
- optical/SiPM nuisance envelope propagation for the #1303 grid (08 chapter holds the numbers under `\publicationhold`, `MC_MODEL_DEPENDENT`).
- the open provenance/physics issues (#1179, #1091, #1088, #1046, #1045, #968, #962, #954) correspond to the BLOCKED peripheral rows above; the conclusions section correctly describes the paper as "not yet a quantitative detector-performance publication" pending them.

## Cycle-3 → Cycle-4 delta

- C3-P0-001/002 (18-sample non-authorising product; #956/#1297 demotions) — chapters now bind the 8×16 product (#1318/#1320 artifacts) or quarantine legacy values (#1380).
- The Cycle-3 false Category-B clearance in `STALE_CLAIM_AUDIT_20260814.md` (scope stated as WIKI.md, Result line claimed repo-wide) is documented in that file's 2026-08-16 re-audit addendum and discharged by #1380.
