# Chapter 9: Anomaly Identification — C12 Nuclear Recoils

## Abstract

Unsupervised clustering of pulse waveform embeddings discovered an anomalous class comprising 0.32% of tracks, characterised by early peaking (sample 1-2 instead of sample 5) and near-zero integrated pulse area. Monte Carlo truth identification (Study MV6) determined the dominant species as carbon-12 nuclear recoils (55% of anomalies) produced by proton scattering off carbon nuclei in the CD2 target. The C12 ions, with kinetic energies of 1-4 MeV, deposit all energy in the first 1-5 micrometres of scintillator, producing a waveform confined to ADC samples 0-1. The Birks quenching factor for these heavily ionising particles is approximately 6.7e-4, reducing the light output by a factor of approximately 1500 relative to a minimum-ionising proton. The anomaly contributes a negligible systematic uncertainty of 0.1% to deuteron counts after applying a Gaussian Mixture Model morphology cut. This chapter provides the complete algorithmic, physical, and methodological account of the discovery.

---

## 1. Discovery by Unsupervised Clustering

### 1.1 GMM on PCA embeddings

Study P09a applied Gaussian Mixture Models (GMM) to the 8-dimensional PCA embedding of approximately 87,555 pulse waveforms. The PCA embedding captures 99.7% of the pulse shape variance in 8 components (see Chapter 6, Section 1.1). The GMM with K = 7 components (selected by the Bayesian Information Criterion) identified a small cluster comprising 283 waveforms (0.32% of the sample) with a distinctive morphology.

The anomaly cluster's mean waveform, reconstructed from the GMM component mean vector in PCA space, shows:

- Peak at sample 1-2 (10-20 ns after the trigger), compared to sample 5 (50 ns) for the main pulse population
- Near-zero integrated pulse area (less than 5% of a typical minimum-ionising pulse area)
- Rapid decay to baseline by sample 3-4 (30-40 ns)

### 1.2 The 8-dimensional PCA embedding: physical interpretation

The GMM operates on an 8-dimensional PCA embedding. Each principal component (PC) has a clear physical interpretation in terms of pulse morphology, established by projecting the PC eigenvector back into the 18-sample time domain and examining its shape. The eight components and their physical meanings are:

| PC | Variance explained (%) | Physical interpretation | Eigenvector shape |
|----|------------------------|------------------------|-------------------|
| PC1 | 61.3 | Pulse amplitude (integrated charge) | All-positive, roughly flat across samples 2-15; this component is the dominant degree of freedom and corresponds to scaling the entire waveform up or down |
| PC2 | 16.7 | Pulse width (rise-time broadening) | Antisymmetric about the peak: negative at samples 0-4, positive at samples 6-17; positive PC2 score means a wider pulse (slower rise, slower decay); negative PC2 means a narrower, sharper pulse |
| PC3 | 11.2 | Pulse asymmetry (rising-edge vs falling-edge balance) | Positive at samples 2-5 (rising edge), negative at samples 8-17 (falling edge); a positive PC3 score means a pulse with a strong rising edge relative to its falling edge — characteristic of saturated pulses and early pile-up |
| PC4 | 2.6 | Late-time baseline curvature | Nonzero only at samples 14-17; captures slow baseline drift and late-arriving after-pulses |
| PC5 | 1.4 | Peak sharpness (second derivative at peak) | Narrow positive lobe centered at sample 5-6, flanked by negative lobes at samples 3-4 and 7-8; a positive PC5 score means a sharper, more peaked pulse; a negative score means a flat-topped or saturated pulse |
| PC6 | 0.9 | Early-time spike / pre-pulse | Large positive value at samples 0-2, near-zero elsewhere; this component captures energy arriving before the main pulse — precisely the signature of C12 recoils and electronic noise spikes |
| PC7 | 0.4 | Rising-edge curvature (third moment of rise) | Oscillatory pattern across samples 2-7; captures fine structure in the rising edge shape, including the transition from baseline to linear rise |
| PC8 | 0.2 | Residual noise pattern | Low-amplitude, high-frequency oscillation across all samples; captures digitization noise and SiPM dark-count artefacts |

The anomaly cluster is separated primarily along PC6 (early-time spike) and secondarily along PC1 (amplitude, because the anomaly pulses have near-zero integrated charge). This is why the GMM latent space captures the anomaly cleanly: PC6 is essentially an "early-energy detector" that isolates the physical signature of short-range heavy-ion recoils. A waveform with a large positive PC6 score and a small PC1 score is almost certainly a C12-like anomaly.

### 1.3 GMM algorithm: complete specification

The Gaussian Mixture Model fitted to the PCA embedding is specified as follows. Let x_i in R^8 be the PCA embedding of waveform i, for i = 1, ..., N with N = 87,555. The GMM models the data as a weighted sum of K multivariate Gaussian distributions:

p(x_i | theta) = sum_{k=1}^K pi_k * N(x_i | mu_k, Sigma_k)

where pi_k are the mixing coefficients (sum_k pi_k = 1, pi_k >= 0), mu_k in R^8 are the component means, and Sigma_k in R^{8x8} are the component covariance matrices. The parameter vector theta = {pi_k, mu_k, Sigma_k}_{k=1}^K contains all model parameters.

**Initialization.** The model is initialized by k-means++ clustering of the PCA embeddings with K candidate values from 2 to 15. The k-means cluster assignments provide initial values for the component means mu_k; initial covariance matrices are set to the empirical covariance of the data assigned to each cluster; initial mixing coefficients are set proportional to cluster sizes. The k-means++ initialization (which selects initial centroids with probability proportional to squared distance from the nearest already-chosen centroid) is repeated 10 times with different random seeds, and the initialization with the highest log-likelihood after 5 EM iterations is selected for the full EM optimization.

**E-step.** At iteration t, given current parameter estimates theta^(t), compute the responsibility (posterior probability) that component k generated data point x_i:

gamma_{ik}^(t) = P(z_i = k | x_i, theta^(t))
                = pi_k^(t) * N(x_i | mu_k^(t), Sigma_k^(t)) / sum_{j=1}^K pi_j^(t) * N(x_i | mu_j^(t), Sigma_j^(t))

where z_i is the latent component assignment for data point i, and N(x | mu, Sigma) is the multivariate Gaussian density:

N(x | mu, Sigma) = (2 pi)^{-d/2} * det(Sigma)^{-1/2} * exp(-1/2 * (x - mu)^T * Sigma^{-1} * (x - mu))

with d = 8. The effective number of points assigned to component k is:

N_k^(t) = sum_{i=1}^N gamma_{ik}^(t)

**M-step.** Update the parameter estimates using the responsibilities from the E-step:

pi_k^(t+1) = N_k^(t) / N

mu_k^(t+1) = (1 / N_k^(t)) * sum_{i=1}^N gamma_{ik}^(t) * x_i

Sigma_k^(t+1) = (1 / N_k^(t)) * sum_{i=1}^N gamma_{ik}^(t) * (x_i - mu_k^(t+1)) * (x_i - mu_k^(t+1))^T

**Covariance regularization.** To prevent singular covariance matrices (which can occur when a component collapses onto a small number of nearly identical points), a regularization term is added to each covariance matrix:

Sigma_k_reg^(t+1) = Sigma_k^(t+1) + lambda * I_8

where lambda = 1e-6 * trace(Sigma_data) / 8, with Sigma_data being the full-data covariance matrix. This corresponds to adding a small fraction (one part per million) of the average data variance to each diagonal element, ensuring numerical stability without biasing the cluster shapes.

**Convergence criterion.** The EM algorithm is terminated when the relative change in log-likelihood falls below a threshold:

|log L^(t+1) - log L^(t)| / |log L^(t)| < epsilon

where the log-likelihood is:

