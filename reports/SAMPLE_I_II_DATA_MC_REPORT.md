# Sample I vs Sample II — Stave Outputs, Trigger Mimicry, and the First Data↔MC Comparison

<!-- claim-gate: #1045 / ADR-0002 -->
> **Evidence gate (2026-08-11):** MC Sample I/II membership uses the HRD
> first-stack-layer charged-hit **proxy** only (`MC_TRIGGER_PROXY`). Hardware
> trigger geometry/electronics remain `UNKNOWN_EXTERNAL` / **BLOCKED**. Do not
> read proxy agreement as validated hardware-trigger reproduction. See
> `docs/contracts/TRIGGER_HARDWARE_RESPONSE.json` and
> `docs/mc_validation/ADR-0002-trigger-hardware-proxy-blocked.md`.


**CCB / Krakow test beam (190 MeV p on CD₂, HRD range stacks A & B)**
Status: preliminary. Generated 2026-06-23 on LUNARC (SLURM job `3309697`, full 1M-event MC + 640k-pulse data).
Artifacts: `reports/sampleI_II_trigger_split_1782210822/` (JSON + figures), scripts `scripts/mc01_trigger_split_truth.py`, `scripts/data01_sample_split_staves.py`, `scripts/compare_data_mc.py`.

---

## 0. What this answers

This report addresses the four tasks set by the supervisor:

1. **Stave outputs for Sample I vs Sample II, in data and MC.**
2. **Does the MC description improve when we mimic the trigger cuts** for the two samples?
3. **Truth-level particle ID of particles entering A and B** for each trigger configuration.
4. **The first quantitative comparison of real data with the Monte Carlo.**

**Headline:** Matthias' prediction is reproduced and, for the first time, **confirmed against real data**. The coincidence trigger (Sample I) selects events where a **deuteron stops in the first B layer** (large pulses) while a **proton goes into A** — the p+d conjugate-kinematics signature. The single-B trigger (Sample II) is far more proton-like and penetrating, with no large-pulse pile-up in the first B layer.

---

## 1. Definitions

### Samples (trigger configurations)
| Sample | Hardware trigger | In **data** | In **MC** (mimicked) |
|---|---|---|---|
| **I** | coincidence: trigger in front of **A AND B** | runs 44–57 (`sample_i_analysis`) | charged particle entering A **and** B within **15 ns** |
| **II** | single: trigger in front of **B** only | runs 58–65 (`sample_ii_analysis`) | charged particle entering B (A ignored) |

Samples III/IV are the A-stack versions of I/II; the A data are hard to analyse and are not pursued here (B is the important stack), but the **A arm is used in MC** to form the coincidence.

### MC detector decoding (from `output_krakow_1M.root`, tree `hibeam`)
The two telescope arms are both stored in the `Sci_bar` detector and separated by `Sci_bar_LayerID1`:

- **`LayerID1 == 1` → B-stack** (8 layers, downstream arm @ −38°, the main detector)
- **`LayerID1 == 2` → A-stack** (4 layers, recoil arm @ +71.5°)
- `LayerID` = depth in the stack (0 = first layer); `PDG`/`EDep`/`Time` = truth particle / deposit / hit time.

"Entering A/B" = a **charged** `Sci_bar` hit in that arm's **first layer** (`LayerID==0`). EDep (MeV) is the MC proxy for the data pulse amplitude (ADC). Each generated event contains a primary **proton and a primary deuteron** (the p+d reaction products), so the coincidence is a genuine kinematic selection, not a rate accident.

---

## 2. MC trigger counts (1,000,000 events)

| | events |
|---|---|
| enter B (→ Sample II) | 237,098 |
| enter A | 69,770 |
| **A∧B coincidence ≤15 ns (→ Sample I)** | **64,762** |

So in MC the coincidence keeps ~27% of B-triggered events.

---

## 3. Task 3 — Truth PID of particles entering A and B

**Particles entering the first B layer (truth):**

| species | Sample I (coinc) | Sample II (single-B) |
|---|---|---|
| deuteron | **0.735** | 0.484 |
| proton | 0.124 | 0.404 |
| alpha | 0.074 | 0.054 |
| ¹²C | 0.039 | 0.029 |

**Particles entering the first A layer (truth), Sample I:** proton **0.833**, deuteron 0.074, …

