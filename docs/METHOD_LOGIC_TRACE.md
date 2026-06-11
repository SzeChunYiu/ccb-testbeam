# Method Logic Trace

This file explains the analysis logic at reviewer granularity. It is deliberately
more explicit than the findings summary: each step states the input, the action,
the reason for the action, the failure mode it prevents, the evidence used, and
the interpretation that is allowed. The goal is to make every high-level claim
traceable back to a reproducible operation or to a stated limitation.

## Rules Used Throughout

1. **Start from raw waveforms when a count or selection matters.**  
   Derived branches and sorted tables are useful diagnostics, but they can encode
   historical choices. Raw `HRDv` waveforms are the least ambiguous source for a
   pulse-count claim.

2. **Separate deterministic definitions from learned approximations.**  
   If a label is exactly `A > 1000 ADC`, a model that predicts that label is not
   discovering physics. It is approximating the definition. The deterministic
   rule remains the accepted method.

3. **Use run-held-out comparisons for performance claims.**  
   Random row splits are too optimistic because run period, current, topology,
   and calibration are correlated. A method that works only after mixing rows
   from the same run is not a robust detector correction.

4. **Require a traditional comparator before accepting ML.**  
   ML is useful only if it beats a clear non-ML method on the same input
   population, target, split, and metric. A higher score on a weaker comparator
   does not justify adoption.

5. **Distinguish closure truth, proxy truth, and physics truth.**  
   Injected pile-up and artificial saturation have known construction truth.
   Duplicate readout is an independent electronics closure. GEANT4 supplies
   simulation truth. None of these automatically gives event-level particle ID
   or deposited-energy truth for real HRD data.

6. **Report uncertainty at the correlation scale.**  
   Pulse rows are not independent when they share a run, current setting, or
   topology. Bootstrap intervals are therefore interpreted only when the resample
   unit matches the physical correlation structure used by the study.

## End-to-End Analysis Chain

| Step | Input | Operation | Why this is done | Evidence | Accepted interpretation |
|---|---|---|---|---|---|
| 1 | B-stack raw ROOT `h101/HRDv` | Read 18-sample waveform blocks for the physical even B channels | Establishes the pulse population before any derived table semantics enter | S00 raw-gate reproduction | Count claims are tied to raw data, not to sorted proxies |
| 2 | Samples 0-3 of each waveform | Compute `b = median(w0,w1,w2,w3)` | A short pre-pulse pedestal is robust to one bad sample and avoids using post-pulse tail information | Reproduced gate count and pedestal validation studies | This is a selection baseline, not a final electronics pedestal truth |
| 3 | Baseline-subtracted waveform | Compute `A = max_j(w_j - b)` | Peak amplitude is the historical and reproducible selection scalar | Exact 640,737 selected B-pulse count | Selection is deterministic for fixed input bytes and code |
| 4 | `A` and physical stave id | Keep B2/B4/B6/B8 pulses with `A > 1000 ADC` | Defines a high-confidence pulse population and preserves the B-stack range topology | `fig_counts_by_run.png`, `fig_counts_by_group_stave.png` | Downstream analyses inherit this population |
| 5 | Selected waveforms | Build stave- and amplitude-binned templates | Pulse shape changes with stave and amplitude; a single global template would hide quenching and readout effects | `fig_template_library_examples.png`, `fig_q_template_by_group_stave.png` | Template residuals are covariates, not absolute truth labels |
| 6 | Leading edge waveform | Compute CFD20 seed time | A fixed fractional crossing gives an interpretable, local timing seed | Timing benchmark chapters | CFD20 is a software seed, not a hardware-timing truth |
| 7 | Template, derivative, non-jagged samples | Fit local template phase / optimal-filter time | Sub-sample timing needs a shape model while avoiding obviously broken samples | Timing reconstruction reports | Raw timing is a model estimate with later corrections |
| 8 | Amplitude and run structure | Apply analytic timewalk and offset corrections | Leading-edge time depends on amplitude and calibration period | Timewalk head-to-head plot | Analytic timewalk explains most timing gain |
| 9 | Corrected stave times | Form inter-stave residuals | Same-particle residuals avoid needing absolute external time truth | Timing residual and covariance plots | Downstream B4/B6/B8 residuals define the clean timing benchmark |
| 10 | Residual distribution | Quote sigma68 and selected core fits | Tails are important; sigma68 is less tail-dominated than RMS but more honest than a narrow Gaussian alone | Timing chapters and covariance figure | Timing claims must name the metric |
| 11 | B2-containing residuals | Compare topology-specific covariances | B2 has terminal and overlap-dominated populations that can dominate width | `fig_pair_covariance_by_topology.png` | B2 pathology is detector/topology local, not a global timing failure |
| 12 | Occupancy target and live-time | Compute Poisson rate scaling | Pile-up rate is an occupancy calculation, so the live-time window enters directly | `fig_poisson_rmax.png`, threshold scan | The old 4.22 MHz number is conditional on 90 ns |
| 13 | Raw waveform tails | Measure live-time from data | The 90 ns window was an assumption and must be tested | `fig_threshold_scan_by_run.png` | The preferred 10-percent estimate rescales the combined criterion to about 3.05 MHz |
| 14 | Low/high-current runs | Compare current-dependent excess | Real beam pile-up should increase with current; fixed waveform pathologies should not | `fig_current_excess.png`, score-ratio reports | Quote high-current excess, not the raw score |
| 15 | Clean pulses plus injected overlaps | Fit traditional and ML two-pulse recovery | Synthetic truth lets us compare recovery methods under controlled overlap | `fig_resolvability_delay_bias.png`, failure-gate plots | ML can improve conditional RMS, but adoption must include failure rate |
| 16 | Waveform-shape matrices | Compare PCA and autoencoder representations | Tests whether useful pulse information is low-dimensional and whether nonlinearity helps | `fig_pca_vs_ae_and_latent.png` | Pulse shape is compact; nonlinear embeddings help only in the compact regime |
| 17 | Duplicate odd-readout targets | Predict amplitude and charge closures | Duplicate electronics provide an independent target without claiming absolute energy truth | Amplitude/charge closure reports | ML wins this closure, but it is not per-event beam energy |
| 18 | Artificial saturation clips | Recover unclipped amplitude | Construction truth is known, so leakage-fixed saturation recovery can be tested | `fig_saturation_recovery.png` | ML wins artificial clip recovery; natural saturation still needs transfer proof |
| 19 | Pretrigger samples | Validate pedestal estimators | A positivity constraint can pass by construction; independent pretrigger prediction tests bias | `fig_heldout_residual_distributions.png` | Adaptive lowering is a pathology diagnostic until zero-signal truth exists |
| 20 | GEANT4 truth tree | Compare energy models against simulation prior | HRD data alone lacks deposited-energy and particle-ID truth | `sim_vs_data.png`, `deltae_e_truth_bands.png` | GEANT4 Birks lookup is the current truth-anchored energy winner |

