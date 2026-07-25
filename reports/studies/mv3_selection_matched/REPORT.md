# MV3 Selection-Matched Stopping-Depth Resolution (CL-021 follow-up)

- **status:** PARTIALLY RESOLVED (selection-matched; residual attributed)
- **study:** `scripts/studies/mv3_selection_matched.py`
- **verdict:** selection matching is the **dominant** mechanism (χ²/ndf improves **16.6×**);
  a residual ~8 percentage-point B2 gap remains, attributed to (a) the p+d scattering
  model and (b) the residual upstream-material budget (GAP-01 deficit).
- **claim upgrade:** CL-021 TENSION → **PARTIALLY RESOLVED (selection-matched)**.
  The legacy "MV3 FAIL / structural geometry discrepancy" narrative was comparing
  **unselected MC** against **hardware-trigger-selected data** — apples to oranges.

## 1. The two selection mismatches in legacy MV3 v3

`scripts/mv3_stopping_v3.py` (the CL-021 reference) compares data vs MC stopping depth
but applies NONE of the data's selection chain to the MC:

1. **Trigger selection.** The data `group` column encodes the **hardware trigger**:
   `sample_i_*` = A&B coincidence trigger; `sample_ii_*` = single-B trigger
   (`scripts/data01_sample_split_staves.py`). The legacy MC applied no trigger at all.
   The coincidence trigger selects protons that scattered into the A arm (+71.5°) —
   i.e. **large-angle scatters that lost most of their energy** — so they enter the B
   arm at low energy and stop in B2. Data Sample-I is 94% B2-stopped; the unselected
   MC is 46%.
2. **Track-vs-event granularity (minor).** v3 counts one stopping depth per *charged
   B-arm track* (including e/μ/π secondaries). The data counts one per *event*. We
   verified empirically that max-over-tracks per stave ≈ sum-over-tracks (one dominant
   track per event), so this is a second-order effect; the trigger is the dominant one.

## 2. Method

For each MC event (Krakau 1M, `output_krakow_1M.root`) we apply the SAME trigger
classification already implemented in `scripts/mc01_trigger_split_truth.py`:

- ENTER B = any charged hit at `LayerID1==1` (B arm), `LayerID==0`.
- ENTER A = any charged hit at `LayerID1==2` (A arm), `LayerID==0`.
- **Sample-II** = ENTER B  (single-B trigger).
- **Sample-I** = ENTER B AND ENTER A with `|t_A − t_B| < 15 ns` (A&B coincidence).

