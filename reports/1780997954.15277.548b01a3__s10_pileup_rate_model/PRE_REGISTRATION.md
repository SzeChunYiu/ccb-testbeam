# S10 pre-registration

- **Ticket:** `1780997954.15277.548b01a3`
- **Worker:** `testbeam-laptop-5`
- **Date:** 2026-06-09
- **Committed before S10 result inspection:** yes; created before computing run-46/run-47 S10 metrics.

## Inputs and fixed cuts

- Raw B-stack ROOT only.
- Initial intended current comparison was run 46 vs run 47, but `docs/01_setup_and_detector.md`
  states both are 2 nA low-current reference runs. The fixed comparison is therefore runs
  46+47 at 2 nA against the surrounding Sample-I analysis 20 nA runs
  44,45,48,49,50,51,52,53,54,55,56,57. This correction was made because the documentation
  contradicted the initial assumption and the documented fractions reproduce only with this
  grouping and a selected-event denominator.
- B staves are even physical channels: B2=0, B4=2, B6=4, B8=6.
- Pulse amplitude is `max(HRDv - median(samples 0..3))`.
- Selected pulse cut is fixed at `A > 1000 ADC`, matching S00.
- Low-current group is runs 46+47; high-current group is Sample-I analysis runs excluding 46+47.
- Event topology fractions are measured per event: multi-stave means at least two selected B staves; downstream means any selected B4/B6/B8; three-stave means at least three selected B staves.
- The documented current topology fractions use the denominator of events with at least one
  selected B pulse, not all triggers.

## Primary metrics

1. Reproduce the documented run-46/run-47 current topology fractions:
   multi-stave 1.56% vs 2.68%, three-stave 0.41% vs 0.85%, downstream 2.31% vs 3.34%.
2. Reproduce the Poisson occupancy model `R_max = mu_max / tau_eff` for the Table-47 thresholds, especially the combined `mu_max=0.380`, `tau_eff=90 ns`, `R_max ~= 4.22 MHz`.
3. Test the `tau_eff=90 ns` assumption with a fixed waveform handle: mean contiguous above-threshold width of selected raw pulses, using a per-pulse threshold of 10% and 20% of amplitude after baseline subtraction.
4. Isolate genuine current-dependent excess with the pre-registered estimator `excess_fraction_high = (f_high - f_low) / f_high` for event topology rates and for the ML pile-up score mean.
5. Head-to-head benchmark on injected pile-up labels: traditional scalar score = late-fraction plus width; ML score = calibrated logistic regression using waveform shape features only. The low-current group trains the fixed ML score; the high-current group is scored as transfer data. The comparison metric is AUC/AP on injected labels and high/low score ratio on real pulses.

## Falsification

- The occupancy reproduction fails if the combined `R_max` differs from 4.22 MHz by more than 0.02 MHz when using `mu_max=0.380` and `tau_eff=90 ns`.
- The current-excess claim fails if the bootstrap 95% CI for `f_high - f_low` includes zero for the downstream topology fraction.
- The ML scaling claim is treated as non-definitive if calibrated ML probabilities are not stable under run-transfer bootstrap or if they are driven by selected-stave multiplicity rather than waveform shape.