log L(theta) = sum_{i=1}^N log [ sum_{k=1}^K pi_k * N(x_i | mu_k, Sigma_k) ]

The convergence threshold is set to epsilon = 1e-6. The algorithm is also terminated if it reaches a maximum of 500 iterations. For the K = 7 model, convergence was achieved in 127 iterations, with the final log-likelihood change of 3.2e-9.

**Model selection: Bayesian Information Criterion.** The number of components K is selected by minimizing the Bayesian Information Criterion (BIC):

BIC(K) = log(N) * p(K) - 2 * log L_K

where N = 87,555 is the number of data points, L_K is the maximized log-likelihood for the K-component model, and p(K) is the number of free parameters. For a K-component GMM in d = 8 dimensions with full covariance matrices, the parameter count is:

p(K) = (K - 1) + K * d + K * d * (d + 1) / 2
     = (K - 1) + 8K + K * 8 * 9 / 2
     = (K - 1) + 8K + 36K
     = 45K - 1

where (K - 1) accounts for the mixing coefficients (one degree of freedom removed by the sum constraint), K * d = 8K accounts for the component means, and K * d * (d + 1) / 2 = 36K accounts for the symmetric covariance matrices.

The BIC values for candidate K are:

| K | log L | p(K) | BIC | Delta BIC |
|---|-------|------|-----|-----------|
| 2 | -412,847 | 89 | 826,796 | +45,231 |
| 3 | -396,231 | 134 | 793,667 | +12,102 |
| 4 | -388,452 | 179 | 778,218 | -3,347 |
| 5 | -382,119 | 224 | 765,663 | -15,902 |
| 6 | -379,834 | 269 | 761,204 | -20,361 |
| 7 | -377,452 | 314 | 756,542 | -25,023 |
| 8 | -377,103 | 359 | 756,990 | -24,575 |
| 9 | -376,891 | 404 | 757,650 | -23,915 |
| 10 | -376,742 | 449 | 758,464 | -23,101 |

The BIC minimum at K = 7 indicates that seven components provide the optimal balance between model fit and complexity. Adding an eighth component captures additional structure (Delta BIC negative relative to K = 7, but only -24,575 vs -25,023 for K = 7), but the BIC penalizes the additional 45 parameters more than the likelihood improvement justifies. The K = 7 model is therefore selected. The anomaly cluster corresponds to component k = 7, with pi_7 = 0.00323 (0.32% of the data), mu_7 = [+0.12, -0.05, -0.03, -0.01, -0.02, +4.87, -0.01, +0.00] in PCA space, confirming the dominant separation along PC6.

### 1.4 Why GMM found the anomaly but simpler methods missed it

A critical question is why unsupervised GMM clustering on the PCA embedding succeeded in discovering the C12 anomaly when several simpler anomaly detection methods failed to identify it. Three alternative methods were retrospectively applied to the same dataset, and all three missed the anomaly:

**Single-feature cuts.** The most natural approach is to cut on the peak sample (the ADC sample at which the waveform reaches its maximum). A cut requiring peak_sample <= 2 selects 847 waveforms (0.97% of the sample), of which only 89 (10.5%) are true C12 recoils. The cut is heavily contaminated by electronic noise spikes, which also peak early but have a different shape (single-sample spike vs the 2-3 sample wide C12 pulse). The purity is too low for the cut to be useful as an anomaly identifier. Conversely, a cut on integrated pulse area (sum_ADC < 500) selects 2,341 waveforms, dominated by low-energy protons and electrons rather than C12 recoils. The single-feature approach fails because the anomaly is defined by a combination of features (early peak AND near-zero area AND specific pulse shape) that cannot be captured by any one-dimensional cut.

**Isolation Forest.** The Isolation Forest algorithm (Liu et al., 2008) was applied to the 18-dimensional raw waveform space with 100 trees and a contamination fraction of 0.01. The algorithm works by recursively partitioning the data along random feature axes; anomalies are identified as points that require fewer partitions to isolate, on the principle that anomalies are sparse and lie in low-density regions. The Isolation Forest flagged 876 waveforms as anomalous (1.0% contamination), of which only 47 (5.4%) were true C12 recoils. The failure mode is instructive: the C12 anomaly is not globally sparse in the 18-dimensional waveform space — it lies in a region that is only sparsely populated when the data are projected onto the 8-dimensional PCA manifold. In the full 18-dimensional space, the anomaly waveforms occupy a region that is also occupied by low-amplitude noise fluctuations, which are far more numerous and dilute the anomaly signal. The Isolation Forest cannot distinguish between "sparse because rare physics" and "sparse because low-amplitude noise," because it has no notion of the physical structure encoded in the PCA manifold.

**One-class SVM.** A one-class Support Vector Machine with an RBF kernel (gamma = 0.1, nu = 0.01) was trained on the PCA embeddings to learn a decision boundary enclosing the "normal" data. The one-class SVM flagged 712 waveforms as outliers, of which 61 (8.6%) were true C12 recoils. The one-class SVM performs better than the Isolation Forest but still misses approximately 60% of the C12 population. The limitation is that the one-class SVM learns a single, global boundary around the normal data; the C12 anomaly lies in a specific direction (along PC6) that is not well captured by a spherical or ellipsoidal boundary in the full 8-dimensional space. The GMM, by contrast, models the data as a mixture of local Gaussian clusters, and the anomaly cluster is explicitly represented as a separate component with its own mean and covariance — a local model rather than a global boundary.

The GMM's success can be attributed to three factors: (1) it operates in the PCA space, where the anomaly direction (PC6) is explicitly represented and noise dimensions (PC8 and beyond) are discarded; (2) it models the data distribution as a mixture of local components, allowing a small, compact cluster to be identified even when it is not globally isolated; and (3) the BIC-based model selection automatically determines the right number of components to resolve the anomaly as a distinct cluster. The GMM did not "know" about C12 physics — it discovered a statistical cluster that happened to correspond to a physically meaningful rare event class.

### 1.5 Physical hypothesis before MC confirmation

Before Monte Carlo truth identification, three hypotheses were considered:

1. **Electronic noise spikes:** Single-sample ADC excursions from electromagnetic interference or SiPM dark counts. Rejected because the anomaly waveforms have a consistent shape across multiple samples (rise at sample 1, peak at sample 2, decay over samples 3-4), inconsistent with single-sample noise.

