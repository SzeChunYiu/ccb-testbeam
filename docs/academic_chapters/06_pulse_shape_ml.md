# Chapter 6: Pulse Shape Representation and Machine Learning

## Abstract

The 18-sample scintillator waveforms recorded by the HRD staves encode particle identity, energy deposition, and arrival time in their pulse shape. This chapter presents the systematic analysis of pulse shape information content through dimensionality reduction (Principal Component Analysis and autoencoder compression), the evaluation of machine learning methods across eight analysis domains with rigorous leakage controls, and the identification of an anomalous waveform class subsequently confirmed by Monte Carlo truth as carbon-12 nuclear recoils. The central finding is methodological: most apparent machine learning wins in this analysis programme failed one or more leakage controls (target shuffle, leave-one-run-out cross-validation, event-block shuffle), and the corrected picture is that traditional physics-anchored methods remain competitive with or superior to deep learning in the majority of domains. Machine learning wins only where the truth label is independent of the input waveform and the missing information is genuinely encoded in pulse shape: saturation recovery and duplicate-readout closure.

---

## 1. Pulse Shape Dimensionality

### 1.1 Principal Component Analysis

The 18-sample ADC waveform, after baseline subtraction and amplitude normalisation, is an 18-dimensional vector. The effective dimensionality of the pulse shape manifold — the number of independent degrees of freedom that describe the variation across the population of approximately 640,000 pulses — is assessed by Principal Component Analysis (PCA). PCA computes the eigendecomposition of the waveform covariance matrix Sigma = (1/N) * sum_i (w_i - w_bar)(w_i - w_bar)^T, where w_i is the 18-sample waveform vector for pulse i and w_bar is the mean waveform. The eigenvectors (principal components) form an orthonormal basis ordered by explained variance.

The PCA results (Study P01) reveal that pulse shapes are fundamentally low-dimensional:

| Latent dimension | Cumulative explained variance | Reconstruction MSE |
|---|---|---|
| 2 | 78.0% | 0.02622 |
| 3 | 89.2% | 0.01416 |
| 4 | 93.5% | 0.00880 |
| 8 | 99.7% | 0.00166 |

Three principal components capture 89% of the total pulse shape variance. The first component corresponds to the overall pulse amplitude (the dominant source of variation), the second to the pulse width (rise-time variation and saturation broadening), and the third to the pulse asymmetry (the balance between rising-edge and falling-edge shape, which encodes pile-up and particle species information). The remaining 15 components collectively account for only 0.3% of the variance, indicating that the pulse shape manifold has no deep hidden structure — the scintillator physics (BC-408 decay time, WLS fibre transport, SiPM response) produces a limited family of pulse shapes.

### 1.2 Autoencoder compression

A deep autoencoder — a neural network consisting of an encoder f_theta: R^18 -> R^d that compresses the 18-sample waveform to a d-dimensional latent code, and a decoder g_phi: R^d -> R^18 that reconstructs the waveform from the latent code — was trained to minimise the mean squared reconstruction error L = (1/N) * sum_i ||w_i - g_phi(f_theta(w_i))||^2. The autoencoder architecture uses fully connected layers with ReLU activations: encoder [18 -> 64 -> 32 -> d], decoder [d -> 32 -> 64 -> 18].

The autoencoder outperforms PCA at very low latent dimensions (d = 2, 3, 4), where the nonlinear manifold structure — the fact that pulse shapes lie on a curved surface in the 18-dimensional space rather than a flat hyperplane — gives the autoencoder an advantage:

| Latent dim | PCA MSE | AE MSE | AE improvement |
|---|---|---|---|
| 2 | 0.02622 | 0.01294 | +50.6% |
| 3 | 0.01416 | 0.00841 | +40.6% |
| 4 | 0.00880 | 0.00527 | +40.1% |
| 8 | 0.00166 | 0.00292 | -75.9% (PCA wins) |

At d = 8, PCA overtakes the autoencoder. This reversal occurs because 8 linear components capture 99.7% of the variance, and the autoencoder's additional model capacity (network weights) is spent fitting noise rather than signal — a classic bias-variance tradeoff where the simpler model (PCA, with 18 * 8 = 144 parameters) generalises better than the overparametrised autoencoder (approximately 3,500 parameters) when the data are nearly linearly representable. The cross-over point at d approximately equal to 5-6 indicates that the pulse shape manifold has a small but genuine nonlinear component, consistent with saturation effects (nonlinear amplitude-dependent pulse broadening) and pile-up (nonlinear superposition of two exponential pulses).