**Reading:** requiring the A coincidence flips the particle entering B from a ~50/50 d/p mix to **74% deuteron, 12% proton** — because the conjugate recoil that fires A is a **proton** (83%). This is the p+d → p+d elastic/quasi-elastic correlation: proton into A (forward recoil), deuteron into B. This is precisely the physics that produces the D-enrichment Matthias saw.

---

## 4. Task 1 — Stave outputs, Sample I vs II

### 4a. MC, per B-layer

**Sample I (coincidence):**
| layer | hits | mean EDep (MeV) | d-frac | p-frac |
|---|---|---|---|---|
| 0 | 82,729 | **32.2** | **0.735** | 0.124 |
| 1 | 54,606 | 30.8 | 0.751 | 0.148 |
| 2 | 11,027 | 25.4 | 0.332 | 0.526 |
| 3 | 7,712 | 14.2 | 0.217 | 0.684 |
| 4–6 | ~5k each | 18–26 | ~0.005 | 0.84–0.92 |

**Sample II (single-B):**
| layer | hits | mean EDep (MeV) | d-frac | p-frac |
|---|---|---|---|---|
| 0 | 289,006 | 23.1 | 0.484 | 0.404 |
| 1 | 234,170 | 20.7 | 0.447 | 0.470 |
| 2 | 151,755 | 19.2 | 0.233 | 0.673 |
| 3 | 132,943 | 18.0 | 0.205 | 0.720 |
| 4–7 | 34k–100k | 17–24 | ~0.005 | 0.89–0.91 |

→ MC: Sample I deposits **more energy in the first two B layers** and is **deuteron-dominated there**; deuterons stop by layer 2. Sample II penetrates much more uniformly and is proton-dominated.

### 4b. DATA, per B-stave (analysis runs)

**Sample I:**
| stave | n pulses | mean ADC | p95 | frac large (>6000) | frac saturated (≥7000) |
|---|---|---|---|---|---|
| **B2** | 241,422 | **6090** | 9006 | **0.588** | **0.417** |
| B4 | 6,451 | 3034 | 5186 | 0.020 | 0.005 |
| B6 | 3,094 | 2857 | 4537 | 0.003 | 0.001 |
| B8 | 1,299 | 2841 | 4961 | 0.014 | 0.002 |

**Sample II:**
| stave | n pulses | mean ADC | p95 | frac large | frac saturated |
|---|---|---|---|---|---|
| B2 | 88,213 | 3663 | 7265 | 0.117 | 0.061 |
| B4 | 21,229 | 3006 | 5021 | 0.013 | 0.003 |
| B6 | 11,148 | 2811 | 4541 | 0.003 | 0.001 |
| B8 | 4,506 | 3277 | 5314 | 0.017 | 0.002 |

→ Data: Sample I is **96% concentrated in B2** with **42% of B2 pulses saturated** and a mean nearly 2× Sample II. Sample II is lower-amplitude and **penetrates** to B4/B6/B8. This is the data-side image of the MC stopping/penetrating contrast.

---

## 5. Task 2 & 4 — Mimicking the trigger, and the data↔MC comparison

**The Matthias effect — large pulses in the first B layer for Sample I, absent for Sample II — appears in BOTH:**

| first B layer (B2 / MC layer 0) | MC | DATA |
|---|---|---|
| large-pulse fraction, Sample I | 0.730 | 0.588 |
| large-pulse fraction, Sample II | 0.481 | 0.117 |
| **excess (I − II)** | **+0.249** | **+0.471** |
| mean signal ratio I/II | 1.39 (EDep) | 1.66 (ADC) |

Both excesses are positive and large → **the effect is real in data, and the MC trigger mimicry reproduces it.** Crude energy-scale anchor from matching the Sample-II first-layer medians: **≈ 246 ADC/MeV**.

**Does mimicking the trigger improve the MC description?** Yes, qualitatively decisively: without the trigger split the MC is a single inclusive distribution that matches neither sample. With the A∧B vs B-only split, the MC reproduces (i) the deuteron enrichment, (ii) the larger first-layer deposits, and (iii) the steeper depth fall-off of Sample I. Quantitatively the **data excess (0.47) is larger than MC (0.25)** — i.e. the real Sample I is *even more* stopping/saturating than MC. Likely causes, to pin next: the data `A>1000 ADC` selection preferentially keeps Bragg-peak pulses, B2 saturation (~7000 ADC) compresses the data tail, and the exact MC `LayerID ↔ B-stave` mapping + energy scale are not yet calibrated.

