# S23 - End-to-end Geant4/data consistency review
- Study ID:      S23
- Ticket:        1781181864.166962.68322ee6
- Title:         Reconcile Geant4 simulation claims with data findings
- Date:          2026-07-10
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00, S14h/S17b, S15b, S17a, S19
- Data anchor:   640,737 selected B-stave pulses

**ML loses for the energy-scale adoption claim: the traditional Geant4/Birks lookup has res68 0.04024 versus the best ML method 0.05668, so the transparent physics baseline remains the production candidate; for the simulation-only PID bridge, hist-gradient-boosted trees wins average precision 0.99178 versus 0.76661 for the DeltaE/range baseline.**

## Reproduction gate

Command:

```bash
python3 scripts/s23_1781181864_166962_68322ee6_geant4_data_consistency_review.py
```

The default S23 Python environment does not have `uproot` available, so the script records that as an environment caveat. For the completion audit, I created an isolated `/tmp/s23_rootcheck_env` virtual environment with `uproot` and reran the raw `h101/HRDv` count directly from `data/root/root/*.root`. The exact S00 anchor was reproduced: 640,737 selected B-stave pulses, zero delta, with median samples 0-3 as baseline, physical B-stack channels 0,2,4,6, and `A > 1000 ADC`.

| anchor                                     | source                                   | expected                  | observed | delta | status |
| ------------------------------------------ | ---------------------------------------- | ------------------------- | -------- | ----- | ------ |
| S00 selected B-stave pulse count           | S14h result.json                         | 640737                    | 640737   | 0     | PASS   |
| total selected B-stave pulses              | S15b result.json                         | 640737                    | 640737   | 0     | PASS   |
| sample_i_calib selected pulses             | S15b result.json                         | 248745                    | 248745   | 0     | PASS   |
| sample_i_analysis selected pulses          | S15b result.json                         | 252266                    | 252266   | 0     | PASS   |
| sample_ii_calib selected pulses            | S15b result.json                         | 14630                     | 14630    | 0     | PASS   |
| sample_ii_analysis selected pulses         | S15b result.json                         | 125096                    | 125096   | 0     | PASS   |
| S19 raw-root B-stack penetration fractions | S19 result.json and raw_data_per_run.csv | nonempty data_penetration | 4        | 0     | PASS   |

Environment checks:

| component           | status  | note                                                |
| ------------------- | ------- | --------------------------------------------------- |
| python              | 3.8.10  | Linux-5.15.0-139-generic-x86_64-with-glibc2.29      |
| numpy               | 1.24.3  |                                                     |
| pandas              | 2.0.3   |                                                     |
| uproot              | missing | needed only for direct raw ROOT rerun               |
| awkward             | missing | needed only for direct raw ROOT rerun               |
| raw_root_files      | 110     | files under data/root/root                          |
| sigma_pd_cm_190.txt | missing | not found under geant4/ or data/                    |
| dedx tables         | missing | no explicit table file found under geant4/ or data/ |

## Key metrics table

| claim                                                             | metric                                      | sim_or_ml_value | data_or_baseline_value | ci95                                        | verdict                   |
| ----------------------------------------------------------------- | ------------------------------------------- | --------------- | ---------------------- | ------------------------------------------- | ------------------------- |
| Build/run Geant4 reproduction                                     | truth tree and Sci_bar hit summary present  | present         | n/a                    | n/a                                         | PASS                      |
| Raw B-stack reproduction anchor                                   | selected B-stave pulses                     | n/a             | 640737                 | exact gate                                  | PASS                      |
| Energy scale is consistent with data-driven S14 ordering          | held-out fractional res68, lower is better  | 0.04024         | 0.09667                | [0.03885687265429256, 0.041606317494948857] | PASS_WITH_RESPONSE_CAVEAT |
| PID p/d truth supports a supervised bridge                        | average precision, higher is better         | 0.99179         | 0.76661                | [0.99098, 0.99245]                          | PASS_FOR_SIM_TRUTH_ONLY   |
| Penetration profile matches data after selection                  | B8/B2 sim/data ratio gap at best threshold  | 50.0            | 0.6446                 | [0.3825970295502876, 1.189361369134437]     | TENSION                   |
| Cross-section and dE/dx provenance are sufficient for publication | sigma_pd_cm_190.txt and dedx tables present | not found       | not found              | n/a                                         | FAIL_PROVENANCE           |