### 1.3 Per-sample information content

Study P01c performed a per-sample ablation analysis: individual ADC samples were systematically perturbed or removed, and the impact on downstream timing and amplitude reconstruction was measured. Samples 3-6 (30-60 ns after the trigger, corresponding to the pulse rising edge) carry the majority of the timing information. Sample 5 (50 ns) showed an apparent sign-flip in its contribution to the CFD time — perturbing sample 5 shifted the reconstructed time in the opposite direction from perturbing samples 4 or 6. This was traced to a CFD algorithm artefact: the 20% threshold crossing typically falls between samples 4 and 5, and the linear interpolation between these two samples produces a derivative with respect to sample 5 that is opposite in sign to the derivative with respect to sample 4. This is a digitizer-level algorithmic effect, not a physics effect.

The conclusion is robust: pulse shapes are low-dimensional and their information content is concentrated in the rising edge (samples 3-6) and peak region (samples 5-8). The falling edge (samples 9-17) carries limited additional information beyond the integrated charge and decay time, both of which are strongly correlated with the peak amplitude for isolated pulses.

---

## 2. Machine Learning Evaluation Framework

### 2.1 The three leakage controls

The evaluation of any machine learning method in this analysis programme must survive three leakage controls before its performance can be considered validated. These controls are designed to detect different failure modes of supervised learning applied to waveform data:

**Control 1: Target shuffle (null-hypothesis test).** The regression or classification target (e.g., the true timing residual, the true particle identity) is randomly permuted across the training set while keeping the input features fixed. The model is then trained on this shuffled data and evaluated on unshuffled held-out data. If the model achieves performance comparable to training on unshuffled data, the apparent learning is spurious: the model is exploiting correlations in the input features themselves (e.g., run-dependent baseline shifts, stave-dependent amplitude distributions) rather than learning the physical relationship between input and target. A model that passes the target shuffle test must show performance on shuffled data that is indistinguishable from a constant baseline predictor (e.g., always predicting the mean target value).

**Control 2: Leave-one-run-out (LORO) cross-validation.** The model is trained on all runs except one and evaluated on the held-out run, repeating for each run in the dataset. This tests whether the model generalises across runs, which may differ in beam conditions, detector calibration, and environmental factors. A model that performs well in k-fold cross-validation (where training and test data are randomly split across all runs) but fails under LORO is learning run-specific features — for example, the run-dependent baseline level or the run-dependent pulse shape template — rather than the physics quantity of interest. LORO is the minimum acceptable cross-validation strategy for any claim that a model could be used in production on future data from different runs.

**Control 3: Event-block shuffle.** Events are grouped into blocks (typically 100-200 consecutive events within a run), and the blocks — not individual events — are randomly assigned to training and test sets. This tests whether the model is exploiting short-range temporal correlations: if the beam conditions (intensity, spot position) drift slowly within a run, events within the same block share systematic offsets that a model can learn as proxies for the target variable. An event-block-shuffled model that performs worse than a randomly-shuffled model is learning these temporal correlations rather than the physics. Event-block shuffle is the strongest leakage control and is required for any claim of ML superiority over traditional methods.

**Worked example: The representation-superiority correction.** The autoencoder-based pulse embedding (Study P02) initially appeared to improve downstream timing resolution by approximately 5-8% compared to PCA embeddings of the same dimension. The training procedure used randomly shuffled events from all runs, and the improvement passed bootstrap confidence interval tests. However, when subjected to event-block shuffle, the improvement disappeared: the autoencoder embedding contained run-specific waveform features (subtle variations in the baseline shape, the SiPM gain, and the digitizer clock phase) that were correlated with timing performance within a run but did not generalise across runs. The autoencoder had learned to encode run identity in its latent space, and the downstream timing model had learned to use run identity as a proxy for timing corrections. This is a leakage artefact, not a representation learning success. The study was CORRECTED: the autoencoder does not provide a superior pulse representation for downstream tasks; its apparent advantage was a leakage artefact.

### 2.2 The self-referential label problem

A particularly subtle form of leakage occurs when the target variable is a deterministic function of the input waveform. The curvature-based particle ID classifiers (Study P01f) achieved near-perfect AUC of approximately 1.0 for separating "proton-like" from "deuteron-like" pulses using features derived from the pulse shape curvature (second derivative of the waveform). However, the label "proton-like" was defined by a threshold on the very same pulse shape features used as input: label = 1 if curvature_feature > threshold, else 0. The classifier was learning the identity function — it discovered the threshold used to define the labels — rather than learning a physical relationship between pulse shape and particle species. This is a self-referential label problem: the label is a function of the input, so any sufficiently flexible model can achieve perfect performance by inverting that function, regardless of whether the label carries physical meaning.

