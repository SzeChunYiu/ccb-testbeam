# P04l Baseline-to-Charge Dropout Coupling

- **Ticket:** `1781030650.727.08857c2c`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw `data/root/root/hrdb_run_*.root`; no simulation or derived data are required.
- **Run split:** train on Sample I plus run 64; hold out Sample II analysis runs `58, 59, 60, 61, 62, 63, 65`.
- **Primary target:** paired odd-channel inverted duplicate-readout charge, `sum(max(-odd,0))`; features use the even channel only.

## Raw ROOT Reproduction Gate

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

The gate is the P04/S00 raw `HRDv` selection: subtract the per-channel median of samples 0--3, then retain B2/B4/B6/B8 records whose even-channel peak exceeds 1000 ADC. Rows with unusable odd duplicate charge or amplitude below 100 ADC are removed only after this reproduction gate.

## Statistical Setup

For pulse record \(i\), the charge target is

\[ y_i = \sum_t \max[-o_i(t),0], \]

where \(o_i(t)\) is the baseline-subtracted paired odd-channel waveform. A method predicts \(\hat y_i\), and the fractional residual is

\[ r_i = (\hat y_i-y_i)/\max(y_i,1). \]

The primary width metric is \(Q_{0.68}(|r_i|)\). Full RMS, median bias, catastrophic rate \(P(|r_i|>0.25)\), and timing-tail error are reported as secondary metrics. Confidence intervals are non-parametric run-block bootstraps over held-out runs; event bootstraps are retained in the CSV for within-run uncertainty.

## Methods

- **Frozen traditional estimators:** per-stave log calibrations of peak, positive integral, shifted adaptive-template scale, and a Huber diagnostic model. A dropout-injected correction applies train-run median residual corrections in `(stave, amplitude bin, peak bin, saturation, dropout)` cells.
- **ML/NN estimators:** ridge regression, histogram gradient-boosted trees, a tabular MLP, a waveform-only 1D-CNN, and `wave_atom_net`, a dual-branch architecture with a 1D waveform encoder plus atom/context branch.
- **Atoms and controls:** baseline excursion uses train-run 95th percentile of pretrigger MAD/slope/range score; delayed peak combines late peak sample and secondary-peak score; dropout uses post-peak undershoot plus tail charge deficit. Matched effects condition on run, stave, amplitude bin, peak bin, and saturation.
- **Sentinels:** shuffled target, topology-only, baseline-only, and saturation-only models are trained on the same split to check for target leakage and proxy-only explanations.

## Held-out Benchmark

| method                    |      n |   bias_median_frac |   res68_abs_frac | run_block_res68_ci95                         |   full_rms_frac |   catastrophic_rate | run_block_catastrophic_rate_ci95              |   timing_tail_abs_frac_mean |
|:--------------------------|-------:|-------------------:|-----------------:|:---------------------------------------------|----------------:|--------------------:|:----------------------------------------------|----------------------------:|
| hgb_waveform_atoms        | 125078 |        0.000983714 |        0.0168406 | [0.013598834854329861, 0.019451627778927602] |       0.0460247 |          0.00434129 | [0.0027382210014789774, 0.005442766221143725] |                   0.0166367 |
| mlp_waveform_atoms        | 125078 |        0.00586395  |        0.0223796 | [0.018695384699851273, 0.02597492690756917]  |       0.0742606 |          0.0148947  | [0.011236771412614078, 0.017943531217584813]  |                   0.0248783 |
| ridge_waveform_atoms      | 125078 |        0.000325738 |        0.0253795 | [0.022025958796963112, 0.02857150831259787]  |       0.14907   |          0.0440125  | [0.03084055763666353, 0.05296804797647019]    |                   0.0365412 |
| dropout_injected_integral | 125078 |       -0.00295366  |        0.0310563 | [0.02566256371174276, 0.036835843868974295]  |       1.03899   |          0.125706   | [0.08916917381274184, 0.15069796671312438]    |                   0.0625067 |
| wave_atom_net             | 125078 |        0.0323016   |        0.0486302 | [0.04331323638185859, 0.052628378462046384]  |       0.109749  |          0.0252083  | [0.017692756783274616, 0.03014914481865092]   |                   0.0493293 |
| strong_huber_atoms        | 125078 |        0.0251971   |        0.156473  | [0.11742931397207666, 0.1825485709569599]    |       0.653114  |          0.232215   | [0.19817251119247026, 0.2583380607100563]     |                   0.218225  |
| integral_logcal           | 125078 |       -0.107371    |        0.186395  | [0.16933236364094534, 0.20053142809753557]   |       1.75017   |          0.21202    | [0.1700605550384839, 0.24004838637346324]     |                   0.176064  |
| cnn_1d_waveform           | 125078 |       -0.0378204   |        0.223436  | [0.18649592135846615, 0.2625658886432648]    |       1.08667   |          0.297598   | [0.2474601998991498, 0.33001402930243995]     |                   0.2306    |
| peak_logcal               | 125078 |       -0.232842    |        0.318023  | [0.28816475546178066, 0.33489785306546715]   |       1.97456   |          0.553271   | [0.5043902066409544, 0.5840734646453508]      |                   0.396534  |
| adaptive_template_logcal  | 125078 |        0.138055    |        0.539309  | [0.4757253939911952, 0.6263998891053515]     |       2.92618   |          0.561634   | [0.4928006277040471, 0.601548137973177]       |                   0.438423  |

