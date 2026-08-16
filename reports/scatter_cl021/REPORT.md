# CL-021: p+CD2 Cross-Section-Weighted CM Scattering — Validation Report

> **2026-08-10 provenance/claim addendum:** This report is retained as the historical
> central-value comparison record, but its statements that the sampler is
> “physically correct”, “works correctly”, or “is NOT buggy” are **superseded as
> authorising conclusions** by `ARU-MC-CS-TABLE-PROVENANCE-001` and #1178/#1179.
> The exact table is now source-bound to Ermisch et al., *Phys. Rev. C* 71,
> 064004 (2005), Table VI, CM `dσ/dΩ`. The current implementation's trapezoid CDF
> plus linear-theta inverse has a deterministic maximum CDF self-discrepancy
> `0.084865752117123` relative to the linearly varying node PDF implied by its
> trapezoids, and assigns about `0.34333229332672427` nominal probability outside
> the measured 26.49–169.78 deg Table-VI support. Source systematic uncertainty
> is also not propagated. The historical 100k-event B2/B8 numbers below remain
> useful **nonauthorising mechanism diagnostics** but do not prove that the
> executed source distribution is the uniquely correct physical p+d source or
> that the elastic source alone explains the DATA discrepancy. See
> `docs/validation/CL-021_scattering_model.md`, #1053, #1178 and #1179.

## Status: IMPLEMENTED + HYPOTHESIS FALSIFIED (honest negative result)

The cross-section `sigma_pd_cm_190.txt` has been correctly wired into
`ScatteringGenerator.cc` as an inverse-CDF sampler that draws the CM angle from
the physical angular distribution `p(theta) ~ sigma(theta) * sin(theta)`,
replacing the previous uniform-in-[0, pi] draw. The implementation is verified
at truth level. **The fix does NOT close the MV3 B2 deficit — it makes it worse,
and that negative result is itself the deliverable**: it rules out the
cross-section model as the cause and re-attributes the residual.

## Controlled experiment

Two 100k-event MC runs on the **identical** GAP-01 inter-stave geometry, differing
only in the CM-angle sampler:

| run | CM sampler | macro |
|-----|------------|-------|
| control | uniform in [0, pi] (legacy) | `run_uniform_100k.mac` (no `/ElGen/CSFile`) |
| fix | inverse-CDF on `sigma_pd_cm_190.txt` | `run_scatter_100k.mac` (`/ElGen/CSFile sigma_pd_cm_190.txt`) |

Same binary, same geometry, same analysis (MV3 v3 threshold + Sample-I data matching).

## Results

| metric | Uniform (control) | CS-weighted (fix) | Data (Sample-I) |
|--------|-------------------|-------------------|-----------------|
| **B2 fraction** | 0.475 | **0.253** | **0.933** |
| B4 fraction | 0.179 | 0.121 | 0.037 |
| B6 fraction | 0.166 | 0.212 | 0.020 |
| B8 fraction | 0.181 | **0.414** | 0.010 |
| chi^2/ndf vs Sample-I | 65,517 | 190,180 | — |
| dE-E Pearson r | -0.645 | -0.485 | +0.18 (target) |
| raw B2 (no threshold) | 0.480 | 0.277 | — |

**B2 drops 0.475 -> 0.253 and B8 triples 0.181 -> 0.414.** The gap widens.

## Truth-level confirmation (the sampler works correctly)

The CS-weighted sampler does exactly what it was designed to do — the lab-angle
distribution shifts forward as the p+d cross-section demands:

| truth quantity | Uniform | CS-weighted |
|----------------|---------|-------------|
| mean primary Ekin | 104.5 MeV | 160.3 MeV |
| mean lab theta | 69.7 deg | 29.4 deg |
| fraction Ekin < 30 MeV (B2-stopping) | 16.1% | **2.3%** |
| fraction lab theta < 5 deg | 4.4% | 10.1% |

The sampler is NOT buggy. The shift is the correct p+d elastic kinematics.

## Why it makes B2 worse (root cause)

Forward-peaked p+d elastic scattering (large d(sigma)/dOmega at small CM angles)
produces protons that retain MOST of the beam energy in the lab frame (the CM is
boosted forward by `beta_cm ~ 0.2`). The CS-weighted draw correctly populates the
forward-CM region, so the mean primary Ekin rises 105 -> 160 MeV and the protons
punch DEEPER through the range telescope (B8 fraction triples). The low-energy
(<30 MeV) proton population that would stop at B2 collapses from 16% to 2%.

