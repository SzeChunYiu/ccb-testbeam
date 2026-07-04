# Phase 2 — Geometry Audit + Stopping-Profile Diagnostics (MV3 closure)

- Generated: 2026-07-03 (UTC)
- Author: Phase-2 execution session (per EXTERNAL_REVIEW_2026-07-02.md §7, Phase 2)
- Diagnostic job: LUNARC SLURM **3346841** (`ccb_mv3v4diag`, lu2026-2-51/lu48, COMPLETED, 9 s)
- Artifacts: `mv3v4_grid.json`, `grid_table.md` (this directory, LUNARC + local mirror)
- Script: `scripts/mv3_stopping_v4_diagnostics.py` (new; reproduces MV3 v3 bit-for-bit at its
  reference point, then scans hypothesis axes)

## Verdict (one line)

**The "missing upstream material" narrative is retracted.** The production geometry already
contains every named upstream component except ~0.13 g/cm2 of air; the physically available
missing material (<~1 g/cm2) is an order of magnitude below the ~10.5 g/cm2 a material
explanation would require. The MV3 FAIL is instead dominated by the **unsimulated two-arm
coincidence trigger**: requiring an A-arm coincidence in MC truth alone collapses
chi2/ndf from 68,269 -> 3,141, and with the gain scan to 555-625 (**~120x / 2.1 orders of
magnitude**). No new GEANT4 production was needed or launched.

---

## Stage 1 — Geometry audit (what the PRODUCTION file actually contains)

### Provenance chain (settled)

| Item | Finding |
|---|---|
| Geometry file used for the 1M production | `krakow_109_8-38deg_4-71deg.root`, **md5 `8fc9d2163105c8461a602bde18676b3f` identical** in (i) the actual build dir `billy:/home/billy/ccb-geant4/hibeam_g4_github/build_conda/`, (ii) `billy:/home/billy/ccb-geant4/`, (iii) LUNARC `geant4/data/`. File dated 2026-02-11, i.e. **after** the geobuilder trigger-scintillator commit `ced58bf` (2026-01-26). |
| 1M truth file | `output_krakow_1M.root`, md5 `31c84858365d5d9696a674c0f45fb39f` identical local (production host) and LUNARC (analysis host). 1,000,000 events, produced 2026-06-10 by `run_full.sh` on workstation `billy` (NOT on LUNARC — the LUNARC jobs 33xxxxx are analysis only; "original job 3310358" is the 23-second `ccb_mv1mv2` analysis job). |
| MV3c §3 file-provenance ambiguity | **Resolved by direct volume dump** of the production file (definitive regardless of file dates): the trigger scintillators ARE in the geometry that produced the 1M sample. |

### Volume inventory (direct `TGeoManager` dump of the production file)