The winner by held-out res68 is `hgb_waveform_atoms`. The strongest traditional method is `dropout_injected_integral`.

## Per-run Check

| method                    | split          |     n |   res68_abs_frac |   catastrophic_rate |   timing_tail_abs_frac_mean |
|:--------------------------|:---------------|------:|-----------------:|--------------------:|----------------------------:|
| dropout_injected_integral | heldout_run_58 | 16780 |       0.0198562  |         0.0247318   |                   0.0377525 |
| dropout_injected_integral | heldout_run_59 | 21374 |       0.0418019  |         0.166464    |                   0.0963032 |
| dropout_injected_integral | heldout_run_60 | 17021 |       0.0369028  |         0.148052    |                   0.051853  |
| dropout_injected_integral | heldout_run_61 | 18963 |       0.0351752  |         0.141855    |                   0.0469779 |
| dropout_injected_integral | heldout_run_62 | 19088 |       0.0364141  |         0.144646    |                   0.0561209 |
| dropout_injected_integral | heldout_run_63 | 18814 |       0.0308192  |         0.129478    |                   0.0857524 |
| dropout_injected_integral | heldout_run_65 | 13038 |       0.0288211  |         0.103007    |                   0.054296  |
| ridge_waveform_atoms      | heldout_run_58 | 16780 |       0.0187369  |         0.0105483   |                   0.0347472 |
| ridge_waveform_atoms      | heldout_run_59 | 21374 |       0.0298554  |         0.0504819   |                   0.0361885 |
| ridge_waveform_atoms      | heldout_run_60 | 17021 |       0.0295086  |         0.059691    |                   0.0416831 |
| ridge_waveform_atoms      | heldout_run_61 | 18963 |       0.0284487  |         0.0536835   |                   0.0348204 |
| ridge_waveform_atoms      | heldout_run_62 | 19088 |       0.0278233  |         0.0507649   |                   0.0358958 |
| ridge_waveform_atoms      | heldout_run_63 | 18814 |       0.0247068  |         0.0416179   |                   0.0383965 |
| ridge_waveform_atoms      | heldout_run_65 | 13038 |       0.022762   |         0.0355116   |                   0.0335018 |
| hgb_waveform_atoms        | heldout_run_58 | 16780 |       0.00996213 |         0.000834327 |                   0.0124969 |
| hgb_waveform_atoms        | heldout_run_59 | 21374 |       0.0196327  |         0.0062693   |                   0.0192735 |
| hgb_waveform_atoms        | heldout_run_60 | 17021 |       0.0190125  |         0.00376006  |                   0.0159749 |
| hgb_waveform_atoms        | heldout_run_61 | 18963 |       0.0213043  |         0.00442968  |                   0.0175397 |
| hgb_waveform_atoms        | heldout_run_62 | 19088 |       0.0187816  |         0.00487217  |                   0.0167466 |
| hgb_waveform_atoms        | heldout_run_63 | 18814 |       0.0159109  |         0.0055278   |                   0.0173149 |
| hgb_waveform_atoms        | heldout_run_65 | 13038 |       0.0144672  |         0.00383494  |                   0.0155053 |

## Atom-matched Direct Effects