The correction: particle ID classifiers must be trained on labels that are independent of the waveform features used as input. The MC truth PID study (MV1, Chapter 8) achieves this by using GEANT4 truth particle identity (PDG code) as the label, which is independent of the digitised waveform. The data-only PID classifiers are limited to labels derived from sample-level enrichment (Sample I vs II statistics) or stopping-depth proxies, both of which are noisy and cannot achieve the AUC = 0.986 ceiling established by the MC truth study.

---

## 3. Where Machine Learning Wins and Loses

### 3.1 Domains where ML wins

**Saturation recovery (Study P04).** When the B2 stave saturates (ADC clipped at approximately 7000), the true pulse amplitude is unknown. A regression model trained to predict the true (unsaturated) amplitude from the unsaturated waveform samples (samples 0-4, before the peak reaches the saturation ceiling) and the waveform shape in the saturated region (the flat top and the falling edge) achieves a recovery residual of 3-7 times smaller than the conventional method of extrapolating from the unsaturated rising edge. The truth label — the true amplitude, obtained either from an unsaturated neighbouring channel or from the integrated pulse area of an unsaturated pulse of similar shape — is independent of the saturated waveform samples used as input, satisfying the label independence condition. The information is genuinely in the waveform shape: the rising-edge slope, the saturation onset time, and the falling-edge shape collectively constrain the true amplitude.

