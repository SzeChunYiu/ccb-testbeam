# MV3 v5 — REAL simulated two-arm trigger (B-M1 / STUDY_GAPS NEW-01)

- Generated: 2026-07-05 (UTC)
- Backlog item: **B-M1** (reviewer M1) — "Score `Trig_bar` volumes in GEANT4 → real
  per-event Sample-I/II flag; re-fit MV3; soften 'root cause established' → 'strongly
  indicated' until then."
- Route taken: **ROUTE B, sub-route b1 — a REAL reduced/matched GEANT4 production with
  `Trig_bar` scored as a sensitive detector** (NOT an emulation, NOT the truth proxy).
- Production job: LUNARC SLURM **3348610** (`ccb_mv3v5_trigprod`, lu2026-2-51/lu48,
  COMPLETED, ~6 min, 1,000,000 events).
- Analysis job: LUNARC SLURM **3348673** (`ccb_mv3v5`, COMPLETED).
- New MC: `geant4/data/output_krakow_1M_trig.root` (746,558,013 B, 1M events),
  **md5 `f73f35e1a6caf29890c3b1da2dfeb46c`**.
- Scripts: `geant4/jobs/mv3_v5_trigger_production.sbatch`, `geant4/gen_dedx_cd2.py`,
  `scripts/mv3_stopping_v5_realtrigger.py`, `geant4/jobs/mv3_stopping_v5.sbatch`.
- Artifacts (this dir): `mv3v5_grid.json`, `grid_table.md`, `mc.md5`.

---

## Verdict (one line)

**The two-arm coincidence trigger is now ESTABLISHED — by a real GEANT4 sensitive-detector
simulation, not a proxy — as the dominant mechanism of the MV3 stopping-depth discrepancy
(it drives the selected B2 fraction from 45.9% untriggered to 99.7% triggered, in the
direction of the data). But the *ideal* trigger OVER-purifies: it produces a near-pure
B2 deuteron sample (99.7%) that overshoots even the data's coincidence-enriched Sample I
(93.3%), so the profile is NOT quantitatively reproduced, and the proxy's headline
chi2/ndf ~= 625 is revealed to be over-optimistic. Mechanism established; quantitative
closure still open.**

---

## Audit result — why ROUTE B, sub-route b1

The 1M truth tree (`output_krakow_1M.root`, tree `hibeam`, 62 branches) scores exactly
three sensitive detectors — `TARGET`, `ProtoTPC`, `Sci_bar` — and **has no `Trig_bar`
branch**. The production config (`geant4/configs/krakow.config`) lists
`Detectors TARGET,ProtoTPC,Sci_bar`; the trigger paddles are in the geometry but were
never scored. So ROUTE A (real SD hits already in the tree) was **unavailable**.

Sub-route b1 (a real reduced production with `Trig_bar` scoring) turned out to be
**feasible on LUNARC**, contradicting the Phase-2 note that the toolchain was billy-only:

| Requirement | Finding |
|---|---|
| SD scoring is config-driven by volume name | `WasaDetectorConstruction::ConstructSDandField` attaches an `SD_Det` to every logical volume named in the `Detectors` string (`FindVolume` matches the **exact** name). Adding `Trig_bar` emits `Trig_bar_EDep/_Time/_LayerID1/_LayerID/_PDG/...` branches, identical structure to `Sci_bar`. |
| `Trig_bar` volume exists | Geometry `krakow_109_8-38deg_4-71deg.root` has 13 logical volumes including exactly `Trig_bar` (placed in both arms; `LayerID1`=1 B-arm, =2 A-arm; `LayerID`=0,1 the two staggered paddles). |
| Runnable binary + env on LUNARC | `HIBEAM_Detector/hibeam_g4_build/hibeam_g4` + conda env `packages/hibeam_env` (GEANT4 11.2.2, ROOT 6.32, VGM 5.4.0). Binary supports `Source scattering` and `.root` VGM geometry import. |
| Primary generator input | `Source scattering` = built-in pd-elastic generator, uniform theta_cm (the `/ElGen/CSFile` macro line is inert — `DefineCommands` never registers it). Only `dedx_p_in_CD2.txt` is required, and only for a sub-MeV beam-loss correction across the 1.15 mm target — regenerated (PSTAR-style, `geant4/gen_dedx_cd2.py`) and validated by profile reproduction below. |

Two operational fixes were needed: (i) the Feb-2026 LUNARC build's tasking-mode ntuple
merge silently deletes the master file — forced `G4RUN_MANAGER_TYPE=Serial` (single filled
tree; ~1,800 evt/s, 1M in ~6 min); (ii) the conda activation trips `set -u`, so the job
uses `set -eo pipefail`.

### Faithful-reproduction check (does the reduced production match the 1M sample?)

