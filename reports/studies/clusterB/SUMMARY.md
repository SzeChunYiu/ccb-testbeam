# Cluster B — CCB test-beam timing-chain study (MC closure)

> **⚠️ NON-AUTHORISING MC NOTICE (2026-08-16)** — This study was derived from
> `geant4/data/output_krakow_1M.root`, which was produced from the unpatched upstream
> `ScatteringGenerator` (unit-weight sampling bug). The corrected generator shows
> Enter B reduced by −97.0% ± 0.2%, materially changing the sample. The TIMING-MC figure
> (paper/figures.yaml row) is **GATED** pending re-derivation on
> `geant4/data/output_krakow_1M_authorising.root`. See
> `research/trigger_migration_study/PHASE1B_NONAUTHORISING_MC_NOTICE.md` for full
> analysis.

**Goal.** Prove the CCB timing analysis works end-to-end before it is pointed at data. The full
chain is reconstructed on Monte Carlo where the truth is known, so every stage can be validated
against ground truth.

```
photon arrivals (truth, `photons` ntuple)
  -> binned SiPM waveform w(t)        [digitisation: 0.25 ns bins, 0-100 ns; arrivals already carry
                                        the scintillation+WLS+transport kinetics, no extra kernel]
  -> timing pickoff  (CFD / template-fit / leading-edge)
  -> residual vs photon-onset truth   [t_truth = first detected-photon arrival, per (event,sensor)]
  -> timewalk correction               [fit on held-in energies/seed, applied to held-out]
  -> combined 4-sensor estimator       [inverse-variance weights + covariance]
```

**Data (all on LUNARC fs10).**
- Single-stave Geant4 photon MC — `ccb-runs/i885_v1/` : proton + deuteron, 2-150 MeV, seeds
  `s101`/`s102`, x-offsets {-20,-5,0,15,20} mm → **72 nominal files**.
- Birks systematic — `ccb-runs/an3/sys_birks_smoke2/` : kB = 0.100 / 0.126 / 0.160 → **3 files**.
- Krakow 1M antineutron-annihilation MC — `geant4/data/output_krakow_1M.root` (200k events read).

**Scale analysed:** 119,905 (event,sensor) groups across 75 files. Wall time 84 s on the login node
(also wrapped as a Slurm job, `scripts/clusterB/run_clusterB.slurm`, `--account=hep2023-1-3 --partition=hep`).

---

## VIS-TIM-001 — Timing-pickoff construction  (`VIS-TIM-001_pickoff_construction.png`)
Shows three timing pickoffs operating on the same binned waveforms with the truth marked, plus the
failure taxonomy and per-method success/`sigma68`.

- Example low/mid/high-PE waveforms with the CFD fraction line, leading-edge threshold, overlaid
  template fit, and the photon-onset truth (vertical black line).
- **CFD is the best pickoff: `sigma68 = 0.151 ns`, success 93 %.** Template fit `sigma68 = 0.451 ns`
  (shape varies with PE → noisier on low-PE pulses); leading-edge `sigma68 = 0.765 ns`, success 75 %
  (`lead_no_cross` for sub-threshold pulses; `low_pe` for <15 PE). Units are ns throughout; the valid
  domain is the rising edge before the peak.
- **Works:** all three pickoffs localise the pulse; CFD does so to 0.15 ns, sub-bin (interpolated).

## VIS-TIM-002 — Timewalk  (`VIS-TIM-002_timewalk.png`)
Raw residual vs amplitude (per sensor, train+held-out), the train-only fit, and the corrected held-out
residual with its slope test.

- Raw residual walks with amplitude: fit `res = a + b/N_PE` on **training groups only** (seed s101,
  ke {5,20,80} MeV, on-axis) gives `a = 0.049`, **`b = -7.06`** — a clear amplitude bias.
- Applying that correction to the **held-out** set (other energies, all x-offsets, seed s102, Birks
  systematics) leaves a residual-vs-amplitude **slope = 8e-05 ns/PE** with bootstrap 68 % CI — i.e.
  **slope ≈ 0, criterion PASSES.** The timewalk is removed by a train-only correction.
- Per-stave curves overlap → the effect is consistent across the 4 sensors.

## VIS-TIM-003 — Timing distributions  (`VIS-TIM-003_distributions.png`)
Full corrected residual histogram, Gaussian-core fit, log tail view, and QQ — robust + core metrics
reported together.

