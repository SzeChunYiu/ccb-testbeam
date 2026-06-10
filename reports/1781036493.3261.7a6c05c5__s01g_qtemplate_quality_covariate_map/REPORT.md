# S01g q-template quality covariate map

- **Ticket:** 1781036493.3261.7a6c05c5
- **Worker:** testbeam-laptop-3
- **Inputs:** raw B-stack ROOT files under `data/root/root`; no shared q-template artifact is read.
- **Primary endpoint:** S03b pair-residual timing-tail quality map, leave-one-run-out over Sample-II runs `[58, 59, 60, 61, 62, 63, 65]`.

## Preregistered question

S01f showed that fold-local q_template vetoes did not securely narrow S03b timing tails. S01g asks the broader question: does the fold-local q_template residual remain a useful atomic quality covariate for timing-tail, amplitude/support, saturation-like, pile-up-like, baseline, dropout, PID, or energy maps?

The raw B-stack files do not contain external PID or absolute energy truth labels. I therefore treat timing-tail classification as the primary benchmark and report secondary support-map proxies only as covariate diagnostics, not PID or energy claims.

## Raw-ROOT reproduction

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The run-65 S03 timing references were regenerated from the same raw-derived pulse table before training any S01g model.

| method               |   value |   reference_value |   delta | pass   |
|:---------------------|--------:|------------------:|--------:|:-------|
| template_phase_base  | 2.88915 |           2.88915 |       0 | True   |
| s03a_amp_only        | 1.49464 |           1.49464 |       0 | True   |
| s03b_monotone_binned | 1.56958 |           1.56958 |       0 | True   |

## Methods

For held-out run \(r\), all q_template medians are built only from train runs \(R \setminus r\). Each waveform \(x_i(t)\) is baseline-subtracted, peak-normalized, CFD20-aligned, and compared with the train-run median template \(m_{s,b}(t)\) for stave \(s\) and amplitude bin \(b\):

\[q_i = \left(|T_i|^{-1}\sum_{t\in T_i}(x_i(t)-m_{s,b}(t))^2\right)^{1/2}.\]

The pair-level target is \(y=1[|\Delta t - \mathrm{median}_{train}(\Delta t)|>5\,\mathrm{ns}]\), where \(\Delta t\) is the S03b monotone timewalk-corrected residual for B4-B6, B4-B8, or B6-B8. Each method chooses a train-run score threshold from the preregistered quantile grid with at least 88% train-pair retention, minimizing train tail fraction and then train sigma68. The same threshold is applied to the held-out run.

The strong traditional baseline is a fold-local threshold on `q_pair_max`. ML/NN competitors are ridge, gradient-boosted trees, MLP, 1D-CNN, and the new `q_token_attention` architecture. The new architecture is sensible here because it treats left-pulse, right-pulse, and downstream-summary q/shape atoms as tokens, allowing a tiny attention layer to learn asymmetric quality interactions without using event IDs, run IDs, residuals, or labels as features.

Confidence intervals are 95% nonparametric run-block bootstraps. For a statistic \(S\), each bootstrap replicate samples the seven held-out runs with replacement, pools their retained pair residuals, and recomputes \(S_b\).

## Head-to-head benchmark

| method                  | family           |   value |   ci_low |   ci_high |   delta_vs_no_cut_ns |   delta_ci_low |   delta_ci_high |   keep_fraction |   n_pair_residuals |
|:------------------------|:-----------------|--------:|---------:|----------:|---------------------:|---------------:|----------------:|----------------:|-------------------:|
| q_token_attention       | new_architecture | 1.52643 |  1.31166 |   1.85176 |           -0.118722  |     -0.202082  |      0          |        0.901309 |              10329 |
| gradient_boosted_trees  | ml               | 1.52643 |  1.31166 |   1.85188 |           -0.118722  |     -0.201477  |      0          |        0.939529 |              10767 |
| mlp                     | nn               | 1.52643 |  1.31436 |   1.90729 |           -0.118722  |     -0.157863  |      0          |        0.901309 |              10329 |
| 1d_cnn                  | nn               | 1.56166 |  1.31436 |   1.90729 |           -0.0834861 |     -0.134034  |      0.00532249 |        0.897208 |              10282 |
| ridge                   | ml               | 1.56562 |  1.31906 |   1.90729 |           -0.0795265 |     -0.12893   |      0.0298428  |        0.893368 |              10238 |
| no_cut                  | reference        | 1.64515 |  1.32175 |   1.94446 |            0         |      0         |      0          |        1        |              11460 |
| traditional_q_threshold | traditional      | 1.69978 |  1.43371 |   2.02026 |            0.0546285 |      0.0308613 |      0.148022   |        0.888831 |              10186 |

