# Track A — Held-out timing confirmation on the reserved partition {64, 12–30}

- Generated: 2026-07-05 (post-review improvement round, follow-up to B-M4 / S25)
- Goal: perform the one-shot held-out confirmation of the combined inter-stave
  timing resolution **σ₆₈ = 0.490 ns [0.470, 0.508]** (S25, `reports/s25_covariance_timing_1783241582/`)
  on the reserved confirmation partition, which the S25 run reported as
  "BLOCKED — data unavailable (not staged)".
- Provenance: `reserved_partition_format_diag.json` (this dir),
  `s25_exploration_reproduction.slurm.out` (LUNARC job 3349014).

## Executive summary

The reserved raw runs **do exist** (in `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/`,
Matthias Holl's raw store) — they were simply never staged into the working
`data/root/root/` directory, which is why S25 reported them unavailable. Staging them
and attempting the confirmation revealed the real, physically meaningful blocker:

> **The reserved partition {64, 12–30} was recorded in a different data-acquisition
> configuration from the Sample-II analysis runs, so it cannot serve as an
> apples-to-apples held-out confirmation of the 18-sample Sample-II downstream-stave
> timing resolution.** A valid one-shot confirmation requires a *new* beam run in the
> Sample-II configuration; no such data exists in this dataset. This upgrades the S25
> status from "BLOCKED — data not staged" to **"BLOCKED — reserved partition is an
> incompatible acquisition configuration"**, which is a definitive (not a pending) result.

Two concrete, positive outcomes were obtained:

1. **Exploration reproducibility (bit-exact).** Re-running S25 on the staged analysis
   runs reproduced the headline **combined σ₆₈ = 0.490 ns** exactly (LUNARC job 3349014,
   git-clean), confirming the S25 pipeline is deterministic and the number is stable.
2. **The blocker is now characterised, not assumed.** The confirmation-partition policy
   (`docs/CONFIRMATION_PARTITION.md`) had *warned* that runs 12–30 might differ in
   beam/detector conditions; this study shows the incompatibility is at the raw-DAQ
   level and, crucially, that it applies to **run 64 as well** (previously believed to be
   the cleanest in-Sample-II holdout).

## What the confirmation attempt found

`s25_covariance_timing.py`'s held-out branch crashed on run 64 with
`ValueError: cannot reshape array of size … into shape (8,18)`. Diagnosis of the raw
`HRDv` waveform branch across runs (analysis map: **B2=ch0, B4=ch2, B6=ch4, B8=ch6**,
even channels, 18-sample basis):

| Run | Sample | Samples/chan | Active-channel pattern | Downstream-stave signal under frozen map | Pulse truncation |
|---|---|---|---|---|---|
| **65** | II (analysis) | **18** | signal on **even** ch 0/2/4/6 (= B2/B4/B6/B8) | B4/B6/B8 populated as expected | peak@last-2 samples ≈ 13–15% (normal) |
| **64** | II (reserved calib) | **16** | signal on **odd** ch 1/3/5/7 (med 1.9k–2.6k ADC); even ch 0/2/4/6 near-empty | B4/B6/B8 (even) essentially empty (med 13–17 ADC) | odd ch7 peak@last-2 ≈ **99%** (truncated) |
| **12** | pre-Sample-I (reserved) | **16** | odd + ch0 large; even downstream empty | B6/B8 med 13–15 ADC | ch7 peak@last-2 ≈ **100%** |
| **30** | pre-Sample-I (reserved) | **16** | odd + ch0 large; even downstream empty | B6/B8 med 13–14 ADC | ch7 peak@last-2 ≈ **100%** |

Three independent incompatibilities, any one of which invalidates the frozen-model
confirmation:

1. **Window length.** Reserved runs use a **16-sample** acquisition window vs the
   **18-sample** analysis window. The frozen CFD/timewalk pipeline is hard-wired to 18.
2. **Channel-to-stave cabling.** In the analysis runs the B-staves sit on the **even**
   channels (0/2/4/6); in the reserved runs the large signals are on the **odd** channels
   (1/3/5/7). Under the frozen (even-channel) mapping the S25 downstream triple
   (B4·B6·B8, all A>1000) selects **near-empty channels** — the timing fit would run on
   baseline noise.
3. **Pulse truncation.** The active (odd) channels peak at the **last sample** of the
   16-sample window (ch7: ~99–100% of pulses in the final two samples). A rising-edge
   CFD time and a peak amplitude are not measurable when the pulse is not contained in
   the record. This alone kills any timing measurement on the downstream stave that maps
   to that channel, even if the cabling were remapped.

## Why this is a definitive closure, not a deferral

- The S25 policy requires the *exact frozen model and preregistered metric* evaluated
  **once** on the reserved runs. There is no legitimate way to do that here: the reserved
  waveforms are a different length, on different channels, and truncated. Any adaptation
  (remap channels, re-window, refit CFD/timewalk on the reserved runs) would no longer be
  the frozen one-shot model — it would be a *new exploration*, defeating the purpose of a
  held-out partition and re-introducing the multiple-comparisons problem the partition was
  created to escape.
- Therefore the honest, final status of the "first validated timing number" is:
  **σ₆₈ = 0.490 ns remains a single-partition (uncorroborated) result**, and it cannot be
  upgraded to "held-out validated" without a fresh Sample-II-configuration beam run.
  Run 65 stays the only (already-exhausted) Sample-II holdout.

## Recommendation

Carry the timing resolution as **"σ₆₈ = 0.490 ns [0.470, 0.508], single-partition;
held-out confirmation not achievable in this dataset (reserved partition is an
incompatible 16-sample / odd-channel / truncated acquisition)"**. Flag a new Sample-II
beam run as the only path to a confirmed number. Do not attempt a format-adapted
confirmation and present it as a held-out validation — it would be neither frozen nor
one-shot.