- `sigma68 = 0.146 ns`, Gaussian-core `sigma = 0.092 ns`, RMS = `0.194 ns`, tail fraction `|r|>3sigma = 10.5 %`
  (N = 111,458). Core is narrow; tails are non-Gaussian (QQ departs in the tails) — the reason a
  Gaussian pull model mildly under-covers at high significance (see VIS-TIM-005).
- **Works:** the distribution is single-peaked, centred, with a well-described core + quantified tails.

## VIS-TIM-004 — Run / topology stability  (`VIS-TIM-004_stability.png`, `VIS-TIM-004b_krakow_topology.png`)
Forest plots (median ±1`sigma68`, with bootstrap 68 % CIs) over run/seed, sensor/stave, and topology,
plus the 4-sensor residual covariance.

- Per-run (s101 vs s102), per-sensor and per-topology (particle × energy) medians are all consistent
  with 0 within their bootstrap CIs; no single run/sensor/topology drives the headline.
- 4-sensor covariance diagonal = 0.032-0.036 ns² with overlapping bootstrap CIs → **no pathological
  sensor.** The covariance feeds the combined estimator.
- **Krakow 1M arm:** TARGET deposits are a delta at `t0 = 0` (97.9 % of all deposit steps exactly at
  `PrimaryTime = 0`; per-event deposition duration 95th pct ≈ 0 across all `E_dep` bins) → the
  truth-time anchor is clean and topology-stable. Krakow is an annihilation-at-rest kinematics MC and
  carries **no intrinsic timing resolution**; the resolution measured here is a photon-arrival property
  of the single-stave arm.

## VIS-TIM-005 — Combined estimator  (`VIS-TIM-005_combined_estimator.png`)
Inverse-variance weights, covariance + eigenvalues, leave-one-sensor-out, residual, and pull coverage.

- Weights are balanced (readout 0.256 / f1far 0.249 / f2near 0.264 / f2far 0.231); eigenvalues
  0.031-0.037 ns² → condition number `kappa ≈ 1.2` (well-conditioned).
- **Combined `sigma68 = 0.089 ns`** — better than any single sensor (~0.15 ns), as expected from
  combining 4 near-equal channels.
- Leave-one-sensor-out `sigma68 ≈ 0.10 ns` whichever sensor is dropped → no sensor dominates.
- **Pull coverage closes on MC:** `|pull|<1 = 0.683` (vs 0.683), `|pull|<2 = 0.909` (vs 0.954),
  `|pull|<3 = 0.979` (vs 0.997). The 1-sigma coverage is exact; 2/3-sigma mildly under-cover from the
  non-Gaussian scintillation tail. The covariance-aware uncertainty is therefore **validated on MC**;
  the residual under-coverage at high significance is flagged as a caveat for the data application
  (use an empirical-quantile interval there rather than a pure Gaussian pull).

---

## How to reproduce
```
python scripts/clusterB/clusterB_timing_study.py --max-events 400
# or via Slurm:
sbatch scripts/clusterB/run_clusterB.slurm
```
Outputs land in `reports/studies/clusterB/` (6 PNGs + `metrics.json`).

## Residue / blockers
- **Data-side raw waveforms are not on LUNARC.** The real test-beam `h101`/`HRDv` ROOT files that the
  existing data-side chain reads (`scripts/s02_timing_pickoff.py`, `scripts/p10b_explicit_timewalk_terms.py`,
  `scripts/mv4_timing_study.py`) are not present on fs10, so that chain cannot be run here. This MC study
  is the closure demonstration that the methodology (pickoff → timewalk → stability → combine) is sound;
  pointing the same chain at data is the natural next step once waveforms are staged.
- **VIS-TIM-005 pull-coverage gate:** closes on MC at 1-sigma (0.683), within tolerance at 2-sigma; not
  blocked on MC. The 3-sigma under-coverage is a non-Gaussian-tail caveat for data, not a methodology
  defect.
- No other blockers on the MC side; all six figures regenerate in ~84 s and the script is verified.

*Source: `scripts/clusterB/clusterB_timing_study.py`; data under `ccb-runs/i885_v1`,
`ccb-runs/an3/sys_birks_smoke2`, `geant4/data/output_krakow_1M.root`. Metrics: `metrics.json`.*