Per-run held-out performance:

|   heldout_run | method                  |   average_precision |    roc_auc |        brier |   keep_fraction |   sigma68_delta_vs_no_cut_ns |   sigma68_ns |   tail_frac_abs_gt5ns |
|--------------:|:------------------------|--------------------:|-----------:|-------------:|----------------:|-----------------------------:|-------------:|----------------------:|
|            58 | 1d_cnn                  |          0.216995   |   0.882629 |   0.0648913  |        0.926941 |                 -7.10543e-15 |      1.3214  |            0.0197044  |
|            58 | gradient_boosted_trees  |          0.423903   |   0.975743 |   0.0510719  |        0.926941 |                 -1.11022e-15 |      1.3214  |            0.00492611 |
|            58 | mlp                     |          0.477994   |   0.974178 |   0.0201188  |        0.899543 |                 -7.10543e-15 |      1.3214  |            0          |
|            58 | no_cut                  |        nan          | nan        | nan          |        1        |                  0           |      1.3214  |            0.0319635  |
|            58 | q_token_attention       |          0.395876   |   0.916275 |   0.0650933  |        0.940639 |                  0           |      1.3214  |            0.0145631  |
|            58 | ridge                   |          0.58082    |   0.92097  |   0.152456   |        0.931507 |                  0           |      1.3214  |            0.0147059  |
|            58 | traditional_q_threshold |          0.38784    |   0.785603 |   0.026343   |        0.917808 |                 -7.10543e-15 |      1.3214  |            0.0199005  |
|            59 | 1d_cnn                  |          0.543123   |   0.937774 |   0.0739012  |        0.896024 |                 -0.188337    |      1.31166 |            0.00390054 |
|            59 | gradient_boosted_trees  |          0.546372   |   0.934334 |   0.0335788  |        0.939275 |                 -0.188337    |      1.31166 |            0.0055814  |
|            59 | mlp                     |          0.417978   |   0.894844 |   0.0114278  |        0.908257 |                 -0.188337    |      1.31166 |            0.00529101 |
|            59 | no_cut                  |        nan          | nan        | nan          |        1        |                  0           |      1.5     |            0.0157274  |
|            59 | q_token_attention       |          0.482742   |   0.891429 |   0.0678699  |        0.892529 |                 -0.188337    |      1.31166 |            0.00636319 |
|            59 | ridge                   |          0.369527   |   0.894844 |   0.163057   |        0.906073 |                 -0.188337    |      1.31166 |            0.00626808 |
|            59 | traditional_q_threshold |          0.0820231  |   0.80153  |   0.0151524  |        0.882045 |                  0.0616634   |      1.56166 |            0.00792472 |
|            60 | 1d_cnn                  |          0.622907   |   0.953545 |   0.0735227  |        0.901403 |                 -1.11022e-15 |      1.23065 |            0.002746   |
|            60 | gradient_boosted_trees  |          0.717383   |   0.940034 |   0.0252499  |        0.952558 |                 -1.11022e-15 |      1.23065 |            0.0034647  |
|            60 | mlp                     |          0.673046   |   0.948107 |   0.00761557 |        0.905116 |                 -1.11022e-15 |      1.23065 |            0.00273473 |
|            60 | no_cut                  |        nan          | nan        | nan          |        1        |                  0           |      1.23065 |            0.0156766  |
|            60 | q_token_attention       |          0.702064   |   0.957901 |   0.0553918  |        0.906766 |                 -1.11022e-15 |      1.23065 |            0.00272975 |
|            60 | ridge                   |          0.599049   |   0.955607 |   0.167341   |        0.869637 |                 -1.11022e-15 |      1.23065 |            0.00332068 |
|            60 | traditional_q_threshold |          0.0870007  |   0.859184 |   0.0146396  |        0.884076 |                  0.0193482   |      1.25    |            0.00326645 |
|            61 | 1d_cnn                  |          0.289144   |   0.849526 |   0.0764907  |        0.883173 |                  0           |      2.10176 |            0.0121359  |
|            61 | gradient_boosted_trees  |          0.416524   |   0.845317 |   0.0362973  |        0.940693 |                 -3.55271e-15 |      2.10176 |            0.0163312  |
|            61 | mlp                     |          0.401597   |   0.857836 |   0.0224128  |        0.885316 |                  0           |      2.10176 |            0.0145278  |
|            61 | no_cut                  |        nan          | nan        | nan          |        1        |                  0           |      2.10176 |            0.0310825  |
|            61 | q_token_attention       |          0.274833   |   0.796049 |   0.0515763  |        0.907824 |                 -3.55271e-15 |      2.10176 |            0.0157418  |
|            61 | ridge                   |          0.22395    |   0.7892   |   0.167228   |        0.8796   |                  0.00528694  |      2.10704 |            0.0170593  |
|            61 | traditional_q_threshold |          0.0923325  |   0.698494 |   0.0286425  |        0.898535 |                  0.0992704   |      2.20103 |            0.0222664  |
|            62 | 1d_cnn                  |          0.491676   |   0.959274 |   0.0641974  |        0.920694 |                 -0.111844    |      1.32559 |            0.00269179 |
|            62 | gradient_boosted_trees  |          0.700232   |   0.963513 |   0.0260989  |        0.964891 |                  0           |      1.43743 |            0.00428082 |
|            62 | mlp                     |          0.649426   |   0.955909 |   0.00797192 |        0.914498 |                 -0.111844    |      1.32559 |            0.0031617  |
|            62 | no_cut                  |        nan          | nan        | nan          |        1        |                  0           |      1.43743 |            0.0144568  |
|            62 | q_token_attention       |          0.49941    |   0.914417 |   0.0605342  |        0.904998 |                 -0.111844    |      1.32559 |            0.00547695 |
|            62 | ridge                   |          0.462674   |   0.945013 |   0.163263   |        0.919455 |                 -0.0863904   |      1.35104 |            0.00404313 |
|            62 | traditional_q_threshold |          0.0791466  |   0.789187 |   0.0138136  |        0.897563 |                  0.175965    |      1.6134  |            0.00644271 |
|            63 | 1d_cnn                  |          0.541864   |   0.955482 |   0.0898084  |        0.863063 |                 -0.118754    |      1.31436 |            0.00417537 |
|            63 | gradient_boosted_trees  |          0.577888   |   0.946882 |   0.0466746  |        0.872072 |                 -0.118754    |      1.31436 |            0.00413223 |
|            63 | mlp                     |          0.634994   |   0.947082 |   0.01154    |        0.881982 |                 -0.118754    |      1.31436 |            0.0040858  |
|            63 | no_cut                  |        nan          | nan        | nan          |        1        |                  0           |      1.43311 |            0.0198198  |
|            63 | q_token_attention       |          0.512491   |   0.943482 |   0.0703764  |        0.872973 |                 -0.118754    |      1.31436 |            0.00412797 |
|            63 | ridge                   |          0.387467   |   0.900364 |   0.161398   |        0.89009  |                 -0.118754    |      1.31436 |            0.00708502 |
|            63 | traditional_q_threshold |          0.0673139  |   0.788808 |   0.0197303  |        0.859459 |                  0.12143     |      1.55454 |            0.00943396 |
|            65 | 1d_cnn                  |          0.02       |   0.751269 |   0.0693089  |        0.929293 |                 -0.0857407   |      1.48384 |            0.00543478 |
|            65 | gradient_boosted_trees  |          0.00840336 |   0.401015 |   0.0601517  |        0.848485 |                 -0.138592    |      1.43098 |            0.00595238 |
|            65 | mlp                     |          0.0113636  |   0.558376 |   0.00520725 |        0.949495 |                 -0.0695764   |      1.5     |            0.00531915 |
|            65 | no_cut                  |        nan          | nan        | nan          |        1        |                  0           |      1.56958 |            0.00505051 |
|            65 | q_token_attention       |          0.0119048  |   0.57868  |   0.0595568  |        0.914141 |                  0           |      1.56958 |            0.00552486 |
|            65 | ridge                   |          0.00892857 |   0.436548 |   0.170304   |        0.888889 |                 -0.138592    |      1.43098 |            0.00568182 |
|            65 | traditional_q_threshold |          0.00613497 |   0.177665 |   0.00569269 |        0.914141 |                 -0.0556611   |      1.51392 |            0.00552486 |

