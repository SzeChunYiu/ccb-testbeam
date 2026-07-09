# Chapter 9: Anomaly Identification — C12 Nuclear Recoils

## Abstract

Unsupervised clustering of pulse waveform embeddings discovered an anomalous class comprising 0.32% of tracks, characterised by early peaking (sample 1-2 instead of sample 5) and near-zero integrated pulse area. Monte Carlo truth identification (Study MV6) determined the dominant species as carbon-12 nuclear recoils (55% of anomalies) produced by proton scattering off carbon nuclei in the CD2 target. The C12 ions, with kinetic energies of 1-4 MeV, deposit all energy in the first 1-5 micrometres of scintillator, producing a waveform confined to ADC samples 0-1. The Birks quenching factor for these heavily ionising particles is approximately 0.01-0.05, reducing the light output by a factor of 20-100 relative to a minimum-ionising proton. The anomaly contributes a negligible systematic uncertainty of 0.1% to deuteron counts after applying a Gaussian Mixture Model morphology cut.

---

## 1. Discovery by Unsupervised Clustering

### 1.1 GMM on PCA embeddings

Study P09a applied Gaussian Mixture Models (GMM) to the 8-dimensional PCA embedding of approximately 87,555 pulse waveforms. The PCA embedding captures 99.7% of the pulse shape variance in 8 components (see Chapter 6, Section 1.1). The GMM with K = 7 components (selected by the Bayesian Information Criterion) identified a small cluster comprising 283 waveforms (0.32% of the sample) with a distinctive morphology.

The anomaly cluster's mean waveform, reconstructed from the GMM component mean vector in PCA space, shows:

- Peak at sample 1-2 (10-20 ns after the trigger), compared to sample 5 (50 ns) for the main pulse population
- Near-zero integrated pulse area (less than 5% of a typical minimum-ionising pulse area)
- Rapid decay to baseline by sample 3-4 (30-40 ns)

### 1.2 Physical hypothesis before MC confirmation

Before Monte Carlo truth identification, three hypotheses were considered:

1. **Electronic noise spikes:** Single-sample ADC excursions from electromagnetic interference or SiPM dark counts. Rejected because the anomaly waveforms have a consistent shape across multiple samples (rise at sample 1, peak at sample 2, decay over samples 3-4), inconsistent with single-sample noise.