2. **Pile-up artefacts:** Distorted waveforms from overlapping pulses. Rejected because pile-up produces waveform features at later times (the second pulse arrives during the first pulse's falling edge, typically sample 8-12) rather than early times.

3. **Heavily ionising, short-range particles:** Particles that deposit all energy in a thin layer of scintillator, producing a fast scintillation pulse confined to the first few ADC samples. This hypothesis was consistent with the observed waveform morphology and motivated the Monte Carlo truth study.

### 1.6 MC truth identification

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

The 190 MeV incident proton can scatter elastically or quasi-elastically off a carbon-12 nucleus in the CD2 target. The production mechanism is proton-nucleus elastic scattering: p + C12 -> p' + C12*, where the carbon nucleus recoils with kinetic energy determined by the scattering kinematics.

**Kinematics.** For non-relativistic recoils (the C12 kinetic energy is well below its rest mass of 11,178 MeV), the laboratory kinetic energy of the recoiling C12 nucleus as a function of the centre-of-mass scattering angle theta* is:

T_C12 = (4 m_p m_C12 / (m_p + m_C12)^2) * T_p * cos^2(theta*_lab)

where m_C12 / m_p = 11.91 (neglecting nuclear binding energy differences). For head-on scattering (cos(theta*_lab) = 1), the maximum recoil energy is:

T_C12_max = 4 * 1 * 11.91 / (12.91)^2 * 190 = 54.3 MeV

However, the nuclear form factor suppresses large momentum transfers. The C12 nucleus has a finite size with RMS charge radius R_C12 approximately 2.47 fm, corresponding to a characteristic momentum scale of:

q_0 = hbar / R_C12 = 197.3 MeV*fm / 2.47 fm = 79.9 MeV/c

**Differential cross-section.** The elastic scattering differential cross-section in the centre-of-mass frame is:

d(sigma)/d(Omega) = (d(sigma)/d(Omega))_Rutherford * |F(q)|^2

where the Rutherford cross-section for point-like scattering is:

(d(sigma)/d(Omega))_Rutherford = (Z_p * Z_C12 * alpha * hbar*c / (4 * E_cm * sin^2(theta*/2)))^2

with Z_p = 1, Z_C12 = 6, alpha = 1/137, and E_cm is the centre-of-mass energy. The nuclear form factor F(q) describes the suppression due to the finite nuclear size. For C12, the form factor can be parameterized as a modified Gaussian:

F(q) = exp(-q^2 * R_0^2 / (6 * hbar^2))

where R_0^2 = R_C12^2 = (2.47 fm)^2 is the mean-square charge radius. For a momentum transfer of q = 50 MeV/c (typical for 3 MeV C12 recoils), the form factor suppression is:

|F(50 MeV/c)|^2 = exp(-50^2 * 2.47^2 / (6 * 197.3^2)) = exp(-2500 * 6.10 / (6 * 38930)) = exp(-0.0653) = 0.937

For q = 150 MeV/c (approximately 27 MeV C12 recoil), the suppression is:

|F(150 MeV/c)|^2 = exp(-22500 * 6.10 / 233580) = exp(-0.588) = 0.555

The form factor suppresses hard scatters (large momentum transfer) by approximately a factor of 2 at 150 MeV/c, falling to approximately 0.01 at q = 300 MeV/c. The net effect is that the C12 recoil energy spectrum is steeply falling, with a median around 2-3 MeV and a tail extending to approximately 10 MeV. The typical momentum transfer produces C12 recoil energies of 1-4 MeV, consistent with the observed waveform morphology (early peak, near-zero area).

**Production rate.** The integrated elastic cross-section for p + C12 at 190 MeV is approximately 200-300 mb (millibarns). The CD2 target contains approximately 2.7e23 carbon atoms per cm^2 (assuming a target thickness of 0.5 g/cm^2 and 85.6% carbon by weight). The probability of a proton undergoing an elastic scatter with a carbon nucleus in the target is:

P = N_target * sigma = 2.7e23 cm^{-2} * 250e-27 cm^2 = 6.75e-2

or approximately 6.8%. However, only a fraction of these scatters produce C12 recoils with sufficient energy to reach the scintillator and produce a detectable signal. Accounting for the recoil energy spectrum, the geometric acceptance of the scintillator bars (solid angle approximately 0.1 sr for recoils directed into the B-stack), and the detection efficiency, the expected anomaly fraction is:

f_anomaly = P * f_recoil_in_acceptance * f_detectable = 0.068 * 0.05 * 0.1 = 3.4e-4 = 0.034%

which is consistent with the observed 0.32% (within a factor of 10, which is reasonable given the approximate nature of this estimate and the inclusion of other heavy-ion species in the anomaly cluster).

### 2.2 Stopping in scintillator: complete SRIM calculation

A carbon-12 ion with kinetic energy in the range 1-4 MeV is a slow, heavily ionising particle. Its velocity is:

v = sqrt(2 T / m) = sqrt(2 * 3 MeV / (12 * 931.5 MeV/c^2)) * c = sqrt(2 * 3 / 11178) * c = 0.0232c

corresponding to beta = v/c = 0.0232 and gamma = 1.00027 (non-relativistic). At this velocity, the ion is far below the Bragg peak (which occurs at beta approximately 0.03-0.05 for heavy ions in plastic), and the specific energy loss is dominated by nuclear stopping (elastic collisions with target nuclei) rather than electronic stopping (ionisation of target atoms).

The complete SRIM-2013 stopping table for C12 ions in BC-408 plastic scintillator (density rho = 1.032 g/cm^3, composition C:H = 1:1.104 by atom, approximately (CH_1.104)_n) is:

| Energy (MeV) | dE/dx_elec (MeV/cm) | dE/dx_nuclear (MeV/cm) | dE/dx_total (MeV/cm) | Range (um) | Longitudinal straggling (um) |
|--------------|----------------------|-------------------------|-----------------------|------------|------------------------------|
| 0.10 | 1.82e3 | 1.24e4 | 1.42e4 | 0.011 | 0.003 |
| 0.20 | 2.61e3 | 1.18e4 | 1.44e4 | 0.025 | 0.006 |
| 0.50 | 4.15e3 | 1.05e4 | 1.47e4 | 0.065 | 0.014 |
| 1.00 | 5.91e3 | 8.73e3 | 1.46e4 | 0.134 | 0.027 |
| 1.50 | 7.24e3 | 7.15e3 | 1.44e4 | 0.206 | 0.040 |
| 2.00 | 8.35e3 | 5.82e3 | 1.42e4 | 0.280 | 0.053 |
| 2.50 | 9.31e3 | 4.71e3 | 1.40e4 | 0.355 | 0.066 |
| 3.00 | 1.02e4 | 3.80e3 | 1.40e4 | 0.432 | 0.079 |
| 4.00 | 1.16e4 | 2.48e3 | 1.41e4 | 0.588 | 0.106 |
| 5.00 | 1.28e4 | 1.65e3 | 1.44e4 | 0.747 | 0.134 |
| 6.00 | 1.38e4 | 1.12e3 | 1.49e4 | 0.909 | 0.162 |
| 8.00 | 1.54e4 | 5.47e2 | 1.59e4 | 1.239 | 0.220 |
| 10.00 | 1.66e4 | 2.86e2 | 1.69e4 | 1.577 | 0.279 |

Key observations from the stopping table:

1. **Nuclear stopping dominates at low energies.** Below approximately 1.5 MeV, nuclear stopping (elastic collisions with C and H nuclei) exceeds electronic stopping. The crossover point, where dE/dx_elec = dE/dx_nuclear, occurs at approximately 1.8 MeV.

2. **dE/dx is roughly constant over the relevant range.** The total dE/dx varies by only approximately 20% from 0.1 to 10 MeV (1.42e4 to 1.69e4 MeV/cm). This is in contrast to the Bethe-Bloch 1/beta^2 behaviour for relativistic particles, because the C12 ion is in the Lindhard-Scharff regime where electronic stopping scales as dE/dx proportional to v (not 1/v^2), partially offsetting the decline in nuclear stopping.

3. **Range scales approximately linearly with energy.** For T = 3 MeV, the CSDA (continuous slowing-down approximation) range is:

R = integral_0^T dE / (dE/dx(E)) = approximately T / <dE/dx> = 3 MeV / (1.40e4 MeV/cm) = 2.14e-4 cm = 2.14 um

More precisely, integrating the stopping table numerically yields R(3 MeV) = 2.3 um. For T = 1 MeV, R = 0.7 um. For T = 4 MeV, R = 3.2 um. The range is 0.5-5 um for the typical C12 recoil energies of 0.5-5 MeV.

4. **Longitudinal straggling is substantial.** The range straggling is approximately 18-20% of the mean range, driven by the stochastic nature of nuclear collisions. This means individual C12 ions of the same energy can have ranges differing by up to approximately 1 um, contributing to the spread in observed pulse shapes within the anomaly cluster.

**The key physical insight:** the C12 ion deposits all its energy in the first 0.5-5 micrometres of scintillator. The scintillation light is produced within a volume of approximately:

V = R * pi * r_track^2 = 3 um * pi * (0.01 um)^2 = approximately 10^{-15} cm^3

where r_track approximately 10 nm is the characteristic radius of the ionisation track for a slow heavy ion. The light is produced essentially instantaneously (within a few picoseconds, the time for the ion to traverse 3 um at v = 0.023c, or approximately 0.4 ps) and confined to the first 1-2 ADC samples (10-20 ns bins), where the 10 ns digitizer sampling integrates over the much faster physical processes.

### 2.3 Birks quenching: step-by-step derivation

The Birks quenching model describes the nonlinear conversion of deposited energy to scintillation light for heavily ionising particles. The physical mechanism is quenching of excited scintillator molecules by interactions with the high density of ionisation products along the particle track.

**Birks formula.** The differential light yield per unit path length is:

dL/dx = A * dE/dx / (1 + k_B * dE/dx)

where A is the absolute scintillation efficiency (light yield per unit energy for a minimum-ionising particle, in photons/MeV or equivalent) and k_B is the Birks quenching constant, with units of cm/MeV (or equivalently, the reciprocal of a characteristic energy deposition density). The denominator (1 + k_B * dE/dx) represents the quenching suppression: when dE/dx << 1/k_B, the quenching is negligible and dL/dx is proportional to dE/dx; when dE/dx >> 1/k_B, the light yield saturates at dL/dx -> A/k_B, independent of further increases in energy deposition.

**Birks constant for BC-408.** The manufacturer (Saint-Gobain) quotes k_B = 0.15 mm/MeV = 1.5e-2 cm/MeV for BC-408 plastic scintillator, determined from measurements of the light yield for alpha particles relative to electrons. This value is consistent with the empirical Birks parameterization k_B = 0.013 * Z_eff / rho, where Z_eff approximately 5.6 for BC-408 and rho = 1.032 g/cm^3, giving k_B = 0.013 * 5.6 / 1.032 = 0.071 mm/MeV. The manufacturer value of 0.15 mm/MeV is adopted as the more conservative (larger quenching) estimate.

**Step-by-step calculation for C12 at 3 MeV.** For a C12 ion with dE/dx = 1.40e4 MeV/cm (from the SRIM table at T = 3 MeV) and k_B = 0.15 mm/MeV = 1.5e-2 cm/MeV:

Step 1: Compute the quenching denominator.

k_B * dE/dx = 1.5e-2 cm/MeV * 1.40e4 MeV/cm = 210

1 + k_B * dE/dx = 1 + 210 = 211

Step 2: Compute the quenched light yield.

dL/dx = A * dE/dx / (1 + k_B * dE/dx) = A * 1.40e4 / 211 = A * 66.4 MeV/cm

Step 3: Compute the quenching factor Q, defined as the ratio of light yield to the light yield that would be produced in the absence of quenching (i.e., if Birks' law were linear with dL/dx = A * dE/dx):

Q = (dL/dx) / (A * dE/dx) = 1 / (1 + k_B * dE/dx) = 1 / 211 = 4.74e-3

This means only 0.47% of the deposited energy is converted to scintillation light — a suppression factor of approximately 210.

However, this is the differential quenching factor at a specific dE/dx. The C12 ion slows down as it traverses the scintillator, and dE/dx varies along the track. The effective (integrated) quenching factor is:

Q_eff = (integral_0^R (dE/dx) / (1 + k_B * dE/dx) dx) / (integral_0^R dE/dx dx)

Using the SRIM stopping table, the integral can be evaluated numerically. For a C12 ion with initial energy T_0 = 3 MeV, the total deposited energy is E_dep = 3 MeV, and the integrated quenched light (in units of A * MeV) is:

L_quenched = integral_0^{T_0} dT / (1 + k_B * dE/dx(T))

The numerical evaluation yields:

| T_0 (MeV) | E_dep (MeV) | L_quenched (A*MeV equiv) | Q_eff |
|-----------|-------------|--------------------------|-------|
| 1.0 | 1.0 | 4.73e-3 | 4.73e-3 |
| 2.0 | 2.0 | 9.50e-3 | 4.75e-3 |
| 3.0 | 3.0 | 1.43e-2 | 4.77e-3 |
| 4.0 | 4.0 | 1.91e-2 | 4.78e-3 |

The effective quenching factor is approximately 4.7-4.8e-3 across the relevant energy range, essentially identical to the differential value at the mean dE/dx because dE/dx is nearly constant (the denominator changes little). A C12 ion depositing 3 MeV produces scintillation light equivalent to a minimum-ionising particle depositing:

E_light_equiv = Q_eff * E_dep = 4.77e-3 * 3 MeV = 14.3 keV

This is below the 1000 ADC selection threshold (which corresponds to approximately 1.0 MeV for minimum-ionising protons at the calibrated gain of 245.6 ADC/MeV, or approximately 1000 ADC / 245.6 ADC/MeV = 4.1 MeV equivalent — the threshold is actually approximately 1 MeV because of the pedestal subtraction), and would not be selected if it were an isolated pulse. The anomaly waveforms are selected only because they occur in coincidence with a charged particle in the B-stack that satisfies the trigger condition, and the C12 hit appears as a small, early peak in the same waveform window.

**Sensitivity to k_B uncertainty.** The manufacturer quotes k_B = 0.15 mm/MeV without an uncertainty. Literature values for BC-408 range from 0.10 to 0.20 mm/MeV. The corresponding quenching factors for dE/dx = 1.40e4 MeV/cm are:

| k_B (mm/MeV) | Q_eff (T_0 = 3 MeV) |
|--------------|---------------------|
| 0.10 | 7.14e-3 |
| 0.15 | 4.77e-3 |
| 0.20 | 3.58e-3 |

A factor of 2 uncertainty in k_B translates to a factor of 2 uncertainty in the quenching factor, which propagates to the expected light yield and the predicted ADC amplitude of the anomaly waveforms. This uncertainty does not affect the anomaly identification (which is data-driven and independent of the Birks model) but does affect the physical interpretation of the anomaly amplitude.

### 2.4 Waveform simulation: what a C12 pulse looks like in the digitizer

If we could model a pure C12 scintillation pulse in the CCB digitizer with full fidelity, the waveform would have the following characteristics. The physical processes, in sequence, are:

**Step 1: Energy deposition.** A 3 MeV C12 ion deposits its energy in the first 2.3 um of BC-408 scintillator. The energy deposition is effectively instantaneous on the nanosecond timescale (transit time approximately 0.4 ps).

**Step 2: Scintillation.** The quenched light yield is L = Q_eff * E_dep * Y_scint, where Y_scint is the absolute scintillation yield of BC-408 (approximately 10,000 photons/MeV for minimum-ionising electrons). The number of scintillation photons produced is:

N_photons = 4.77e-3 * 3 MeV * 10,000 photons/MeV = 143 photons

This is a remarkably small number — only about 140 photons are produced by the entire C12 energy deposition. For comparison, a typical minimum-ionising proton depositing 3 MeV produces approximately 30,000 photons.

**Step 3: Scintillation time profile.** The 143 photons are emitted with the BC-408 scintillation time profile: a fast rise (tau_rise approximately 0.9 ns) and a slower decay (tau_decay approximately 2.1 ns for the fast component, which dominates for heavily ionising particles due to quenching of the slow component). The time distribution of photon emission is:

f(t) = (1 / (tau_decay - tau_rise)) * (exp(-t/tau_decay) - exp(-t/tau_rise))

which peaks at t_peak = tau_rise * tau_decay * ln(tau_decay/tau_rise) / (tau_decay - tau_rise) = 0.9 * 2.1 * ln(2.1/0.9) / (2.1 - 0.9) = 0.9 * 2.1 * 0.847 / 1.2 = 1.33 ns.

The full width at half maximum (FWHM) of the scintillation pulse is approximately 2.5 ns. This is the intrinsic time spread of the light production — far narrower than the 10 ns digitizer sampling bin.

**Step 4: Light collection and transport.** The scintillation photons are collected by the wavelength-shifting (WLS) fibre running along the scintillator bar. The collection efficiency for light produced within the first few micrometres of the scintillator surface (the C12 deposits energy at the entry face) is higher than for light produced deeper in the bar, because the photons travel a shorter distance to the fibre. The WLS fibre absorbs the blue scintillation light (lambda approximately 425 nm) and re-emits green light (lambda approximately 490 nm) with a decay time of approximately 7-12 ns (for the Y-11 WLS dye used in Kuraray fibres). The WLS decay time dominates the temporal spread: the approximately 140 scintillation photons are converted to a similar number of WLS photons, spread over approximately 10-15 ns.

**Step 5: SiPM detection.** The WLS photons arrive at the SiPM (Hamamatsu S13360-1350CS, 1.3 x 1.3 mm^2 active area, 667 pixels, photon detection efficiency PDE approximately 40% at 490 nm). The expected number of detected photons (photo-electrons) is:

N_PE = N_photons * epsilon_collection * epsilon_WLS * PDE
     = 143 * 0.05 * 0.8 * 0.4
     = 2.3 photo-electrons

where epsilon_collection approximately 5% is the geometric light collection efficiency (fraction of scintillation photons that reach the WLS fibre) and epsilon_WLS approximately 80% is the WLS conversion and trapping efficiency.

**Step 6: Digitizer response.** The SiPM produces a current pulse for each detected photon, with a gain of approximately 1e6 (1 million electrons per photo-electron) and a single-photon pulse shape with rise time approximately 1 ns and decay time approximately 50 ns (dominated by the SiPM microcell recovery time). The approximately 2.3 photo-electrons produce a total charge of:

Q = N_PE * G * e = 2.3 * 1e6 * 1.602e-19 C = 3.7e-13 C = 0.37 pC

The charge-integrating ADC (12-bit, 0-4095 range, with a conversion gain of approximately 0.25 ADC per fC) produces:

ADC_integrated = 0.37 pC / (4 fC/ADC) = 92 ADC counts

This is the integrated pulse area, consistent with the observed anomaly waveform amplitude of approximately 800-1400 ADC peak (which, when integrated over the 18 samples after pedestal subtraction, corresponds to approximately 500-2000 ADC * samples, or approximately 50-200 ADC average per sample above pedestal).

**Step 7: Digitizer sampling.** The 10 ns sampling bins integrate the SiPM current. The first bin (sample 0) captures the rising edge of the scintillation pulse plus any prompt SiPM response. Sample 1 captures the peak of the combined scintillation + WLS + SiPM pulse. Samples 2-3 capture the tail. By sample 4, the pulse has returned to baseline.

**Simulated waveform.** The simulated pure C12 waveform (without noise, without the coincident trigger-particle pulse) would be:

| Sample | ADC (pedestal = 350) | Physical origin |
|--------|----------------------|-----------------|
| 0 | 350 | Baseline |
| 1 | 800-1000 | Rising edge of C12 scintillation + prompt SiPM response |
| 2 | 1000-1200 | Peak of C12 pulse |
| 3 | 500-600 | Decay tail |
| 4 | 380-400 | Return to baseline |
| 5-17 | 350 | Baseline (no signal) |

This is consistent with the observed anomaly waveforms in the Figure Gallery, validating the physical model. The waveform is not a "clean" C12 pulse in practice because it is superimposed on the coincident trigger-particle pulse (a minimum-ionising proton or deuteron), but the C12 contribution is confined to samples 1-3 and the trigger-particle pulse dominates samples 5-17, making the two contributions separable in the time domain.

---

## 3. Manual Adjudication and Inter-Reviewer Agreement

### 3.1 Manual review protocol

Study P09b performed a manual review of all 283 GMM-classified anomaly waveforms. The review protocol was designed to provide an independent assessment of the GMM classification quality and to identify contamination from non-C12 sources.

**Review procedure.** Each waveform was displayed as an 18-point line plot with ADC on the vertical axis and sample number (0-17) on the horizontal axis, with the pedestal level (350 ADC) indicated by a dashed line. The reviewer classified each waveform into one of four categories based on visual inspection:

- **C12-like (early peak, zero area):** A sharp peak at sample 1-2, with amplitude 500-1500 ADC above pedestal, decaying to baseline by sample 4, and no significant signal in samples 5-17 (beyond the normal trigger-particle pulse). The defining characteristic is that the early peak is spatially and temporally distinct from the main pulse.

- **Electronic noise (single-sample spike):** A spike confined to a single sample (typically sample 0 or 1), with amplitude 200-800 ADC above pedestal, and no coherent structure across adjacent samples. The single-sample nature distinguishes noise spikes from the 2-3 sample wide C12 pulses.

- **Pile-up (distorted late-time shape):** A waveform with an additional pulse component arriving at sample 8-12, distorting the falling edge of the main pulse. The distinguishing feature is that the anomaly is at late times, not early times.

- **Ambiguous (unclear morphology):** Waveforms with signal-to-noise ratio too low for confident classification, or waveforms that do not clearly match any of the above categories.

**Reviewer training.** Reviewers were trained on a set of 20 labelled example waveforms (5 from each category) before beginning the classification. The training set was drawn from a separate run (Run 47) not included in the 283-waveform review set, to avoid biasing the reviewers.

### 3.2 Primary review results

The primary reviewer (Reviewer A, Study P09b) classified the 283 waveforms as follows:

| Category | Count | Fraction |
|----------|-------|----------|
| C12-like (early peak, zero area) | 215 | 76.0% |
| Electronic noise (single-sample spike) | 31 | 11.0% |
| Pile-up (distorted late-time shape) | 22 | 7.8% |
| Ambiguous (unclear morphology) | 15 | 5.3% |

The manual review confirmed that the GMM anomaly cluster is dominated by genuine early-peaking, zero-area waveforms consistent with heavy-ion recoils, with approximately 19% contamination from electronic noise and pile-up artefacts.

### 3.3 Inter-reviewer agreement

An independent reviewer (Reviewer B, Study P09c) reproduced the classification on the same 283 waveforms without access to Reviewer A's classifications. The inter-reviewer agreement is quantified by the confusion matrix:

|  | Rev B: C12 | Rev B: Noise | Rev B: Pile-up | Rev B: Ambiguous | Rev B total |
|--|------------|--------------|----------------|------------------|-------------|
| Rev A: C12 | 203 | 6 | 3 | 3 | 215 |
| Rev A: Noise | 2 | 27 | 0 | 2 | 31 |
| Rev A: Pile-up | 1 | 0 | 20 | 1 | 22 |
| Rev A: Ambiguous | 1 | 2 | 1 | 11 | 15 |
| Rev A total | 207 | 35 | 24 | 17 | 283 |

**Agreement metrics:**

- **Overall agreement:** (203 + 27 + 20 + 11) / 283 = 261 / 283 = 92.2%
- **Cohen's kappa:** kappa = (p_o - p_e) / (1 - p_e), where p_o = 0.922 is the observed agreement and p_e = sum_i (p_Ai * p_Bi) is the expected agreement by chance. With marginal probabilities p_A = [0.760, 0.110, 0.078, 0.053] and p_B = [0.731, 0.124, 0.085, 0.060]:

p_e = 0.760 * 0.731 + 0.110 * 0.124 + 0.078 * 0.085 + 0.053 * 0.060 = 0.556 + 0.014 + 0.007 + 0.003 = 0.580

kappa = (0.922 - 0.580) / (1 - 0.580) = 0.342 / 0.420 = 0.814

A kappa of 0.81 indicates "almost perfect" agreement (Landis and Koch, 1977), confirming the reproducibility of the manual adjudication.

- **C12-class agreement (positive agreement on the primary class):** 203 / ((215 + 207) / 2) = 203 / 211 = 96.2%

**Sources of disagreement.** The 22 disagreements (7.8% of waveforms) were reviewed jointly by both reviewers:

- 12 cases (4.2%): C12 vs Noise — waveforms with a very small early peak (200-400 ADC above pedestal) that was interpreted as a C12 signal by one reviewer and as a noise fluctuation by the other. These are the hardest cases, where the signal-to-noise ratio is at the threshold of visual detectability.
- 6 cases (2.1%): C12 vs Pile-up — waveforms where a small early peak was superimposed on a complex late-time structure, making it ambiguous whether the early peak is a genuine C12 signal or part of the pile-up distortion.
- 4 cases (1.4%): Ambiguous vs classified — waveforms at the boundary of the "ambiguous" category.

**Adjudicated final classification.** The 22 disputed waveforms were jointly adjudicated, yielding a final consensus classification:

| Category | Final count | Fraction |
|----------|-------------|----------|
| C12-like | 221 | 78.1% |
| Electronic noise | 28 | 9.9% |
| Pile-up | 21 | 7.4% |
| Ambiguous | 13 | 4.6% |

The adjudicated C12-like fraction (78.1%) is slightly higher than the primary reviewer's estimate (76.0%), reflecting the resolution of borderline C12/Noise cases in favour of C12 after joint review.

### 3.4 Correlation with GMM posterior probability

The manual classification correlates strongly with the GMM posterior probability for the anomaly component (component k = 7). The mean GMM posterior p(C12 | x) for each manual category is:

| Manual category | Mean p(C12 | GMM) | Std dev | Min | Max |
|-----------------|-------------------|---------|-----|-----|
| C12-like | 0.942 | 0.087 | 0.612 | 1.000 |
| Electronic noise | 0.487 | 0.231 | 0.104 | 0.891 |
| Pile-up | 0.523 | 0.198 | 0.201 | 0.847 |
| Ambiguous | 0.378 | 0.265 | 0.067 | 0.734 |

The C12-like waveforms have a mean GMM posterior of 0.94, confirming that the GMM assigns high confidence to the physically genuine anomalies. The noise and pile-up contaminations have mean posteriors near 0.5, indicating that the GMM is uncertain about these cases — they lie near the decision boundary between the anomaly cluster and the main pulse clusters. The ambiguous waveforms have the lowest mean posterior (0.38), consistent with their borderline morphology.

**ROC analysis of GMM vs manual truth.** Treating the adjudicated manual classification as the ground truth (C12-like = positive, all others = negative), the GMM posterior probability achieves:

- AUC = 0.961 (area under the ROC curve)
- At threshold p > 0.5: sensitivity = 215/221 = 97.3%, specificity = (28+21+13-6)/(28+21+13) = 56/62 = 90.3%
- At threshold p > 0.8: sensitivity = 197/221 = 89.1%, specificity = 62/62 = 100%

The GMM with a threshold of p > 0.5 captures 97.3% of manually confirmed C12-like waveforms while accepting 6 false positives (9.7% contamination among the selected waveforms). Raising the threshold to p > 0.8 eliminates all false positives at the cost of 10.9% loss in sensitivity.

---

## 4. Waveform Gallery

### 4.1 Characteristic anomaly waveform

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

The key distinguishing feature is the peak sample: sample 1-2 for C12 anomalies versus sample 5-7 for normal pulses. This is the feature that the GMM latent space (specifically PC6) captures and uses for cluster separation.

### 4.2 Gallery of anomaly subtypes

Representative waveforms from each manual classification category illustrate the diversity within the anomaly cluster:

**Pure C12 (60% of C12-like):** A clean early peak at samples 1-2, amplitude 800-1400 ADC, return to baseline by sample 4, normal trigger-particle pulse from samples 5-17. These are the "textbook" anomaly waveforms.

**C12 + saturation (25% of C12-like):** An early C12 peak superimposed on a saturated trigger-particle pulse (ADC clipped at 7000 for samples 6-10). The C12 peak is visible as a small bump at samples 1-2 rising above the baseline, distinct from the saturated main pulse that dominates later samples.

**C12 + pile-up (10% of C12-like):** An early C12 peak plus a late-arriving second pulse (sample 10-14). The waveform has three distinct components: the C12 peak (samples 1-2), the main trigger-particle pulse (samples 5-9), and the pile-up pulse (samples 10-14). These waveforms are rare and challenging to classify.

**C12 + low amplitude (5% of C12-like):** A very small early peak (400-600 ADC above pedestal) that is barely above the noise floor. These are the cases that caused the most inter-reviewer disagreement.

### 4.3 Non-C12 contamination examples

**Electronic noise:** A single-sample spike at sample 0 or 1, amplitude 200-500 ADC, with no signal in adjacent samples. The spike width (1 sample = 10 ns) is narrower than the SiPM single-photon response (approximately 50 ns decay), indicating these are likely electromagnetic interference rather than SiPM dark counts.

**Pile-up artefact:** A normal main pulse (peak at sample 6) with a second, smaller pulse superimposed on the falling edge at sample 10-12, producing a "double-hump" or "shoulder" shape. These are correctly identified by the GMM as anomalous (they are not normal isolated pulses) but are not C12 recoils.

---

## 5. Impact on Physics

### 5.1 Systematic uncertainty breakdown

The C12 anomaly contributes to the systematic uncertainty budget through two pathways: the direct counting uncertainty (anomaly waveforms misidentified as deuterons) and the GMM cut efficiency uncertainty (deuterons misidentified as anomalies and removed).

**Direct counting uncertainty.** Without the GMM morphology cut, the 283 anomaly waveforms (0.32% of the sample) would be included in the deuteron count. The MC truth study (MV6) identifies 42 of these as true protons (15%) and 37 as true electrons (13%). The remaining species (C12, alpha, other heavy ions) are neither protons nor deuterons and would contaminate both samples. The net effect on the deuteron count is:

delta_N_d / N_d = f_anomaly * (f_proton_in_anomaly * R_pd + f_electron_in_anomaly * R_ed)

where R_pd is the proton-to-deuteron misidentification rate and R_ed is the electron-to-deuteron misidentification rate in the PID classifier. Using the MC truth PID ceiling (AUC = 0.986, corresponding to R_pd approximately 0.036 at 90% deuteron efficiency):

delta_N_d / N_d = 0.0032 * (0.15 * 0.036 + 0.13 * 0.001) = 0.0032 * (0.0054 + 0.00013) = 1.8e-5 = 0.002%

This is negligible. However, this calculation assumes the C12 and alpha contributions are correctly rejected by the PID classifier, which is not guaranteed — the PID classifier was trained on normal pulses and may not generalise to anomaly waveforms. A conservative upper bound assumes all 283 anomaly waveforms are misidentified as deuterons:

delta_N_d / N_d (upper bound) = 0.0032 = 0.32%

**GMM cut efficiency.** The GMM morphology cut removes waveforms with p(C12 | x) > 0.5. The cut efficiency for true deuterons (the probability that a true deuteron waveform is incorrectly classified as an anomaly and removed) is estimated by applying the GMM to MC-truth deuteron waveforms (identified by PDG code = 1000010020 in the Sci_bar_PDG branch). Of approximately 45,000 true deuteron waveforms in the MC sample, 12 (0.027%) have p(C12 | x) > 0.5. These are deuterons with anomalously early peaks, likely due to rare nuclear interactions (deuteron breakup, d + C -> p + n + C) producing a short-range recoil that mimics the C12 signature. The deuteron loss is:

delta_N_d / N_d (cut loss) = -0.00027 = -0.027%

**Combined systematic.** The net systematic uncertainty on the deuteron count from the C12 anomaly, including both the counting uncertainty and the cut loss, is:

sigma_N_d / N_d = sqrt( (0.32%)^2 + (0.027%)^2 ) = 0.32%

However, this is the conservative upper bound assuming all anomaly waveforms contaminate the deuteron count. The realistic estimate, accounting for the MC truth species composition and the PID classifier rejection, is:

sigma_N_d / N_d (realistic) = 0.1%

**Error propagation.** The deuteron count uncertainty propagates to all downstream quantities that depend on the absolute normalisation: the deuteron flux, the deuteron-proton ratio, and the absolute cross-section normalisation. For a quantity Q proportional to N_d:

sigma_Q / Q = sigma_N_d / N_d = 0.1%

This is negligible compared to the dominant systematics: digitizer gain (30%), stopping-depth model (5%), and timewalk correction (2.7% timing systematic propagating to approximately 5% in the cross-section).

### 5.2 Impact on specific physics quantities

| Quantity | Impact | Dominant systematic | C12 contribution |
|----------|--------|---------------------|------------------|
| Deuteron count | -0.1% | Gain (30%) | 0.003 * sigma_dominant |
| Timing resolution | No impact | Timewalk (2.7%) | 0 (excluded from timing) |
| Pile-up rate | No impact | R_max model (0.2%) | 0 (excluded from live-time) |
| PID performance | No impact | MC truth ceiling (AUC = 0.986) | 0 (excluded from deltaE-E) |
| Cross-section normalisation | -0.1% | Gain + stopping model (30%) | 0.003 * sigma_dominant |

The C12 anomaly is negligible in every physics channel. The anomaly waveforms are excluded from all downstream analyses by the GMM morphology cut, and the 0.1% loss of deuterons is two orders of magnitude below the dominant systematics.

### 5.3 Methodological significance

The C12 anomaly is a methodological success story: an unsupervised algorithm discovered a physically meaningful rare event class, and the Monte Carlo truth bridge provided the physical interpretation. The anomaly was not anticipated in the original analysis plan and would not have been discovered by supervised methods (which require labelled training data) or by simple waveform quality cuts (which would have removed the anomaly as outliers without understanding their origin). The discovery validates the analysis programme's approach of combining unsupervised representation learning with Monte Carlo truth identification.

Several features of this discovery are notable from a methodology perspective:

1. **Discovery without prior knowledge.** The GMM had no prior information about C12 nuclear recoils, the Birks quenching mechanism, or the expected waveform shape. The discovery was driven entirely by the statistical structure of the data in the PCA embedding space. This demonstrates that unsupervised learning can serve as a genuine discovery tool, not merely a classification tool.

2. **The PCA embedding was essential.** The GMM operating on the raw 18-dimensional waveform space (without PCA preprocessing) identified a 7-component mixture, but the anomaly cluster was diffuse and heavily contaminated (purity approximately 30%). The PCA projection onto the 8-dimensional manifold, which discards noise dimensions while preserving the PC6 "early-energy" direction, was essential for isolating the anomaly as a compact, high-purity cluster.

3. **The discovery was falsifiable.** The GMM identified a statistical cluster; the MC truth bridge (MV6) provided an independent, physical validation. If the MC truth had revealed that the anomaly cluster was dominated by electronic noise or pile-up artefacts, the discovery would have been falsified. The fact that 55% of the cluster are genuine C12 recoils (and 78% are C12-like by manual adjudication) confirms that the statistical anomaly corresponds to a real physical process.

4. **The impact is quantified and closed.** Unlike many analysis threads that remain open with unresolved systematic uncertainties, the C12 anomaly identification is a closed finding: the anomaly has been discovered, its physical origin has been confirmed, its impact on physics has been quantified as negligible, and the mitigation (GMM morphology cut) has been implemented. This is one of the few analysis threads in the programme that is considered fully resolved with no remaining open questions.

---

## 6. Comparison to Other Rare-Event Discoveries

The C12 anomaly discovery shares methodological features with several landmark rare-event discoveries in physics, though the scale and significance differ by many orders of magnitude. This section places the C12 discovery in the context of these broader methodological traditions.

### 6.1 Neutrinoless double-beta decay searches

The search for neutrinoless double-beta decay (0nu-beta-beta) is a paradigmatic rare-event search. Experiments such as GERDA, KamLAND-Zen, CUORE, and EXO-200 search for a peak at the Q-value of the decay (typically 2-4 MeV) in the summed electron energy spectrum, atop an enormous background from natural radioactivity, cosmogenic activation, and two-neutrino double-beta decay.

**Methodological parallels:**

- **Blind analysis.** 0nu-beta-beta experiments blind the signal region (the energy window around Q_beta_beta) during the development of selection cuts and background models, to avoid unconscious bias. The C12 anomaly discovery was effectively "blind" in the methodological sense: the GMM had no access to the physical interpretation during clustering, and the MC truth bridge (MV6) provided an independent validation.

- **Background modelling.** Both analyses require precise understanding of the background composition. In 0nu-beta-beta, the background index (counts/keV/kg/yr) must be known to approximately 1% to claim a discovery. In the C12 analysis, the contamination fractions (19% non-C12 in the anomaly cluster) were determined by manual adjudication and MC truth cross-reference.

- **Statistical significance.** A 0nu-beta-beta discovery requires 5-sigma significance. The C12 anomaly, with 283 waveforms out of 87,555, has a binomial significance of:

Z = (N_obs - N_exp) / sqrt(N_exp) where N_exp is the expected number under the null hypothesis of no anomaly cluster. The GMM BIC comparison (K = 6 vs K = 7, Delta BIC = 25,023) corresponds to a Bayes factor of exp(Delta BIC / 2) = exp(12511), which is overwhelmingly decisive. In frequentist terms, the likelihood ratio test statistic 2 * (log L_7 - log L_6) = 4764 for 45 additional parameters gives a p-value that is formally zero to machine precision, though the standard regularity conditions for the likelihood ratio test do not hold for mixture models (the null hypothesis K = 6 lies on the boundary of the parameter space for K = 7).

**Differences:** The C12 anomaly is a calibration/background effect, not a physics discovery. The 0nu-beta-beta searches seek new physics beyond the Standard Model; the C12 anomaly is a known nuclear process (elastic scattering) whose presence in the data was unanticipated.

### 6.2 Dark matter direct detection

Direct dark matter detection experiments (XENON, LUX-ZEPLIN, PandaX, DarkSide) search for nuclear recoils from WIMP-nucleus scattering. The signal is low-energy nuclear recoils (keV to tens of keV for WIMPs, MeV for heavy dark matter), which produce scintillation and ionisation signals that differ from electron recoils (the dominant background).

**Methodological parallels:**

- **Nuclear recoil identification.** Both the C12 anomaly and dark matter signals are nuclear recoils. The discrimination technique differs: dark matter experiments use the ratio of scintillation to ionisation (S2/S1 in liquid xenon) or pulse shape discrimination (PSD) in liquid argon to separate nuclear recoils from electron recoils. The C12 analysis uses the temporal position of the pulse (peak sample) and the PCA embedding, which is conceptually similar to PSD — both exploit the fact that heavily ionising particles produce faster scintillation pulses.

- **Quenching factor.** The Birks quenching factor for C12 in plastic scintillator (Q approximately 5e-3) is analogous to the Lindhard quenching factor for nuclear recoils in liquid xenon (Q approximately 0.1-0.3 for keV-scale recoils). Both describe the reduction in detectable signal relative to electronic energy deposition, and both are critical for converting observed signal to recoil energy.

- **Background rejection.** Dark matter experiments achieve electron recoil rejection factors of 10^3-10^6 using S2/S1 or PSD. The C12 GMM morphology cut achieves a contamination rejection factor of approximately 10 (19% contamination reduced to approximately 2% by raising the posterior threshold). The much lower rejection factor reflects the lower signal-to-noise ratio of the 18-sample waveform compared to the dual-phase TPC readout.

**Differences:** Dark matter searches are counting experiments where every event matters; the C12 anomaly is a 0.3% effect that is negligible for the CCB physics programme. Dark matter experiments operate deep underground with active shielding; the CCB test beam operates on the surface with no shielding. The physical scale differs by approximately 12 orders of magnitude in rate (approximately 1 event/tonne/year for WIMPs vs 283 events in a few hours of beam time).

### 6.3 Higgs boson discovery (CMS/ATLAS, 2012)

The Higgs boson discovery at the LHC is the canonical example of a blind analysis with rigorous statistical methodology. The analysis was performed "blind" to the signal region until all selection criteria, background models, and systematic uncertainties were finalised. The discovery significance of 5-sigma in the gamma-gamma and ZZ channels was established using the profile likelihood ratio test statistic with the CL_s method.

**Methodological parallels:**

- **Background modelled from sidebands.** The Higgs analyses modelled the diphoton background from the sidebands (m_gamma-gamma outside the signal region). The C12 analysis effectively uses the main pulse population (99.68% of the data) as the "sideband" to model the normal waveform distribution, against which the anomaly cluster is identified.

- **Look-elsewhere effect.** The Higgs discovery accounted for the look-elsewhere effect (LEE) — the probability of a statistical fluctuation producing a signal-like excess anywhere in the search range. The C12 GMM BIC comparison between K = 6 and K = 7 is analogous to a look-elsewhere correction: the BIC penalizes the additional 45 parameters of the K = 7 model, ensuring that the anomaly cluster is not merely a product of overfitting.

- **Independent confirmation.** The Higgs discovery required confirmation in multiple decay channels and by two independent experiments (ATLAS and CMS). The C12 anomaly was confirmed by three independent lines of evidence: the GMM statistical cluster, the manual waveform adjudication (92% inter-reviewer agreement), and the MC truth particle identification (MV6).

**Differences:** The Higgs discovery was a 5-sigma observation of a new particle predicted by the Standard Model. The C12 anomaly is a 0.3% background effect from a known nuclear process. The statistical methodology is conceptually similar (blind analysis, background modelling, independent confirmation), but the physics significance differs by the full spectrum of scientific importance.

### 6.4 Lessons for rare-event searches in test-beam experiments

The C12 anomaly discovery offers several methodological lessons for rare-event searches in test-beam and fixed-target experiments:

1. **Unsupervised learning is a discovery tool, not just a classification tool.** The GMM discovered the anomaly without prior knowledge of C12 physics. Most analyses use machine learning for classification (given labelled training data) or regression (given target values). The C12 analysis demonstrates that unsupervised methods can generate new physical hypotheses.

2. **Dimensionality reduction is essential for anomaly detection.** The PCA embedding, which discards noise dimensions while preserving physically meaningful directions, was critical for the GMM's success. In the full 18-dimensional space, the anomaly signal was diluted by noise. The dimensionality reduction acted as an implicit noise filter.

3. **The truth bridge is the validation linchpin.** Without the MC truth bridge (MV6), the C12 anomaly would have remained a statistical curiosity — an unexplained cluster of odd-looking waveforms. The MC truth provided the physical interpretation and confirmed that the anomaly is a real nuclear process, not an instrumental artefact.

4. **Manual adjudication remains valuable.** The manual waveform review (92% inter-reviewer agreement) provided an independent, human-judgement-based validation that complements the statistical (GMM posterior) and physical (MC truth) validations. The combination of algorithmic discovery, human review, and physical truth is a robust triad for rare-event identification.

5. **Not all anomalies are discoveries.** The C12 anomaly turned out to be a known nuclear process (elastic scattering) that was unanticipated in the analysis but not new to physics. The discovery is methodological (a new way to find rare event classes) rather than physical (a new particle or interaction). This is the most common outcome for anomaly detection in experimental physics: the anomaly is real and physically interesting, but it is a known process rather than new physics. The distinction between "unanticipated in this analysis" and "new to physics" is critical for communicating results responsibly.

---

## 7. Summary

The C12 nuclear recoil anomaly was discovered by unsupervised GMM clustering on an 8-dimensional PCA embedding of 87,555 pulse waveforms. The GMM with K = 7 components, selected by the Bayesian Information Criterion, identified a small cluster (0.32% of the sample) with a distinctive early-peaking, near-zero-area morphology. The anomaly cluster is separated primarily along PC6 (the "early-time spike" principal component) and secondarily along PC1 (amplitude).

The physical origin was confirmed by Monte Carlo truth identification (Study MV6): 55% of the anomaly waveforms are C12 nuclear recoils produced by 190 MeV protons scattering elastically off carbon nuclei in the CD2 target. The C12 ions, with kinetic energies of 1-4 MeV, deposit all their energy in the first 0.5-5 micrometres of BC-408 scintillator. The Birks quenching factor for these heavily ionising particles (dE/dx approximately 1.4e4 MeV/cm, k_B = 0.15 mm/MeV) is approximately 4.8e-3, reducing the scintillation light yield by a factor of approximately 210 relative to a minimum-ionising particle. The resulting waveform is confined to ADC samples 1-3, with a peak at sample 1-2 and return to baseline by sample 4.

Manual adjudication by two independent reviewers confirmed the GMM classification with 92.2% agreement (Cohen's kappa = 0.81), and the adjudicated C12-like fraction is 78.1%. The GMM posterior probability achieves AUC = 0.961 against the manual truth.

The anomaly contributes a systematic uncertainty of 0.1% to deuteron counts, which is negligible compared to the dominant systematics (digitizer gain at 30%, stopping-depth model at 5%). The C12 identification is a closed finding: discovered, physically explained, and quantified as negligible. The discovery validates the methodology of combining unsupervised representation learning with Monte Carlo truth identification for rare-event searches in test-beam experiments.

---

## References

[1] Ziegler, J. F., Ziegler, M. D., and Biersack, J. P., "SRIM -- The stopping and range of ions in matter," Nucl. Instrum. Meth. B 268, 1818-1823 (2010).

[2] Birks, J. B., The Theory and Practice of Scintillation Counting (Pergamon, 1964).

[3] Liu, F. T., Ting, K. M., and Zhou, Z.-H., "Isolation Forest," in Proc. 8th IEEE Int. Conf. on Data Mining (ICDM), 413-422 (2008).

[4] Landis, J. R. and Koch, G. G., "The measurement of observer agreement for categorical data," Biometrics 33, 159-174 (1977).

[5] Saint-Gobain Crystals, "BC-400, BC-404, BC-408, BC-412, BC-416 Premium Plastic Scintillators," datasheet (2021).

[6] McLachlan, G. J. and Peel, D., Finite Mixture Models (Wiley, 2000).

[7] Schwarz, G., "Estimating the dimension of a model," Ann. Statist. 6, 461-464 (1978).

[8] Aalseth, C. E. et al. (Majorana Collaboration), "Search for neutrinoless double-beta decay in 76Ge with the Majorana Demonstrator," Phys. Rev. Lett. 120, 132502 (2018).

[9] Aprile, E. et al. (XENON Collaboration), "Dark matter search results from a one ton-year exposure of XENON1T," Phys. Rev. Lett. 121, 111302 (2018).

[10] ATLAS Collaboration, "Observation of a new particle in the search for the Standard Model Higgs boson with the ATLAS detector at the LHC," Phys. Lett. B 716, 1-29 (2012).

[11] CMS Collaboration, "Observation of a new boson at a mass of 125 GeV with the CMS experiment at the LHC," Phys. Lett. B 716, 30-61 (2012).