## Secondary q-template support maps

| map                                | contrast                         |         value |       ci_low |      ci_high |   high_q_threshold |
|:-----------------------------------|:---------------------------------|--------------:|-------------:|-------------:|-------------------:|
| timing_tail_abs_gt5ns              | top_decile_q_pair_max_minus_rest |   0.0810701   |   0.0675872  |   0.0898894  |           0.183444 |
| abs_residual_ns                    | top_decile_q_pair_max_minus_rest |   1.02264     |   0.836439   |   1.18642    |           0.183444 |
| amplitude_log_mean                 | top_decile_q_pair_max_minus_rest |  -0.307164    |  -0.316554   |  -0.300422   |           0.183444 |
| saturation_boundary_amp_ge_6800    | top_decile_q_pair_max_minus_rest |  -0.000777411 |  -0.00385071 |   0.00274608 |           0.183444 |
| pileup_late_fraction_max           | top_decile_q_pair_max_minus_rest |  -0.395116    |  -0.459978   |  -0.328291   |           0.183444 |
| pileup_late_top_decile             | top_decile_q_pair_max_minus_rest |   0.00222825  |  -0.0523793  |   0.0312362  |           0.183444 |
| baseline_excursion_rms_max         | top_decile_q_pair_max_minus_rest | 740.466       | 582.454      | 907.265      |           0.183444 |
| baseline_excursion_top_decile      | top_decile_q_pair_max_minus_rest |   0.49535     |   0.383195   |   0.593246   |           0.183444 |
| charge_shape_area_over_amp_absdiff | top_decile_q_pair_max_minus_rest |   1.2827      |   0.955031   |   1.70574    |           0.183444 |
| dropout_peak_edge_proxy            | top_decile_q_pair_max_minus_rest |   0.385336    |   0.290011   |   0.446718   |           0.183444 |
| pid_energy_proxy_log_amp_absdiff   | top_decile_q_pair_max_minus_rest |   0.10083     |   0.0860059  |   0.118535   |           0.183444 |
| downstream_q_max                   | top_decile_q_pair_max_minus_rest |   0.269531    |   0.253043   |   0.283465   |           0.183444 |