| method                    | atom                    |   n_cells |   delta_abs_frac | delta_abs_frac_ci95                              |   delta_catastrophic_rate | delta_catastrophic_rate_ci95                    |
|:--------------------------|:------------------------|----------:|-----------------:|:-------------------------------------------------|--------------------------:|:------------------------------------------------|
| dropout_injected_integral | atom_baseline_excursion |       177 |       1.38487    | [1.2906428090240174, 1.5061843662020569]         |                0.610793   | [0.5861611854398254, 0.6466362636220251]        |
| dropout_injected_integral | atom_delayed_peak       |       117 |      -0.0622678  | [-0.07797476912055207, -0.04173012392221229]     |               -0.0444623  | [-0.057827024600054774, -0.02785748716083421]   |
| dropout_injected_integral | atom_dropout            |       129 |       0.602843   | [0.48422285515572516, 0.7039890870797161]        |                0.293464   | [0.25326195632139376, 0.32666124540787045]      |
| hgb_waveform_atoms        | atom_baseline_excursion |       177 |       0.0436071  | [0.0361507093752094, 0.05101824744068691]        |                0.0299053  | [0.0206699438260322, 0.03939545408171789]       |
| hgb_waveform_atoms        | atom_delayed_peak       |       117 |      -0.00157454 | [-0.002664743566262797, -0.00036340497152638235] |               -0.00234176 | [-0.003265194864504985, -0.0014804577560133781] |
| hgb_waveform_atoms        | atom_dropout            |       129 |       0.045626   | [0.04031307761854833, 0.0499908296732784]        |                0.0411051  | [0.03171286059183867, 0.047851058434754984]     |

Positive `delta_abs_frac` means the atom stratum has larger charge error after matching on the stated controls.

## Estimator-specific Atom Effects

| method                    | atom                    |   n_cells |   delta_abs_frac | delta_abs_frac_ci95                              |   delta_catastrophic_rate | delta_catastrophic_rate_ci95                   |
|:--------------------------|:------------------------|----------:|-----------------:|:-------------------------------------------------|--------------------------:|:-----------------------------------------------|
| peak_logcal               | atom_baseline_excursion |       177 |       2.88789    | [2.7147230299455725, 3.0996478389544917]         |                0.557519   | [0.5345861827877111, 0.5900952303944828]       |
| peak_logcal               | atom_delayed_peak       |       117 |      -0.390421   | [-0.4815289310321819, -0.27437660289960775]      |                0.0424719  | [0.021142833905436316, 0.06784109126135822]    |
| peak_logcal               | atom_dropout            |       129 |       3.89553    | [3.3345966559171702, 4.617321234213269]          |                0.237085   | [0.20370358166263416, 0.2507371642914228]      |
| integral_logcal           | atom_baseline_excursion |       177 |       2.85472    | [2.7017419412449026, 3.0350421262503615]         |                0.482192   | [0.4494874125917065, 0.5241594475327583]       |
| integral_logcal           | atom_delayed_peak       |       117 |      -0.260063   | [-0.3197808354393631, -0.17645933967776486]      |               -0.00598786 | [-0.01695476518560459, 0.005288617435151063]   |
| integral_logcal           | atom_dropout            |       129 |       3.03094    | [2.655033450720385, 3.4264738800096524]          |                0.228176   | [0.19644215001962595, 0.2581813395542458]      |
| adaptive_template_logcal  | atom_baseline_excursion |       177 |       3.23314    | [3.1026967139158375, 3.409530637474194]          |                0.260352   | [0.22146959796694754, 0.31747162343007385]     |
| adaptive_template_logcal  | atom_delayed_peak       |       117 |      -0.244912   | [-0.3069765900442821, -0.1494241887707737]       |                0.0435613  | [0.02822291483104492, 0.06670176794002156]     |
| adaptive_template_logcal  | atom_dropout            |       129 |       4.70398    | [4.251686258438311, 5.255987654151751]           |                0.0687585  | [0.048353684423141516, 0.09730030210280688]    |
| strong_huber_atoms        | atom_baseline_excursion |       177 |       0.407631   | [0.36644073752694, 0.42932829385691024]          |                0.321618   | [0.3104109243157912, 0.3324151388173261]       |
| strong_huber_atoms        | atom_delayed_peak       |       117 |      -0.0669477  | [-0.08213695099397401, -0.045308397802448726]    |               -0.0541014  | [-0.06260735014464162, -0.042278647371196854]  |
| strong_huber_atoms        | atom_dropout            |       129 |       0.632582   | [0.5538929940678861, 0.7079076901091731]         |                0.460282   | [0.4159474562028842, 0.5126779687976496]       |
| dropout_injected_integral | atom_baseline_excursion |       177 |       1.38487    | [1.2868865680494799, 1.4962014734720828]         |                0.610793   | [0.5824344389696137, 0.6450936716991262]       |
| dropout_injected_integral | atom_delayed_peak       |       117 |      -0.0622678  | [-0.07849663372854543, -0.041601239568614196]    |               -0.0444623  | [-0.05989491996382198, -0.029661147470575754]  |
| dropout_injected_integral | atom_dropout            |       129 |       0.602843   | [0.4870491933568534, 0.6964645018026123]         |                0.293464   | [0.25462469926207004, 0.32765723502342076]     |
| ridge_waveform_atoms      | atom_baseline_excursion |       177 |       0.157435   | [0.1474778288290575, 0.16392537878706337]        |                0.263445   | [0.2455552954490998, 0.2758848970755567]       |
| ridge_waveform_atoms      | atom_delayed_peak       |       117 |      -0.0110702  | [-0.012999535418766951, -0.009382592448698218]   |               -0.00900086 | [-0.014012347799530887, -0.004902533389810298] |
| ridge_waveform_atoms      | atom_dropout            |       129 |       0.209479   | [0.19424990067316206, 0.22379785517961204]       |                0.419584   | [0.37401794059963156, 0.46652167587245746]     |
| hgb_waveform_atoms        | atom_baseline_excursion |       177 |       0.0436071  | [0.036297401490628316, 0.05105318620019825]      |                0.0299053  | [0.020822890356733, 0.039518277728791296]      |
| hgb_waveform_atoms        | atom_delayed_peak       |       117 |      -0.00157454 | [-0.0027074366904728205, -0.0003669967054491526] |               -0.00234176 | [-0.003183780370336732, -0.001514555725675003] |
| hgb_waveform_atoms        | atom_dropout            |       129 |       0.045626   | [0.04029532723892197, 0.049462096082065775]      |                0.0411051  | [0.0325318023614925, 0.04772758971943596]      |
| mlp_waveform_atoms        | atom_baseline_excursion |       177 |       0.0736047  | [0.07003919947073256, 0.0759771754825333]        |                0.0892317  | [0.08152533065908657, 0.09518151113745062]     |
| mlp_waveform_atoms        | atom_delayed_peak       |       117 |      -0.00825026 | [-0.0099049649066338, -0.005888992026977345]     |               -0.0184677  | [-0.02229722965062671, -0.012785452563529842]  |
| mlp_waveform_atoms        | atom_dropout            |       129 |       0.097046   | [0.09322916102700442, 0.10084239457720261]       |                0.132014   | [0.12061737463811537, 0.14509812938812974]     |
| cnn_1d_waveform           | atom_baseline_excursion |       177 |       0.952744   | [0.8769155115885903, 1.0474419978403506]         |                0.329345   | [0.2889675121281225, 0.39352959397647397]      |
| cnn_1d_waveform           | atom_delayed_peak       |       117 |      -0.123416   | [-0.15274463731888815, -0.07697966736361805]     |               -0.0602036  | [-0.07353489028304815, -0.044183120114849206]  |
| cnn_1d_waveform           | atom_dropout            |       129 |       0.40689    | [0.34900258021053493, 0.4788156733108484]        |                0.128604   | [0.11051419828877909, 0.1578584899247335]      |
| wave_atom_net             | atom_baseline_excursion |       177 |       0.0773049  | [0.07004548979508776, 0.08384298173858644]       |                0.121689   | [0.10818153345259075, 0.1317614067997641]      |
| wave_atom_net             | atom_delayed_peak       |       117 |      -0.00293031 | [-0.004813466644732583, -0.0007344523046895146]  |               -0.0175949  | [-0.021516962918677697, -0.012703048993836364] |
| wave_atom_net             | atom_dropout            |       129 |       0.114283   | [0.11073917969203574, 0.11762495525342984]       |                0.22195    | [0.2092481389485195, 0.23188312194098534]      |

