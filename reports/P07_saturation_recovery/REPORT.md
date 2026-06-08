# Study report: P07 — Saturation recovery for high-amplitude pulses

- **Study ID:** P07 (orchestrator-run while the codex fleet was credit-paused)
- **Author:** Claude (orchestrator) · **Date:** 2026-06-08
- **Depends on:** S00 (selection) · **Code:** `scripts/p07_saturation_recovery.py`
- **Input:** raw `data/root/root/hrdb_run_{58..63,65}.root` (immutable; sha256 in `manifest.json`)

## 0. Question
~30–40% of Sample-I B2 pulses exceed 7000 ADC and likely saturate the digitiser, destroying the
peak. Can we recover the true amplitude from the unsaturated **rising edge**, and does ML beat a
traditional template extrapolation? Benchmarked on **self-generated truth**.

## 1. Method & self-generated truth
Take **clean, unsaturated** pulses (single-peaked, peak in samples 4–12, 1500<A<6500 ADC — true
amplitude known). Artificially **clip at a fixed ADC ceiling C** (a real ADC saturates at a
constant level), keeping only pulses with A>1.05·C so they genuinely saturate. Recover A from the
clipped waveform. **Train/test split BY RUN** (train 58–61, test 62/63/65) — no leakage.
- **Naive baseline:** assume A = ceiling.
- **Traditional:** least-squares scale of the mean clean pulse **template** to the *unclipped*
  rising-edge samples → peak.
- **ML:** GradientBoostingRegressor on the clipped waveform → log A.

## 2. ⚠ Leakage caught and fixed (process honesty)
The **first** version clipped at `C = frac·A` (ceiling proportional to true amplitude). That makes
`max(clipped) = frac·A`, so the ML trivially learned `A = max/frac` and scored res68 ≈ 0.002–0.008
— *too good to be true*. That is a textbook **target-leakage** artifact, not a real result. Fixed
by clipping at a **constant** ceiling (physical ADC behaviour), where `max(clipped)=C` carries no
direct amplitude information and recovery must come from the rising-edge **shape**. All numbers
below are from the corrected, leakage-free version.

## 3. Head-to-head benchmark (res68 of |A_rec − A_true|/A_true, lower = better)

| Fixed ceiling C (ADC) | N saturating (test) | naive (=C) | traditional (template) | **ML (GBR)** |
|---|---|---|---|---|
| 4000 | 8,873 | 0.264 | 0.104 | **0.032** |
| 3000 | 20,254 | 0.346 | 0.239 | **0.039** |
| 2500 | 27,971 | 0.403 | 0.233 | **0.042** |
| 2000 | 33,823 | 0.493 | 0.286 | **0.046** |

**Verdict.** ML recovers the saturated amplitude to **~3–5%**, beating the traditional template
extrapolation by **3–7×** and the naive ceiling assumption by ~8–11×. Crucially the ML **degrades
gracefully** with severity (0.032 → 0.046 as the ceiling drops from 4000 to 2000 ADC, i.e. as more
samples are clipped), whereas the template method degrades much faster (0.10 → 0.29). The likely
reason: the GBR learns the *amplitude-dependent* rising-edge shape (quenching / non-linear
response), which a single fixed template cannot capture. (`fig_saturation_recovery.png`.)

## 4. Threats to validity
- **Idealised clipping:** hard clip at a constant ceiling; real ADC saturation can have
  differential non-linearity / soft knee near the rail and correlated noise — not modelled.
- **Clean-pulse template** is built from train pulses; real saturated B2 may have late/overlap
  components (the P02 anomalous class) the clean template doesn't represent.
- **No real-saturation truth:** the benchmark uses *simulated* saturation of clean pulses; real
  B2>7000 pulses have no truth label — a consistency cross-check (recover then re-saturate) is
  the honest next step, and ultimately GEANT4 (S17).
- ML not hyperparameter-scanned beyond a sensible default; a stronger traditional baseline (fit
  the rising edge with the amplitude-adaptive template family, S01/P10) should be tried before
  declaring ML the winner for production.

## 5. Findings & next steps
- **ML is strongly preferred for B2 saturation recovery** on this leakage-free benchmark (~4% vs
  ~10–29%). This directly enables a usable amplitude for the 30–40% of B2>7000 pulses currently
  treated as diagnostic-only.
- Next: (a) validate on **real** saturated B2 (consistency, no truth); (b) strengthen the
  traditional baseline with the amplitude-adaptive template (S01); (c) propagate recovered-A
  uncertainty into the energy estimate (S14) and timing (saturated pulses' timewalk).
- Methodological: this study is the concrete cautionary example for `LESSONS.md` — *a benchmark
  that looks perfect is usually leaking*; always make the truth independent of the input.

## 6. Reproducibility
`python3 scripts/p07_saturation_recovery.py` → `result.json`, `fig_saturation_recovery.png`.
Inputs/code hash in `manifest.json`.