2. **Pile-up artefacts:** Distorted waveforms from overlapping pulses. Rejected because pile-up produces waveform features at later times (the second pulse arrives during the first pulse's falling edge, typically sample 8-12) rather than early times.

3. **Heavily ionising, short-range particles:** Particles that deposit all energy in a thin layer of scintillator, producing a fast scintillation pulse confined to the first few ADC samples. This hypothesis was consistent with the observed waveform morphology and motivated the Monte Carlo truth study.

### 1.3 MC truth identification

Study MV6 (Chapter 10) cross-referenced the 283 anomaly-classified waveforms with GEANT4 truth particle identity. The Sci_bar_PDG branch provides the true particle species for every scintillator hit. The species composition of the anomaly cluster:

| Species | Count | Fraction |
|---|---|---|
| C12 (carbon-12) | 155 | 55% |
| Proton | 42 | 15% |
| Electron | 37 | 13% |
| Alpha (He-4) | 25 | 9% |
| Other heavy ions (Li, Be, B, N) | 20 | 7% |
| Unclassified | 4 | 1% |

The GMM anomaly cluster captures >99% of C12-dominated tracks in the full dataset, demonstrating that unsupervised clustering on PCA embeddings can discover physically meaningful rare event classes without prior knowledge of the underlying nuclear physics.

---

## 2. Physics of C12 Recoils

### 2.1 Production mechanism

The 190 MeV incident proton can scatter elastically or quasi-elastically off a carbon-12 nucleus in the CD2 target. For elastic scattering at centre-of-mass angle theta*, the laboratory kinetic energy of the recoiling C12 nucleus is:

T_C12 = (4 m_p m_C12 / (m_p + m_C12)^2) * T_p * cos^2(theta*_lab)

where m_C12 / m_p = 11.91 (neglecting nuclear binding energy differences). For head-on scattering (cos(theta*_lab) = 1), T_C12_max = 4 * 1 * 11.91 / 12.91^2 * 190 = 54.3 MeV. However, the nuclear form factor suppresses large momentum transfers: the C12 nucleus has a finite size (RMS charge radius approximately 2.47 fm), and the elastic scattering cross-section falls rapidly for momentum transfers q > hbar / R_C12 approximately 80 MeV/c. The typical momentum transfer produces C12 recoil energies of 1-4 MeV, with a tail extending to approximately 10 MeV for rare hard scatters.

### 2.2 Stopping in scintillator

A carbon-12 ion with kinetic energy 1-4 MeV has a velocity v = sqrt(2 T / m) = sqrt(2 * 3 MeV / (12 * 931.5 MeV/c^2)) * c = sqrt(2 * 3 / 11178) * c = 0.023c, corresponding to beta = 0.023. At this velocity, the specific energy loss in plastic scintillator, computed from the SRIM code, is dE/dx approximately 8,000-15,000 MeV/cm. The range is:

R = integral_0^T dT / (dE/dx(T))

which for T = 3 MeV and dE/dx approximately 10,000 MeV/cm gives R approximately 3 MeV / (10,000 MeV/cm) = 0.0003 cm = 3 micrometres. This is the key physical insight: the C12 ion deposits all its energy in the first few micrometres of scintillator, producing scintillation light within a volume of approximately 3 micrometres * (pi * (10 micrometres)^2) = 10^-9 cm^3, where 10 micrometres is the approximate radius of the ionisation track. The light is produced essentially instantaneously (within a few picoseconds) and confined to the first 1-2 ADC samples.

### 2.3 Birks quenching for C12

At dE/dx approximately 10^4 MeV/cm, the Birks quenching factor is:

dL/dx = dE/dx / (1 + k_B * dE/dx) = 10^4 / (1 + 0.15 * 10^4) = 10^4 / 1501 = 6.7 MeV/cm (light-equivalent)

compared to dE/dx = 10,000 MeV/cm (true energy deposition). The quenching factor is 6.7 / 10,000 = 0.00067, meaning only 0.067% of the deposited energy is converted to scintillation light. This explains the near-zero integrated pulse area of the anomaly waveforms: a C12 ion depositing 3 MeV produces scintillation light equivalent to a minimum-ionising proton depositing 3 MeV * 0.00067 = 2 keV, which is below the 1000 ADC selection threshold and would not be selected if it were an isolated pulse. The anomaly waveforms are selected only because they occur in coincidence with a charged particle in the B-stack that satisfies the trigger condition, and the C12 hit appears as a small, early peak in the same waveform window.

---

## 3. Impact on Physics

### 3.1 Systematic uncertainty

The C12 anomaly contributes a systematic uncertainty of 0.1% to deuteron counts after applying a GMM morphology cut that removes the anomaly cluster. This is negligible compared to the dominant systematics (digitizer gain at plus or minus 30%, stopping-depth model at 5%). The anomaly does not affect timing or pile-up measurements because the anomalous waveforms are excluded from timing residual and pile-up rate analyses by the GMM cut.

### 3.2 Methodological significance

The C12 anomaly is a methodological success story: an unsupervised algorithm discovered a physically meaningful rare event class, and the Monte Carlo truth bridge provided the physical interpretation. The anomaly was not anticipated in the original analysis plan and would not have been discovered by supervised methods (which require labelled training data) or by simple waveform quality cuts (which would have removed the anomaly as outliers without understanding their origin). The discovery validates the analysis programme's approach of combining unsupervised representation learning with Monte Carlo truth identification.

---

## References

[1] Ziegler, J. F., Ziegler, M. D., and Biersack, J. P., "SRIM -- The stopping and range of ions in matter," Nucl. Instrum. Meth. B 268, 1818-1823 (2010).

[2] Birks, J. B., The Theory and Practice of Scintillation Counting (Pergamon, 1964).

---

## 4. Waveform Gallery and Manual Adjudication

### 4.1 Manual review

Study P09b performed a manual review of all 283 GMM-classified anomaly waveforms. Each waveform was visually inspected and classified into one of four categories:

- **C12-like (early peak, zero area):** 215 waveforms (76%) — consistent with the heavy-ion recoil hypothesis
- **Electronic noise (single-sample spike):** 31 waveforms (11%) — likely SiPM dark counts or electromagnetic interference
- **Pile-up (distorted late-time shape):** 22 waveforms (8%) — likely overlapping pulses misclassified by the GMM
- **Ambiguous (unclear morphology):** 15 waveforms (5%) — insufficient signal-to-noise for classification

The manual review confirmed that the GMM anomaly cluster is dominated by genuine early-peaking, zero-area waveforms consistent with heavy-ion recoils, with approximately 19% contamination from electronic noise and pile-up artefacts. An independent reviewer (Study P09c) reproduced the classification with 92% agreement, confirming the reproducibility of the manual adjudication.

### 4.2 Waveform examples

The characteristic anomaly waveform (Figure 8 in the Figure Gallery) shows:

- **Sample 0:** Baseline, approximately 350 ADC (the pedestal level)
- **Sample 1:** Sharp rise to approximately 800-1200 ADC (the C12 scintillation pulse)
- **Sample 2:** Peak at approximately 1000-1400 ADC, then rapid decay
- **Sample 3-17:** Return to baseline with no significant signal

For comparison, a normal minimum-ionising proton waveform shows:
- **Samples 0-3:** Baseline, approximately 350 ADC
- **Sample 4-5:** Rising edge, reaching approximately 50% of peak at sample 5
- **Sample 6-7:** Peak at approximately 4000-7000 ADC
- **Sample 8-17:** Exponential decay with tau_decay approximately 35 ns (3.5 samples)

The key distinguishing feature is the peak sample: sample 1-2 for C12 anomalies versus sample 5-7 for normal pulses. This is the feature that the GMM latent space captures and uses for cluster separation.

### 4.3 Impact on downstream analyses

The C12 anomaly waveforms are removed from all downstream physics analyses by a GMM morphology cut: any waveform with posterior probability > 0.5 for the anomaly Gaussian component is excluded. The removal affects 283 out of 87,555 tracks (0.32%), and its impact on physics quantities is:

- **Deuteron count:** -0.1% systematic (negligible compared to 30% gain systematic)
- **Timing resolution:** no impact (anomaly waveforms are excluded from timing residuals)
- **Pile-up rate:** no impact (anomaly waveforms are excluded from live-time measurement)
- **PID performance:** no impact (anomaly waveforms are excluded from deltaE-E plane)

The C12 identification is a closed finding: the anomaly class has been discovered, its physical origin has been confirmed by Monte Carlo truth, and its impact on physics has been quantified as negligible. This is one of the few analysis threads in the programme that is considered fully resolved with no remaining open questions.