## Physics motivation

The ticket asks whether the simulation and data-driven analyses are mutually consistent across penetration, proton/deuteron truth, and energy scale. This matters because Geant4 is the only available source of event-level particle identity and deposited-energy truth, while the real HRD data provide ADC waveforms under threshold, trigger, saturation, and support effects. A valid physics interpretation requires the two domains to agree where their observables overlap and to abstain where the bridge is not yet instrumented.

## Methodology

Let `C_raw` be the raw selected-pulse count reconstructed from HRD waveforms. The admissibility gate is

`C_raw = sum_e sum_s I(max_j(V_e,s,j - median(V_e,s,0:3)) > 1000) = 640737`.

For energy, the traditional method is the S14h/S17b Geant4/Birks lookup. With per-stave charge `Q_i`, truth stopping power `(dE/dx)_i`, fitted light-yield scale `alpha`, and Birks constant `k_B`, its inverse deposited-energy estimate is

`Ehat = sum_i Q_i (1 + k_B (dE/dx)_i) / alpha`.

The benchmark metric is held-out fractional robust resolution,

`res68 = percentile_68(|(Ehat - E_truth) / E_truth|)`.

The ML/NN comparators are the S14h ridge regression, gradient-boosted trees, physics residual MLP, and 1D CNN, all evaluated on the same held-out events with run bootstrap confidence intervals.

For PID, S17a supplies a simulation-truth benchmark on primary protons and deuterons. The transparent traditional comparator is a DeltaE/range cut trained on held-out pseudo-runs. The ML/NN panel contains ridge logistic regression, histogram gradient-boosted trees, sklearn MLP, 1D CNN, and the physics-gated CNN architecture. The score is average precision for the deuteron class with pseudo-run bootstrap intervals.

For penetration, S19 reconstructs the raw data event-level deepest selected B stave and compares it to Sci_bar truth at EDep thresholds. The scalar closure diagnostic is `(B8/B2)_sim / (B8/B2)_data`; perfect closure is one.

For provenance, S23 searches the visible repo/data tree for the ticket-named `sigma_pd_cm_190.txt` and explicit dE/dx tables. Absence is treated as a release-blocking provenance failure for any claim that relies on those files.

## Results

### Consistency scoreboard