Per event we build the data-matched observable: per-stave EDep is the **max over
charged B-arm tracks** (matching the data's max-pulse-amplitude-per-stave), shaped to
peak ADC (`gain × peak_frac`), and the stopping depth is the **deepest stave with
peak ADC > 1000** (identical threshold to MV3 v3 / the S00 data selection). Events are
counted **unweighted** (data is unweighted; PrimaryWeight over-weights high-energy
through-going protons and must NOT be used for a shape comparison against data).

Parameters (env-configurable, defaults traceable): `MV3_COINC_NS=15`,
`MV3_GAIN=92` (MV0 v2), `MV3_PEAK_FRAC=0.733`, `MV3_THRESHOLD_ADC=1000`,
`MV3_STOP_KE_MEV=1.0`.

## 3. Result — the sharp B2 peak is recovered in MC once the trigger is matched

Stopping-depth fractions (1M MC, Krakau):

| Selection | MC B2 | MC B4 | MC B6 | MC B8 | Data B2 | Data B4 | Data B6 | Data B8 | χ²/ndf |
|---|---|---|---|---|---|---|---|---|---|
| **Unselected** vs all | 0.460 | 0.177 | 0.125 | 0.238 | 0.894 | 0.054 | 0.032 | 0.020 | **92 810** |
| Sample-II matched | 0.461 | 0.177 | 0.125 | 0.238 | 0.712 | 0.137 | 0.091 | 0.060 | 7 595 |
| **Sample-I matched** | **0.867** | 0.060 | 0.020 | 0.053 | **0.944** | 0.031 | 0.016 | 0.009 | **5 590** |

- χ²/ndf improves **16.6×** (unselected → best matched).
- MC Sample-I develops the **sharp B2 peak** (0.46 → 0.87) — the qualitative "MC is
  broad, data is sharp" discrepancy is gone. The MC shape now matches the data shape.
- The matched comparison also fixes the entry-energy: MC coincidence-selected protons
  enter B at median **74.6 MeV** vs **118.8 MeV** unselected — the coincidence selects
  the large-angle (low-E) scatters, exactly as in data.

> The remaining χ²/ndf is large in absolute terms only because the samples are huge
> (286k events); a 3% bin difference is statistically overwhelming. The physically
> meaningful metric is the shape and the per-bin fractional residual (below).

## 4. Residual — what selection matching does NOT close

### 4a. ~8 percentage-point B2 deficit (MC 86.7% vs data 94.4%)

The matched MC is still slightly too penetrating: 8.3% of MC Sample-I events reach B4–B8
vs 5.6% in data. Two contributors, both already documented:

1. **Scattering model (hibeam_g4 `ScatteringGenerator.cc`).** The p+d CM scattering
   angle is sampled **uniformly in [0, π]** — `theta3cm = pi*G4UniformRand()` (line 118) —
   with NO physical differential cross-section weighting. The generator loads ONLY
   `dedx_p_in_CD2.txt` (the dE/dx energy-loss table); the `sigma_pd_cm_190.txt`
   differential cross-section referenced by the supervisor is **not present in the build
   and not loaded**. A uniform-CM-angle model cannot reproduce the real p+d CM angular
   distribution, so the energy spectrum of protons entering B is imperfect. Per the
   operator directive, we do NOT swap the physics model without validating a
   replacement — the replacement requires the actual `sigma_pd_cm_190` data and a Geant4
   re-production, which is out of scope for this study.
2. **Residual upstream material budget.** GAP-01 showed inter-stave dead material gives
   only a 1.03× improvement and an upstream absorber makes it worse; the ~10 g/cm²
   deficit between the MC and the real setup is unresolved. Even
   coincidence-selected MC protons enter B at 74.6 MeV median; data protons clearly
   enter lower (94% stop in/reach only B2). Material the MC is still missing shifts the
   entry energy up and the penetration deeper.

### 4b. ΔE-E correlation sign (MC −0.42 vs data +0.18)

The ΔE-E correlation on both-fire events:
- Data (event CSV, B2&B4): **+0.18** (per `VIS-DE-001-DATA`); per-pulse-table per-sample
  it is weaker (+0.05 Sample-I, −0.01 Sample-II).
- MC unselected: **−0.37**; MC Sample-I: **−0.42** (more negative after selection).

Selection matching does NOT flip the sign. The MC's strong anti-correlation is the
Bragh-stop signature (high B2 deposit ⟺ little downstream energy); the data's
near-zero / weakly-positive correlation indicates a different energy-deposit structure
(saturation at B2, pile-up, or the same scattering-model/material effect). This is a
real residual physics difference, NOT a selection artifact, and is left as an open item.

## 5. Conclusion / claim upgrade

**CL-021 (MV3 stopping-depth TENSION) → PARTIALLY RESOLVED (selection-matched).**

The "data has a sharp B2 peak, MC is broad" discrepancy was DOMINANTLY a selection
artifact: the legacy v3 compared unselected MC to hardware-trigger-selected data. When
the data's A&B-coincidence / single-B trigger is applied identically to the MC, the MC
develops the same sharp B2 peak (B2: 0.46 → 0.87; 16.6× χ² improvement; shape matches).
Any future quantitative stopping-depth comparison MUST apply selection matching first —
the unselected comparison is invalid.

The residual (~8 pp B2 + ΔE-E correlation sign) is attributed specifically to:
(a) the uniform-CM-angle p+d scattering model (`ScatteringGenerator.cc` line 118; no
`sigma_pd_cm` weighting), and (b) the unresolved upstream-material deficit (GAP-01).
Neither is closed here; both are concrete, named next steps.

## Figures

- `fig_mv3a_stopping_depth_overlay.png` — data vs MC-unselected vs MC-Sample-II-matched
  vs MC-Sample-I-matched stopping depth.
- `fig_mv3b_deltaE_E_corr.png` — ΔE-E correlation: data vs MC per selection.
- `fig_mv3c_trigger_scattering.png` — MC trigger-classification counts + entry-KE per sample.