These secondary maps show whether high-q pairs concentrate other quality atoms. They do not establish external PID or absolute energy resolution because the raw B-stack stream used here lacks those truth labels.

## Policies and leakage checks

|   heldout_run | method                  |   threshold |   threshold_quantile |   train_keep_fraction |   train_tail_fraction |   train_sigma68_ns |
|--------------:|:------------------------|------------:|---------------------:|----------------------:|----------------------:|-------------------:|
|            58 | traditional_q_threshold |   0.185317  |                 0.9  |              0.900009 |           0.0107739   |            1.72937 |
|            58 | ridge                   |   0.0549279 |                 0.9  |              0.900009 |           0.00741326  |            1.5714  |
|            58 | gradient_boosted_trees  |   0.496355  |                 0.9  |              0.900009 |           0.00148265  |            1.5714  |
|            58 | mlp                     |   0.0287339 |                 0.9  |              0.900009 |           0.00513986  |            1.5714  |
|            58 | 1d_cnn                  |   0.596027  |                 0.9  |              0.900009 |           0.00316299  |            1.5714  |
|            58 | q_token_attention       |   0.652616  |                 0.9  |              0.900009 |           0.00247109  |            1.38659 |
|            59 | traditional_q_threshold |   0.152488  |                 0.88 |              0.880057 |           0.00991203  |            1.6905  |
|            59 | ridge                   |   0.0440161 |                 0.9  |              0.900011 |           0.00666344  |            1.5     |
|            59 | gradient_boosted_trees  |   0.432837  |                 0.95 |              0.949951 |           0           |            1.37116 |
|            59 | mlp                     |   0.0249986 |                 0.9  |              0.900011 |           0.00508844  |            1.37116 |
|            59 | 1d_cnn                  |   0.51377   |                 0.9  |              0.900011 |           0.00230191  |            1.5     |
|            59 | q_token_attention       |   0.482796  |                 0.9  |              0.900011 |           0.000848074 |            1.37116 |
|            60 | traditional_q_threshold |   0.148189  |                 0.88 |              0.880035 |           0.0096831   |            1.58    |
|            60 | ridge                   |  -0.0154514 |                 0.9  |              0.899956 |           0.00664043  |            1.48065 |
|            60 | gradient_boosted_trees  |   0.419418  |                 0.95 |              0.949978 |           0           |            1.48065 |
|            60 | mlp                     |   0.0271528 |                 0.9  |              0.899956 |           0.00639449  |            1.48065 |
|            60 | 1d_cnn                  |   0.510419  |                 0.9  |              0.899956 |           0.00270536  |            1.48065 |
|            60 | q_token_attention       |   0.464725  |                 0.9  |              0.899956 |           0.00172159  |            1.48065 |
|            61 | traditional_q_threshold |   0.184291  |                 0.9  |              0.900012 |           0.00949326  |            1.55554 |
|            61 | ridge                   |   0.101015  |                 0.9  |              0.900012 |           0.00564464  |            1.40729 |
|            61 | gradient_boosted_trees  |   0.358681  |                 0.95 |              0.950006 |           0           |            1.40729 |
|            61 | mlp                     |   0.0199006 |                 0.9  |              0.900012 |           0.0020526   |            1.40729 |
|            61 | 1d_cnn                  |   0.513122  |                 0.9  |              0.900012 |           0.0010263   |            1.40729 |
|            61 | q_token_attention       |   0.365788  |                 0.9  |              0.900012 |           0.00166774  |            1.40729 |
|            62 | traditional_q_threshold |   0.181112  |                 0.9  |              0.9001   |           0.0120452   |            1.68743 |
|            62 | ridge                   |   0.0417435 |                 0.9  |              0.899989 |           0.00725261  |            1.57559 |
|            62 | gradient_boosted_trees  |   0.466438  |                 0.95 |              0.949994 |           0           |            1.57559 |
|            62 | mlp                     |   0.0291454 |                 0.9  |              0.899989 |           0.00393362  |            1.57559 |
|            62 | 1d_cnn                  |   0.570611  |                 0.9  |              0.899989 |           0.00270436  |            1.57559 |
|            62 | q_token_attention       |   0.502016  |                 0.9  |              0.899989 |           0.00172096  |            1.57559 |
|            63 | traditional_q_threshold |   0.148571  |                 0.88 |              0.880097 |           0.0102097   |            1.70857 |
|            63 | ridge                   |   0.0345142 |                 0.88 |              0.88     |           0.006917    |            1.56436 |
|            63 | gradient_boosted_trees  |   0.334018  |                 0.88 |              0.88     |           0.000439174 |            1.56436 |
|            63 | mlp                     |   0.0223731 |                 0.88 |              0.88     |           0.00384278  |            1.56436 |
|            63 | 1d_cnn                  |   0.572959  |                 0.88 |              0.88     |           0.00329381  |            1.56436 |
|            63 | q_token_attention       |   0.46355   |                 0.88 |              0.88     |           0.00131752  |            1.56135 |
|            65 | traditional_q_threshold |   0.152409  |                 0.88 |              0.880039 |           0.0104934   |            1.75    |
|            65 | ridge                   |   0.0467173 |                 0.9  |              0.899929 |           0.00720276  |            1.56958 |
|            65 | gradient_boosted_trees  |   0.396361  |                 0.9  |              0.899929 |           0.000888012 |            1.39173 |
|            65 | mlp                     |   0.0315009 |                 0.9  |              0.899929 |           0.00473606  |            1.56958 |
|            65 | 1d_cnn                  |   0.581027  |                 0.9  |              0.899929 |           0.00286137  |            1.56958 |
|            65 | q_token_attention       |   0.482859  |                 0.9  |              0.899929 |           0.00098668  |            1.38859 |