| claim                                                             | sim_source                                                     | data_source                        | metric                                      | sim_or_ml_value | data_or_baseline_value | ci95                                        | verdict                   | deepest_cause                                                                                                                                                               |
| ----------------------------------------------------------------- | -------------------------------------------------------------- | ---------------------------------- | ------------------------------------------- | --------------- | ---------------------- | ------------------------------------------- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Build/run Geant4 reproduction                                     | geant4/REPRODUCTION_STATUS.md, geant4/results/sim_summary.json | not a data claim                   | truth tree and Sci_bar hit summary present  | present         | n/a                    | n/a                                         | PASS                      | Environment reproduction already isolated to nnbar_env; S23 verifies artifacts but does not rebuild Geant4.                                                                 |
| Raw B-stack reproduction anchor                                   | n/a                                                            | S14h/S15b/S19 raw-root artifacts   | selected B-stave pulses                     | n/a             | 640737                 | exact gate                                  | PASS                      | Direct S23 audit reran HRDv with uproot in an isolated /tmp venv and reproduced 640737; S00/S14h/S15b/S19 artifacts agree.                                                  |
| Energy scale is consistent with data-driven S14 ordering          | S14h/S17b direct Sci_bar truth                                 | S14h raw duplicate-readout closure | held-out fractional res68, lower is better  | 0.04024         | 0.09667                | [0.03885687265429256, 0.041606317494948857] | PASS_WITH_RESPONSE_CAVEAT | The direct Geant4/Birks lookup wins the closure benchmark, but absolute ADC-to-MeV certification is limited by missing detector response.                                   |
| PID p/d truth supports a supervised bridge                        | S17a Geant4 primary p/d truth                                  | S15b weak-label raw-HRD PID proxy  | average precision, higher is better         | 0.99179         | 0.76661                | [0.99098, 0.99245]                          | PASS_FOR_SIM_TRUTH_ONLY   | Geant4 truth gives usable p/d labels; S15b data-side labels remain support proxies, not event-level PID truth.                                                              |
| Penetration profile matches data after selection                  | S19 Geant4 threshold scan                                      | S19 raw HRD deepest selected stave | B8/B2 sim/data ratio gap at best threshold  | 50.0            | 0.6446                 | [0.3825970295502876, 1.189361369134437]     | TENSION                   | A 50 MeV EDep threshold reduces but does not eliminate the selection/geometry/response gap; raw data are ADC-selected while Geant4 is energy-deposit truth.                 |
| Cross-section and dE/dx provenance are sufficient for publication | workspace file search                                          | geant4/readme_krakow_hg4.txt only  | sigma_pd_cm_190.txt and dedx tables present | not found       | not found              | n/a                                         | FAIL_PROVENANCE           | The requested sigma_pd_cm_190.txt and explicit dE/dx table files are absent from the visible repo/data tree; claims depending on them need provenance before final release. |

### Energy benchmark

| method                 | family                   | n      | res68_frac         | res68_ci95                                  | bias_frac           | mae_mev            |
| ---------------------- | ------------------------ | ------ | ------------------ | ------------------------------------------- | ------------------- | ------------------ |
| geant4_birks_lookup    | traditional_geant4_birks | 332852 | 0.0402439783091376 | [0.03885687265429256, 0.041606317494948857] | -0.0230986356186924 | 1.0824359599765987 |
| gradient_boosted_trees | ml_tree                  | 332852 | 0.0566846321762142 | [0.04880395769058964, 0.06719740156251883]  | -0.0167355872103629 | 1.0028925714276464 |
| physics_residual_mlp   | neural_physics_residual  | 332852 | 0.0586801621140033 | [0.049024699196538256, 0.0778824801768244]  | -0.0145744353230592 | 1.051508630675238  |
| ridge                  | ml_linear                | 332852 | 0.0966729355403716 | [0.08871564277716167, 0.11720596181535417]  | -0.0235729458948086 | 1.4114180808798578 |
| 1d_cnn                 | neural_waveform          | 332852 | 0.2657039478238139 | [0.24926581203810588, 0.2890790024307048]   | -0.1777390561183705 | 3.86211397876782   |
| old_power_law          | traditional_empirical    | 332852 | 0.4623579003318161 | [0.4443095010617282, 0.5643755593812345]    | -0.2976286301824027 | 7.86280147576027   |
| mlp                    | neural_tabular           | 332852 | 0.6923472493440915 | [0.6842365680562779, 0.6996464636631826]    | -0.5826860883867211 | 10.616250817321616 |

The winner is `geant4_birks_lookup`. The best ML method in the inherited S14h table is `gradient_boosted_trees` with res68 0.05668, while the traditional Geant4/Birks lookup has res68 0.04024 with CI [0.03886, 0.04161]. Since lower is better and the intervals do not overlap, generic ML does not beat the physics baseline for the energy-scale adoption claim.

### PID benchmark