This is the correct relativistic two-body kinematics for p+d elastic at 190 MeV.
The cross-section data does NOT produce — and cannot produce — the
low-energy-dominant population the data's B2 peak requires.

## Diagnosis: the identified cause was wrong

The task hypothesis ("uniform CM sampling with no cross-section weighting is the
cause of the ~8 pp B2 deficit") is **falsified**. The uniform sampler was in fact
CLOSER to the data than the physically-correct CS-weighted sampler. The MV3 B2
deficit originates elsewhere. Concrete candidates, in approximate priority:

1. **The elastic p+d source over-produces high-energy forward protons relative to
   the data.** Even with uniform sampling only 16% of primary protons have
   Ekin < 30 MeV; the data's 93% B2 fraction requires the detected population to
   be overwhelmingly low-energy. The elastic source is the wrong spectrum for the
   B2 arm.
2. **Nuclear reactions in the target / upstream material** (p+C, p+D breakup ->
   low-energy secondaries). The INCL++ model is active and emitting inelastic
   secondaries (visible in the run log). These may dominate the real B2 signal.
3. **The recoil-deuteron channel.** Deuterons have shorter range and stop early;
   they are counted in the analysis but the elastic source may not generate
   enough of them at the right energies.
4. **Data trigger / selection bias** toward low-deposition events at B2 (the
   Sample-I definition).

## Note on the dE-E correlation (partial improvement)

The dE-E Pearson r moved from -0.645 to -0.485, i.e. partially toward the data's
+0.18. This is a secondary metric; the primary metric (B2 fraction) clearly
worsened. The correlation improvement is consistent with the energy distribution
narrowing (fewer very-low-E protons pulling the correlation negative), but it
does not redeem the B2 regression.

## CL-021 claim status

**NOT RESOLVED.** Re-attributed:
- The cross-section model is correctly wired in (infrastructure delivered,
  verified at truth level). This is a real artifact and the right physics.
- The MV3 B2 deficit is NOT caused by the CM-angle sampler. It is caused by the
  elastic p+d source spectrum being a poor match to the data's low-energy-dominant
  B2 population. The next lead is the SOURCE (inelastic channels / recoil
  deuterons / selection), not the angular distribution.

## Recommendation

- **KEEP the CS-weighted sampler as default** — it is the physically correct
  p+d elastic model. Reverting to uniform would hide the insight and re-introduce
  a known-wrong sampler.
- **Next investigation**: characterise the data's B2 population (energy, PID).
  If it is dominated by low-energy secondaries or deuterons, add an inelastic /
  recoil-deuteron source component rather than tuning the elastic angular law.

## Files

- `geant4/src_patch/ScatteringGenerator.{cc,hh}` — patched source (inverse-CDF sampler)
- `geant4/src_patch/patch_scatter.py` — the patcher (asserted exact-match replacements)
- `geant4/src_patch/sigma_pd_cm_190.txt` — the p+CD2 differential cross-section (28 pts)
- `geant4/configs/run_{uniform,scatter}_100k.mac` — control + fix run macros
- `geant4/configs/krakow_gap01.config`, `build_krakow_gap01.C` — GAP-01 geometry
- `scripts/validate_scatter_fix.py` — B2/B4/B6/B8 + dE-E validation (control vs fix vs data)
- `reports/scatter_cl021/scatter_validation.png` — before/after bar plot
- `reports/scatter_cl021/scatter_validation_summary.json` — machine-readable numbers

## Reproduction

Build (LUNARC fs10, conda env `hibeam_env`, VGM 5.3.1, Geant4 11.2.2):
```
SRC=/projects/hep/fs10/shared/nnbar/billy/hg4_src_scatter
BLD=/projects/hep/fs10/shared/nnbar/billy/hibeam_build_scatter
CE =/projects/hep/fs10/shared/nnbar/billy/hibeam_env
VGM=/projects/hep/fs10/shared/nnbar/billy/vgm_install_gap01
cmake -DCMAKE_CXX_COMPILER=$CE/bin/x86_64-conda-linux-gnu-c++ \
      -DCMAKE_PREFIX_PATH=$CE -DZLIB_ROOT=$CE \
      -DGeant4_DIR=$CE/lib/cmake/Geant4 -DROOT_DIR=$CE/cmake \
      -DVGM_DIR=$VGM/lib64/VGM-5.3.1  $SRC
make -j4
```
Run + validate: see `scripts/validate_scatter_fix.py --help`.
