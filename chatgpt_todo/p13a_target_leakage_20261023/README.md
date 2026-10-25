# P13A-LK01 — masked-sample target leakage (2026-10-23)

**TARGET_LEAKAGE_REPRODUCED; scientific release NOT_AUTHORIZED.** Live report:
https://github.com/SzeChunYiu/ccb-testbeam/issues/1609#issuecomment-6375156719
Posted and read back. Refs #1628/#1594; physical-noise/timing dependencies #1604/#1605.

## Source and decisive result

Main `a61427813344e29047ca9eb9b764182eb29e4c83`; producer
`scripts/p13a_1781035073_1085_4d0e5a1e_adc_noise_floor.py`, Git blob
`05f2175ff3cc587a5f16f6f00b855fa1d77cc575`. Only the verbatim `row_view`
(source lines 326-384) and phase helper were executed, with final newlines
normalized and excerpt SHA-256 guards. This is NOT full producer/ROOT execution.

The masked normalized target is recoverable from predictor inputs:
`z_j = full_area/amplitude - sum(masked_normalized_context)`.
A fixed linear map needs neither training nor a target argument: -1 on the first
18 feature columns, +1 on zero-based column 42. The neural auxiliary path also
contains this information. Disjoint runs do not remove within-row leakage.

Executed synthetic controls (not detector data): 4,096 artificial waveforms,
seed 20261023, 73,728 dependent masked views; oracle MAE/max error exactly 0 ADC.
The context-zero guard passes despite leakage. An arbitrary-scale float32
control (seed 20261024, 1,024 waveforms/18,432 views) gives MAE 0.00400134 ADC and
max error 0.0215519 ADC, arithmetic roundoff rather than physical noise.
A hidden nonpeak +256 ADC intervention changes only column 42 and reconstructs
exactly +256 ADC. Deleting area alone is insufficient: a hidden maximum still
changes full-waveform normalization/amplitude features.

14 unittest methods pass normally and under Python optimization; those are the
same tests, not independent replications. Strict result JSON is byte-identical.
The first arbitrary-scale test used an unjustified 0.02 ADC bound and failed;
it now checks a conservative scale-dependent float32 envelope. Initial/final
logs and the longer report are retained in the conversation evidence ZIP.

## Claim genealogy and limits

P13a report directory `reports/1781035073.1085.4d0e5a1e__p13a_adc_noise_floor/`:
reported ridge MAE 57.9566078 vs traditional 156.1694794 ADC, rising-edge floor
0.5339546 ns and charge floor 252.8075557 ADC-sample. These are source-reported,
NOT reproduced or corrected detector estimates. The report cites historical
commit `9342bdb1f91a70bf517dbcb384ace4db597edf69`; its exact runtime source/model
was not independently bound. Current source and report describe the same design.
The archived masking PASS artifact is included and full-blob checked.

The exact downstream consumer is
`configs/p13b_1781119277_1012_58a021c9_noise_weighted_timing.yaml`, blob
`de7ece758c564bf940bb992c9080e825f28599a9`: P13a sample_noise_floor.csv with
preferred method **gradient_boosted_trees, not ridge**. Reassess its affected
branch; no changed P13b result has been measured.

No authoritative raw ROOT, complete 12.65 MB heldout_predictions.csv, historical
model checkpoint, native Geant4/DAQ, noise covariance or independent human review
was obtained. Zero oracle error is NOT zero detector noise. Production repair is
NOT_INTEGRATED. Protected #977/PR1294 and canonical PR1595 ledgers are untouched.

Primary methodology: Batson & Royer, Noise2Self, ICML/PMLR 97 (2019), Definition 1
and Proposition 1: https://proceedings.mlr.press/v97/batson19a.html . The relevant
PDF page was visually read. Its MSE identity requires target invariance and
conditional-noise assumptions; it does not automatically apply to MAE/MAD or
correlated electronics. The algebraic leakage proof does not require the theorem.

## Reproduce and continue

Run in this directory with NumPy/pandas (versions in RECEIPT.json):

    python -m unittest -v test_audit
    python -O -m unittest -v test_audit
    python audit.py > RESULT.new.json

Tests should exit 0; audit.py deliberately exits 1 on the pinned reproduced flaw,
2 on source/execution error. Compare RESULT.new.json with RESULT.json.

Next owner work is raw-target masking BEFORE every dependent baseline, amplitude,
peak, area, normalization and template-selection operation, plus whole-input
noninterference controls. Rebuild fold-local preprocessing, refit authorized data,
preserve event/run dependence and evaluate untouched data. The mask-first control
here is review-only, not an integrated repair/calibration. Preserve old outputs,
qualify affected P13a figures and the identified P13b branch, then reconcile the
canonical ledgers after executed owner review. See HANDOFF.md. Do not repeat this
source oracle as another new atom or reopen the cleared Table-VI transcription.