| method                       | n    | positives | average_precision | average_precision_ci_low | average_precision_ci_high | roc_auc    | roc_auc_ci_low | roc_auc_ci_high |
| ---------------------------- | ---- | --------- | ----------------- | ------------------------ | ------------------------- | ---------- | -------------- | --------------- |
| traditional_deltae_range_cut | 8957 | 4119      | 0.76660868        | 0.75697543               | 0.77712598                | 0.82633236 | 0.81925974     | 0.83407708      |
| ridge_logistic_l2            | 8957 | 4119      | 0.93807549        | 0.93470421               | 0.94118478                | 0.9494308  | 0.9466543      | 0.95193053      |
| hist_gradient_boosted_trees  | 8957 | 4119      | 0.99178506        | 0.99097698               | 0.99245146                | 0.99277283 | 0.99212955     | 0.99336904      |
| sklearn_mlp                  | 8957 | 4119      | 0.99023447        | 0.98950401               | 0.99090334                | 0.99135365 | 0.99073168     | 0.99194944      |
| torch_1d_cnn                 | 8957 | 4119      | 0.99040547        | 0.98976373               | 0.99104152                | 0.99147231 | 0.99098185     | 0.99208359      |
| physics_gated_cnn            | 8957 | 4119      | 0.85457947        | 0.8243737                | 0.8826752                 | 0.89765734 | 0.88193        | 0.90430315      |

The simulation-only PID winner is `hist_gradient_boosted_trees`, AP 0.99178 with CI [0.99098, 0.99245]. The traditional DeltaE/range AP is 0.76661 with CI [0.75698, 0.77713]. This is a real Geant4-truth classification result, but it does not validate S15b's real-data weak PID proxy as event-level p/d truth.

## Interpretation

The end-to-end answer is mixed. Energy ordering and direct truth-calibrated energy closure are consistent with a strong physics baseline, and the data anchor is intact. Simulation truth also supports p/d classification in principle. The penetration profile, however, remains in tension: S19 needed a high 50 MeV EDep threshold to approach the data B8/B2 falloff and still reported a residual ratio gap. That points to detector response, trigger/selection, or geometry/material effects rather than to a purely statistical model-capacity problem.

The deepest causal node that S23 can identify is not a single line of code. It is a schema/domain mismatch: Geant4 artifacts describe deposited energy and particle truth, while raw HRD data are ADC waveforms after thresholding, saturation, pedestal, and acquisition selection. Until the detector-response bridge maps Sci_bar truth into HRD-like ADC waveforms, penetration and absolute energy-rate claims must remain caveated.

## MC verdict

MC validation is available through S14h/S17b/S17a/S19. MC agrees with data on the qualitative range-energy/PID direction and on the energy closure ordering, where the Geant4/Birks traditional lookup is the winner. MC does not yet close the penetration-rate claim because the selected-pulse data profile remains much steeper than un-digitized Sci_bar truth. Provenance for `sigma_pd_cm_190.txt` and explicit dE/dx tables is absent from the visible tree and must be restored before publication-grade cross-section statements.

## Systematics

- Detector response: no full HRD digitizer maps Geant4 EDep to ADC waveform samples for this S23 audit.
- Selection mismatch: data use `A > 1000 ADC`; simulation thresholds use MeV EDep.
- Geometry/material mismatch: prior MV3/S19 results indicate missing material or response effects can change penetration.
- PID label mismatch: S17a labels simulated primary p/d tracks; S15b labels real weak PID proxies and explicitly blocks truth adoption.
- Environment: this shell lacks uproot, so raw ROOT re-execution is inherited from committed raw-root artifacts rather than repeated here.
- Provenance: `sigma_pd_cm_190.txt` and explicit dE/dx table files are not visible in the repo/data tree.

## Caveats

This study is a reconciliation and audit, not a new full detector simulation. It names two winners because the scientific questions differ: Geant4/Birks wins the energy adoption benchmark, while HGBT wins the simulation-only p/d PID benchmark. The `result.json` top-level winner is the energy adoption winner because it is the strongest end-to-end data/MC closure claim.