|   heldout_run | check                              |   value | flag   |
|--------------:|:-----------------------------------|--------:|:-------|
|            58 | train_heldout_event_id_overlap     |       0 | False  |
|            58 | train_tail_positive_pairs          |     210 | False  |
|            58 | heldout_tail_positive_pairs        |       6 | False  |
|            58 | q_template_missing_heldout_rows    |       0 | False  |
|            58 | forbidden_identifier_features_used |       0 | False  |
|            59 | train_heldout_event_id_overlap     |       0 | False  |
|            59 | train_tail_positive_pairs          |     168 | False  |
|            59 | heldout_tail_positive_pairs        |      36 | False  |
|            59 | q_template_missing_heldout_rows    |       0 | False  |
|            59 | forbidden_identifier_features_used |       0 | False  |
|            60 | train_heldout_event_id_overlap     |       0 | False  |
|            60 | train_tail_positive_pairs          |     163 | False  |
|            60 | heldout_tail_positive_pairs        |      38 | False  |
|            60 | q_template_missing_heldout_rows    |       0 | False  |
|            60 | forbidden_identifier_features_used |       0 | False  |
|            61 | train_heldout_event_id_overlap     |       0 | False  |
|            61 | train_tail_positive_pairs          |     145 | False  |
|            61 | heldout_tail_positive_pairs        |      84 | False  |
|            61 | q_template_missing_heldout_rows    |       0 | False  |
|            61 | forbidden_identifier_features_used |       0 | False  |
|            62 | train_heldout_event_id_overlap     |       0 | False  |
|            62 | train_tail_positive_pairs          |     179 | False  |
|            62 | heldout_tail_positive_pairs        |      35 | False  |
|            62 | q_template_missing_heldout_rows    |       0 | False  |
|            62 | forbidden_identifier_features_used |       0 | False  |
|            63 | train_heldout_event_id_overlap     |       0 | False  |
|            63 | train_tail_positive_pairs          |     195 | False  |
|            63 | heldout_tail_positive_pairs        |      23 | False  |
|            63 | q_template_missing_heldout_rows    |       0 | False  |
|            63 | forbidden_identifier_features_used |       0 | False  |
|            65 | train_heldout_event_id_overlap     |       0 | False  |
|            65 | train_tail_positive_pairs          |     216 | False  |
|            65 | heldout_tail_positive_pairs        |       1 | False  |
|            65 | q_template_missing_heldout_rows    |       0 | False  |
|            65 | forbidden_identifier_features_used |       0 | False  |

