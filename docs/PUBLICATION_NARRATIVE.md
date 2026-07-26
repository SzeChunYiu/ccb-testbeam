# CCB Test-Beam — Publication Narrative

> **The honest one-page story.** What the simulation chain proves, where the Opticks
> GPU bridge stands, what the SiPM core contributes, and exactly what remains open.
> Every number below is reproduced from [`reports/PROJECT_DASHBOARD.md`](../reports/PROJECT_DASHBOARD.md)
> and [`reports/studies/clusterE/claims_table.csv`](../reports/studies/clusterE/claims_table.csv) — no
> value is hand-entered. Where the legacy `PROJECT_REPORT.md` / `FINDINGS_SYNTHESIS.md`
> (2026-06-28) conflict with this narrative, **this file and the dashboard win**.
>
> Status: research in progress; all numbers **preliminary, not peer-reviewed**.

## 1. The headline, honestly

**The CCB test-beam analysis chain is proven end-to-end on Monte Carlo.** That is
what this programme demonstrates. Timing, ΔE-E particle identification, ADC/Birks
energy calibration, and digitizer-domain pile-up tolerance are all closed on the
Krakow 1M-event Geant4 simulation. The detector-performance claims that would
transfer those MC results onto the real beam data are **BLOCKED_DATA**: the raw beam
ROOT (`hrdb_run_*.root`) is not staged on LUNARC, and device/electronics calibration
is an operator-bench item that no amount of analysis can substitute for.

## 2. What the simulation chain proves (clusters A–D)

