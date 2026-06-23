# MC-Validation Program — comparing every research direction against the GEANT4 simulation

**Owner:** analysis lead (Claude). **Status:** active, opened 2026-06-23.
**Why now:** the project completed ~230 *data-driven* studies (`reports/SUMMARY.md`, `FINDINGS_SYNTHESIS.md`) explicitly **without** Monte-Carlo truth. The `hibeam_g4` Krakow simulation is now built, run (1M events), and validated (the Sample I/II trigger-split reproduces Matthias' deuteron-enrichment — `reports/SAMPLE_I_II_DATA_MC_REPORT.md`). This program systematically brings the MC into **every** research direction and turns the synthesis "open questions (no data-driven answer)" into answered ones.

This document is the source of truth for the MC studies. Each study (MV*) becomes a LUNARC job under `geant4/jobs/` and a report under `reports/`. Same governing rules as `studies/STUDIES.md`: reproduce-first, traditional **and** ML, atomic decomposition, honest uncertainty, pinned provenance.

---

## The central fact that shapes the program

The MC tree `hibeam` contains **truth only** — per `Sci_bar` hit: arm (`LayerID1`: 1=B, 2=A), depth (`LayerID`), particle (`PDG`), energy (`EDep` MeV), time (ns), position, momentum. **It has no waveforms.** The data, conversely, is 18-sample ADC waveforms with no truth labels. So the research directions split into two tiers:

- **Tier-1 — truth-directly-comparable (no digitizer):** PID, energy/range, stopping-depth profile, Sample I/II. Compare truth quantities to the data-driven *inferences*. **Start immediately.**
- **Tier-2 — needs a digitizer:** timing, pile-up, pulse-shape/representation, pedestal, saturation. These data methods operate on the *waveform*; to compare we must turn MC truth into synthetic waveforms. **The digitizer is the program backbone.**

### The backbone: `MV0` — a calibrated digitizer (truth → synthetic 18-sample ADC waveform)
Turn each truth hit (EDep, time, PID) into a realistic one-ended WLS-fibre pulse: scintillator rise/decay convolution, WLS/fibre transit smearing, 10 ns sampling × 18, electronics noise + baseline, and **saturation clip at the data ceiling (~7000 ADC)**. Shape and noise are **calibrated against real average data pulses per stave**, ADC scale from `MV2`. Output: an MC "pulse table" byte-compatible with `s00_selected_b_pulses.csv.gz` plus the raw 18-sample arrays — so **every existing data script runs unchanged on MC, now with truth labels attached.** This is the single highest-leverage deliverable: it unlocks Tier-2 wholesale and lets us validate each data method against ground truth.

---

## Study lines (each maps a research direction to its MC comparison)

| ID | Research direction (data studies) | MC comparison | Tier / dep | Closes open question? |
|---|---|---|---|---|
| **MV1** | **Particle ID p vs d** (S15, P08) | truth p/d/α vs data ΔE–E & PSD separation; achievable purity/efficiency, ROC vs truth | T1 | **Yes** — "p vs d needs GEANT4" |
| **MV2** | **Energy / range calibration** (S14, P04) | truth EDep & range vs PSTAR/power-law range-energy; pin MeV↔ADC; test "10% absolute energy unreachable" | T1 | **Yes** — absolute energy |
| **MV3** | **Stopping-depth / stave profile** (Sample I/II, done-seed) | truth depth profile vs data per-stave counts; LayerID↔B2/B4/B6/B8 mapping | T1 | partially done |
| **MV4** | **Timing resolution & timewalk** (S02–S06, S18, P03) | digitized MC through data pickoff (CFD/OF/template) vs **truth time**; is 1.5 ns single-stave + timewalk reproduced? is the residual covariance structure (B2-dominated) real? | T2 (MV0) | validates method bias |
| **MV5** | **Pile-up & two-pulse recovery** (S10–S13, S11) | MC event-overlay at beam rate → **true** two-pulse separation/labels → validate failure-rate, dead-time/τ_eff, and the R_max≈3 MHz revision | T2 (MV0) | **Yes** — real pile-up truth |
| **MV6** | **Pulse-shape & representation** (S01, P02, P09) | digitized MC shape low-dimensionality (PCA/AE) vs data; **identify the ~4% early-peak/low-area anomalous class** (particle species? cross-talk? δ-ray?) | T2 (MV0) | **Yes** — anomaly identity |
| **MV7** | **Pedestal / baseline** (S16, P11) | digitizer with **known** pedestal → true forced/random pedestal sample → validate learned pedestal (MAE 49 ADC) without proxy | T2 (MV0) | **Yes** — true pedestal sample |
| **MV8** | **Saturation recovery** (P07) | MC **true** amplitude for B2>7000 ADC saturating pulses → validate natural-saturation recovery (vs the artificial-clip benchmark) | T2 (MV0) | validates transfer |

Plus **MV9 — synthesis**: an MC-vs-data column added to `reports/SUMMARY.md` and the `07_geant4_truth.tex` chapter; one verdict per direction (data method validated / biased / open).

---

## Execution order (value × independence)

1. **MV1 + MV2 + MV3** (Tier-1, now) — no digitizer; pure truth. These answer the headline physics open questions (PID, energy) and harden the energy scale the digitizer needs.
2. **MV0 digitizer** — the backbone. Build + calibrate to data, validate by reproducing data amplitude spectra and shape low-dimensionality (MV6 sanity).
3. **MV4 → MV5 → MV6 → MV7 → MV8** — Tier-2, each a clean truth-vs-method validation once MV0 exists.
4. **MV9 synthesis** — fold all verdicts into the report/scoreboard/LaTeX.

## Infrastructure
- All runs are `sbatch` jobs on LUNARC (env `/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3`, uproot 5.6.4); MC at `geant4/data/output_krakow_1M.root`; data table = S00 selected-pulse CSV. Reach fs10 via `ssh cosmos2`.
- Each MV study: a `scripts/mv*_*.py`, a `geant4/jobs/mv*.sbatch`, a `reports/<id>/` with JSON + figures + `REPORT.md`, committed with pinned provenance.
- Bigger MC statistics on demand: re-run `hibeam_g4` (`geant4/setup_and_run.sh`) for more events or alternate generators (elastic-only, breakup) as systematic variations.

## Acceptance for the whole program
Every research direction in `FINDINGS_SYNTHESIS.md` carries an explicit **MC verdict**: the data-driven method is either (a) validated against truth within stated tolerance, (b) shown biased with the bias quantified, or (c) genuinely limited (truth needed, now supplied). No direction is left "data-only, MC unknown."
