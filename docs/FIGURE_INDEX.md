# Figure Index

The docs tree now carries the plot assets used by the thesis-style manuscript in
`docs/figures/`. These figures are intentionally referenced from both Markdown
and LaTeX so the report is visual and auditable.

| Topic | Figure | Used for |
|---|---|---|
| Raw sample reproduction | `fig_counts_by_run.png`, `fig_counts_by_group_stave.png` | Selected-pulse population and stave topology |
| Template reconstruction | `fig_template_library_examples.png`, `fig_q_template_by_group_stave.png`, `fig_template_vs_autoencoder_benchmark.png` | Pulse template quality and reconstruction benchmark |
| Timing | `fig_s03a_head_to_head.png`, `fig_s03d_pooled_run_bootstrap.png`, `fig_pair_covariance_by_topology.png`, `fig_timing_architecture_sweep.png` | Timewalk, run stability, topology covariance, and architecture sweep |
| Pile-up | `fig_threshold_scan_by_run.png`, `fig_current_excess.png`, `fig_poisson_rmax.png`, `fig_resolvability_delay_bias.png`, `fig_gate_coverage_bad_rate.png`, `fig_run_block_score_ratios.png` | Live-time, current excess, occupancy scaling, and two-pulse recovery |
| Pulse-shape ML | `fig_reconstruction_head_to_head.png`, `fig_pca_vs_ae_and_latent.png`, `fig_cluster_mean_waveforms.png`, `fig_loro_sigma68.png`, `fig_roc_pr.png` | Representation learning, strict timing audits, and classifier diagnostics |
| Amplitude/energy/pedestal | `fig_saturation_recovery.png`, `fig_heldout_residual_distributions.png`, `fig_head_to_head.png`, `deltae_e_truth_bands.png` | Saturation, pedestal validation, and truth-band energy interpretation |
| GEANT4 truth | `sim_vs_data.png`, `geometry_tof.png` | Simulation/data bridge and timing geometry |

The LaTeX build references these assets via paths such as
`../figures/reports/...`, relative to `docs/latex/`.