### Figures (`reports/sampleI_II_trigger_split_1782210822/compare/`)
- `first_B_layer_data_mc.png` — first-B-layer signal, data vs scaled MC, Sample I and II panels.
- `depth_profile_data.png` — fraction of pulses per stave, Sample I vs II (the stopping vs penetrating contrast).
- `mc_d_fraction_vs_layer.png` — MC truth deuteron fraction vs depth, both samples.

---

## 6. Caveats / what is NOT yet done
- **Energy/ADC scale and LayerID↔stave mapping are uncalibrated** — comparisons are shape/direction-level, not absolute. (Next: anchor with S14 range-energy + Birks; map MC 8 layers onto the 4 instrumented even-channel staves.)
- The MC coincidence uses **Sci_bar first-layer hits as a trigger proxy**; the real trigger scintillators are not in the geometry. A ±window scan (5/10/15/20 ns) would test robustness.
- Data Sample I/II split is by **run range** (the hardware trigger); we did **not** re-impose a 15 ns A∧B cut in data (A timing is hard, and B is what matters).
- A-stack (Sample III/IV) not analysed.
- Statistics: MC 1M events; data 640,737 selected B-pulses.

## 7. Next steps
1. Pin the MC energy→ADC scale and the LayerID↔B2/B4/B6/B8 mapping; redo the overlay on an absolute axis.
2. Coincidence-window scan in MC (5–20 ns) and a charged-vs-all-particle sensitivity check.
3. Add B2 saturation modelling to the MC (clip at the data ceiling) before comparing tails.
4. Fold this into the LaTeX report as the "GEANT4 truth + data/MC" chapter.

---

*Reproduce:* `sbatch geant4/jobs/mc01_trigger_split.sbatch` on LUNARC (uses `packages/hibeam_env` python, reads `geant4/data/output_krakow_1M.root` + the S00 selected-pulse table).


---

## Addendum 2026-08-16 -- Corrected entering-species estimators (#1046; supersedes the species-fraction numbers in this report)

Defect being closed: the species fractions in the body of this report did not
name their estimator (hit-record vs unique-track vs event-presence vs
deposited-energy counting), and the headline narrative treated a single
ambiguous "deuteron fraction" as a well-defined observable.

Corrected result -- regenerated 2M campaign `cmc_2m_regenerated_20260814`
(unique truth-TrackID counting, event-level bootstrap n=1000, seed 1046, 68%
CI; `reports/issue_1046_entering_species/cmc_2m_regenerated_20260814/mc_trigger_split_summary.json`):

| Estimator (B arm, first layer) | Sample I proxy (coinc, n=1106) | Sample II proxy (enterB, n=14112) |
|---|---|---|
| H2 unique-track flux, d | 0.593 [0.577, 0.607] | 0.173 [0.170, 0.176] |
| H2 unique-track flux, p | 0.282 [0.272, 0.294] | 0.734 [0.730, 0.737] |
| H3 event-presence, d | 0.620 | 0.176 |
| H4 deposited-energy share, d | 0.855 | 0.420 |

Corrected reading of the headline claim ("coincidence trigger selects events
where a deuteron stops in the first B layer while a proton goes into A"):

- SURVIVES, weakened and made precise: the coincidence-like population is
  deuteron-ENRICHED in the first B layer by track flux (59.3%) and
  deuteron-DOMINATED by deposited-energy share (85.5%); the
  entering-any-layer population is proton-dominated by track flux (73.4%).
- The A-arm composition is proton-led in both populations (p ~ 0.65,
  d ~ 0.24-0.26) and carries negligible discriminating power between them.
- Estimator choice moves the sample-I deuteron fraction by 26 percentage
  points (H2 0.593 -> H4 0.855): the three compositions answer different
  questions and are reported separately; none substitutes for another.
- All numbers remain MC_TRIGGER_PROXY-gated (#1045 open; cross-section
  uncertainty contract #1179 not propagated): they describe the MC transport
  model under the software coincidence proxy, not a validated
  hardware-trigger composition.

Provenance: `reports/issue_1046_entering_species/provenance.json` (input
sha256 0d8c8275..., seed 3500420, MODE_DIRECT_UNIT, producer sha-bound).