## Leakage and Systematics

- Train/held-out run overlap: `[]`.
- Train/held-out `(run,event,stave)` key overlap: `0`.
- Invalid odd-target rows removed after reproduction: `255`.
- Shuffled-target HGB res68: `1.2191`.
- Topology-only ridge res68: `0.3488`.
- Baseline-only ridge res68: `1.2179`.
- Saturation-only ridge res68: `0.2830`.

The target remains duplicate-readout closure rather than deposited-energy truth. Baseline and dropout atoms are derived from the same even waveform used by the estimators, so causal language is restricted to residual association after explicit matching, not intervention. Run-block CIs are intentionally emphasized because Sample II contains only seven held-out runs.

## Finding

The best held-out charge estimator is hgb_waveform_atoms with res68=0.0168 and run-block 95% CI [0.0136, 0.0195]. The strongest traditional comparator is dropout_injected_integral at res68=0.0311 [0.0257, 0.0368]. After exact matching on run, stave, amplitude bin, peak bin, and saturation, the atom table shows whether baseline excursion, delayed peaks, or dropout retain residual charge-error excess; those matched deltas are interpreted as controlled associations, not absolute deposited-energy causation.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04l_baseline_charge_dropout_coupling.py --config configs/p04l_baseline_charge_dropout_coupling.json
```