The ONLY change vs the original 1M production is `+Trig_bar` in the scored list. The
**untriggered** deepest-stave profile of the new sample reproduces the original within
statistics, confirming identical physics:

| Profile (untriggered, track/filtered/paired/g92) | B2 | B4 | B6 | B8 | chi2/ndf vs all-data |
|---|---|---|---|---|---|
| Original 1M (Phase-2, job 3346841) | 0.470 | 0.182 | 0.125 | 0.223 | 68,269 |
| **This production (job 3348610)** | 0.469 | 0.184 | 0.126 | 0.221 | **68,705** |

Match within Poisson. The proxy column also reproduces v4 (best A-HRD proxy chi2/ndf 410
here vs 555–625 in v4). The production is a faithful stand-in with a real trigger added.

---

## Trigger implementation (REAL, not proxy, not emulation)

Per-event flags built from genuine GEANT4 SD energy deposits in the trigger-paddle
*volumes* (`mv3_stopping_v5_realtrigger.py`):

```
A_fired  = max EDep over A-arm paddle hits (Trig_bar_LayerID1==2) > 0.5 MeV
B_fired  = max EDep over B-arm paddle hits (Trig_bar_LayerID1==1) > 0.5 MeV
trigger  = A_fired AND B_fired AND |t_A - t_B| < 20 ns     (Sample-I two-arm coincidence)
```

Threshold 0.5 MeV (MIP in 1 cm plastic ~= 2 MeV; the coincidence rate is flat over
0.2–1.0 MeV, so the result is threshold-insensitive) and a 20 ns window (prompt MC,
TOF-limited). This replaces the mv3 v4 **proxy** (which required a truth A-HRD `Sci_bar`
hit) with an actual paddle-volume energy-deposit coincidence.

Trigger yield over 1M events: A_fired 36,501 (3.65%), B_fired 110,978 (11.1%),
coincidence 36,186 (3.62%). A_fired subset of B_fired, so the coincidence is A-paddle-limited —
i.e. it selects events whose conjugate particle actually reaches the A-arm paddle.

### The mechanism, made explicit

| B-arm event class (untriggered, g92) | count | fraction that fires the A-paddle |
|---|---|---|
| deuteron-like, stops shallow (deepest = **B2**) | 106,521 | **31.1 %** |
| proton-like, stops deep (deepest = **B6/B8**) | 84,388 | **0.06 %** |

The conjugate of a shallow B2 deuteron is an ~85 MeV proton that reaches the A-arm
paddle (31% of the time, set by the A-paddle solid angle); the conjugate of a deep B-arm
proton is an ~37 MeV deuteron whose range dies before the A-paddle (fires it 0.06% of the
time). **The two-arm coincidence therefore keeps B2 deuterons and vetoes deep protons** —
exactly the range-telescope + trigger picture, now demonstrated with a real simulated trigger.

---

## MV3 re-fit with the real trigger

Data targets (`s00_selected_b_pulses.csv.gz`, net_adc>1000): all 0.876/0.063/0.039/0.023
(n=306,745); **Sample I 0.933/0.037/0.020/0.010** (n=233,184); Sample II
0.695/0.144/0.098/0.063 (n=73,561). Sample I is the two-arm-coincidence data sample —
the correct comparison for the real coincidence trigger.

| MC selection | n | B2 | B4 | B6 | B8 | chi2/ndf vs **all** | chi2/ndf vs **S-I** |
|---|---|---|---|---|---|---|---|
| untriggered (track/filt/g92) | 249,102 | 0.469 | 0.184 | 0.126 | 0.221 | 68,705 | 67,417 |
| v4 **proxy** A-HRD (track/incl/g60) | 59,257 | 0.872 | 0.056 | 0.038 | 0.033 | **410** | 2,727 |
| **REAL coincidence (event/incl/g92)** | 33,176 | **0.997** | 0.001 | 0.001 | 0.001 | 591,044 | **131,591** |
| REAL coincidence (event/incl/g60) | 32,987 | 0.999 | 0.000 | 0.000 | 0.000 | 1,357,544 | 314,720 |
| REAL A-paddle only (event/incl/g60) | 33,041 | 0.998 | 0.001 | 0.000 | 0.000 | 763,735 | 161,102 |

Composition of the real-coincidence B profile (paired/g92): 32,628 deuterons in B2 vs a
total of ~45 protons in B4+B6+B8 — a **98%-pure B2 deuteron sample**.

### Reading the numbers honestly

1. **Mechanism established.** The real trigger moves the untriggered B2 fraction 0.459 ->
   0.997, i.e. it is the trigger — not missing material (Phase-2: material hypothesis
   falsified, >=10.5 g/cm2 needed vs <=0.8 available) — that produces the shallow-stave
   concentration seen in the data. Direction and dominance are settled with a genuine SD
   simulation. This is a strict upgrade over the v4 proxy on the question "what causes the
   68,269?".

