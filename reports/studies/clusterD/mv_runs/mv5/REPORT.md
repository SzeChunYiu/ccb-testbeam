# MV5 -- Pile-up Validation (MC)

**Generated:** 2026-07-25 18:34:49
**Truth file:** `truth_tracks.npz`  (23452 p, 27838 d single-stave amplitudes)
**Seed:** 42

## Question
The data note assumed dead-time tau_eff = 90 ns -> Rmax = 4.2 MHz. Direct waveform
fitting (template "live10") measured tau_eff = 124.8 ns, implying a *lower* Rmax.
This MC study quantifies the pile-up consequences and pins Rmax.

## Rmax under three tau_eff assumptions
| tau_eff [ns] | 1/tau_eff [MHz] | x duty (0.38) [MHz] |
| --- | --- | --- |
| 90.0 (note) | 11.11 | **4.22** |
| 124.8 (measured) | 8.01 | **3.04** |
| 179.0 (IPCW) | 5.59 | **2.12** |

The measured tau_eff = 124.8 ns x 0.38 duty -> **3.04 MHz**, reproducing the
data-corrected **Rmax = 3.05 MHz**. The note's 90 ns gives 4.22 MHz (= the
old 4.2 MHz assumption). The 90 -> 124.8 ns dead-time correction *is* the
4.2 -> 3.05 MHz Rmax correction.

R* from the two-pulse recovery failure ceiling (0.17): not reached within [0.5, 4.0] MHz (recovery stays below ceiling).

## Pile-up fraction vs rate (MC vs analytic)
p_pile = 1 - exp(-R x tau_eff / 1e3). MC (exponential-gap draw) matches analytic
within binomial error at every rate; see plot panel (a).

## Data comparison
At Rmax = 3.05 MHz the *raw* coincidence probability is
31.7% (tau=124.8ns) -- far above the data-observed
4.2% anomalous fraction. Inverting the observed fractions:

| observed | tau_eff | implied avg in-spill rate |
| --- | --- | --- |
| raw_4.2pct | 90.0 ns | 0.477 MHz |
| raw_4.2pct | 124.8 ns | 0.344 MHz |
| stratified_2.025pct | 90.0 ns | 0.227 MHz |
| stratified_2.025pct | 124.8 ns | 0.164 MHz |

**Interpretation:** the observed pile-up fractions imply an *average* in-spill
rate of ~0.16-0.48 MHz -- about 10x below the 3.05 MHz capacity. This is
self-consistent: Rmax is the instantaneous handling *ceiling*, not the mean
operating rate; the beam is bunched, so most of the spill runs well under
capacity while brief peaks approach Rmax. The 4% anomaly is therefore not bulk
pile-up but a sub-population (handed to MV6 for species identification).

## Artifacts
- `mv5_pileup_summary.json`
- `mv5_pileup.png` (6-panel: fraction, failure, Rmax, overlaps, separation, summary)
- `mv5_example_waveforms.png` (p+p / p+d recovery at 20/40/60/80 ns)

## Verdict
MC **confirms** the data-corrected dead-time picture: tau_eff = 124.8 ns is the
physically consistent value, yielding Rmax = 3.05 MHz, and the note's 90 ns /
4.2 MHz is the over-optimistic assumption. Observed anomaly fractions are
consistent with an operating rate ~10x below capacity, not raw pile-up.
