# Study report: P07 — Synthetic clipping-recovery benchmark (non-authorising for hardware saturation)

- **Study ID:** P07 (orchestrator-run while the codex fleet was credit-paused)
- **Author:** Claude (orchestrator) · **Date:** 2026-06-08
- **Depends on:** S00 (selection) · **Code:** `scripts/p07_saturation_recovery.py`
- **Input:** raw `data/root/root/hrdb_run_{58..63,65}.root` (historical manifest reports hashes)
- **Current claim state:** `GATED / SYNTHETIC-CLIPPING ONLY` under #1073/#1014. The repository has not established that 7000 ADC, 4095 ADC, or 16383 ADC is the physical CCB digitiser censoring rail.

## 0. Question
A substantial historical B2 population lies above the **7000-ADC analysis region** used by this study. Earlier text called those pulses likely digitiser saturation. That hardware interpretation is now **withdrawn pending #1073/#1014**: the native-to-stored ADC transfer and actual clipping mechanism are unresolved. The valid bounded question here is narrower: if otherwise clean pulses are *artificially hard-clipped* at a chosen constant ceiling, how well can their original amplitude be reconstructed from the remaining rising-edge samples?

This benchmark does not estimate a physical saturation fraction and does not establish that the real high-amplitude B2 population was digitally clipped.

## 1. Method & self-generated truth
Take **clean, unsaturated-by-construction-for-this-benchmark** pulses (single-peaked, peak in samples 4–12, 1500<A<6500 ADC — pre-clipping amplitude used as pseudo-truth). Artificially **clip at a fixed analysis ceiling C**, keeping only pulses with A>1.05·C so they are clipped by the injected transform. Recover A from the clipped waveform. **Train/test split BY RUN** (train 58–61, test 62/63/65) — no row-level leakage across that split.

- **Naive baseline:** assume A = injected ceiling.
- **Traditional:** least-squares scale of the mean clean pulse **template** to the unclipped rising-edge samples → peak.
- **ML:** GradientBoostingRegressor on the artificially clipped waveform → log A.

The hard clip is an injected sensitivity model. It is not yet the measured DATA transfer function.

## 2. Leakage caught and fixed
The **first** version clipped at `C = frac·A` (ceiling proportional to pseudo-truth amplitude). That makes `max(clipped) = frac·A`, so the ML can infer `A = max/frac` and produced res68 ≈ 0.002–0.008. That is target leakage, not a valid recovery benchmark. The study was corrected to use a constant injected ceiling, so `max(clipped)=C` no longer directly reveals pseudo-truth amplitude.

This correction removes that specific leakage. It does **not** validate the constant hard-clip model as the CCB hardware response.

## 3. Head-to-head benchmark under the injected hard-clip model

res68 of `|A_rec − A_pseudotruth|/A_pseudotruth` (lower is better):

| Injected ceiling C (ADC) | N clipped (test) | naive (=C) | traditional (template) | **ML (GBR)** |
|---|---:|---:|---:|---:|
| 4000 | 8,873 | 0.264 | 0.104 | **0.032** |
| 3000 | 20,254 | 0.346 | 0.239 | **0.039** |
| 2500 | 27,971 | 0.403 | 0.233 | **0.042** |
| 2000 | 33,823 | 0.493 | 0.286 | **0.046** |

**Bounded result.** Within this synthetic hard-clipping task and its selected clean-pulse domain, the reported GBR reconstructs the pre-clipping amplitude with res68 ≈3–5%, compared with ≈10–29% for the fixed-template method and ≈26–49% for the naive ceiling baseline. These numbers are properties of this benchmark dataset, split, pseudo-truth definition and injected transform. They are **not** a detector saturation-recovery calibration and do not authorize correction of real B2 high-amplitude pulses.

The original report speculated that the GBR advantage reflected amplitude-dependent quenching/non-linear response. That mechanism attribution is not identified by this benchmark: waveform-shape dependence may arise from multiple detector, electronics, selection or nuisance mechanisms. It remains a hypothesis, not a measured explanation.

## 4. Threats to validity

- **Physical transfer unresolved:** #1073/#1014 do not establish the hardware identity, code range, rail, repacking/calibration transform or over-range behavior. A constant hard clip is only one injected mechanism.
- **Pseudo-truth only:** the benchmark uses the pre-injection waveform amplitude, not an independently measured latent deposited energy or incident-particle truth.
- **Selection/domain shift:** clean single-peaked pulses used to construct pseudo-truth may not represent the real high-amplitude B2 population, which can contain late/overlap/recovery components.
- **No real-clipping truth:** real high-amplitude B2 pulses have no hardware-clipping label or independent pre-clipping amplitude truth in this study.
- **Model selection:** ML hyperparameters were not comprehensively preregistered/held out; a stronger amplitude-adaptive traditional baseline remains relevant.
- **Statistical unit / clustering:** the table reports the historical test-population counts and point diagnostics; authorising detector-performance inference would additionally require the current run/event-aware uncertainty and held-out-validation contracts.

## 5. Findings & required next steps

- **Validated only as a synthetic transform comparison:** under the injected constant hard-clip model, the historical GBR outperforms the two recorded baselines on the stated pseudo-truth metric.
- **Not authorized for production saturation recovery:** no real B2 pulse may be called hardware-saturated or corrected by this model solely because its code/amplitude is near or above 7000 ADC.
- Resolve #1014/#1073 first: bind hardware/firmware/native words, native→stored transform, rail/over-range semantics, polarity and code domain.
- Then measure run/channel absolute-code extrema and boundary occupancy, and if censoring is demonstrated, construct a source-bound saturation label/transfer model.
- Re-evaluate this recovery family on held-out real or independently instrumented evidence with run/event-aware uncertainty, stronger traditional baselines, and preregistered acceptance criteria.
- Propagate only an accepted recovery uncertainty into downstream energy/timing studies.

## 6. Reproducibility / provenance boundary

Historical command: `python3 scripts/p07_saturation_recovery.py` → `result.json`, `fig_saturation_recovery.png`; the historical manifest is intended to bind inputs/code. This report edit does not rerun those artifacts. The numerical table above is retained as the historical synthetic-clipping benchmark result, while its hardware interpretation is demoted.

See #1073 (`ARU-DAQ-ADC-RANGE-001`) and `docs/contracts/ADC_SATURATION_WORLD_REGISTRY.md`. Until their physical acceptance gates pass, P07 remains `GATED / SYNTHETIC-CLIPPING ONLY`.