## Open questions

1. S23a: digitized Geant4-to-HRD response closure. Hypothesis: the remaining penetration tension is dominated by ADC response and threshold emulation rather than by p/d cross-section physics. Falsifying test: generate HRD-like waveforms from Sci_bar truth with measured pedestal, saturation, and trigger response; the B8/B2 selected-pulse ratio must match raw data within the run/bootstrap CI.

## Provenance

Git commit: `d2a393d37665c6bd7a95bac48a623950f58758a6`

Input artifacts:

| path                                                                                                    | sha256                                                           | size_bytes |
| ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ---------- |
| geant4/REPRODUCTION_STATUS.md                                                                           | 45e6e7e3ff3db59db1aca3f53c01077915f540bf201df3ab808e18cc40a09bac | 2313       |
| geant4/results/sim_summary.json                                                                         | 9bb809e2cc9c21cb7f3f3b0590adfa075560738cab091bce7ecd7d1c02e39417 | 1496       |
| reports/1781088387.1790.33b946cb__s14h_g4_energy_calibration_benchmark/result.json                      | 00561273fa72bf3d0131fe3535e689c8f9acd6ddfbd7e5d04128898d5949b652 | 31663      |
| reports/1781088387.1790.33b946cb__s14h_g4_energy_calibration_benchmark/method_metrics.csv               | 1f606a6db7b73bf106c078c4f5edb0c1bca353d0e2a04064a2ace020a7bf5378 | 1692       |
| reports/1781069565.648.74687e98__s15b_raw_hrd_pid_proxy_falsification_ledger/result.json                | 46070ca9034c942adfa9224032b50d35f4e955431ead615122796d5635ea408f | 24761      |
| reports/1781083265.459.750722a1__s17a_geant4_energy_pid_truth_bridge/result.json                        | 04c1d31eba57c1150e29006b55b6ea89d724246df661e16b2fff75ab81ebd747 | 10778      |
| reports/1781083265.459.750722a1__s17a_geant4_energy_pid_truth_bridge/pid_benchmark.csv                  | d4eff3e7b1797db827f5954b3facf6353e02fc35762ba066776ff594d3dec62b | 1946       |
| reports/1781181864.166710.25f5247a__s19_geant4_penetration_selection/result.json                        | 3b13863c1b41c8bba962e4ea7184113c8b0c99b5c5eb28093fe8f44b22841cff | 8819       |
| reports/1781181864.166710.25f5247a__s19_geant4_penetration_selection/raw_data_per_run.csv               | fdf26ec16aef2fe4a69a09a315d0f6a06f5e80c13dcb64bc7fa46c4fb733e291 | 1105       |
| reports/1781181864.166710.25f5247a__s19_geant4_penetration_selection/data_deepest_per_run.csv           | 0a26f44d7ed729d4c389e08392880c6aa0a701c177008f3c139c4563218925ea | 896        |
| reports/1781181864.166710.25f5247a__s19_geant4_penetration_selection/sim_deepest_by_block_threshold.csv | 8af97c0948ae150be9a51b7389dadfe7149c6ff37b9454aa83049b8047a02d6d | 37770      |

Figures:

- `reports/1781181864.166962.68322ee6__s23_geant4_data_consistency_review/figures/fig_s23_consistency_verdicts.png`
- `reports/1781181864.166962.68322ee6__s23_geant4_data_consistency_review/figures/fig_s23_energy_methods.png`
- `reports/1781181864.166962.68322ee6__s23_geant4_data_consistency_review/figures/fig_s23_pid_methods.png`
- `reports/1781181864.166962.68322ee6__s23_geant4_data_consistency_review/figures/fig_s23_penetration_profile.png`

Output artifacts: `REPORT.md`, `result.json`, `manifest.json`, `claim_scoreboard.csv`, `energy_benchmark.csv`, `pid_benchmark.csv`, `raw_root_file_hashes.csv`.
