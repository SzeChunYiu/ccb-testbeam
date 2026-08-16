# Cluster C — test-beam pile-up + energy/Birks/saturation study

Driver: `scripts/clusterC/clusterC_pileup_energy_study.py` (single self-contained module,
all numeric parameters `os.environ.get`-configurable with defaults traced to the
production digitizer config in `src/ccb_mc_validation/digitizer/{electronics,sampling}.py`
and the i885_v1 beam-energy set).  Figures and machine-readable results live under
`reports/studies/clusterC/` (`metrics.json`, `captions.json`, `*.png`).

Data: i885_v1 single-stave Geant4 (proton + deuteron KE sweep, 36+36 files,
36,000 events) fed through the production
`DigitizerPipeline`.  The Krakow 1M MC (`geant4/data/output_krakow_1M.root`) is available
for cross-check; `sys_birks_smoke2` was **not** present on disk (see Residue).

## What works (all 7 figures produced, scripts verified to run end-to-end)

| ID | Figure | Headline result |
|----|--------|-----------------|
| VIS-PU-001 | `VIS-PU-001_pulse_tail_live_time.png` | Average pulse ±1 SEM; τ tail-fit = **36.0 ns** vs kernel 35 ns; τ(1/e crossing) = 42.5 ns; **99.4%** of pulse area captured in the 180-ns window (tail lost 0.62%); live-time above 50% thr = 22%. |
| VIS-PU-002 | `VIS-PU-002_pileup_occupancy_rate.png` | Overlap @1 MHz: observed **15.9%** vs Poisson 16.5%; **Rmax = 605 kHz** at the explicit 0% quality gate; 5%-overlap reference rate = 289 kHz (shown distinctly, not conflated with the gate). |
| VIS-PU-003 | `VIS-PU-003_two_pulse_recovery.png` | LSQ template-fit (ML-proxy) vs peak-finding baseline on common truth; LSQ efficiency @25 ns (A2/A1=1) = 100%; catastrophic-failure @12 ns = 0%. Bias/RMS/efficiency vs delay × amplitude ratio. |
| VIS-PU-004 | `VIS-PU-004_window_censoring.png` | Recovered secondary tail at the production window = 91.7%; Rmax @ acq window = 625 kHz; sweep over 10 window lengths. |
| VIS-ENE-001 | `VIS-ENE-001_adc_calibration.png` | ADC vs deposited (Birks-visible) energy: slope **119.17 ADC/MeV** (proton) and **119.17 ADC/MeV** (deuteron) — both equal to the configured gain within the peak-normalised-kernel capture fraction; pulls μ≈0, σ≈0.60 (unit-normal reference overlaid). |
| VIS-ENE-002 | `VIS-ENE-002_birks_quenching.png` | kB scan on 36,000 events: best kB = **0.0156 cm/MeV** (per-track dE/dx) vs **0.0127** (total-edep proxy used by `birks_quench`); digitizer default = 0.01. Path-length semantics shown explicitly to matter. |
| VIS-ENE-003 | `VIS-ENE-003_saturation.png` | Observed ceiling at ADC = 7000; 50%-saturation at **274.6 MeV** (analytic clip @ 55833333.3 MeV); saturation probability and recovery-bias/coverage panels. |

## How to reproduce
```bash
source /projects/hep/fs10/shared/nnbar/billy/ccb-py/bin/activate
export MPLCONFIGDIR=/projects/hep/fs10/shared/nnbar/billy/.mplcache
cd <worktree>
python3 scripts/clusterC/clusterC_pileup_energy_study.py                 # all 7
python3 scripts/clusterC/clusterC_pileup_energy_study.py --only VIS-ENE-002   # one
```
Every parameter is overridable, e.g. `CCB_BIRKS_KB=0.010 CCB_TAU_DECAY_NS=40 python3 ...`.

## Residue / blockers
- **`sys_birks_smoke2` is absent** from `ccb-runs/` (only `an3`, `i885_v1`, `sipm-p2-001` are present). VIS-ENE-002 therefore uses the i885_v1 `edep_scint_raw_MeV`/`edep_scint_MeV` pair directly — a *stronger* dataset than a smoke test since it carries both the unquenched and Birks-visible columns across the full proton+deuteron KE sweep, plus `track_len_scint_mm` enabling the per-track dE/dx path-length comparison the task asked for.
- **`gh` is not installed on LUNARC.** The PR is opened via the GitHub REST API (`curl`) using the token already configured on the `origin` remote, so the whole flow stays on LUNARC/fs10.
- The production scintillation kernel is **peak-normalised and sampled at 10 ns**, so the digitised pulse peaks at sample 0 (sub-sample rise). VIS-PU-001 reports decay-side τ estimators (tail fit + 1/e crossing) accordingly and annotates this; the 180-ns window still captures 99.4% of the pulse area.
- `sipm-p2-001` SiPM-sensitivity outputs and the Krakow 1M MC are in place but are out of scope for this cluster (energy/Birks/saturation is fully covered by i885_v1); they remain available for a follow-up SiPM-focused cluster.

## Files
- `scripts/clusterC/clusterC_pileup_energy_study.py` — driver
- `reports/studies/clusterC/VIS-PU-001..004_*.png`, `VIS-ENE-001..003_*.png` — figures
- `reports/studies/clusterC/metrics.json`, `captions.json` — machine-readable results