## Systematics and caveats

- Run-heldout splitting is the main leakage guard; event IDs and run IDs are excluded from model features.
- The target is an S03b timing residual tail, so it is a quality-risk proxy rather than independent detector truth.
- The high-q secondary maps use internally defined baseline, late-shape, and support proxies. They are useful for hypothesis generation, not final PID/energy calibration.
- The seven-run bootstrap captures run-to-run instability, but run 65 has low statistics and therefore visibly affects the interval width.
- The NN models use fixed small architectures to avoid a large multiple-comparison scan on a small pair table.

## Verdict

The point-estimate winner is q_token_attention: kept-pair sigma68 1.526 ns [1.312, 1.852], delta vs no-cut -0.119 ns [-0.202, 0.000]. The traditional q-threshold gives 1.700 ns [1.434, 2.020], while no-cut is 1.645 ns [1.322, 1.944]. Adoption status: diagnostic only; CI does not prove narrowing. Clear separation from traditional: 0.

## Hypothesis and next experiment

Hypothesis: q_template is best treated as a local support/risk atom, not a standalone timing-tail veto. If this is correct, future externally labeled PID/energy or injected-pileup studies should show high-q enrichment in failure modes but only weak standalone resolution gains after amplitude, topology, and run-family controls.

## Artifacts

`reproduction_match_table.csv`, `run65_reproduction.csv`, `heldout_model_metrics.csv`, `model_predictions.csv`, `run_bootstrap_ci.csv`, `secondary_support_map.csv`, `threshold_policies.csv`, `fold_local_template_bin_counts.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