**Duplicate-readout closure (Study P04b).** In the duplicate-readout configuration, the same scintillator light is split between two independent readout channels (e.g., two SiPMs on the same WLS fibre, or a beam-splitter between the fibre and two SiPMs). The amplitude measured by channel 1 is used as input features, and the amplitude measured by channel 2 is the target. A regression model achieves residual_68 = 0.003 (fractional amplitude error), compared to 0.12 for the direct channel-1 amplitude. This is a genuine ML win: the truth (channel 2) is independent of the input (channel 1), the information is in the pulse shape (channel 1's waveform carries information about light collection efficiency and SiPM gain that correlates with channel 2), and the model survives all three leakage controls.

### 3.2 Domains where ML ties or loses

**Timewalk correction (Studies S03a-S03k).** The analytic timewalk correction f(A) = A_0 + B/A achieves sigma_68 = 1.49-1.55 ns under LORO cross-validation. A histogram gradient boosting regressor (HGB) trained on waveform samples, amplitude, and derived shape features initially appeared to improve this to sigma_68 = 1.107 ns in-fold (Study S03k). This result is explicitly gated pending a transfer audit: the in-fold evaluation does not guarantee generalisation to unseen runs, and LORO evaluations of similar models (S03e, S03f) showed the HGB advantage narrowing to sigma_68 = 1.39-1.47 ns, which overlaps with the analytic baseline when bootstrap uncertainties are included. The analytic correction remains the recommended method. The deeper lesson is that timewalk is fundamentally an amplitude-dependent effect: the pulse shape variations that correlate with residual timing beyond the amplitude dependence are dominated by run-specific and event-specific noise, not by a universal waveform feature that a machine learning model can capture.

**Pile-up rate estimation (Study S10).** The Poisson model for pile-up probability, using the measured effective live-time tau_eff = 124.79 ns, is already the maximum-likelihood estimator for a Poisson process. Machine learning models (density estimation, anomaly detection on waveform features) offer no improvement because the Poisson assumption is well-satisfied for the observed beam intensities: the pile-up fraction scales with beam current as expected, with the sub-linear current dependence explained by current-independent waveform pathologies (SiPM afterpulsing, dark counts) rather than by a failure of the Poisson model.

**Deep-network timing (Study P03a-c).** A multi-layer perceptron and a 1-dimensional convolutional neural network trained end-to-end on raw 18-sample waveforms to predict inter-stave time residuals achieved worse timing resolution than the CFD + analytic timewalk pipeline. The deep networks introduce additional trainable parameters (approximately 10^4-10^5) that require regularisation and hyperparameter tuning, and the limited dataset (approximately 6 * 10^5 pulses) provides insufficient statistical power to constrain these parameters beyond what the 2-parameter analytic model (A_0, B) already captures. This is a case where adding model complexity degrades performance: the bias reduction from the more flexible model is outweighed by the variance increase from fitting noise.

### 3.3 Summary

| Domain | ML vs Traditional | Leakage Status | Verdict |
|---|---|---|---|
| Saturation recovery | ML wins (3-7x better) | Passed all controls | ML adopted |
| Duplicate-readout closure | ML wins (res_68 0.003 vs 0.12) | Passed all controls | ML adopted |
| Two-pulse time RMS | ML wins RMS, higher failure rate | Gated (GAP-04) | Template fit recommended |
| Timewalk correction | ML ties or loses | S03k gated | Analytic recommended |
| Pile-up rate | ML ties | N/A (Poisson optimal) | Analytic recommended |
| Deep-net timing | ML loses | Passed controls | Analytic recommended |
| PID (data-only) | Rejected (self-referential label) | CORRECTED | MC truth required |
| Representation superiority | Rejected (run-family leak) | CORRECTED | PCA sufficient |

---

## 4. The C12 Anomaly

### 4.1 Unsupervised discovery

Study P09a applied Gaussian Mixture Models (GMM) to the 8-dimensional PCA embedding of approximately 87,000 pulse waveforms. The GMM, with the number of components selected by the Bayesian Information Criterion (BIC), identified a small cluster (0.32% of pulses, 283 out of 87,555) with a distinct waveform morphology: the pulse peaks at sample 1-2 (10-20 ns after the trigger) instead of the normal peak at sample 5 (50 ns), and the integrated pulse area is near zero (less than 5% of a typical minimum-ionising pulse). This cluster was not visible in any single projected dimension — it required the full 8-dimensional latent space to separate from the main pulse population.

### 4.2 MC truth identification

Study MV6 (Chapter 9) cross-referenced the anomalous waveform cluster with GEANT4 truth particle identity. Of the 283 anomaly-classified tracks:

- C12 (carbon-12 recoil nuclei): 55%
- Proton: 15%
- Electron: 13%
- Alpha: 9%
- Other heavy ions (Li, Be, B): 7%

The dominant species, C12 recoils, are produced when the 190 MeV incident proton scatters elastically or quasi-elastically off a carbon-12 nucleus in the CD2 target. The recoiling C12 nucleus receives kinetic energy of 1-4 MeV (from two-body kinematics: for a head-on collision, T_C12 = 4 * m_p * m_C12 / (m_p + m_C12)^2 * T_p = 4 * 1 * 12 / 13^2 * 190 = 53.8 MeV in the non-relativistic limit, but the actual energy transfer is limited by the nuclear form factor and the scattering angle). At these low kinetic energies, the C12 ion has an extremely short range in plastic scintillator — approximately 1-5 micrometres (from SRIM calculations) — depositing all its energy in the first fraction of a micrometre of scintillator material. The resulting scintillation light is produced within a few picoseconds and confined to the first 1-2 ADC samples (0-20 ns). The near-zero integrated area reflects the low total light yield: the Birks quenching factor for a carbon ion with dE/dx approximately 10^4 MeV/cm is approximately 0.01-0.05, reducing the light output by a factor of 20-100 relative to a minimum-ionising proton depositing the same energy.

### 4.3 Impact on physics

The C12 anomaly contributes a systematic uncertainty of 0.1% to the deuteron count after applying a GMM morphology cut that removes the anomalous cluster. This is negligible compared to the dominant systematics (digitizer gain at +/-30%, stopping-depth model at 5%). The C12 identification is a methodological success story: an unsupervised algorithm discovered a physically meaningful rare event class, and the Monte Carlo truth bridge provided the physical interpretation.

---

## 5. Algorithm Implementation Details

### 5.1 Autoencoder training

The autoencoder used for pulse shape compression is implemented in PyTorch with the following architecture and training protocol. The encoder consists of three fully connected layers: input dimension 18 (the baseline-subtracted, amplitude-normalised waveform), hidden layers of 64 and 32 units with ReLU activation, and a bottleneck layer of dimension d (tunable, evaluated at d = 2, 3, 4, 8). The decoder mirrors the encoder: d -> 32 -> 64 -> 18 with ReLU activations in the hidden layers and a linear output layer. The loss function is the mean squared error between the input waveform and the reconstructed waveform, averaged over the batch. Training uses the Adam optimiser with learning rate 0.001, batch size 256, and early stopping with patience of 20 epochs on a 10% validation split. The training set comprises approximately 500,000 randomly selected pulses from all runs; the remaining pulses are held out for evaluation.

The autoencoder's advantage over PCA at low latent dimensions arises from the nonlinear activation functions, which allow the encoder to warp the 18-dimensional waveform space to better align with the curved pulse shape manifold. Specifically, saturation produces a nonlinear relationship between amplitude and pulse width: as the amplitude approaches the ADC ceiling, the pulse shape broadens because the SiPM and ADC saturate gradually rather than clipping abruptly. This broadening is a nonlinear function of the true deposited energy and cannot be captured by linear PCA components. The autoencoder's nonlinear hidden layers can represent this saturation-induced shape variation in a compact latent code.

### 5.2 GMM clustering for anomaly detection

The Gaussian Mixture Model used for anomaly detection (Study P09a) fits a weighted sum of K multivariate Gaussian distributions to the 8-dimensional PCA embedding of the waveform population. The probability density of a waveform with PCA embedding z is:

p(z) = sum_{k=1}^K pi_k * N(z | mu_k, Sigma_k)

where pi_k are the mixture weights (sum_k pi_k = 1), mu_k are the component means, and Sigma_k are the component covariance matrices (constrained to be diagonal for computational efficiency with 87,000 samples in 8 dimensions). The model is fit by Expectation-Maximisation (EM), alternating between the E-step (computing the posterior probability gamma_{ik} = P(component k | z_i) for each data point) and the M-step (updating pi_k, mu_k, Sigma_k to maximise the expected complete-data log-likelihood).

The number of components K is selected by minimising the Bayesian Information Criterion: BIC(K) = -2 * log L + K * (1 + 8 + 8) * log(N), where log L is the maximised log-likelihood, K * (1 + 8 + 8) is the number of free parameters (K weights + K * 8 means + K * 8 diagonal variances), and N = 87,555 is the number of waveforms. The BIC penalises model complexity and selects K = 7 as the optimal number of components for the full waveform population.

The anomaly cluster is identified as the component with the smallest mixture weight (pi approximately 0.0032) and the most extreme mean vector: its mean waveform has peak at sample 1-2 (compared to sample 5 for the main pulse population) and integrated area approximately 5% of the main component. Waveforms are assigned to the anomaly class if their posterior probability for this component exceeds 0.5, yielding 283 anomaly-classified waveforms.

The physical interpretation of the anomaly is confirmed by cross-referencing the anomaly-classified waveforms with GEANT4 truth in Study MV6. The GMM captures >99% of C12-dominated tracks in its anomaly component, demonstrating that unsupervised clustering on PCA embeddings can discover physically meaningful rare event classes without prior knowledge of the underlying nuclear physics.

### 5.3 Leakage control implementation

The three leakage controls are implemented as follows in the evaluation pipeline:

**Target shuffle:** The regression target vector y (length N) is permuted by a random permutation sigma: y_shuffled[i] = y[sigma(i)]. The model is trained on (X, y_shuffled) and evaluated on held-out data with unshuffled targets. This is repeated for 100 random permutations to build a null distribution of performance metrics. A model passes the target shuffle test if its performance on shuffled data is consistent with the null distribution (p > 0.05, two-sided) — that is, the model performs no better than random guessing.

**Leave-one-run-out:** For R runs in the dataset, R separate models are trained. For model r, all events from run r are held out, and the model is trained on events from the remaining R-1 runs. The model is evaluated on the held-out run r, and the performance metrics are averaged over all R folds. The LORO standard deviation across folds provides an estimate of the run-to-run variability of the model's performance.

**Event-block shuffle:** Events within each run are divided into blocks of B = 200 consecutive events (approximately 1-2 seconds of data taking at typical beam rates). The blocks — not individual events — are randomly assigned to training (80% of blocks) and test (20% of blocks) sets. This prevents events from the same block (which share short-range temporal correlations in beam conditions, detector temperature, and electronics drift) from appearing in both training and test sets.

[1] Jolliffe, I. T., Principal Component Analysis, 2nd ed. (Springer, 2002).

[2] Goodfellow, I., Bengio, Y., and Courville, A., Deep Learning (MIT Press, 2016), Ch. 14.

[3] Birks, J. B., The Theory and Practice of Scintillation Counting (Pergamon, 1964).

[4] Ziegler, J. F., Ziegler, M. D., and Biersack, J. P., "SRIM — The stopping and range of ions in matter," Nucl. Instrum. Meth. B 268, 1818-1823 (2010).