Coordinates in cm, target at origin; B stack = `Sci_stack1` (8 bars, -38 deg side, LayerID1=1);
A stack = `Sci_stack2` (4 bars, +71.5 deg side, LayerID1=2; ProtoTPC in front -> matches the
owner's "TPC sits in front of Stack A").

| Component | In production geometry? | Details |
|---|---|---|
| CD2 target | **YES** | tube r=2.93, thickness 0.23 cm CD2 (0.232 g/cm2) at z=0 |
| Vacuum/beam window | **YES** | 100 um Mylar disc at z=-5 (0.014 g/cm2) |
| Beam pipe | **YES** | Al tube, 5 mm wall, z=-55..-5 (upstream of target; not in the arm paths) |
| B-arm trigger scintillators | **YES** | `Trig_stack_1` at r~99 cm (stack front at 109 cm): 2 staggered `Trig_bar` paddles, PSci 1 cm each (1.03 g/cm2 per paddle crossed) |
| A-arm trigger scintillators | **YES** | `Trig_stack_2`, same construction, r~99 cm |
| ProtoTPC (A arm) | **YES** | Al hull (0.25 cm walls) + Ar80CO2 gas, in front of Stack A only |
| B HRD stack | 8 x `Sci_bar` PSci 2 cm, contiguous (16 cm = 16.5 g/cm2) | |
| **Air** | **NO — genuinely missing** | world (`MOTHER`) is **Vacuum**; the real ~109 cm target->stack path is air ~ **0.13 g/cm2** |
| Inter-stave dead material (wrapping/PCB) | **NO** (confirms MV3c) | bars placed back-to-back with zero gap; realistic budget ~0.1-0.5 g/cm2/pair (MV3b errata) |

So of the owner's named upstream candidates for the B arm — vacuum window, ~100 cm air,
B trigger scintillators — **only the air is missing**, and it is worth 0.13 g/cm2
(a 105 MeV deuteron loses ~1.8 MeV crossing it: negligible).

Geobuilder checkouts found: `lastrand/hibeam_g4_geobuilder` (LUNARC, has built binary but its
`krakow.cxx` contains **no** trigSci -> predates `ced58bf`; unusable as-is),
`bmeirose/FullSimCondaTEST2/wasa_full/hibeam_g4_geobuilder` (LUNARC, other user's dir).
Neither was needed (see Decision). A rebuild, if ever required, should clone fresh from
`HIBEAM-NNBAR/hibeam_g4_geobuilder@main`.

---

## Stage 2 — How much material would be needed vs. how much is available

Barkas/PSTAR-calibrated CSDA ranges in PSci (rho=1.032), pd-elastic kinematics at 190 MeV:

| Particle into B arm (38 deg) | Energy | Range | Where it stops (bare stack) |
|---|---|---|---|
| Recoil deuteron | **104.9 MeV** | 4.50 g/cm2 = 4.4 cm | **B2/B4 boundary** |
| Scattered proton | **152.9 MeV** | 14.6 g/cm2 = 14.2 cm | **B8** (layer 7) |
| Beam proton (reference) | 190 MeV | 21.4 g/cm2 | punches through (16.5 g/cm2 stack) |

- A stave-pair (2 x 2 cm) = 4.13 g/cm2. A proton must enter the stack below ~74 MeV to stop
  within B2. Degrading the 153 MeV elastic protons to that point requires **>= 10.5 g/cm2**
  of upstream material.
- Physically available missing material: air 0.13 + inter-stave wrapping <~0.5 + B2 ESR
  wrapping <~0.1 ~ **<~ 0.8 g/cm2** — a factor **>= 13 short**. (Consistent with the MV3b
  errata's retraction of the 8-10 g/cm2 toy estimate; the toy's baseline was wrong.)

**Honest conclusion: no physically defensible amount of upstream material can move the MC
profile (B2 47%) to the data profile (B2 88%).** The explanation must lie in what is being
compared, not in the geometry — which the cheap diagnostics below confirm.

### Cheap-diagnostic chi2 table (the key science)

Grid over the EXISTING 1M truth (job 3346841). Threshold model identical to MV3 v3
(`peak_adc = gain x edep x 0.733 > 1000`). Data target = MV3 v3 data counts
(all: 87.6/6.3/3.9/2.3 %, n=306,745). Reference row reproduced exactly.

| Hypothesis (change vs MV3 v3) | B2 | B4 | B6 | B8 | chi2/ndf (all) |
|---|---|---|---|---|---|
| **MV3 v3 reference** (track, species-filtered, paired map, gain 92, no trigger) | 0.470 | 0.182 | 0.125 | 0.223 | **68,269** |
| (a) event basis only | 0.461 | 0.176 | 0.125 | 0.238 | 71,624 (worse) |
| (b) species-inclusive only (add alpha, C12, ions) | 0.473 | 0.184 | 0.124 | 0.219 | 67,096 (~no change) |
| (c) odd mapping, layers 1,3,5,7 read | 0.409 | 0.167 | 0.285 | 0.139 | 92,723 (worse) |
| (c') even mapping, layers 0,2,4,6 read | 0.463 | 0.174 | 0.122 | 0.242 | 70,857 (worse) |
| **(e) A-arm coincidence trigger proxy only** | 0.869 | 0.059 | 0.021 | 0.051 | **3,141** |
| (d) event + inclusive combined (no trigger) | 0.460 | 0.177 | 0.124 | 0.238 | 71,760 |
| (d') event + inclusive + trigger | 0.869 | 0.057 | 0.020 | 0.054 | 3,613 |
| event + inclusive + trigger, **gain 60** | 0.871 | 0.055 | 0.038 | 0.036 | **625** |
| best overall: track + inclusive + trigger, gain 60 | 0.871 | 0.056 | 0.038 | 0.036 | **555** |

Gain scan (event/inclusive/paired/trigger): monotonic preference for the low end —
60->625, 80->2,618, 92->3,613, 110->4,840, ..., 300->7,017. Without the trigger the gain
scan is flat at ~71-74k: **gain cannot rescue the untriggered comparison**, and the
previously "reported and discarded" KS-optimal gain 60 is independently supported.

Answers to the four review hypotheses:
1. **Event-vs-track basis: explains nothing** (slightly negative).
2. **Species filter (C12/alpha excluded): explains nothing** (heavy ions are only ~2% of
   B-arm deepest-stave tracks).
3. **Odd-bar mapping (review P4): disfavored** — both unread-bar variants are *worse* than
   the paired-sum guess at every gain/trigger setting. P4 can be closed: `paired` stands.
4. **Trigger (flagged as source #1 in the MV3 v3 report itself but never tested):
   explains essentially everything.**

### Why the trigger is the physics

The composition split at the reference point (paired/g92, deepest-stave counts
[B2,B4,B6,B8]) shows two populations:

- deuterons: [101,388, 32,870, 407, 113] — stop in B2/B4, exactly the ~105 MeV / 4.5 g/cm2 range calc;
- protons: [15,825, 12,637, 30,738, 55,506] — run deep to B6/B8, exactly the ~153 MeV / 14.6 g/cm2 calc.

The data is trigger-selected: Sample I (76% of events) requires the two-arm coincidence.
When the *deuteron* goes to the B arm at 38 deg, the conjugate ~85 MeV proton reaches Stack A
(range 5.2 g/cm2 >> TPC hull) -> trigger fires. When the *proton* goes to the B arm, the
conjugate deuteron carries only ~37 MeV (range 0.7 g/cm2) and dies in the TPC hull ->
no coincidence. **The trigger keeps deuteron-into-B events and vetoes the deep-proton ones.**
MC without a trigger contains both; that — not missing material — was MV3's 68,269.

### Data-side cross-check (review C2)

`amplitude_adc` in `s00_selected_b_pulses.csv.gz` is confirmed already baseline-subtracted
(68% of rows have amplitude < baseline), so MV3 v3's data-side `|amplitude - baseline|`
folds the scale. Recomputing the data profile with the corrected semantics
(`amplitude_adc > 1000` directly) gives B2/B4/B6/B8 = 0.894/0.054/0.032/0.020 (n=364,938) —
close to the folded 0.876/0.063/0.039/0.023, so the target was only mildly distorted.
Scored against the **corrected** data: reference 88,542 -> best 1,061 (**83x**). The
conclusion is unchanged under either data-side convention.

---

## Stage 3 — Decision

**Option (a): cheap fixes close the profile; the expensive production is skipped.**

- No geometry rebuild, no new 1M production, no `hibeam_g4` job launched.
- The missing-material narrative in FINDINGS/WIKI (already weakened by the MV3b errata)
  is now positively **falsified**: the required ~10.5 g/cm2 does not physically exist,
  and the trigger proxy reproduces the data profile without any geometry change.
- **PR #8** (`HIBEAM-NNBAR/hibeam_g4_geobuilder`, inter-stave Al proxy, default
  2.51 g/cm2/pair) **should be closed or reworked, not merged**: its default injects
  ~10x more material than the realistic wrapping budget and was motivated by the retracted
  toy number. Real wrapping (~0.1-0.5 g/cm2/pair) plus air (~0.13 g/cm2) are legitimate
  fidelity improvements for a future geometry rev, but they are second-order to
  **simulating the trigger**, which is the actual missing piece of the MC.
- Recommended next MC-side work item (supersedes "add material"): score the `Trig_bar`
  volumes as sensitive detectors (add to `Detectors` in `krakow.config` if supported, or
  extend the geobuilder/hibeam_g4 detector list) and emit a per-event Sample-I/Sample-II
  trigger flag, replacing the A-HRD proxy used here.

## Stage 4 — Gated MV3 rerun result

The gate (chi2/ndf drop by orders of magnitude, not perfection) is **MET** on the existing
1M sample, with the comparison made like-for-like (trigger required, gain scanned 60-300,
event basis, species-inclusive):

| Comparison | chi2/ndf |
|---|---|
| MV3 v3 as published (reproduced) | 68,269 |
| + trigger proxy alone | 3,141 (-22x) |
| + trigger, gain 60, event basis, species-inclusive | **625 (-109x)** |
| best grid point (track-basis variant) | 555 (-123x) |
| vs C2-corrected data profile | 88,542 -> **1,061 (-83x)** |

MV3 verdict update: **FAIL (structural geometry error) -> retracted; re-graded TENSION
(trigger-selection mismatch, now mostly closed by a truth-level trigger proxy).** The
residual chi2/ndf ~600-1,100 on 307-365k events corresponds to <~1% absolute per-stave
deviations and plausibly reflects: the crudeness of the A-HRD proxy vs the real
trigger-paddle coincidence (vs Sample I alone the best point gives 2,883), no Birks
quenching in the threshold model, pile-up in data B2, and the phase-locked peak_frac.
These belong to Phase 1 (digitizer) and the trigger-flag work item above, not to a
geometry production.

## Job/production summary

| What | Where | ID / state |
|---|---|---|
| Stage-2/4 diagnostic grid (1M events, 264 hypothesis points) | LUNARC lu48 | **3346841 COMPLETED** (9 s, exit 0) |
| New GEANT4 production | — | **not launched** (decision (a)) |

## Blockers

None blocking. Notes: (i) both LUNARC geobuilder checkouts are other users' directories and
predate the trigger commit — a fresh clone is required if a geometry rebuild is ever needed;
(ii) the GEANT4 production toolchain lives on workstation `billy` (conda `nnbar_env`,
GEANT4 11.2.2), not on LUNARC — REPRODUCTION_STATUS.md's `/home/billy/...` paths refer to
that machine, which matters for whoever schedules a future production.