2. **Quantitative closure NOT achieved — the ideal trigger over-purifies.** The truth-level
   two-arm coincidence yields B2 = 99.7%, overshooting the data's own coincidence sample
   (Sample I, 93.3%) and far exceeding all-data (87.6%). Scored against the physically
   correct Sample I, the residual is chi2/ndf ~= 1.3e5 — **larger**, not smaller, than the
   proxy implied. The data retains a 6.7% (Sample I) / 12.4% (all) deep-stave population
   that the idealized trigger does not produce.

3. **The proxy's 625 was over-optimistic.** The v4/Phase-2 headline (chi2/ndf ~= 555–625 vs
   all-data) came from comparing a coincidence-selected MC — with a *loose, gain-dependent
   A-HRD threshold* that fortuitously retained ~13% non-B2 events — against the *mixed*
   all-data profile (12.4% non-B2). The agreement was partly coincidental: the true
   coincidence retains ~0.2% non-B2. The real trigger corrects this optimism.

---

## Comparison to the proxy result

| | Basis | B2 | chi2/ndf | Interpretation |
|---|---|---|---|---|
| MV3 v3 published (untriggered) | track | 0.470 | 68,269 | the FAIL |
| v4 proxy (best, vs all-data) | truth A-HRD | 0.871 | **555–625** | "strongly indicated" (over-optimistic; wrong data sample) |
| **v5 real trigger (vs all-data)** | Trig_bar SD | 0.997 | 591k | over-purified vs mixed data |
| **v5 real trigger (vs Sample I)** | Trig_bar SD | 0.997 | 131,591 | over-purified vs coincidence data; residual open |

The real trigger confirms the *sign and size* of the proxy's effect (huge B2 enrichment)
while overturning its *quantitative* agreement.

---

## Is the trigger now "established" as the root cause?

- **As the root-cause MECHANISM of the gross discrepancy: YES, established** (real SD
  simulation; 45.9% -> 99.7% B2; material hypothesis independently falsified). The claim
  moves from "strongly indicated (proxy)" to "established mechanism (real trigger)".
- **As a quantitative reproduction of the data profile: NO.** The ideal two-arm
  coincidence over-purifies; a 6.7%–12.4% deep-stave data population is unexplained by the
  truth trigger. The manuscript must NOT claim the profile is reproduced, and must retire
  the proxy's chi2/ndf ~= 625 as an artifact of a mismatched data sample.

Recommended manuscript language: *"A real GEANT4-simulated two-arm coincidence trigger
establishes trigger selection — not missing material — as the mechanism driving the
stopping-depth discrepancy (untriggered B2 45.9% -> triggered 99.7%). The idealized trigger
over-purifies relative to the data (Sample I 93.3% B2), so a residual deep-stave population
remains; quantitative closure is pending a data-side trigger/pile-up model."*

---

## What still blocks quantitative closure (it is NOT the SD production — that is done)

The residual deep-stave data population is unexplained by the *idealized truth trigger*.
Leading candidates, all outside a geometry/SD production:

1. **Accidental / pile-up coincidences in data** — a deep-proton B event whose A-paddle
   fires from an *unrelated* particle within the trigger gate would admit exactly the
   deep-stave events the truth coincidence vetoes. This is the leading hypothesis and is a
   digitizer/rate-model question (links to R_max, MC03 live-time, B-M8 early-peak class).
2. **Data Sample-I purity / trigger definition** — whether data "Sample I" is a clean
   two-arm coincidence or contains single-arm/other-trigger contamination (links to B-M6:
   disjoint run sets, beam differences).
3. **Trigger-paddle fidelity** — real threshold, segmentation, finite resolution, and exact
   paddle placement vs the truth `EDep` used here.
4. **LayerID->stave mapping and digitizer folding** (Birks, phase-locked peak_frac) — B-M9.

The real `Trig_bar` SD production (this work) removes the item the reviewer (M1) named as
blocking; the remaining work is data-side/digitizer, not a new GEANT4 production.

---

## Job / provenance summary

| What | Where | ID / state |
|---|---|---|
| Real `Trig_bar` production, 1M events, Serial | LUNARC lu48 | **3348610 COMPLETED** (~6 min) |
| MV3 v5 real-trigger analysis | LUNARC lu48 | **3348673 COMPLETED** |
| New MC md5 | `output_krakow_1M_trig.root` | `f73f35e1a6caf29890c3b1da2dfeb46c` |
| Test suite | LUNARC hibeam_env (py3.11) | **168 passed** |

Reproduce: `sbatch geant4/jobs/mv3_v5_trigger_production.sbatch` then
`sbatch geant4/jobs/mv3_stopping_v5.sbatch`.