| Result | Value | Evidence class | Cluster |
|---|---|---|---|
| Combined timing resolution σ₆₈ (4-sensor) | **0.089 ns** | MC_METHOD_CLOSURE | B (#918) |
| PID p-vs-d AUC (realistic ΔE-E chain) | **0.898** | SIMULATION_RESULT | A (#921) |
| ADC calibration (digitizer gain) | **119.17 ADC/MeV** | SIMULATION_RESULT | C (#917) |
| Birks kB (per-track dE/dx fit) | **0.0156 cm/MeV** | SIMULATION_RESULT | C (#917) |
| Digitizer-domain Rmax (0% quality gate) | **0.605 MHz** | SIMULATION_RESULT | C (#917) |

**Timing (cluster B).** CFD pickoff reaches σ₆₈ = 0.151 ns (93% success); template
0.451 ns; leading-edge 0.765 ns. The timewalk train-fit (`a = 0.049, b = −7.06`)
satisfies the held-out-leaf slope test (≈ 8×10⁻⁵ ns/PE, effectively zero). The
4-sensor inverse-variance combination closes at **σ₆₈ = 0.089 ns** (RMS 0.112 ns,
condition κ ≈ 1.2, leave-one-sensor-out ≈ 0.10 ns). Pull coverage is exact at 1σ
(|z|<1 = 0.683) with mild 2σ/3σ under-coverage from a 10.5% non-Gaussian tail.

**PID / ΔE-E / stopping (cluster A).** On 131,198 ΔE-E-selected events
(ΔE_wmed = 24.13 MeV, E_wmed = 101.03 MeV, corr = −0.533) the logistic p-vs-d
classifier reaches **full AUC = 0.898** (5-fold 0.898 ± 0.01; AP 0.47; Brier 0.017).
Stopping/censoring is reported honestly: stop 2.3% / escape 22% / censored 76%
(STOP_KE = 1.0 MeV). Worst slices are reported, not averaged away (last-layer AUC
0.042, saturated-ΔE 0.029). The legacy HGB truth ceiling of 0.986 is retained
separately as a TRUTH_LEVEL_MC_ONLY diagnostic (CL-017, GATED) — it is **not** the
realistic-chain number and is not a beam-data result.

**Pile-up / energy / Birks / saturation (cluster C).** Pulse τ_fit = 36.0 ns (99.4%
of area in the 180 ns window). Overlap at 1 MHz: 15.9% observed vs 16.5% Poisson.
Digitizer-domain **Rmax = 0.605 MHz** at the 0% quality gate (0.289 MHz at 5%
overlap). Two-pulse LSQ recovery: 100% efficiency at 25 ns separation, 0%
catastrophic at 12 ns. **ADC = 119.17 ADC/MeV** (proton = deuteron; pulls μ ≈ 0).
**Birks kB = 0.0156 cm/MeV** from per-track dE/dx, vs 0.0127 from a total-edep proxy
and 0.008 from the digitizer default. Saturation ceiling 7000 ADC; 50% point
274.6 MeV.

## 3. The SiPM / optical-readout core (cluster D)

The scintillator-to-digital chain is a BC-408 plastic scintillator read out at one
end via a Kuraray Y-11 wavelength-shifting fibre onto Hamamatsu S13360-3050CS SiPMs
(3×3 mm²). Cluster D's optical-chain audit (`VIS-MC-003`) maps 11 SiPM/optical-chain
nuisance knobs and bounds the dominant elasticities: reflectivity (3.48), coupling
(0.94), and `pde_scale` (0.89). The Birks PE-yield grid (`fig_birks_pe_yield`)
spans kB = 0.100–0.160 mm/MeV and is consistent with the cluster-C per-track fit.
The i885 linearity/timing/attenuation studies (`fig_i885_*`) characterise the
single-photoelectron response. **Honest caveat:** these are simulation-knob
elasticities, not bench-measured device constants — the SiPM PDE, reflectivity, and
fibre-coupling values are operator-bench inputs (see §5).

## 4. The Opticks GPU bridge — PARTIAL

The Opticks GPU path is proven **up to the last-mile hit gather, but no further**.
On the A40, production GDML ingestion (booleans + TiO₂ preserved), 4-SiPM annotation
(`sensor_count = 4` in the CSGFoundry — the earlier `hit_total = 0` spike cause is
fixed at ingestion), and explicit-scintillation-genstep upload are all demonstrated:
**148,697 photons/event** are uploaded as Opticks `INPUT_PHOTON` (297,394 over the
2-event parity run, ~424 nm raw-scintillation band), genstep uploaded and launch
dispatched.

The CPU Geant4 reference is byte-for-byte untouched: **4592 named-sensor arrivals
(2296/event)**; per-sensor F1_PlusX = 552, F1_MinusX = 573, F2_PlusX = 580,
F2_MinusX = 592; wavelength mean 529.9 nm (WLS-shifted Y-11 band); time mean
25.7 ns; path mean 372.1 mm. The CPU ctest is **9/9 PASS**.

The residual is the device→host photon/hit **GATHER**: in the standalone
G4CXOpticks / CSGOptiXSMTest invocation the output component gather returns null
(`null_component`) for both the input-photon bridge and the spike torch. The GPU
transport therefore records **0 hits**. This is an Opticks EventMode / component-save
pipeline configuration point, **not** a sensor or geometry defect, and **no number
has been hacked**. Until a non-null gather is configured, **no GPU speedup figure is
claimed** — a speedup is undefined when 0 GPU hits are gathered.

## 5. Explicit open items (what is NOT yet proven)

1. **Raw beam ROOT not staged.** `hrdb_run_*.root` (data-side ΔE-E, ADC,
   composite-key join, PID-on-data, data-side timing waveforms) is not on LUNARC —
   only the Krakow 1M MC and the derived `s00_selected_b_pulses.csv.gz` table are.
   Until it is staged, every detector-performance claim stays at MC-closure level.
2. **Operator-bench device calibration.** SiPM PDE / reflectivity / coupling,
   digitizer gain against a pulser, and measured time anchors are bench measurements;
   LUNARC cannot produce them. The MV0 ±30% gain envelope (CL-013) is a heuristic,
   **not a confidence interval**.
3. **Canonical Rmax undefined (S-STAT-003).** Cluster C's 0.605 MHz is a
   digitizer-domain quality-gate number; the legacy 3.044 MHz (CL-012) is superseded
   duty-factor arithmetic (`(1/τ_eff)×0.38`, where 0.38 is the beam duty factor, not
   a quality threshold). A canonical detector Rmax is BLOCKED (CL-010) until the
   occupancy-quality criterion is fixed.
4. **MV3 geometry (stopping-depth TENSION).** The data/MC stopping profile disagrees
   at χ²/ndf ≈ 6.8e4 (CL-021) because ~8–10 g/cm² of upstream material budget is
   missing from the MC geometry. All quantitative MC stopping-depth claims are
   unreliable until the geometry is fixed and re-run.
5. **Systematic budget incomplete (CL-026).** No per-claim nuisance model,
   covariance, hash-bound inputs, or coverage study exists yet; component estimates
   are not blanket authorisation.
6. **Opticks GPU gather.** Switch the standalone invocation to an
   EventMode/component-save config that returns a non-null gather to complete GPU
   parity. (CPU parity already 9/9.)
7. **Anomaly identity.** The data anomaly near 4% is **not** identified as C12
   (CL-022, AUD-ANOM-001); the C12 attribution is truth-MC only.

## 6. How to read the rest of the repository

- One-screen canonical status → [`reports/PROJECT_DASHBOARD.md`](../reports/PROJECT_DASHBOARD.md)
- Claim-by-claim table → [`reports/studies/clusterE/claims_table.csv`](../reports/studies/clusterE/claims_table.csv)
- Row-by-row authority → [`docs/claim_ledger.csv`](claim_ledger.csv)
- Illustrated wiki → [`WIKI.md`](../WIKI.md)
- Per-cluster detail → `reports/studies/cluster{A,B,C,D}/SUMMARY.md`, `figures/opticks/SUMMARY.md`