## Why Each Major Conclusion Follows

### Selection

The selected-pulse count is accepted because every operation is deterministic:
choose physical B channels, compute a median pedestal, compute a maximum
baseline-subtracted amplitude, and apply `A > 1000 ADC`. There is no fitted
parameter and no statistical sampling step in the definition. Therefore the
correct uncertainty on the count is not a binomial interval; the relevant
uncertainty is provenance and implementation reproducibility. S00 closes that
gate by reproducing 640,737 selected B-stave pulse records.

### Timing

The timing conclusion is conditional. A first ML residual model beat a weak
template baseline, but a stronger analytic amplitude-timewalk comparator closed
most of that advantage. The accepted logic is therefore:

1. Leading-edge timing depends on amplitude.
2. A transparent amplitude correction explains most observed improvement.
3. Small ML residual gains are not enough to displace the analytic method unless
   they survive run-held-out comparisons with a larger margin and calibrated
   failure behavior.

This is why the report says timing is mostly analytic timewalk, not that ML is
useless.

### Pile-up Rate

The pile-up rate is not just a classifier problem. It is an occupancy problem:
`R_max = mu_max / tau_eff`. The old headline used `tau_eff = 90 ns`, so it was
always conditional on that assumption. The measured waveform live-time is longer,
about 124.8 ns at the 10-percent threshold, so the same `mu_max` implies a lower
rate. The classifier and CWoLa studies are still useful, but they diagnose
current-dependent waveform structure; they do not replace the transparent
Poisson/live-time calculation.

### ML Wins

ML is accepted where the target is independent of the input definition and the
traditional comparator is genuinely weaker. Duplicate readout and artificial
saturation are examples: the target is not simply `max(sample) > threshold`, and
shape information can recover missing calibration structure. ML is rejected or
kept diagnostic where the label is self-defined, where leakage risk is high, or
where a physics model already captures the dominant structure.

### Energy and PID

The HRD waveform data do not contain event-level particle identity or deposited
energy truth. A charge/depth pattern can suggest a proton- or deuteron-enriched
sample, but it cannot prove event-level PID by itself. GEANT4 is therefore the
truth bridge. The current truth-anchored panel shows that the GEANT4 Birks lookup
beats the learned regressors on the held-out energy benchmark, so the correct
conclusion is not "use a neural energy model"; it is "use simulation truth to
anchor energy and use ML only where it adds validated residual information."

## Reviewer Questions and Direct Answers

| Question | Direct answer |
|---|---|
| Why not train ML for the `A > 1000` gate? | Because the label is exactly the threshold; ML can only approximate a known deterministic rule. |
| Why not quote the old 4.22 MHz rate? | It is still reproducible, but it assumes 90 ns live-time. Measured live-time gives the preferred 3.05 MHz estimate for the same criterion. |
| Why exclude or downweight B2 for precision timing? | B2-containing residuals are tens of ns wide in Sample I and topology dominated; downstream B4/B6/B8 residuals are the stable same-particle reference. |
| Why use sigma68? | It is robust to tails. Gaussian core sigma is useful but incomplete, and full RMS can be dominated by topology tails. |
| Why are duplicate-readout ML wins not energy wins? | Duplicate readout is an electronics closure target. It validates recoverable shape information but does not supply absolute deposited-energy truth. |
| Why does GEANT4 matter? | It supplies particle and deposited-energy labels absent from real HRD waveform data. |
| Why keep traditional methods when ML sometimes wins? | The accepted method is task-specific. Transparent models remain preferred when they match or beat ML under the same split and metric. |
| What still blocks final physics claims? | Event-aligned GEANT4/HRD truth, real pile-up labels, zero-signal pedestal validation, and transfer of ML closures across run/current/topology domains. |

## Audit Checklist for Future Changes

Before changing a headline number, update all of the following:

1. The source study or report path that produced the number.
2. The Markdown summary that quotes it.
3. The LaTeX chapter that uses it.
4. The figure or table that visualizes it.
5. The validation command that proves the figure path and manuscript still build.
6. The caveat section if the interpretation boundary changed.

This checklist prevents a future edit from updating a table while leaving the
reader-facing logic stale.
